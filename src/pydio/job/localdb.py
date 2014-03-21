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

import sqlite3
import os
import hashlib
import time
import fnmatch
import pickle
import logging
from pathlib import *

from watchdog.events import FileSystemEventHandler
from watchdog.utils.dirsnapshot import DirectorySnapshotDiff

from pydio.utils.functions import hashfile


class SqlSnapshot(object):

    def __init__(self, basepath, job_data_path):
        self.db = job_data_path + '/pydio.sqlite'
        self.basepath = basepath
        self._stat_snapshot = {}
        self._inode_to_path = {}
        self.is_recursive = True
        self.load_from_db()

    def load_from_db(self):

        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        for row in c.execute("SELECT node_path,stat_result FROM ajxp_index WHERE stat_result NOT NULL"):
            stat = pickle.loads(str(row['stat_result']))
            path = self.basepath + row['node_path']
            self._stat_snapshot[path] = stat
            self._inode_to_path[stat.st_ino] = path
        c.close()

    def __sub__(self, previous_dirsnap):
        """Allow subtracting a DirectorySnapshot object instance from
        another.

        :returns:
            A :class:`DirectorySnapshotDiff` object.
        """
        return DirectorySnapshotDiff(previous_dirsnap, self)

    @property
    def stat_snapshot(self):
        """
        Returns a dictionary of stat information with file paths being keys.
        """
        return self._stat_snapshot


    def stat_info(self, path):
        """
        Returns a stat information object for the specified path from
        the snapshot.

        :param path:
            The path for which stat information should be obtained
            from a snapshot.
        """
        return self._stat_snapshot[path]


    def path_for_inode(self, inode):
        """
        Determines the path that an inode represents in a snapshot.

        :param inode:
            inode number.
        """
        return self._inode_to_path[inode]


    def stat_info_for_inode(self, inode):
        """
        Determines stat information for a given inode.

        :param inode:
            inode number.
        """
        return self.stat_info(self.path_for_inode(inode))


    @property
    def paths(self):
        """
        List of file/directory paths in the snapshot.
        """
        return set(self._stat_snapshot)


class LocalDbHandler():

    def __init__(self, job_data_path='', base=''):
        self.base = base
        self.db = job_data_path + '/pydio.sqlite'
        self.job_data_path = job_data_path
        if not os.path.exists(self.db):
            self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db)

        cursor = conn.cursor()
        respath = Path(__file__).parent.parent / 'res' / 'create.sql'
        with open(str(respath), 'r') as inserts:
            for statement in inserts:
                cursor.execute(statement)
        conn.close()

    def find_node_by_id(self, node_path, with_status=False):
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        id = False
        q = "SELECT node_id FROM ajxp_index WHERE node_path LIKE ?"
        if with_status:
            q = "SELECT ajxp_index.node_id FROM ajxp_index,ajxp_node_status WHERE ajxp_index.node_path = ? AND ajxp_node_status.node_id = ajxp_index.node_id"
        for row in c.execute(q, (node_path,)):
            id = row['node_id']
            break
        c.close()
        return id

    def get_node_md5(self, node_path):
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        for row in c.execute("SELECT md5 FROM ajxp_index WHERE node_path LIKE ?", (node_path,)):
            return row['md5']
        c.close()
        return hashfile(self.base + node_path, hashlib.md5())

    def get_node_status(self, node_path):
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        status = False
        for row in c.execute("SELECT ajxp_node_status.status FROM ajxp_index,ajxp_node_status "
                             "WHERE ajxp_index.node_path = ? AND ajxp_node_status.node_id = ajxp_index.node_id", (node_path,)):
            status = row['status']
            break
        c.close()
        return status

    def update_node_status(self, node_path, status='IDLE', detail=''):
        node_id = self.find_node_by_id(node_path, with_status=True)
        conn = sqlite3.connect(self.db)
        if not node_id:
            node_id = self.find_node_by_id(node_path, with_status=False)
            if node_id:
                conn.execute("INSERT OR IGNORE INTO ajxp_node_status (node_id,status,detail) VALUES (?,?,?)", (node_id, status, detail))
        else:
            conn.execute("UPDATE ajxp_node_status SET status=?, detail=? WHERE node_id=?", (status, detail, node_id))
        conn.commit()
        conn.close()

    def compare_raw_pathes(self, row1, row2):
        if row1['source'] != 'NULL':
            cmp1 = row1['source']
        else:
            cmp1 = row1['target']
        if row2['source'] != 'NULL':
            cmp2 = row2['source']
        else:
            cmp2 = row2['target']
        return cmp1 == cmp2

    def get_last_operations(self):
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        operations = []
        for row in c.execute("SELECT type,source,target FROM ajxp_last_buffer"):
            dRow = dict()
            dRow['type'] = row['type']
            dRow['source'] = row['source']
            dRow['target'] = row['target']
            operations.append(dRow)
        c.close()
        return operations

    def buffer_real_operation(self, type, source, target):
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO ajxp_last_buffer (type,source,target) VALUES (?,?,?)", (type, source, target))
        conn.commit()
        conn.close()

    def clear_operations_buffer(self):
        conn = sqlite3.connect(self.db)
        conn.execute("DELETE FROM ajxp_last_buffer")
        conn.commit()
        conn.close()

    def get_local_changes(self, seq_id, accumulator=dict()):

        logging.debug("Local sequence " + str(seq_id))
        last = seq_id
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        previous_node_id = -1
        previous_row = None
        deletes = []

        for row in c.execute("SELECT seq , ajxp_changes.node_id ,  type ,  "
                             "source , target, ajxp_index.bytesize, ajxp_index.md5, ajxp_index.mtime, "
                             "ajxp_index.node_path, ajxp_index.stat_result FROM ajxp_changes LEFT JOIN ajxp_index "
                             "ON ajxp_changes.node_id = ajxp_index.node_id "
                             "WHERE seq > ? ORDER BY ajxp_changes.node_id, seq ASC", (seq_id,)):
            drow = dict(row)
            drow['node'] = dict()
            if not row['node_path'] and (not row['source'] or row['source'] == 'NULL') and (not row['target'] or row['source'] == 'NULL'):
                continue
            for att in ('mtime', 'md5', 'bytesize', 'node_path',):
                drow['node'][att] = row[att]
                drow.pop(att, None)
            if drow['node_id'] == previous_node_id and self.compare_raw_pathes(drow, previous_row):
                previous_row['target'] = drow['target']
                previous_row['seq'] = drow['seq']
                if drow['type'] == 'path' or drow['type'] == 'content':
                    if previous_row['type'] == 'delete':
                        previous_row['type'] = drow['type']
                    elif previous_row['type'] == 'create':
                        previous_row['type'] = 'create'
                    else:
                        previous_row['type'] = drow['type']
                elif drow['type'] == 'create':
                    previous_row['type'] = 'create'
                else:
                    previous_row['type'] = drow['type']

            else:
                if previous_row is not None and (previous_row['source'] != previous_row['target'] or previous_row['type'] == 'content'):
                    previous_row['location'] = 'local'
                    accumulator['data'][previous_row['seq']] = previous_row
                    key = previous_row['source'] if previous_row['source'] != 'NULL' else previous_row['target']
                    if not key in accumulator['path_to_seqs']:
                        accumulator['path_to_seqs'][key] = []
                    accumulator['path_to_seqs'][key].append(previous_row['seq'])
                    if previous_row['type'] == 'delete':
                        deletes.append(previous_row['seq'])

                previous_row = drow
                previous_node_id = drow['node_id']
            last = max(row['seq'], last)

        if previous_row is not None and (previous_row['source'] != previous_row['target'] or previous_row['type'] == 'content'):
            previous_row['location'] = 'local'
            accumulator['data'][previous_row['seq']] = previous_row
            key = previous_row['source'] if previous_row['source'] != 'NULL' else previous_row['target']
            if not key in accumulator['path_to_seqs']:
                accumulator['path_to_seqs'][key] = []
            accumulator['path_to_seqs'][key].append(previous_row['seq'])
            if previous_row['type'] == 'delete':
                deletes.append(previous_row['seq'])

        #refilter: create + delete or delete + create must be ignored
        for to_del_seq in deletes:
            to_del_item = accumulator['data'][to_del_seq]
            key = to_del_item['source']
            for del_seq in accumulator['path_to_seqs'][key]:
                item = accumulator['data'][del_seq]
                if item == to_del_item:
                    continue
                if item['seq'] > to_del_seq:
                    del accumulator['data'][to_del_seq]
                    accumulator['path_to_seqs'][key].remove(to_del_seq)
                else:
                    del accumulator['data'][item['seq']]
                    accumulator['path_to_seqs'][key].remove(item['seq'])

        for seq, row in accumulator['data'].items():
            logging.debug('LOCAL CHANGE : ' + str(row['seq']) + '-' + row['type'] + '-' + row['source'] + '-' + row['target'])

        conn.close()
        return last


class SqlEventHandler(FileSystemEventHandler):

    def __init__(self, basepath, includes, excludes, job_data_path):
        super(SqlEventHandler, self).__init__()
        self.base = basepath
        self.includes = includes
        self.excludes = excludes
        db_handler = LocalDbHandler(job_data_path, basepath)
        self.db = db_handler.db

    def get_unicode_path(self, src):
        if isinstance(src, str):
            src = unicode(src, 'utf-8')
        return src

    def remove_prefix(self, text):
        return text[len(self.base):] if text.startswith(self.base) else text

    def included(self, event, base=None):
        if not base:
            base = os.path.basename(event.src_path)
        for i in self.includes:
            if not fnmatch.fnmatch(base, i):
                return False
        for e in self.excludes:
            if fnmatch.fnmatch(base, e):
                return False
        return True

    def on_moved(self, event):
        if not self.included(event):
            return
        logging.debug("Event: move noticed: " + event.event_type + " on file " + event.src_path + " at " + time.asctime())

        conn = sqlite3.connect(self.db)
        t = (
            self.remove_prefix(self.get_unicode_path(event.dest_path)),
            self.remove_prefix(self.get_unicode_path(event.src_path)),
        )
        conn.execute("UPDATE ajxp_index SET node_path=? WHERE node_path=?", t)
        conn.commit()
        conn.close()

    def on_created(self, event):
        if not self.included(event):
            return
        logging.debug("Event: creation noticed: " + event.event_type +
                         " on file " + event.src_path + " at " + time.asctime())

        src_path = self.get_unicode_path(event.src_path)
        if not os.path.exists(src_path):
            return

        search_key = self.remove_prefix(src_path)
        if event.is_directory:
            hash_key = 'directory'
        else:
            hash_key = hashfile(open(src_path, 'rb'), hashlib.md5())

        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        node_id = None
        for row in c.execute("SELECT node_id FROM ajxp_index WHERE node_path=?", (search_key,)):
            node_id = row['node_id']
            break
        c.close()
        if not node_id:
            t = (
                search_key,
                os.path.getsize(src_path),
                hash_key,
                os.path.getmtime(src_path),
                pickle.dumps(os.stat(src_path))
            )
            conn.execute("INSERT INTO ajxp_index (node_path,bytesize,md5,mtime,stat_result) VALUES (?,?,?,?,?)", t)
        else:
            t = (
                os.path.getsize(src_path),
                hash_key,
                os.path.getmtime(src_path),
                pickle.dumps(os.stat(src_path)),
                search_key
            )
            conn.execute("UPDATE ajxp_index SET bytesize=?, md5=?, mtime=?, stat_result=? WHERE node_path=?", t)
        conn.commit()
        conn.close()

    def on_deleted(self, event):
        if not self.included(event):
            return
        logging.debug("Event: deletion noticed: " + event.event_type +
                         " on file " + event.src_path + " at " + time.asctime())
        src_path = self.get_unicode_path(event.src_path)
        conn = sqlite3.connect(self.db)
        conn.execute("DELETE FROM ajxp_index WHERE node_path LIKE ?", (self.remove_prefix(src_path) + '%',))
        conn.commit()
        conn.close()

    def on_modified(self, event):
        super(SqlEventHandler, self).on_modified(event)
        if not self.included(event):
            return
        src_path = self.get_unicode_path(event.src_path)
        if event.is_directory:
            files_in_dir = [src_path+"/"+f for f in os.listdir(src_path)]
            if len(files_in_dir) > 0:
                modified_filename = max(files_in_dir, key=os.path.getmtime)
            else:
                return
            if os.path.isfile(modified_filename) and self.included(event=None, base=modified_filename):
                logging.debug("Event: modified file : %s" % modified_filename)
                conn = sqlite3.connect(self.db)
                size = os.path.getsize(modified_filename)
                the_hash = hashfile(open(modified_filename, 'rb'), hashlib.md5())
                mtime = os.path.getmtime(modified_filename)
                search_path = self.remove_prefix(modified_filename)
                stat_result = pickle.dumps(os.stat(modified_filename))
                t = (size, the_hash, mtime, stat_result, search_path, size, the_hash)
                conn.execute("UPDATE ajxp_index SET bytesize=?, md5=?, mtime=?, stat_result=? WHERE node_path=? AND bytesize!=? AND md5!=?", t)
                conn.commit()
                conn.close()
        else:
            modified_filename = src_path
            if not os.path.exists(src_path):
                return

            logging.debug("Event: modified file : %s" % self.remove_prefix(modified_filename))
            conn = sqlite3.connect(self.db)
            size = os.path.getsize(modified_filename)
            the_hash = hashfile(open(modified_filename, 'rb'), hashlib.md5())
            mtime = os.path.getmtime(modified_filename)
            search_path = self.remove_prefix(modified_filename)
            stat_result = pickle.dumps(os.stat(modified_filename))
            t = (size, the_hash, mtime, stat_result, search_path, size, the_hash)
            conn.execute("UPDATE ajxp_index SET bytesize=?, md5=?, mtime=?, stat_result=? WHERE node_path=? AND bytesize!=? AND md5!=?", t)
            conn.commit()
            conn.close()
