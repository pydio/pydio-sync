import os
from threading import Lock


class MockSDK(object):

    def __init__(self):
        self.fs = dict()
        self.changes = dict()
        self.content = dict()
        self.mutex = Lock()

    def list(self, folder):
        with self.mutex:
            content = self.fs
            parts = folder.replace("\\", "/").split("/")
            for p in parts:
                if content.has_key(p):
                    content = content[p]
                else:
                    return {}
            return content

    def mkdir(self, folder):
        with self.mutex:
            content = self.fs
            parts = folder.replace("\\", "/").split("/")
            for p in parts:
                if content.has_key(p):
                    content = content[p]
                else:
                    content[p] = {}
            content["md5"] = "directory"
            content["name"] = os.path.basename(folder)

    def bulk_mkdir(self, pathes):
        for p in pathes:
            self.mkdir(p)

    def mkfile(self, path):
        with self.mutex:
            content = self.fs
            parts = path.replace("\\", "/").split("/")
            for p in parts:
                if content.has_key(p):
                    content = content[p]
                else:
                    content[p] = {}
            content["md5"] = ""
            content["name"] = os.path.basename(path)

    def bulk_mkfile(self, pathes):
        for p in pathes:
            self.mkfile(p)

    def delete(self, path):
        with self.mutex:
            parent = os.path.pardir(path)
            name = os.path.basename(path)
            content = self.fs
            parts = parent.replace("\\", "/").split("/")
            for p in parts:
                if content.has_key(p):
                    content = content[p]
                else:
                    return
            del content[name]

    def move(self, src, dst):
        with self.mutex:
            pass

    def rename(self, src, dst):
        with self.mutex:
            pass

    def stat(self, path):
        with self.mutex:
            pass

    def bulk_stat(self, pathes):
        with self.mutex:
            pass

    def write(self, path, src, progress_handler=None):
        with self.mutex:
            pass

    def read(self, path, dst, progress_handler=None):
        with self.mutex:
            pass

    def changes(self, seq=0):
        with self.mutex:
            pass