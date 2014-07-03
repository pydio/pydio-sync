__author__ = 'pydio'

from watchdog.utils.dirsnapshot import DirectorySnapshot
from pydio.job.local_watcher import SnapshotDiffStart
from pydio.job.localdb import SqlSnapshot
import json
import xml.etree.ElementTree as ET
import os

class Fs_state_checker(object):

    def __init__(self, sdk, path, data_path):
        self.sdk = sdk
        self.synced_path = path
        self.db_path = data_path
        self.remote_excluded_files = ['recycle_bin']
        self.remote_sql_snap = dict()
        self.remote_dir_snap = dict()

    def remote_sql_snapshot(self):
        """
        self.remote_dir_snap = dict()
        self.sdk.change_stream(recursive='true', call_back=self.remote_dir_snapshot_callback)
        """
        url = self.sdk.url + '/changes/0/?stream=true&flatten=true'
        if self.sdk.remote_folder:
            url += '&filter=' + self.remote_folder
        resp = self.sdk.perform_request(url=url, stream=True)
        snapshot = dict()
        for line in resp.iter_lines(chunk_size=512):
            if not str(line).startswith('LAST_SEQ'):
                element = json.loads(line)
                path = element.pop('target')
                bytesize = element['node']['bytesize']
                if path != 'NULL':
                    snapshot[path] = bytesize
                #compare here with the snapshotdir result
        return snapshot

    def remote_directory_snapshot(self):
        self.remote_sql_snap=dict()
        self.sdk.list(recursive='true', call_back=self.remote_dir_snapshot_callback)
        """
        queue = [ET.ElementTree(ET.fromstring(self.list(recursive=True)))._root]
        snapshot = dict()
        while len(queue):
            tree = queue.pop(0)
            if (tree.get('ajxp_mime') == 'ajxp_folder'):
                for subtree in tree.findall('tree'):
                    queue.append(subtree)
            path = tree.get('filename')
            bytesize = tree.get('bytesize')
            if path and self.remote_excluded_files.count(os.path.basename(path)) != 0:
                snapshot[path] = bytesize
        return snapshot
        """

    def local_sql_snapshot(self):
        return SqlSnapshot(self.synced_path, self.db_path)

    def local_directory_snapshot(self):
        return DirectorySnapshot(self.synced_path, recursive=True)

    def check_remote(self):
        dir_snapshot = self.remote_directory_snapshot()
        sql_snapshot = self.remote_sql_snapshot()

        if len(sql_snapshot) != len(dir_snapshot):
            return False, None

        if not sql_snapshot:
            return True, None

        for path, bytesize in sql_snapshot:
            if not dir_snapshot.has_key(path) or bytesize != dir_snapshot[path]:
                return False, None
        return True, dir_snapshot

    def check_local(self):
        snapshot = self.local_directory_snapshot()
        diff = SnapshotDiffStart(self.local_sql_snapshot(), snapshot)
        if not diff._dirs_created and not diff._dirs_deleted and not diff._dirs_modified and not diff._dirs_moved and \
           not diff._files_created and not diff._files_deleted and not diff._files_modified and not diff.files_moved:
            return True, snapshot
        return False, None

    def check_global(self):
        ok, remote_snapshot = self.check_remote()
        if not ok:
            return False
        ok, local_snapshot = self.check_local()
        if not ok:
            return False

        #exclude .pydio files
        excluded_files_count = 0
        for path, _ in local_snapshot._stat_snapshot.iteritems():
            if path.find('.pydio') != -1:
                excluded_files_count += 1

        if (len(remote_snapshot)+excluded_files_count) != len(local_snapshot._stat_snapshot):
            return False
        if not len(remote_snapshot):
            return True

        for path, stat in local_snapshot._stat_snapshot.iteritems():
            if path.find('.pydio_id') != -1:
                continue
            path = (self.sdk.remote_folder + self.remove_prefix('local', path)).replace('\\', '/')
            if not remote_snapshot.has_key(path):
                return False
            size = int(remote_snapshot[path])
            if stat.st_size != size and stat.st_size != 4096 and size != 0:
                return False
        return True

    def remove_prefix(self, location, path):
        base = self.synced_path if location == 'local' else self.sdk.remote_folder
        text = path[len(base):] if path.startswith(base) else path
        if text:
            return os.path.normpath(text)
        return ''
        return False

    def remote_dir_snapshot_callback(self, element):
        if element:
            self.remote_dir_snap[element['filename']] = element['bytesize']

    def remote_sql_snapshot_callback(self, element):
        if element:
            self.remote_sql_snap[element['target']] = element['node']['bytesize']
