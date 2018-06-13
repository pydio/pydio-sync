#
#  Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
#  This file is part of Pydio.
#
#  Pydio is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Pydio is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Pydio.  If not, see <http://www.gnu.org/licenses/>.
#
#  The latest code can be found at <http://pyd.io/>.
#

import sqlite3
from sqlite3 import OperationalError
import sys
import os
import hashlib
import time
import fnmatch
import pickle
import logging
import threading
from pathlib import *
from watchdog.events import FileSystemEventHandler
from watchdog.utils.dirsnapshot import DirectorySnapshotDiff
try:
    from pydio.utils.pydio_profiler import pydio_profile
    from pydio.utils.functions import hashfile, set_file_hidden, guess_filesystemencoding
    from pydio.utils.global_config import GlobalConfigManager
except ImportError:
    from utils.pydio_profiler import pydio_profile
    from utils.functions import hashfile, set_file_hidden, guess_filesystemencoding
    from utils.global_config import GlobalConfigManager

class DBCorruptedException(Exception):
    pass


class SqlSnapshot(object):

    def __init__(self, basepath, job_data_path, sub_folder=None):
        self.db = job_data_path + '/pydio.sqlite'
        self.basepath = basepath
        self._stat_snapshot = {}
        self._inode_to_path = {}
        self.is_recursive = True
        self.sub_folder = sub_folder
        global_config_manager = GlobalConfigManager.Instance(configs_path=job_data_path)
        # Increasing the timeout (default 5 seconds), to avoid database is locked error
        self.timeout = global_config_manager.get_general_config()['max_wait_time_for_local_db_access']
        try:
            self.load_from_db()
        except OperationalError as oe:
            raise DBCorruptedException(oe)

    @pydio_profile
    def load_from_db(self):

        conn = sqlite3.connect(self.db, timeout=self.timeout)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        if self.sub_folder:
            res = c.execute("SELECT node_path,stat_result FROM ajxp_index WHERE stat_result NOT NULL "
                            "AND (node_path=? OR node_path LIKE ?)",
                            (os.path.normpath(self.sub_folder), os.path.normpath(self.sub_folder+'/%'),))
        else:
            res = c.execute("SELECT node_path,stat_result FROM ajxp_index WHERE stat_result NOT NULL")
        for row in res:
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
    @pydio_profile
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


class ClosingCursor():

    def __init__(self, file='', timeout=4, write=False, withCommit=False, retries=100):
        self.file=file
        self.timeout = timeout
        self.retries = retries
        self.write = write
        self.withCommit = withCommit

    def open(self, retry=0):
        try:
            self.conn = sqlite3.connect(self.file, timeout=self.timeout)
        except sqlite3.OperationalError as e:
            time.sleep(.2)
            if retry < self.retries:
                self.open(retry + 1)
            else:
                raise e

    def __enter__(self):
        self.open()
        if self.write:
            return self.conn
        else:
            self.conn.row_factory = sqlite3.Row
            return self.conn.cursor()

    def __exit__(self, type, value, traceback):
        if self.write and self.withCommit:
            self.conn.commit()
        self.conn.close()


class LocalDbHandler():

    def __init__(self, job_data_path='', base=''):
        self.base = base
        self.db = job_data_path + '/pydio.sqlite'
        self.job_data_path = job_data_path
        self.event_handler = None
        global_config_manager = GlobalConfigManager.Instance(configs_path=job_data_path)
        # Increasing the timeout (default 5 seconds), to avoid database is locked error
        self.timeout = global_config_manager.get_general_config()['max_wait_time_for_local_db_access']
        if not os.path.exists(self.db):
            self.init_db()

    def normpath(self, path):
        return os.path.normpath(path)

    def check_lock_on_event_handler(self, event_handler):
        """
        :param event_handler:SqlEventHandler
        :return:
        """
        self.event_handler = event_handler

    def init_db(self):
        conn = sqlite3.connect(self.db, timeout=self.timeout)
        cursor = conn.cursor()
        if getattr(sys, 'frozen', False):
            respath = (Path(sys._MEIPASS)) / 'res' / 'create.sql'
        else:
            respath = (Path(__file__)).parent.parent / 'res' / 'create.sql'
        logging.debug("respath: %s" % respath)
        with open(str(respath), 'r') as inserts:
            for statement in inserts:
                cursor.execute(statement)
        conn.close()

    @pydio_profile
    def find_node_by_id(self, node_path, with_status=False):
        node_path = self.normpath(node_path)
        with ClosingCursor(self.db, timeout=self.timeout) as c:
            id = False
            q = "SELECT node_id FROM ajxp_index WHERE node_path LIKE ?"
            if with_status:
                q = "SELECT ajxp_index.node_id FROM ajxp_index,ajxp_node_status WHERE ajxp_index.node_path = ? AND ajxp_node_status.node_id = ajxp_index.node_id"
            for row in c.execute(q, (node_path,)):
                id = row['node_id']
                break
            return id

    @pydio_profile
    def get_node_md5(self, node_path):
        """
        WARNING NOT USED
        """
        node_path = self.normpath(node_path)
        with ClosingCursor(self.db, timeout=self.timeout) as c:
            for row in c.execute("SELECT md5 FROM ajxp_index WHERE node_path LIKE ?", (node_path,)):
                md5 = row['md5']
                c.close()
                return md5
        return hashfile(self.base + node_path, hashlib.md5())

    @pydio_profile
    def get_node_status(self, node_path):
        try:
            node_path = self.normpath(node_path)
            with ClosingCursor(self.db, timeout=self.timeout) as c:
                status = "False"
                for row in c.execute("SELECT ajxp_node_status.status FROM ajxp_index,ajxp_node_status "
                                     "WHERE ajxp_index.node_path = ? AND ajxp_node_status.node_id = ajxp_index.node_id", (node_path,)):
                    status = row['status']
                    break
                return status
        except sqlite3.OperationalError:
            # If the database was locked return PENDING state, better than nothing ^_^
            return "PENDING"


    @pydio_profile
    def get_directory_node_status(self, node_path):
        node_path = "" if self.normpath('/') == self.normpath(node_path) else self.normpath(node_path)
        try:
            status = "IDLE"
            with ClosingCursor(self.db, timeout=self.timeout) as c:
                if [r[0] for r in c.execute("SELECT COUNT(ajxp_index.node_id) \
                             FROM ajxp_index \
                             LEFT JOIN ajxp_node_status \
                             ON ajxp_node_status.node_id = ajxp_index.node_id\
                             WHERE ajxp_node_status.status<>'IDLE' \
                             AND ajxp_index.node_path LIKE ?", (self.normpath(node_path + '/%'),))][0] > 0:
                    status = "PENDING"
            return status
        except sqlite3.OperationalError:
            # If the database was locked return PENDING state, better than nothing ^_^
            return "PENDING"

    @pydio_profile
    def list_conflict_nodes(self):
        rows = []
        with ClosingCursor(self.db, timeout=self.timeout) as c:
            for row in c.execute("SELECT * FROM ajxp_index,ajxp_node_status "
                                 "WHERE (ajxp_node_status.status='CONFLICT' OR ajxp_node_status.status LIKE 'SOLVED%' ) AND ajxp_node_status.node_id = ajxp_index.node_id"):
                d = {}
                for idx, col in enumerate(c.description):
                    if col[0] == 'stat_result':
                        continue
                    if col[0] == 'detail' and row[idx]:
                        try:
                            decoded_detail = pickle.loads(row[idx])
                            d[col[0]] = decoded_detail
                        except ValueError:
                            pass
                    else:
                        d[col[0]] = row[idx]
                rows.append(d)
        return rows

    @pydio_profile
    def count_conflicts(self):
        c = 0
        with ClosingCursor(self.db, timeout=self.timeout) as conn:
            for row in conn.execute("SELECT count(node_id) FROM ajxp_node_status WHERE status='CONFLICT'"):
                c = int(row[0])
        return c

    @pydio_profile
    def list_solved_nodes_w_callback(self, cb):
        with ClosingCursor(self.db, timeout=self.timeout) as c:
            for row in c.execute("SELECT * FROM ajxp_index,ajxp_node_status "
                                 "WHERE ajxp_node_status.status LIKE 'SOLVED%' AND ajxp_node_status.node_id = ajxp_index.node_id"):
                d = {}
                for idx, col in enumerate(c.description):
                    if col[0] == 'stat_result':
                        continue
                    d[col[0]] = row[idx]
                cb(d)

    @pydio_profile
    def update_node_status(self, node_path, status='IDLE', detail=''):
        node_path = self.normpath(node_path)
        if detail:
            detail = pickle.dumps(detail)
        node_id = self.find_node_by_id(node_path, with_status=True)

        with ClosingCursor(self.db, timeout=self.timeout, write=True, withCommit=True) as conn:
            if not isinstance(status, str):
                logging.info("The status type is not string by default, explicitly assigning it a string value")
                status = "False"

            if not isinstance(detail, str):
                logging.info("The detail type is not string by default, explicitly assigning it a string value")
                detail = ""

            if not node_id:
                node_id = self.find_node_by_id(node_path, with_status=False)
                if node_id:
                    conn.execute("INSERT OR IGNORE INTO ajxp_node_status (node_id,status,detail) VALUES (?,?,?)", (node_id, status, detail))
            else:
                conn.execute("UPDATE ajxp_node_status SET status=?, detail=? WHERE node_id=?", (status, detail, node_id))

    @pydio_profile
    def update_bulk_node_status_as_idle(self):
        with ClosingCursor(self.db, timeout=self.timeout, write=True, withCommit=True) as conn:
            conn.execute('UPDATE ajxp_node_status SET status="IDLE" WHERE ajxp_node_status.status="NEW"')

    @pydio_profile
    def update_bulk_node_status_as_pending(self, list_seq_ids):
        if(len(list_seq_ids)) > 0:
            conn = sqlite3.connect(self.db, timeout=self.timeout)
            conn.row_factory = sqlite3.Row
            try:
                seq_ids = str(",".join(list_seq_ids))

                # Only update status for files, for directories we handle them separately
                conn.execute('UPDATE ajxp_node_status \
                              SET status="PENDING" \
                              WHERE ajxp_node_status.status<>"CONFLICT" \
                              AND node_id IN \
                             (SELECT ajxp_changes.node_id  \
                              FROM ajxp_changes, ajxp_index \
                              WHERE ajxp_changes.seq IN (' + seq_ids + ') \
                              AND ajxp_changes.node_id = ajxp_index.node_id \
                              AND ajxp_index.md5<>"directory" \
                              AND ajxp_index.bytesize>0)')
                conn.commit()
                conn.close()

            except Exception as ex:
                logging.exception(ex)
                pass

    @pydio_profile
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

    @pydio_profile
    def get_last_operations(self):
        operations = []
        with ClosingCursor(self.db, timeout=self.timeout) as c:
            for row in c.execute("SELECT type,location,source,target FROM ajxp_last_buffer"):
                dRow = dict()
                dRow['location'] = row['location']
                dRow['type'] = row['type']
                dRow['source'] = row['source']
                dRow['target'] = row['target']
                operations.append(dRow)
        return operations

    @pydio_profile
    def is_last_operation(self, location, type, source, target):
        with ClosingCursor(self.db, timeout=self.timeout) as c:
            for row in c.execute("SELECT id FROM ajxp_last_buffer WHERE type=? AND location=? AND source=? AND target=?", (type,location,source.replace("\\", "/"),target.replace("\\", "/"))):
                return True
            return False

    @pydio_profile
    def buffer_real_operation(self, location, type, source, target):
        location = 'remote' if location == 'local' else 'local'
        with ClosingCursor(self.db, timeout=self.timeout, write=True, withCommit=True) as conn:
            conn.execute("INSERT INTO ajxp_last_buffer (type,location,source,target) VALUES (?,?,?,?)", (type, location, source.replace("\\", "/"), target.replace("\\", "/")))

    @pydio_profile
    def clear_operations_buffer(self):
        with ClosingCursor(self.db, timeout=self.timeout, write=True, withCommit=True) as conn:
            conn.execute("DELETE FROM ajxp_last_buffer")

    @pydio_profile
    def get_local_changes_as_stream(self, seq_id, flatten_and_store_callback):
        if self.event_handler:
            i = 1
            cannot_read = (int(round(time.time() * 1000)) - self.event_handler.last_write_time) < (self.event_handler.db_wait_duration*1000)
            while cannot_read:
                logging.info('waiting db writing to end before retrieving local changes...')
                cannot_read = (int(round(time.time() * 1000)) - self.event_handler.last_write_time) < (self.event_handler.db_wait_duration*1000)
                time.sleep(i*self.event_handler.db_wait_duration)
                i += 1
            self.event_handler.reading = True
        info = dict()
        info['max_seq'] = seq_id
        try:
            logging.debug("Local sequence " + str(seq_id))
            with ClosingCursor(self.db, timeout=self.timeout) as c:
                for line in c.execute("SELECT seq , ajxp_changes.node_id ,  type ,  "
                                     "source , target, ajxp_index.bytesize, ajxp_index.md5, ajxp_index.mtime, "
                                     "ajxp_index.node_path, ajxp_index.stat_result FROM ajxp_changes LEFT JOIN ajxp_index "
                                     "ON ajxp_changes.node_id = ajxp_index.node_id "
                                     "WHERE seq > ? ORDER BY ajxp_changes.node_id, seq ASC", (seq_id,)):
                    row = dict(line)
                    flatten_and_store_callback('local', row, info)
                    if info:
                        self.event_handler.last_seq_id = info['max_seq']

            flatten_and_store_callback('local', None, info)
            if info:
                self.event_handler.last_seq_id = info['max_seq']

            if self.event_handler:
                self.event_handler.reading = False
            return info['max_seq']
        except Exception as ex:
            logging.exception(ex)
            if self.event_handler:
                self.event_handler.reading = False
            return info['max_seq']

    def list_non_idle_nodes(self):
        logging.info("Listing non IDLE nodes")
        with ClosingCursor(self.db, timeout=self.timeout) as c:
            q = "SELECT ajxp_index.node_id FROM ajxp_index,ajxp_node_status WHERE ajxp_node_status.status <> 'IDLE'  AND ajxp_node_status.node_id = ajxp_index.node_id"
            for row in c.execute(q):
                logging.info(row)

    def get_max_seq(self):
        """
        :return: the max_id from index
        """
        with ClosingCursor(self.db, timeout=self.timeout) as c:
            res = c.execute("SELECT MAX(seq) FROM ajxp_changes").fetchone()[0]
            if res is None:
                res = 0
            return res


class SqlEventHandler(FileSystemEventHandler):
    """reading = False
    last_write_time = 0
    db_wait_duration = 1"""

    def __init__(self, basepath, includes, excludes, job_data_path):
        super(SqlEventHandler, self).__init__()
        self.base = basepath
        self.includes = includes
        self.excludes = excludes
        db_handler = LocalDbHandler(job_data_path, basepath)
        self.unique_id = hashlib.md5(job_data_path.encode(guess_filesystemencoding())).hexdigest()
        self.db = db_handler.db
        # Increasing the timeout (default 5 seconds), to avoid database is locked error
        self.timeout = db_handler.timeout
        self.reading = False
        self.last_write_time = 0
        self.db_wait_duration = .4
        self.last_seq_id = 0
        self.prevent_atomic_commit = False
        self.con = None
        self.locked = False

    @staticmethod
    def get_unicode_path(src):
        if isinstance(src, str):
            src = unicode(src, 'utf-8')
        return src

    def remove_prefix(self, text):
        text = text[len(self.base):] if text.startswith(self.base) else text
        return os.path.normpath(text)

    @pydio_profile
    def included(self, event, base=None):
        path = ''
        if not base:
            if hasattr(event, 'dest_path'):
                base = os.path.basename(event.dest_path)
                path = self.remove_prefix(self.get_unicode_path(event.dest_path))
            else:
                base = os.path.basename(event.src_path)
                path = self.remove_prefix(self.get_unicode_path(event.src_path))
        try:
            #logging.info(" 1 : " + str(type(base)) + " " + str(type(path)))
            if isinstance(path, str):
                #logging.info('ENCODING PATH')
                path = unicode(path, 'utf-8')
            if isinstance(base, str):
                #logging.info('ENCODING BASE')
                base = unicode(base, 'utf-8')
            #logging.info("2 : " + str(type(base)) + " " + str(type(path)))
            #logging.info(base + u" " + path)
        except Exception as e:
            logging.exception(e)
        if path == '.':
            return False
        for i in self.includes:
            if not fnmatch.fnmatch(base, i):
                return False
        for e in self.excludes:
            if fnmatch.fnmatch(base, e):
                return False
        for e in self.excludes:
            if (e.startswith('/') or e.startswith('*/')) and fnmatch.fnmatch(path, e):
                return False
        return True

    @pydio_profile
    def on_moved(self, event):
        #   logging.info(event.src_path + event.dest_path)
        try:

            if not self.included(event):
                logging.debug('ignoring move event ' + self.get_unicode_path(event.src_path) + " " + self.get_unicode_path(event.dest_path))
                return

            self.lock_db()
            target_key = self.remove_prefix(self.get_unicode_path(event.dest_path))
            source_key = self.remove_prefix(self.get_unicode_path(event.src_path))
            logging.debug("Event: move noticed: " + event.event_type + " on file " + target_key + " at " + time.asctime())

            if self.prevent_atomic_commit:
                conn = self.transaction_conn
            else:
                conn = sqlite3.connect(self.db, timeout=self.timeout)

            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            target_id = None
            node_id = None
            for row in c.execute("SELECT node_id FROM ajxp_index WHERE node_path=?", (source_key,)):
                node_id = row['node_id']
                break
            for row2 in c.execute("SELECT node_id FROM ajxp_index WHERE node_path=?", (target_key,)):
                target_id = row2['node_id']
                break
            c.close()
            if not node_id:
                if target_id:
                    # fake update = content
                    conn.execute("UPDATE ajxp_index SET node_path=? WHERE node_path=?", (target_key, target_key, ))
                else:
                     # detected a move but node not found: create it
                    self.updateOrInsert(self.get_unicode_path(event.dest_path), event.is_directory, True, force_insert=True)
            else:
                t = (target_key,source_key,)
                conn.execute("UPDATE ajxp_index SET node_path=? WHERE node_path=?", t)
            if not self.prevent_atomic_commit:
                conn.commit()
                conn.close()
        except sqlite3.OperationalError:
            time.sleep(.1)
            self.on_moved(event)
        except Exception as ex:
            logging.exception(ex)
        self.unlock_db()

    @pydio_profile
    def on_created(self, event):
        if not self.included(event):
            logging.debug('ignoring create event %s ' % self.get_unicode_path(event.src_path))
            return
        self.lock_db()
        try:
            src_path = self.get_unicode_path(event.src_path)
            logging.debug("Event: creation noticed: " + event.event_type +
                          " on file " + src_path + " at " + time.asctime())
            if not os.path.exists(src_path):
                return
        except Exception as ex:
            logging.exception(ex)
        while True:
            try:
                self.updateOrInsert(src_path, is_directory=event.is_directory, skip_nomodif=False)
                break
            except sqlite3.OperationalError:  # database locked
                logging.info('DB locked')
                time.sleep(.1)
        self.unlock_db()

    @pydio_profile
    def on_deleted(self, event):
        if not self.included(event):
            return
        logging.debug("Event: deletion noticed: " + event.event_type + " on file " + self.get_unicode_path(event.src_path) + " at " + time.asctime())
        self.lock_db()
        while True:
            try:
                src_path = self.get_unicode_path(event.src_path)
                if self.prevent_atomic_commit:
                    conn = self.transaction_conn
                else:
                    conn = sqlite3.connect(self.db, timeout=self.timeout)
                    conn.row_factory = sqlite3.Row
                conn.execute("DELETE FROM ajxp_index WHERE node_path LIKE ?", (self.remove_prefix(src_path) + '%',))
                if not self.prevent_atomic_commit:
                    conn.commit()
                    conn.close()
                break
            except sqlite3.OperationalError:
                time.sleep(.1)
            except Exception as ex:
                logging.exception(ex)
        self.unlock_db()

    @pydio_profile
    def on_modified(self, event):
        super(SqlEventHandler, self).on_modified(event)
        if not self.included(event):
            logging.debug('ignoring modified event ' + self.get_unicode_path(event.src_path))
            return
        self.lock_db()
        while True:
            try:
                src_path = self.get_unicode_path(event.src_path)
                if event.is_directory:
                    if os.path.isdir(src_path):
                        files_in_dir = [src_path+"/"+f for f in os.listdir(src_path)]
                        if len(files_in_dir) > 0:
                            modified_filename = max(files_in_dir, key=os.path.getmtime)
                        else:
                            return
                    else:
                        return
                    if os.path.isfile(modified_filename) and self.included(event=None, base=self.remove_prefix(modified_filename)):
                        logging.debug("Event: modified file 1 : %s" % self.remove_prefix(modified_filename))
                        self.updateOrInsert(modified_filename, is_directory=False, skip_nomodif=True)
                else:
                    modified_filename = src_path
                    if not os.path.exists(src_path):
                        return
                    if not self.included(event=None, base=self.remove_prefix(modified_filename)):
                        return
                    logging.debug("Event: modified file : %s" % self.remove_prefix(modified_filename))
                    self.updateOrInsert(modified_filename, is_directory=False, skip_nomodif=True)
                break
            except sqlite3.OperationalError:
                time.sleep(.1)
            except sqlite3.ProgrammingError:
                logging.info("Note to dev: Experimental check the callee.")
                conn = sqlite3.connect(self.db, timeout=self.timeout)
                conn.row_factory = sqlite3.Row
            except Exception as ex:
                logging.exception(ex)
        self.unlock_db()

    @pydio_profile
    def updateOrInsert(self, src_path, is_directory, skip_nomodif, force_insert=False):
        search_key = self.remove_prefix(src_path)
        size = 0
        mtime = 0

        try:
            stat = os.stat(src_path)
            if is_directory:
                hash_key = 'directory'
            else:
                size = stat.st_size
                mtime = stat.st_mtime
                if self.prevent_atomic_commit:
                    hash_key = "HASHME"  # Will be hashed when transaction ends
                else:
                    hash_key = hashfile(open(src_path, 'rb'), hashlib.md5())
        except IOError:
            # Skip the file from processing, It could be a file that is being copied or a open file!
            logging.debug('Skipping file %s, as it is being copied / kept open!' % src_path)
            return
        except Exception as e:
            logging.exception(e)
            return

        while True:
            try:
                node_id = False
                if self.prevent_atomic_commit:
                    conn = self.transaction_conn
                else:
                    conn = sqlite3.connect(self.db, timeout=self.timeout)
                    conn.row_factory = sqlite3.Row
                if not force_insert:
                    c = conn.cursor()
                    node_id = None
                    for row in c.execute("SELECT node_id FROM ajxp_index WHERE node_path=?", (search_key,)):
                        node_id = row['node_id']
                        break
                    c.close()

                if not node_id:
                    t = (
                        search_key,
                        size,
                        hash_key,
                        mtime,
                        pickle.dumps(stat)
                    )
                    logging.debug("Real insert %s" % search_key)
                    c = conn.cursor()
                    del_element = None
                    existing_id = None
                    if hash_key == 'directory':
                        existing_id = self.find_windows_folder_id(src_path)
                        if existing_id:
                            del_element = self.find_deleted_element(c, self.last_seq_id, os.path.basename(src_path), node_id=existing_id)
                    else:
                        del_element = self.find_deleted_element(c, self.last_seq_id, os.path.basename(src_path), md5=hash_key)

                    if del_element:
                        logging.info("THIS IS CAN BE A MOVE OR WINDOWS UPDATE " + src_path)
                        t = (
                            del_element['node_id'],
                            del_element['source'],
                            size,
                            hash_key,
                            mtime,
                            pickle.dumps(stat)
                        )
                        c.execute("INSERT INTO ajxp_index (node_id,node_path,bytesize,md5,mtime,stat_result) "
                                  "VALUES (?,?,?,?,?,?)", t)
                        c.execute("UPDATE ajxp_index SET node_path=? WHERE node_path=?", (search_key, del_element['source']))

                    else:
                        if hash_key == 'directory' and existing_id:
                            self.clear_windows_folder_id(src_path)
                        c.execute("INSERT INTO ajxp_index (node_path,bytesize,md5,mtime,stat_result) VALUES (?,?,?,?,?)", t)
                        if hash_key == 'directory':
                            self.set_windows_folder_id(c.lastrowid, src_path)
                else:
                    if skip_nomodif:
                        t = (
                            size,
                            hash_key,
                            mtime,
                            pickle.dumps(stat),
                            search_key,
                            hash_key
                        )
                        logging.debug("Real update not the same (size %d)" % size)
                        conn.execute("UPDATE ajxp_index SET bytesize=?, md5=?, mtime=?, stat_result=? WHERE node_path=? AND md5!=?", t)
                    else:
                        t = (
                            size,
                            hash_key,
                            mtime,
                            pickle.dumps(stat),
                            search_key
                        )
                        logging.debug("Real update %s" % search_key)
                        conn.execute("UPDATE ajxp_index SET bytesize=?, md5=?, mtime=?, stat_result=? WHERE node_path=?", t)
                if not self.prevent_atomic_commit:
                    conn.commit()
                    conn.close()
                break
            except sqlite3.OperationalError:
                time.sleep(.1)
            except IOError:
                return

    @pydio_profile
    def set_windows_folder_id(self, node_id, path):
        if os.name in ("nt", "ce"):
            logging.debug("Created folder %s with node id %i" % (path, node_id))
            try:
                self.clear_windows_folder_id(path)
                with open(path + "\\.pydio_id", "w") as hidden:
                    hidden.write("%s:%i" % (self.unique_id, node_id,))
                    hidden.close()
                    set_file_hidden(path + "\\.pydio_id")
            except Exception as e:
                logging.exception(e)
                logging.error("Error while trying to save hidden file .pydio_id : %s" % e.message)

    @pydio_profile
    def find_windows_folder_id(self, path):
        if os.name in("nt", "ce") and os.path.exists(path + "\\.pydio_id"):
            with open(path + "\\.pydio_id") as hidden_file:
                data = hidden_file.readline().split(':')
                if len(data) < 1 or (len(data) == 2 and data[0] != self.unique_id):
                    #wrong format or wrong unique_id!
                    hidden_file.close()
                    self.clear_windows_folder_id(path)
                    return None
                elif len(data) == 2:
                    hidden_file.close()
                    return int(data[1])
                hidden_file.close()
        return None

    def clear_windows_folder_id(self, path):
        if os.name in("nt", "ce") and os.path.exists(path + "\\.pydio_id"):
            os.unlink(path + "\\.pydio_id")

    @pydio_profile
    def find_deleted_element(self, cursor, start_seq, basename, md5=None, node_id=None):
        try:
            res = cursor.execute('SELECT * FROM ajxp_changes WHERE source LIKE ? AND type="delete" '
                                 'AND node_id NOT IN (SELECT node_id FROM ajxp_index) '
                                 'AND seq > ? ORDER BY seq DESC', ("%\\"+basename, start_seq))
            if not res:
                return None
            for row in res:
                try:
                    if (md5 and row['deleted_md5'] == md5) or (node_id and row['node_id'] == node_id):
                        return {'source': row['source'], 'node_id': row['node_id']}
                except Exception as e:
                    logging.exception(e)
                    pass
            return None
        except sqlite3.OperationalError:
            return self.find_deleted_element(cursor, start_seq, basename, md5, node_id)


    @pydio_profile
    def begin_transaction(self):
        self.transaction_conn = sqlite3.connect(self.db, timeout=self.timeout)
        self.transaction_conn.row_factory = sqlite3.Row
        self.prevent_atomic_commit = True

    @pydio_profile
    def end_transaction(self):
        """ The db is unicode_escape encoded, other functions seem to expect unicode
        """
        class hasher(threading.Thread):
            """ This is a thread, used to md5 hash files
            """
            def __init__(self):
                threading.Thread.__init__(self)
                self.brow = ""
                self.res = {}

            def hashrow(self):
                """
                :return: a dict containing SQL code and values to be executed later
                """
                base = self.brow[0]
                row = self.brow[1]
                #logging.info(brow)
                path = row[1] #unicodedata.normalize('NFC', r[1])
                if os.path.exists(base + path):
                    with open(base + path, 'rb') as fd:
                        t = (
                            os.path.getsize(base + path),
                            hashfile(fd, hashlib.md5()),
                            os.path.getmtime(base + path),
                            pickle.dumps(os.stat(base + path)),
                            row[1]
                             )
                    return {"sql": "UPDATE ajxp_index SET bytesize=?, md5=?, mtime=?, stat_result=? WHERE node_path=? AND md5='HASHME'", "values": t}
                else:
                    # delete the index of non existing files
                    return {"sql": "DELETE FROM ajxp_index WHERE node_path=? AND md5='HASHME'", "values": base+path}

            def do(self):
                self.res = self.hashrow()

            def run(self):
                pass
        self.transaction_conn.commit()
        if self.prevent_atomic_commit:
            cur = self.transaction_conn.cursor()
        else:  # This is propably useless
            cur = sqlite3.connect(self.db, timeout=self.timeout).cursor()
            cur.row_factory = sqlite3.Row
        def hashfetcher(cur):
            """ Yields brows (basepath + sql row) of changes to be processed
            :param cur: sqlite cursor
            :yield: brow
            """
            while True:
                try:
                    cur.execute("SELECT * FROM ajxp_index WHERE md5=?", ("HASHME",))
                    rows = cur.fetchmany(100)
                    if not rows:
                        break
                    for row in rows:
                        yield (self.base, row)
                except sqlite3.OperationalError as oe:
                    logging.exception(oe)  # catch DB locked errors
                    pass
        #logging.info(" HASHING BEGINS (" + str(cur.execute("SELECT COUNT(*) FROM ajxp_index WHERE md5=?", ("HASHME",)).fetchone()[0]) + ")")
        #ts = time.time()
        pool = [hasher() for t in range(4)] # TODO Tune me depending on the number of changes to be processed, and HW
        for p in pool:
            p.start()
        shouldexit = False
        brows = hashfetcher(cur)
        hashedfiles = 0
        while True:
            """ A pool of threads is used and managed here, for every cycle we go through the pool to collect
                possible results and load more items in the pool to be hashed, termination is handled by the
                shouldexit flag. We make sure all the results are collected by waiting for the threads to join.
            """
            for t in pool:
                if not t.isAlive():
                    if t.res != {}:
                        """try:  # for debugging
                            import resource, humanize
                            logging.info(' Memory usage: %s' % humanize.naturalsize(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
                        except ImportError:
                            pass
                        """
                        cur.execute(t.res["sql"], t.res["values"])
                        t.res = {}
                        hashedfiles += 1
                        if hashedfiles > 1000:
                            hashedfiles = 0
                            try:
                                self.transaction_conn.commit()
                            except Exception as e:
                                logging.exception(e)
                    if not shouldexit:
                        try:
                            t.brow = next(brows)
                            t.do()
                        except StopIteration:
                            shouldexit = True
            if shouldexit:
                for t in pool:
                    t.join()
                    if t.res != {}:
                        cur.execute(t.res["sql"], t.res["values"])
                break
        #logging.info(" Threaded HASHING DONE " + str(time.time() - ts))
        self.transaction_conn.commit()
        self.prevent_atomic_commit = False
        self.transaction_conn.close()

    @pydio_profile
    def lock_db(self):
        self.locked = True
        ###################################################################
        while self.reading:
            time.sleep(self.db_wait_duration)
        self.last_write_time = int(round(time.time() * 1000))
        ###################################################################

    @pydio_profile
    def unlock_db(self):
        self.locked = False
        self.last_write_time = int(round(time.time() * 1000))

    def db_stats(self):
        """
        :return: some stats about the database
        """
        c = sqlite3.connect(self.db, timeout=self.timeout)
        c.row_factory = sqlite3.Row
        logging.info(self.db)
        while True:
            try:
                dirs = c.execute("SELECT count(*) from ajxp_index where md5=?", ('directory',)).fetchone()
                files = c.execute("SELECT count(*) from ajxp_index where md5<>?", ('directory',)).fetchone()
                c.commit()
                break
            except sqlite3.OperationalError as oe:
                logging.exception(oe)  # catch DB locked errors
                pass
        c.close()
        #logging.info(str(files) + " " + str(dirs))
        return {"nbfiles": files, "nbdirs": dirs}
