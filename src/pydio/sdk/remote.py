#
#  Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
#  This file is part of Pydio.
#
#  Pydio is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Pydio is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with Pydio.  If not, see <http://www.gnu.org/licenses/>.
#
#  The latest code can be found at <http://pyd.io/>.
#
import logging
import urllib
import json
import os
import hmac
import time
import random
import unicodedata
import platform
from hashlib import sha256
from hashlib import sha1
from urlparse import urlparse

import requests
import keyring
from keyring.errors import PasswordSetError
from pydispatch import dispatcher

from exceptions import PydioSdkException, PydioSdkBasicAuthException, PydioSdkTokenAuthException
from .utils import upload_file_with_progress
from pydio import TRANSFER_RATE_SIGNAL, TRANSFER_CALLBACK_SIGNAL
# -*- coding: utf-8 -*-

PYDIO_SDK_MAX_UPLOAD_PIECES = 40 * 1024 * 1024


class PydioSdk():

    def __init__(self, url='', ws_id='', remote_folder='', user_id='', auth=(), device_id='python_client'):
        self.ws_id = ws_id
        self.device_id = device_id
        self.base_url = url.rstrip('/') + '/api/'
        self.url = url.rstrip('/') + '/api/' + ws_id
        self.remote_folder = remote_folder
        self.user_id = user_id
        self.upload_max_size = PYDIO_SDK_MAX_UPLOAD_PIECES
        if user_id:
            self.auth = (user_id, keyring.get_password(url, user_id))
        else:
            self.auth = auth

    def set_server_configs(self, configs):
        """
        Server specific capacities and limitations, provided by the server itself
        :param configs: dict()
        :return:
        """
        if 'UPLOAD_MAX_SIZE' in configs and configs['UPLOAD_MAX_SIZE']:
            self.upload_max_size = min(int(configs['UPLOAD_MAX_SIZE']), PYDIO_SDK_MAX_UPLOAD_PIECES)

    def urlencode_normalized(self, unicode_path):
        """
        Make sure the urlencoding is consistent between various platforms
        E.g, we force the accented chars to be encoded as one char, not the ascci + accent.
        :param unicode_path:
        :return:
        """
        if platform.system() == 'Darwin':
            try:
                test = unicodedata.normalize('NFC', unicode_path)
                unicode_path = test
            except ValueError as e:
                pass
        return urllib.pathname2url(unicode_path.encode('utf-8'))

    def normalize(self, unicode_path):
        if platform.system() == 'Darwin':
            try:
                test = unicodedata.normalize('NFC', unicode_path)
                return test
            except ValueError as e:
                return unicode_path
        else:
            return unicode_path

    def normalize_reverse(self, unicode_path):
        if platform.system() == 'Darwin':
            try:
                test = unicodedata.normalize('NFD', unicode_path)
                return test
            except ValueError as e:
                return unicode_path
        else:
            return unicode_path

    def basic_authenticate(self):
        """
        Use basic-http authenticate to get a key/pair token instead of passing the
        users credentials at each requests
        :return:dict()
        """
        url = self.base_url + 'pydio/keystore_generate_auth_token/' + self.device_id
        resp = requests.get(url=url, auth=self.auth)
        if resp.status_code == 401:
            raise PydioSdkBasicAuthException('Authentication Error')
        try:
            tokens = json.loads(resp.content)
        except ValueError as v:
            return False
        try:
            keyring.set_password(self.url, self.user_id + '-token', tokens['t'] + ':' + tokens['p'])
        except PasswordSetError:
            logging.error("Cannot store tokens in keychain, basic auth will be performed each time!")
        return tokens


    def perform_with_tokens(self, token, private, url, type='get', data=None, files=None, stream=False,
                            with_progress=False):
        """
        :param token: str the token.
        :param private: str private key associated to token
        :param url: str url to query
        :param type: str http method, default is "get"
        :param data: dict query parameters
        :param files: dict files, described as {'fieldname':'path/to/file'}
        :param stream: bool get response as a stream
        :param with_progress: dict an object that can be updated with various progress data
        :return: Http response
        """
        nonce = sha1(str(random.random())).hexdigest()
        uri = urlparse(url).path.rstrip('/')
        msg = uri + ':' + nonce + ':' + private
        the_hash = hmac.new(str(token), str(msg), sha256);
        auth_hash = nonce + ':' + the_hash.hexdigest()

        if type == 'get':
            auth_string = 'auth_token=' + token + '&auth_hash=' + auth_hash
            if '?' in url:
                url += '&' + auth_string
            else:
                url += '?' + auth_string
            resp = requests.get(url=url, stream=stream, timeout=20)
        elif type == 'post':
            if not data:
                data = {}
            data['auth_token'] = token
            data['auth_hash'] = auth_hash
            if files:
                resp = upload_file_with_progress(url, dict(**data), files, stream, with_progress,
                                                 max_size=self.upload_max_size)
            else:
                resp = requests.post(url=url, data=data, stream=stream, timeout=20)
        else:
            raise PydioSdkTokenAuthException("Unsupported HTTP method")

        if resp.status_code == 401:
            raise PydioSdkTokenAuthException("Authentication Exception")
        return resp

    def perform_request(self, url, type='get', data=None, files=None, stream=False, with_progress=False):
        """
        Perform an http request.
        There's a one-time loop, as it first tries to use the auth tokens. If the the token auth fails, it may just
        mean that the token key/pair is expired. So we try once to get fresh new tokens with basic_http auth and
        re-run query with new tokens.

        :param url: str url to query
        :param type: str http method, default is "get"
        :param data: dict query parameters
        :param files: dict files, described as {'fieldname':'path/to/file'}
        :param stream: bool get response as a stream
        :param with_progress: dict an object that can be updated with various progress data
        :return:
        """
        tokens = keyring.get_password(self.url, self.user_id + '-token')
        if not tokens:
            tokens = self.basic_authenticate()
            return self.perform_with_tokens(tokens['t'], tokens['p'], url, type, data, files, stream)
        else:
            tokens = tokens.split(':')
            try:
                resp = self.perform_with_tokens(tokens[0], tokens[1], url, type, data, files, stream, with_progress)
                return resp
            except PydioSdkTokenAuthException as pTok:
                # Tokens may be revoked? Retry
                tokens = self.basic_authenticate()
                try:
                    return self.perform_with_tokens(tokens['t'], tokens['p'], url, type, data, files, stream, with_progress)
                except PydioSdkTokenAuthException as secTok:
                    logging.error('Second Auth Error, what is wrong?')
                    raise secTok

    def changes(self, last_seq):
        """
        Get the list of changes detected on server since a given sequence number

        :param last_seq:int
        :return:list a list of changes
        """
        url = self.url + '/changes/' + str(last_seq)
        if self.remote_folder:
            url += '?filter=' + self.remote_folder
        resp = self.perform_request(url=url)
        try:
            return json.loads(resp.content)
        except ValueError as v:
            raise Exception("Invalid JSON value received while getting remote changes")

    def changes_stream(self, last_seq, flatten_and_store_callback):

        """
        Get the list of changes detected on server since a given sequence number

        :param last_seq:int
        :change_store: AbstractChangeStore
        :return:list a list of changes
        """
        if last_seq == 0:
            perform_flattening = "false"
        else:
            perform_flattening = "false"
        url = self.url + '/changes/' + str(last_seq) + '/?stream=true'
        if self.remote_folder:
            url += '&filter=' + self.remote_folder
        url += '&flatten=' + perform_flattening

        resp = self.perform_request(url=url, stream=True)
        info = dict()
        info['max_seq'] = last_seq
        for line in resp.iter_lines(chunk_size=512):
            if line:
                if str(line).startswith('LAST_SEQ'):
                    #call the merge function with NULL row
                    flatten_and_store_callback('remote', None, info)
                    return int(line.split(':')[1])
                else:
                    try:
                        one_change = json.loads(line)
                        node = one_change.pop('node')
                        one_change = dict(node.items() + one_change.items())
                        flatten_and_store_callback('remote', one_change, info)

                    except ValueError as v:
                        raise Exception("Invalid JSON value received while getting remote changes")
                    except Exception as e:
                        raise e

    def stat(self, path, with_hash=False):
        """
        Equivalent of the local fstat() on the remote server.
        :param path: path of node from the workspace root
        :param with_hash: stat result can be enriched with the node hash
        :return:dict a list of key like
        {
            dev: 16777218,
            ino: 4062280,
            mode: 16895,
            nlink: 15,
            uid: 70,
            gid: 20,
            rdev: 0,
            size: 510,
            atime: 1401915891,
            mtime: 1399883020,
            ctime: 1399883020,
            blksize: 4096,
            blocks: 0
        }
        """
        path = self.remote_folder + path;
        action = '/stat_hash' if with_hash else '/stat'
        try:
            url = self.url + action + self.urlencode_normalized(path)
            resp = self.perform_request(url)
            try:
                data = json.loads(resp.content)
            except ValueError as ve:
                return False
            logging.debug("data: %s" % data)
            if not data:
                return False
            if len(data) > 0 and 'size' in data:
                return data
            else:
                return False
        except Exception, ex:
            logging.warning("Stat failed", exc_info=ex)
            return False

    def bulk_stat(self, pathes, result=None, with_hash=False):
        """
        Perform a stat operation (see self.stat()) but on a set of nodes. Very important to use that method instead
        of sending tons of small stat requests to server. To keep POST content reasonable, pathes will be sent 200 by
        200.

        :param pathes: list() of node pathes
        :param result: dict() an accumulator for the results
        :param with_hash: bool whether to ask for files hash or not (md5)
        :return:
        """
        action = '/stat_hash' if with_hash else '/stat'
        data = dict()
        maxlen = min(len(pathes), 200)
        clean_pathes = map(lambda t: self.remote_folder + t.replace('\\', '/'),
                           filter(lambda x: x != '', pathes[:maxlen]))
        data['nodes[]'] = map(lambda p: self.normalize(p), clean_pathes)
        url = self.url + action + self.urlencode_normalized(clean_pathes[0])
        resp = self.perform_request(url, type='post', data=data)
        try:
            data = json.loads(resp.content)
        except ValueError:
            logging.debug("url: %s" % url)
            logging.debug("resp.content: %s" % resp.content)
            raise

        if len(pathes) == 1:
            englob = dict()
            englob[self.remote_folder + pathes[0]] = data
            data = englob
        if result:
            replaced = result
        else:
            replaced = dict()
        for (p, stat) in data.items():
            if self.remote_folder:
                p = p[len(self.remote_folder):]
                #replaced[os.path.normpath(p)] = stat
            p1 = os.path.normpath(p)
            p2 = os.path.normpath(self.normalize_reverse(p))
            p3 = p
            p4 = self.normalize_reverse(p)
            if p2 in pathes:
                replaced[p2] = stat
                pathes.remove(p2)
            elif p1 in pathes:
                replaced[p1] = stat
                pathes.remove(p1)
            elif p3 in pathes:
                replaced[p3] = stat
                pathes.remove(p3)
            elif p4 in pathes:
                replaced[p4] = stat
                pathes.remove(p4)
            else:
                raise PydioSdkException('bulk_stat', p1, "Encoding problem, failed emptying bulk_stat, "
                                                         "exiting instead of infinite loop")
        if len(pathes):
            self.bulk_stat(pathes, result=replaced, with_hash=with_hash)
        return replaced

    def mkdir(self, path):
        """
        Create a directory of the server
        :param path: path of the new directory to create
        :return: result of the server query, see API
        """
        url = self.url + '/mkdir' + self.urlencode_normalized((self.remote_folder + path))
        resp = self.perform_request(url=url)
        return resp.content

    def bulk_mkdir(self, pathes):
        data = dict()
        data['ignore_exists'] = 'true'
        data['nodes[]'] = map(lambda t: self.normalize(self.remote_folder + t), filter(lambda x: x != '', pathes))
        url = self.url + '/mkdir' + self.urlencode_normalized(self.remote_folder + pathes[0])
        resp = self.perform_request(url=url,type='post', data=data)
        return resp.content

    def mkfile(self, path):
        """
        Create an empty file on the server
        :param path: node path
        :return: result of the server query
        """
        url = self.url + '/mkfile' + self.urlencode_normalized((self.remote_folder + path))
        resp = self.perform_request(url=url)
        return resp.content

    def rename(self, source, target):
        """
        Rename a path to another. Will decide automatically to trigger a rename or a move in the API.
        :param source: origin path
        :param target: target path
        :return: response of the server
        """
        if os.path.dirname(source) == os.path.dirname(target):
            url = self.url + '/rename'
            data = dict(file=(self.remote_folder + source).encode('utf-8'),
                        dest=(self.remote_folder + target).encode('utf-8'))
        else:
            url = self.url + '/move'
            data = dict(
                file=(self.normalize(self.remote_folder + source)).encode('utf-8'),
                dest=os.path.dirname((self.normalize(self.remote_folder + target).encode('utf-8'))))
        resp = self.perform_request(url=url, type='post', data=data)
        return resp.content

    def delete(self, path):
        """
        Delete a resource on the server
        :param path: node path
        :return: response of the server
        """
        url = self.url + '/delete' + self.urlencode_normalized((self.remote_folder + path))
        resp = self.perform_request(url=url)
        return resp.content

    def load_server_configs(self):
        """
        Load the plugins from the registry and parse some of the exposed parameters of the plugins.
        Currently supports the uploaders paramaters, and the filehasher.
        :return: dict() parsed configs
        """
        url = self.base_url + 'pydio/state/plugins?format=json'
        resp = self.perform_request(url=url)
        server_data = dict()
        try:
            data = json.loads(resp.content)
            plugins = data['plugins']
            for p in plugins['ajxpcore']:
                if p['@id'] == 'core.uploader':
                    if 'plugin_configs' in p and 'property' in p['plugin_configs']:
                        properties = p['plugin_configs']['property']
                        for prop in properties:
                            server_data[prop['@name']] = prop['$']
            for p in plugins['meta']:
                if p['@id'] == 'meta.filehasher':
                    if 'plugin_configs' in p and 'property' in p['plugin_configs']:
                        properties = p['plugin_configs']['property']
                        if '@name' in prop:
                            server_data[properties['@name']] = properties['$']
                        else:
                            for prop in properties:
                                server_data[prop['@name']] = prop['$']
        except KeyError, ValueError:
            pass
        return server_data


    def upload(self, local, local_stat, path, callback_dict=None, max_upload_size=-1):
        """
        Upload a file to the server.
        :param local: file path
        :param local_stat: stat of the file
        :param path: target path on the server
        :param callback_dict: an dict that can be fed with progress data
        :param max_upload_size: a known or arbitrary upload max size. If the file file is bigger, it will be
        chunked into many POST requests
        :return: Server response
        """
        if not local_stat:
            raise PydioSdkException('upload', path, 'local file to upload not found!')
        if local_stat['size'] == 0:
            self.mkfile(path)
            new = self.stat(path)
            if not new or not (new['size'] == local_stat['size']):
                raise PydioSdkException('upload', path, 'File not correct after upload (expected size was 0 bytes)')
            return True
        dirpath = os.path.dirname(path)
        if dirpath and dirpath != '/':
            folder = self.stat(dirpath)
            if not folder:
                self.mkdir(os.path.dirname(path))
        url = self.url + '/upload/put' + self.urlencode_normalized((self.remote_folder + os.path.dirname(path)))
        files = {'userfile_0': local}
        data = {
            'force_post': 'true',
            'urlencoded_filename': self.urlencode_normalized(os.path.basename(path))
        }
        self.perform_request(url=url, type='post', data=data, files=files, with_progress=callback_dict)
        new = self.stat(path)
        if not new or not (new['size'] == local_stat['size']):
            raise PydioSdkException('upload', path, 'File incorrect after upload. Max chunk size was ' + str(self.upload_max_size))
        return True

    def download(self, path, local, callback_dict=None):
        """
        Download the content of a server file to a local file.
        :param path: node path on the server
        :param local: local path on filesystem
        :param callback_dict: a dict() than can be updated by with progress data
        :return: Server response
        """
        orig = self.stat(path)
        if not orig:
            raise PydioSdkException('download', path, 'Original not found on server')

        url = self.url + '/download' + self.urlencode_normalized((self.remote_folder + path))
        local_tmp = local + '.pydio_dl'
        if not os.path.exists(os.path.dirname(local)):
            os.makedirs(os.path.dirname(local))
        try:
            with open(local_tmp, 'wb') as fd:
                start = time.clock()
                r = self.perform_request(url=url, stream=True)
                total_length = r.headers.get('content-length')
                dl = 0
                if total_length is None: # no content length header
                    fd.write(r.content)
                else:
                    previous_done = 0
                    for chunk in r.iter_content(1024 * 8):
                        dl += len(chunk)
                        fd.write(chunk)
                        done = int(50 * dl / int(total_length))
                        if done != previous_done:
                            transfer_rate = dl // (time.clock() - start)
                            logging.debug("\r[%s%s] %s bps" % ('=' * done, ' ' * (50 - done), transfer_rate))
                            dispatcher.send(signal=TRANSFER_RATE_SIGNAL, send=self, transfer_rate=transfer_rate)
                            if callback_dict:
                                callback_dict['bytes_sent'] = float(len(chunk))
                                callback_dict['total_bytes_sent'] = float(dl)
                                callback_dict['total_size'] = float(total_length)
                                callback_dict['transfer_rate'] = transfer_rate
                                dispatcher.send(signal=TRANSFER_CALLBACK_SIGNAL, send=self, change=callback_dict)

                        previous_done = done
            if not os.path.exists(local_tmp):
                raise PydioSdkException('download', local, 'File not found after download')
            else:
                stat_result = os.stat(local_tmp)
                if not orig['size'] == stat_result.st_size:
                    os.unlink(local_tmp)
                    raise PydioSdkException('download', path, 'File not correct after download')
                else:
                    if platform.system().startswith('win') and os.path.exists(local):
                        os.unlink(local)
                    os.rename(local_tmp, local)
            return True
        except Exception as e:
            if os.path.exists(local_tmp):
                os.unlink(local_tmp)
            raise PydioSdkException('download', path, 'Error while downloading file: %s' % e.message)
