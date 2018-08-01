import hashlib
import os
import time
from threading import Lock


class MockSDK(object):

    def __init__(self):
        self.fs = dict()
        self.changes = dict()
        self.info = dict()
        self.mutex = Lock()
        self.content = dict()
        self.seq = 0
        self.node_id = 0
        #self.seq = 0

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

            ctime = int(time.time())
            mtime = ctime

            self.node_id += 1
            self.info[folder] = dict()
            self.info[folder]["md5"] = "directory"
            self.info[folder]["name"] = os.path.basename(folder)
            self.info[folder]["path"] = folder
            self.info[folder]["bytesize"] = 4096
            self.info[folder]["ctime"] = ctime
            self.info[folder]["mtime"] = mtime
            self.info[folder]["node_id"] = self.node_id

            self.seq += 1

            change = dict()
            change["seq"] = self.seq
            change["node_id"] = self.seq
            change["type"] = "create"
            change["source"] = "NULL"
            change["target"] = folder
            change["node"] = dict()
            change["node"]["bytessize"] = 4096
            change["node"]["md5"] = "directory"
            change["node"]["mtime"] = int(time.time())
            change["node"]["node_path"] = folder
            content["node"]["repository_identifier"] = "mock-ws"

            self.changes[self.seq] = change

    def bulk_mkdir(self, pathes):
        for p in pathes:
            self.mkdir(p)

    def mkfile(self, path, trigger_change=True):
        with self.mutex:
            content = self.fs
            parts = path.replace("\\", "/").split("/")
            for p in parts:
                if content.has_key(p):
                    content = content[p]
                else:
                    content[p] = {}

            if not trigger_change:
                return

            ctime = int(time.time())
            mtime = ctime

            self.node_id += 1
            self.info[path] = dict()
            self.info[path]["md5"] = "d41d8cd98f00b204e9800998ecf8427e"
            self.info[path]["name"] = os.path.basename(path)
            self.info[path]["path"] = path
            self.info[path]["bytesize"] = 0
            self.info[path]["ctime"] = ctime
            self.info[path]["mtime"] = mtime
            self.info[path]["node_id"] = self.node_id

            self.seq += 1
            change = dict()
            change["seq"] = self.seq
            change["node_id"] = self.seq
            change["type"] = "create"
            change["source"] = "NULL"
            change["target"] = path
            change["node"] = dict()
            change["node"]["bytessize"] = 4096
            change["node"]["md5"] = "d41d8cd98f00b204e9800998ecf8427e"
            change["node"]["mtime"] = mtime
            change["node"]["node_path"] = path
            change["node"]["repository_identifier"] = "mock-ws"

            self.changes[self.seq] = change

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
            info = content[name]


            self.seq += 1
            change = dict()
            change["seq"] = self.seq
            change["node_id"] = self.seq
            change["type"] = "create"
            change["source"] = path
            change["target"] = "NULL"
            change["node"] = dict()
            change["node"]["bytessize"] = 4096
            change["node"]["deleted_md5"] = info["md5"]
            change["node"]["md5"] = ""
            change["node"]["mtime"] = int(time.time())
            change["node"]["node_path"] = path
            change["node"]["repository_identifier"] = os.path.basename(path)

            del content[name]
            self.changes[self.seq] = change

    def move(self, src, dst):
        with self.mutex:
            info = self.info[src]
            del self.info[src]

            info["path"] = dst
            info["name"] = os.path.basename(dst)
            self.info[dst] = info

            content = self.fs
            src_folder = os.path.dirname(src)
            src_name = os.path.basename(src)

            parts = src_folder.replace("\\", "/").split("/")
            for p in parts:
                if content.has_key(p):
                    content = content[p]
                else:
                    return {}
            del content[src_name]

            content = self.fs
            dst_folder = os.path.dirname(dst)
            dst_name = os.path.basename(dst)

            parts = dst_folder.replace("\\", "/").split("/")
            for p in parts:
                if content.has_key(p):
                    content = content[p]
                else:
                    return {}
            content[dst_name] = {}

            self.seq += 1
            change = dict()
            change["seq"] = self.seq
            change["node_id"] = info["node_id"]
            change["type"] = "path"
            change["source"] = src
            change["target"] = dst
            change["node"] = dict()
            change["node"]["bytessize"] = info["bytesize"]
            change["node"]["md5"] = info["md5"]
            change["node"]["mtime"] = info["mtime"]
            change["node"]["node_path"] = dst
            change["node"]["repository_identifier"] = "mock-ws"

            self.changes[self.seq] = change

    def stat(self, path):
        with self.mutex:
            return self.info[path]

    def bulk_stat(self, pathes):
        with self.mutex:
            result = dict()
            for p in pathes:
                result[p] = self.info[p]
            return result

    def upload(self, path, data):
        self.mkfile(path)
        with self.mutex:
            self.content[path] = data
            hash = hashlib.md5(data).digest()

            mtime = int(time.time())
            info = self.info[path]
            info["md5"] = hash
            info["name"] = os.path.basename(path)
            info["path"] = path
            info["mtime"] = mtime
            info["bytesize"] = len(data)

            self.seq += 1
            change = dict()
            change["seq"] = self.seq
            change["node_id"] = info["node_id"]
            change["type"] = "content"
            change["source"] = path
            change["target"] = path
            change["node"] = dict()
            change["node"]["bytessize"] = len(data)
            change["node"]["md5"] = hash
            change["node"]["mtime"] = mtime
            change["node"]["node_path"] = path
            change["node"]["repository_identifier"] = "mock-ws"

            self.changes[self.seq] = change

    def download(self, path):
        with self.mutex:
            return self.content[path]

    def changes(self, seq=0):
        with self.mutex:
            changes = list()
            for i in self.changes.keys():
                if i > seq:
                    changes.append(self.changes[i])
            return changes