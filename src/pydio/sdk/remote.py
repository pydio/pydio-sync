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
import sys

import requests
import urllib
import json
import os
import keyring
import hashlib
import stat
import time

from exceptions import SystemSdkException, PydioSdkException
from pydio.utils.functions import hashfile

class PydioSdk():

    def __init__(self, url='', ws_id='', remote_folder='', user_id='', auth=()):
        self.ws_id = ws_id
        self.url = url+'/api/'+ws_id
        self.remote_folder = remote_folder
        if user_id:
            self.auth = (user_id, keyring.get_password(url, user_id))
        else:
            self.auth = auth

    def changes(self, last_seq):
        url = self.url + '/changes/' + str(last_seq)
        if self.remote_folder:
            url += '?filter=' + self.remote_folder
        resp = requests.get(url=url, auth=self.auth)
        try:
            return json.loads(resp.content)
        except ValueError as v:
            raise Exception("Invalid JSON value received while getting remote changes")

    def stat(self, path, with_hash=False):
        path = self.remote_folder + path;
        action = '/stat_hash' if with_hash else '/stat'
        try:
            url = self.url + action + urllib.pathname2url(path.encode('utf-8'))
            resp = requests.get(url=url, auth=self.auth)
            data = json.loads(resp.content)
            if not data:
                return False
            if len(data) > 0 and 'size' in data:
                return data
            else:
                return False
        except ValueError:
            return False
        except:
            return False

    def bulk_stat(self, pathes, result=None, with_hash=False):
        action = '/stat_hash' if with_hash else '/stat'
        data = dict()
        maxlen = min(len(pathes), 200)
        clean_pathes = map(lambda t: self.remote_folder + t.replace('\\', '/'), filter(lambda x: x !='', pathes[:maxlen]))
        data['nodes[]'] = clean_pathes
        url = self.url + action + urllib.pathname2url(clean_pathes[0].encode('utf-8'))
        resp = requests.post(url, data=data, auth=self.auth)
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
            replaced[os.path.normpath(p)] = stat
            try:
                pathes.remove(os.path.normpath(p))
            except:
                pass
        if len(pathes):
            self.bulk_stat(pathes, result=replaced, with_hash=with_hash)
        return replaced

    def mkdir(self, path):
        url = self.url + '/mkdir' + urllib.pathname2url((self.remote_folder + path).encode('utf-8'))
        resp = requests.get(url=url, auth=self.auth)
        return resp.content

    def rename(self, source, target):
        if os.path.dirname(source) == os.path.dirname(target):
            url = self.url + '/rename'
            resp = requests.post(url=url, data=dict(file=(self.remote_folder + source).encode('utf-8'), dest=(self.remote_folder + target).encode('utf-8')), auth=self.auth)
        else:
            url = self.url + '/move'
            resp = requests.post(url=url, data=dict(file=(self.remote_folder + source).encode('utf-8'), dest=os.path.dirname((self.remote_folder + target).encode('utf-8'))), auth=self.auth)
        return resp.content

    def delete(self, path):
        url = self.url + '/delete' + urllib.pathname2url((self.remote_folder + path).encode('utf-8'))
        resp = requests.get(url=url, auth=self.auth)
        return resp.content

    def upload(self, local, local_stat, path):
        if not local_stat:
            raise PydioSdkException('upload', path, 'local file to upload not found!')

        url = self.url + '/upload/put' + urllib.pathname2url((self.remote_folder + os.path.dirname(path)).encode('utf-8'))
        files = {'userfile_0': ('my-name',open(local, 'rb'))}
        data = {'force_post':'true', 'urlencoded_filename':urllib.pathname2url(os.path.basename(path).encode('utf-8'))}
        resp = requests.post(url, data=data, files=files, auth=self.auth)
        new = self.stat(path)
        if not new or not (new['size'] == local_stat['size']):
            raise PydioSdkException('upload', path, 'File not correct after upload')
        return True

    def download(self, path, local):
        orig = self.stat(path)
        if not orig:
            raise PydioSdkException('download', path, 'Original not found on server')

        url = self.url + '/download' + urllib.pathname2url((self.remote_folder + path).encode('utf-8'))
        local_tmp = local + '.pydio_dl'
        if not os.path.exists(os.path.dirname(local)):
            os.makedirs(os.path.dirname(local))
        try:
            with open(local_tmp, 'wb') as fd:
                start = time.clock()
                r = requests.get(url, stream=True, auth=self.auth)
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
                            logging.debug("\r[%s%s] %s bps" % ('=' * done, ' ' * (50-done), dl//(time.clock() - start)))
                        previous_done = done
            if not os.path.exists(local_tmp):
                raise PydioSdkException('download', local, 'File not found after download')
            else:
                stat_result = os.stat(local_tmp)
                if not orig['size'] == stat_result.st_size:
                    os.unlink(local_tmp)
                    raise PydioSdkException('download', path, 'File not correct after download')
                else:
                    os.rename(local_tmp, local)
            return True
        except Exception as e:
            if(os.path.exists(local_tmp)):
                os.unlink(local_tmp)
            raise PydioSdkException('download', path, 'Error opening local file for writing')
