#
# Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
# This file is part of Pydio.
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
        self.remote_excluded_files = ['/recycle_bin']
        self.remote_sql_snap = dict()
        self.remote_dir_snap = dict()

    def remote_sql_snapshot(self):
        self.remote_sql_snap = dict()
        self.sdk.changes_stream(0, self.remote_sql_snapshot_callback)


    def remote_directory_snapshot(self):
        self.remote_dir_snap=dict()
        self.sdk.list(recursive='true', call_back=self.remote_dir_snapshot_callback)


    def local_sql_snapshot(self):
        return SqlSnapshot(self.synced_path, self.db_path)

    def local_directory_snapshot(self):
        return DirectorySnapshot(self.synced_path, recursive=True)

    def check_remote(self):
        self.remote_sql_snapshot()
        self.remote_directory_snapshot()

        dir_snapshot = self.remote_dir_snap
        sql_snapshot = self.remote_sql_snap

        for excluded in self.remote_excluded_files:
            if dir_snapshot.has_key(excluded):
                dir_snapshot.pop(excluded)

        if len(sql_snapshot) != len(dir_snapshot):
            return False, None

        if not sql_snapshot:
            return True, None

        for path, bytesize in sql_snapshot.iteritems():
            if not dir_snapshot.has_key(path) and bytesize != dir_snapshot[path] and bytesize !=0 and dir_snapshot[path]!=0 and bytesize !=4096 and dir_snapshot[path]!=4096:
                return False, None
        return True, dir_snapshot

    def check_local(self):
        dir_snap = self.local_directory_snapshot()._stat_snapshot
        sql_snap = self.local_sql_snapshot()._stat_snapshot

        l = [self.synced_path]
        """, '.*', '*/.*', '/recycle_bin*', '*.pydio_dl', '*.DS_Store', '.~lock.*'"""
        for path, _ in dir_snap.iteritems():
            path = str(path)
            if path.endswith('\\.pydio_id') or path.startswith('.') or os.path.basename(path).startswith('.') or path.find('\\.') != -1 or path.endswith('.pydio_dl') or path.endswith('.DS_Store'):
                l.append(path)
        for path in l:
            if dir_snap.has_key(path):
                dir_snap.pop(path)

        #comp = set(dir_snapshot._stat_snapshot.items()) & set(sql_snapshot._stat_snapshot.items())
        if len(dir_snap) != len(sql_snap):
            return False, None

        if not len(dir_snap):
            return True, None

        for path, stat in dir_snap.iteritems():
            size1 = sql_snap[path].st_size
            size2 = stat.st_size
            if not sql_snap.has_key(path) and size1 != size2 and size1!=0 and size2!=0 and size1 !=4096 and size2!=4096:
                return False, None

        return True, dir_snap


    def check_global(self):
        ok, remote_snapshot = self.check_remote()
        if not ok:
            return False
        ok, local_snapshot = self.check_local()
        if not ok:
            return False

        #exclude .pydio files
        excluded_files_count = 0
        for path, _ in local_snapshot.iteritems():
            if path.find('.pydio') != -1:
                excluded_files_count += 1

        if (len(remote_snapshot)+excluded_files_count) != len(local_snapshot):
            return False
        if not len(remote_snapshot):
            return True

        for path, stat in local_snapshot.iteritems():
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

    def remote_sql_snapshot_callback(self, location, element, info=None):
        if element:
            self.remote_sql_snap[element['target']] = element['bytesize']
