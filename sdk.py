import requests
import urllib
import json
import os


class ProcessException(Exception):
    def __init__(self, src, operation, path, detail):
        super(ProcessException, self).__init__('['+src+'] [' + operation + '] ' + path + ' ('+detail+')')
        self.src_path = path
        self.operation = operation
        self.detail = detail


class PydioSdkException(ProcessException):
    def __init__(self, operation, path, detail):
        super(PydioSdkException, self).__init__('sdk operation', operation, path, detail)


class SystemSdkException(ProcessException):
    def __init__(self, operation, path, detail):
        super(SystemSdkException, self).__init__('system operation', operation, path, detail)


class PydioSdk():

    def __init__(self, url='', basepath='', ws_id='', auth=('admin', '123456')):
        self.ws_id = ws_id
        self.url = url+'/api/'+ws_id
        self.basepath = basepath
        self.auth = auth
        self.system = SystemSdk(basepath)

    def changes(self, last_seq):
        url = self.url + '/changes/' + str(last_seq)
        resp = requests.get(url=url, auth=self.auth)
        return json.loads(resp.content)

    def stat(self, path):
        try:
            url = self.url + '/stat' + urllib.pathname2url(path.encode('utf-8'))
            resp = requests.get(url=url, auth=self.auth)
            data = json.loads(resp.content)
            if not data:
                return False
            if len(data) > 0 and data['size']:
                return data
            else:
                return False
        except ValueError:
            return False
        except:
            return False

    def bulk_stat(self, pathes, result=None):
        data = dict()
        pathes = map(lambda t: t.replace('\\', '/'), filter(lambda x: x !='', pathes))
        data['nodes[]'] = pathes
        resp = requests.post(self.url + '/stat' + urllib.pathname2url(pathes[0].encode('utf-8')) , data=data, auth=self.auth)
        data = json.loads(resp.content)
        if result:
            replaced = result
        else:
            replaced = dict()
        for (p, stat) in data.items():
            replaced[os.path.normpath(p)] = stat
            try:
                pathes.remove(os.path.normpath(p))
            except:
                pass
        if len(pathes):
            self.bulk_stat(pathes, result=replaced)
        return replaced

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
        orig = self.system.stat(local, full_path=True)
        if not orig:
            raise PydioSdkException('upload', path, 'local file to upload not found!')

        url = self.url + '/upload/put' + urllib.pathname2url(os.path.dirname(path).encode('utf-8'))
        files = {'userfile_0': ('my-name',open(local, 'rb'))}
        data = {'force_post':'true', 'urlencoded_filename':urllib.pathname2url(os.path.basename(path).encode('utf-8'))}
        resp = requests.post(url, data=data, files=files, auth=self.auth)
        new = self.stat(path)
        if not new or not (new['size'] == orig['size']):
            raise PydioSdkException('upload', path, 'file not correct after upload')
        return True

    def download(self, path, local):
        orig = self.stat(path)
        if not orig:
            raise PydioSdkException('download', path, 'original not found on server')

        url = self.url + '/download' + urllib.pathname2url(path.encode('utf-8'))
        resp = requests.get(url=url, stream=True, auth=self.auth)
        if not os.path.exists(os.path.dirname(local)):
            os.makedirs(os.path.dirname(local))
        try:
            with open(local, 'wb') as fd:
                for chunk in resp.iter_content(4096):
                    fd.write(chunk)
            new = self.system.stat(local, full_path=True)
            if not new or not orig['size'] == new['size']:
                raise PydioSdkException('download', path, 'file not correct after download')
            return True
        except Exception as e:
            raise PydioSdkException('download', path, 'error opening local file for writing')


class SystemSdk(object):

    def __init__(self, basepath):
        self.basepath = basepath

    def stat(self, path, full_path=False):
        if not path:
            return False
        if not full_path:
            path = self.basepath + path
        if not os.path.exists(path):
            return False
        else:
            stat_result = os.stat(path)
            stat = dict()
            stat['size'] = stat_result.st_size
            stat['mtime'] = stat_result.st_mtime
            stat['mode'] = stat_result.st_mode
            stat['inode'] = stat_result.st_ino
            return stat

    def rmdir(self, path):
        if not os.path.exists(self.basepath + path):
            return True
        try:
            os.rmdir(self.basepath + path)
        except OSError as e:
            raise SystemSdkException('delete', path, 'cannot remove folder')