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

import urllib
import json
import hmac
import random
import unicodedata
import platform
from pydio.utils.functions import hashfile
from hashlib import sha256
from hashlib import sha1
from urlparse import urlparse


import requests
import keyring
from keyring.errors import PasswordSetError
from pydispatch import dispatcher
import xml.etree.ElementTree as ET

from exceptions import PydioSdkException, PydioSdkBasicAuthException, PydioSdkTokenAuthException, PydioSdkQuotaException, \
    PydioSdkDefaultException, PydioSdkPermissionException
from .utils import *
from pydio import TRANSFER_RATE_SIGNAL, TRANSFER_CALLBACK_SIGNAL
from pydio.utils import i18n
_ = i18n.language.ugettext

# -*- coding: utf-8 -*-

PYDIO_SDK_MAX_UPLOAD_PIECES = 40 * 1024 * 1024


class PydioSdk():

    def __init__(self, url='', ws_id='', remote_folder='', user_id='', auth=(), device_id='python_client', skip_ssl_verify=False):
        self.ws_id = ws_id
        self.device_id = device_id
        self.verify_ssl = not skip_ssl_verify
        if self.verify_ssl and "REQUESTS_CA_BUNDLE" in os.environ:
            self.verify_ssl = os.environ["REQUESTS_CA_BUNDLE"]


        self.base_url = url.rstrip('/') + '/api/'
        self.url = url.rstrip('/') + '/api/' + ws_id
        self.remote_folder = remote_folder
        self.user_id = user_id
        self.interrupt_tasks = False
        self.upload_max_size = PYDIO_SDK_MAX_UPLOAD_PIECES
        self.rsync_server_support = False
        if user_id:
            self.auth = (user_id, keyring.get_password(url, user_id))
        else:
            self.auth = auth
        self.rsync_supported = False
    def set_server_configs(self, configs):
        """
        Server specific capacities and limitations, provided by the server itself
        :param configs: dict()
        :return:
        """
        if 'UPLOAD_MAX_SIZE' in configs and configs['UPLOAD_MAX_SIZE']:
            self.upload_max_size = min(int(float(configs['UPLOAD_MAX_SIZE'])), PYDIO_SDK_MAX_UPLOAD_PIECES)
        if 'RSYNC_SUPPORTED' in configs and configs['RSYNC_SUPPORTED'] == "true":
            self.rsync_server_support = True
        #self.upload_max_size = 8*1024*1024;
        if 'RSYNC_SUPPORTED' in configs:
            self.rsync_supported = configs['RSYNC_SUPPORTED'] == 'true'
        pass

    def set_interrupt(self):
        self.interrupt_tasks = True

    def remove_interrupt(self):
        self.interrupt_tasks = False

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
        resp = requests.get(url=url, auth=self.auth, verify=self.verify_ssl)
        if resp.status_code == 401:
            raise PydioSdkBasicAuthException(_('Authentication Error'))
        try:
            tokens = json.loads(resp.content)
        except ValueError as v:
            return False
        try:
            keyring.set_password(self.url, self.user_id + '-token', tokens['t'] + ':' + tokens['p'])
        except PasswordSetError:
            logging.error(_("Cannot store tokens in keychain, basic auth will be performed each time!"))
        return tokens

    def perform_with_tokens(self, token, private, url, request_type='get', data=None, files=None, headers=None, stream=False,
                            with_progress=False):
        """

        :param headers:
        :param token: str the token.
        :param private: str private key associated to token
        :param url: str url to query
        :param request_type: str http method, default is "get"
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

        if request_type == 'get':
            auth_string = 'auth_token=' + token + '&auth_hash=' + auth_hash
            if '?' in url:
                url += '&' + auth_string
            else:
                url += '?' + auth_string
            resp = requests.get(url=url, stream=stream, timeout=20, verify=self.verify_ssl, headers=headers)
        elif request_type == 'post':
            if not data:
                data = {}
            data['auth_token'] = token
            data['auth_hash'] = auth_hash
            if files:
                resp = self.upload_file_with_progress(url, dict(**data), files, stream, with_progress,
                                                 max_size=self.upload_max_size)
            else:
                resp = requests.post(url=url, data=data, stream=stream, timeout=20, verify=self.verify_ssl, headers=headers)
        else:
            raise PydioSdkTokenAuthException(_("Unsupported HTTP method"))

        if resp.status_code == 401:
            raise PydioSdkTokenAuthException(_("Authentication Exception"))
        return resp

    def perform_request(self, url, type='get', data=None, files=None, headers=None, stream=False, with_progress=False):
        """
        Perform an http request.
        There's a one-time loop, as it first tries to use the auth tokens. If the the token auth fails, it may just
        mean that the token key/pair is expired. So we try once to get fresh new tokens with basic_http auth and
        re-run query with new tokens.

        :param headers:
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
            return self.perform_with_tokens(tokens['t'], tokens['p'], url, type, data, files,
                                            headers=headers, stream=stream)
        else:
            tokens = tokens.split(':')
            try:
                resp = self.perform_with_tokens(tokens[0], tokens[1], url, type, data, files, headers=headers,
                                                stream=stream, with_progress=with_progress)
                return resp
            except PydioSdkTokenAuthException as pTok:
                # Tokens may be revoked? Retry
                tokens = self.basic_authenticate()
                try:
                    return self.perform_with_tokens(tokens['t'], tokens['p'], url, type, data, files,
                                                    headers=headers, stream=stream, with_progress=with_progress)
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
            raise Exception(_("Invalid JSON value received while getting remote changes. Is the server correctly configured?"))

    def changes_stream(self, last_seq, callback):
        """
        Get the list of changes detected on server since a given sequence number

        :param last_seq:int
        :change_store: AbstractChangeStore
        :return:list a list of changes
        """
        if last_seq == 0:
            perform_flattening = "true"
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
                    callback('remote', None, info)
                    return int(line.split(':')[1])
                else:
                    try:
                        one_change = json.loads(line)
                        node = one_change.pop('node')
                        one_change = dict(node.items() + one_change.items())
                        callback('remote', one_change, info)

                    except ValueError as v:
                        raise Exception(_("Invalid JSON value received while getting remote changes."))
                    except Exception as e:
                        raise e

    def stat(self, path, with_hash=False, partial_hash=None):
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
        path = self.remote_folder + path
        action = '/stat_hash' if with_hash else '/stat'
        try:
            url = self.url + action + self.urlencode_normalized(path)
            if partial_hash:
                h = {'range': 'bytes=%i-%i' % (partial_hash[0], partial_hash[1])}
                resp = self.perform_request(url, headers=h)
            else:
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
        # NORMALIZE PATHES FROM START
        pathes = map(lambda p: self.normalize(p), pathes)

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
                #pass
                logging.info('Fatal charset error, cannot find files (%s, %s, %s, %s) in %s' % (repr(p1), repr(p2), repr(p3), repr(p4), repr(pathes),))
                raise PydioSdkException('bulk_stat', p1, "Encoding problem, failed emptying bulk_stat, "
                                                         "exiting to avoid infinite loop")
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
        self.is_pydio_error_response(resp)
        return resp.content

    def bulk_mkdir(self, pathes):
        """
        Create many directories at once
        :param pathes: a set of directories to create
        :return: content of the response
        """
        data = dict()
        data['ignore_exists'] = 'true'
        data['nodes[]'] = map(lambda t: self.normalize(self.remote_folder + t), filter(lambda x: x != '', pathes))
        url = self.url + '/mkdir' + self.urlencode_normalized(self.remote_folder + pathes[0])
        resp = self.perform_request(url=url, type='post', data=data)
        self.is_pydio_error_response(resp)
        return resp.content

    def mkfile(self, path):
        """
        Create an empty file on the server
        :param path: node path
        :return: result of the server query
        """
        url = self.url + '/mkfile' + self.urlencode_normalized((self.remote_folder + path))
        resp = self.perform_request(url=url)
        self.is_pydio_error_response(resp)
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
            data = dict(file=self.normalize(self.remote_folder + source).encode('utf-8'),
                        dest=self.normalize(self.remote_folder + target).encode('utf-8'))
        else:
            url = self.url + '/move'
            data = dict(
                file=(self.normalize(self.remote_folder + source)).encode('utf-8'),
                dest=os.path.dirname((self.normalize(self.remote_folder + target).encode('utf-8'))))
        resp = self.perform_request(url=url, type='post', data=data)
        self.is_pydio_error_response(resp)
        return resp.content

    def delete(self, path):
        """
        Delete a resource on the server
        :param path: node path
        :return: response of the server
        """
        url = self.url + '/delete' + self.urlencode_normalized((self.remote_folder + path))
        resp = self.perform_request(url=url)
        self.is_pydio_error_response(resp)
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
            raise PydioSdkException('upload', path, _('Local file to upload not found!'))
        if local_stat['size'] == 0:
            self.mkfile(path)
            new = self.stat(path)
            if not new or not (new['size'] == local_stat['size']):
                raise PydioSdkException('upload', path, _('File not correct after upload (expected size was 0 bytes)'))
            return True

        existing_part = False
        if (self.upload_max_size - 4096) < local_stat['size']:
            self.has_disk_space_for_upload(path, local_stat['size'])
            existing_part = self.stat(path+'.dlpart', True)

        dirpath = os.path.dirname(path)
        if dirpath and dirpath != '/':
            folder = self.stat(dirpath)
            if not folder:
                self.mkdir(os.path.dirname(path))
        url = self.url + '/upload/put' + self.urlencode_normalized((self.remote_folder + os.path.dirname(path)))
        files = {
            'userfile_0': local
        }
        if existing_part:
            files['existing_dlpart'] = existing_part
        data = {
            'force_post': 'true',
            'xhr_uploader': 'true',
            'urlencoded_filename': self.urlencode_normalized(os.path.basename(path))
        }
        try:
            self.perform_request(url=url, type='post', data=data, files=files, with_progress=callback_dict)
        except PydioSdkDefaultException as e:
            if e.message == '507':
                usage, total = self.quota_usage()
                raise PydioSdkQuotaException(path, local_stat['size'], usage, total)
            if e.message == '412':
                raise PydioSdkPermissionException('Cannot upload '+os.path.basename(path)+' in directory '+os.path.dirname(path))
            else:
                raise e

        new = self.stat(path)
        if not new or not (new['size'] == local_stat['size']):
            raise PydioSdkException('upload', path, _('File is incorrect after upload'))
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
            raise PydioSdkException('download', path, _('Original file was not found on server'))

        url = self.url + '/download' + self.urlencode_normalized((self.remote_folder + path))
        local_tmp = local + '.pydio_dl'
        headers = None
        write_mode = 'wb'
        dl = 0
        if not os.path.exists(os.path.dirname(local)):
            os.makedirs(os.path.dirname(local))
        elif os.path.exists(local_tmp):
            # A .pydio_dl already exists, maybe it's a chunk of the original?
            # Try to get an md5 of the corresponding chunk
            current_size = os.path.getsize(local_tmp)
            chunk_local_hash = hashfile(open(local_tmp, 'rb'), hashlib.md5())
            chunk_remote_stat = self.stat(path, True, partial_hash=[0, current_size])
            if chunk_local_hash == chunk_remote_stat['hash']:
                headers = {'range':'bytes=%i-%i' % (current_size, chunk_remote_stat['size'])}
                write_mode = 'a+'
                dl = current_size
                if callback_dict:
                    callback_dict['bytes_sent'] = float(current_size)
                    callback_dict['total_bytes_sent'] = float(current_size)
                    callback_dict['total_size'] = float(chunk_remote_stat['size'])
                    callback_dict['transfer_rate'] = 0
                    dispatcher.send(signal=TRANSFER_CALLBACK_SIGNAL, send=self, change=callback_dict)

            else:
                os.unlink(local_tmp)

        try:
            with open(local_tmp, write_mode) as fd:
                start = time.clock()
                r = self.perform_request(url=url, stream=True, headers=headers)
                total_length = r.headers.get('content-length')
                if total_length is None: # no content length header
                    fd.write(r.content)
                else:
                    previous_done = 0
                    for chunk in r.iter_content(1024 * 8):
                        if self.interrupt_tasks:
                            raise PydioSdkException("interrupt", path=path, detail=_('Task interrupted by user'))
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
                raise PydioSdkException('download', local, _('File not found after download'))
            else:
                stat_result = os.stat(local_tmp)
                if not orig['size'] == stat_result.st_size:
                    os.unlink(local_tmp)
                    raise PydioSdkException('download', path, _('File is not correct after download'))
                else:
                    is_system_windows = platform.system().lower().startswith('win')
                    if is_system_windows and os.path.exists(local):
                        os.unlink(local)
                    os.rename(local_tmp, local)
            return True

        except PydioSdkException as pe:
            if pe.operation == 'interrupt':
                raise pe
            else:
                if os.path.exists(local_tmp):
                    os.unlink(local_tmp)
                raise pe

        except Exception as e:
            if os.path.exists(local_tmp):
                os.unlink(local_tmp)
            raise PydioSdkException('download', path, _('Error while downloading file: %s') % e.message)

    def list(self, dir=None, nodes=list(), options='al', recursive=False, max_depth=1, remote_order='', order_column='', order_direction='', max_nodes=0, call_back=None):
        url = self.url + '/ls' + self.urlencode_normalized(self.remote_folder)
        data = dict()
        if dir:
            data['dir'] = dir
        if nodes:
            data['nodes'] = nodes
        data['options'] = options
        if recursive:
            data['recursive'] = 'true'
        if max_depth > 1:
            data['max_depth'] = max_depth
        if max_nodes:
            data['max_nodes'] = max_nodes
        if remote_order:
            data['remote_order'] = remote_order
        if order_column:
            data['order_column'] = order_column
        if order_direction:
            data['order_direction'] = order_direction

        resp = self.perform_request(url=url, type='post', data=data)
        self.is_pydio_error_response(resp)
        queue = [ET.ElementTree(ET.fromstring(resp.content)).getroot()]
        snapshot = dict()
        while len(queue):
            tree = queue.pop(0)
            if tree.get('ajxp_mime') == 'ajxp_folder':
                for subtree in tree.findall('tree'):
                    queue.append(subtree)
            path = tree.get('filename')
            bytesize = tree.get('bytesize')
            dict_tree = dict(tree.items())
            if path:
                if call_back:
                    call_back(dict_tree)
                else:
                    snapshot[path] = bytesize
        return snapshot if not call_back else None

    def snapshot_from_changes(self, call_back=None):
        url = self.url + '/changes/0/?stream=true&flatten=true'
        if self.remote_folder:
            url += '&filter=' + self.urlencode_normalized(self.remote_folder)
        resp = self.perform_request(url=url, stream=True)
        files = dict()
        for line in resp.iter_lines(chunk_size=512):
            if not str(line).startswith('LAST_SEQ'):
                element = json.loads(line)
                if call_back:
                    call_back(element)
                else:
                    path = element.pop('target')
                    bytesize = element['node']['bytesize']
                    if path != 'NULL':
                        files[path] = bytesize
        return files if not call_back else None

    def apply_check_hook(self, hook_name='', hook_arg='', file='/'):
        url = self.url + '/apply_check_hook/'+hook_name+'/'+str(hook_arg)+'/'
        resp = self.perform_request(url=url, type='post', data={'file': self.normalize(file)})
        return resp

    def quota_usage(self):
        url = self.url + '/monitor_quota/'
        resp = self.perform_request(url=url, type='post')
        quota = json.loads(resp.text)
        return quota['USAGE'], quota['TOTAL']

    def has_disk_space_for_upload(self, path, file_size):
        resp = self.apply_check_hook(hook_name='before_create', hook_arg=file_size, file=path)
        if str(resp.text).count("type=\"ERROR\""):
            usage, total = self.quota_usage()
            raise PydioSdkQuotaException(path, file_size, usage, total)

    def is_pydio_error_response(self, resp):
        error = False
        message = 'Unknown error'
        try:
            element = ET.ElementTree(ET.fromstring(resp.content)).getroot()
            error = str(element.get('type')).lower() == 'error'
            message = element[0].text
        except Exception as e:
            pass
        if error:
            raise PydioSdkDefaultException(message)

    def rsync_delta(self, path, signature, delta_path):
        url = self.url + ('/filehasher_delta' + self.urlencode_normalized(self.remote_folder + path.replace("\\", "/")))
        resp = self.perform_request(url=url, type='post', files={'userfile_0': signature}, stream=True,
                                    with_progress=False)
        fd = open(delta_path, 'wb')
        for chunk in resp.iter_content(8192):
            fd.write(chunk)
        fd.close()

    def rsync_signature(self, path, signature):
        url = self.url + ('/filehasher_signature'+ self.urlencode_normalized(self.remote_folder + path.replace("\\", "/")))
        resp = self.perform_request(url=url, type='post', stream=True, with_progress=False)
        fd = open(signature, 'wb')
        for chunk in resp.iter_content(8192):
            fd.write(chunk)
        fd.close()

    def rsync_patch(self, path, delta_path):
        url = self.url + ('/filehasher_patch'+ self.urlencode_normalized(self.remote_folder + path.replace("\\", "/")))
        resp = self.perform_request(url=url, type='post', files={'userfile_0': delta_path}, with_progress=False)
        self.is_pydio_error_response(resp)

    def is_rsync_supported(self):
        return self.rsync_supported


    def upload_file_with_progress(self, url, fields, files, stream, with_progress, max_size=0):
        """
        Upload a file with progress, file chunking if necessary, and stream content directly from file.
        :param url: url to post
        :param fields: dict() query parameters
        :param files: dict() {'fieldname' : '/path/to/file'}
        :param stream: whether to get response as stream or not
        :param with_progress: dict() updatable dict with progress data
        :param max_size: upload max size
        :return: response of the last requests if there were many of them
        """
        if with_progress:
            def cb(size=0, progress=0, delta=0, rate=0):
                with_progress['total_size'] = size
                with_progress['bytes_sent'] = delta
                with_progress['total_bytes_sent'] = progress
                dispatcher.send(signal=TRANSFER_CALLBACK_SIGNAL, change=with_progress)
        else:
            def cb(size=0, progress=0, delta=0, rate=0):
                logging.debug('Current transfer rate ' + str(rate))

        def parse_upload_rep(http_response):
            if http_response.headers.get('content-type') != 'application/octet-stream':
                if unicode(http_response.text).count('message type="ERROR"'):

                    if unicode(http_response.text).lower().count("(507)"):
                        raise PydioSdkDefaultException('507')

                    if unicode(http_response.text).lower().count("(412)"):
                        raise PydioSdkDefaultException('412')

                    import re
                    # Remove XML tags
                    text = re.sub('<[^<]+>', '', unicode(http_response.text))
                    raise PydioSdkDefaultException(text)

                if unicode(http_response.text).lower().count("(507)"):
                    raise PydioSdkDefaultException('507')

                if unicode(http_response.text).lower().count("(412)"):
                    raise PydioSdkDefaultException('412')

                if unicode(http_response.text).lower().count("(410)") or unicode(http_response.text).lower().count("(411)"):
                    raise PydioSdkDefaultException(unicode(http_response.text))



        filesize = os.stat(files['userfile_0']).st_size
        if max_size:
            # Reduce max size to leave some room for data header
            max_size -= 4096

        existing_pieces_number = 0

        if max_size and filesize > max_size:
            fields['partial_upload'] = 'true'
            fields['partial_target_bytesize'] = filesize
            # Check if there is already a .dlpart on the server.
            # If it's the case, maybe it's already the beginning of this?
            if 'existing_dlpart' in files:
                existing_dlpart = files['existing_dlpart']
                existing_dlpart_size = existing_dlpart['size']
                if filesize > existing_dlpart_size and \
                        file_start_hash_match(files['userfile_0'], existing_dlpart_size, existing_dlpart['hash']):
                    logging.info('Found the beggining of this file on the other file, skipping the first pieces')
                    existing_pieces_number = existing_dlpart_size / max_size
                    cb(filesize, existing_dlpart_size, existing_dlpart_size, 0)

        if not existing_pieces_number:
            (header_body, close_body, content_type) = encode_multiparts(fields)
            body = BytesIOWithFile(header_body, close_body, files['userfile_0'], callback=cb, chunk_size=max_size, file_part=0)
            resp = requests.post(
                url,
                data=body,
                headers={'Content-Type': content_type},
                stream=True,
                timeout=20
            )

            existing_pieces_number = 1
            parse_upload_rep(resp)
            if resp.status_code == 401:
                return resp

        if max_size and filesize > max_size:
            fields['appendto_urlencoded_part'] = fields['urlencoded_filename']
            del fields['urlencoded_filename']
            (header_body, close_body, content_type) = encode_multiparts(fields)
            for i in range(existing_pieces_number, int(math.ceil(filesize / max_size)) + 1):

                if self.interrupt_tasks:
                    raise PydioSdkException("upload", path=os.path.basename(files['userfile_0']), detail=_('Task interrupted by user'))

                before = time.time()
                body = BytesIOWithFile(header_body, close_body, files['userfile_0'],
                                       callback=cb, chunk_size=max_size, file_part=i)
                resp = requests.post(
                    url,
                    data=body,
                    headers={'Content-Type': content_type},
                    stream=True
                )
                parse_upload_rep(resp)
                if resp.status_code == 401:
                    return resp

                duration = time.time() - before
                logging.info('Uploaded '+str(max_size)+' bytes of data in about %'+str(duration)+' s')

        return resp
