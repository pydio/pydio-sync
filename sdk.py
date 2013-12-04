import requests
import urllib
import json
import os

class PydioSdk():

    def __init__(self, url='', basepath='', ws_id='', auth=('admin', '123456')):
        self.ws_id = ws_id
        self.url = url+'/api/'+ws_id
        self.basepath = basepath
        self.auth = auth

    def changes(self, last_seq):
        url = self.url + '/changes/' + str(last_seq)
        resp = requests.get(url=url, auth=self.auth)
        return json.loads(resp.content)

    def stat(self, path):
        try:
            url = self.url + '/stat' + urllib.pathname2url(path.encode('utf-8'))
            resp = requests.get(url=url, auth=self.auth)
            return json.loads(resp.content)
        except ValueError:
            return False
        except:
            return False

    def mkdir(self, path):
        url = self.url + '/mkdir' + urllib.pathname2url(path.encode('utf-8'))
        resp = requests.get(url=url, auth=self.auth)
        return resp.content

    def rename(self, source, target):
        if os.path.dirname(source) == os.path.dirname(target):
            url = self.url + '/rename'
            resp = requests.post(url=url, data=dict(file=source.encode('utf-8'), dest=target.encode('utf-8')), auth=self.auth)
        else:
            url = self.url + '/move'
            resp = requests.post(url=url, data=dict(file=source.encode('utf-8'), dest=os.path.dirname(target.encode('utf-8'))), auth=self.auth)
        return resp.content

    def delete(self, path):
        url = self.url + '/delete' + urllib.pathname2url(path.encode('utf-8'))
        resp = requests.get(url=url, auth=self.auth)
        return resp.content

    def upload(self, local, path):
        url = self.url + '/upload/put' + urllib.pathname2url(os.path.dirname(path).encode('utf-8'))
        files = {'userfile_0': open(local, 'rb')}
        data = {'force_post':'true'}
        headers = {'X-File-Name': os.path.basename(path).encode('utf-8')}
        resp = requests.post(url, data=data, files=files, auth=self.auth, headers=headers)
        #print resp.content

    def download(self, path, local):
        if not self.stat(path):
            return
        url = self.url + '/download' + urllib.pathname2url(path.encode('utf-8'))
        resp = requests.get(url=url, stream=True, auth=self.auth)
        if not os.path.exists(os.path.dirname(local)):
            os.makedirs(os.path.dirname(local))
        try:
            with open(local, 'wb') as fd:
                for chunk in resp.iter_content(4096):
                    fd.write(chunk)
        except:
            print 'Cannot open local file for writing ' + local

