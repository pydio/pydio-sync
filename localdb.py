__author__ = 'charles'
import sqlite3
import os
import hashlib
import time
import fnmatch

from utils import hashfile

from watchdog.events import FileSystemEventHandler


class LocalDbHandler():

    def __init__(self, base=''):
        self.base = base
        self.db = "data/pydio.sqlite"

    def find_node_by_id(self, node_path):
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        for row in c.execute("SELECT node_id FROM ajxp_index WHERE node_path LIKE ?", (node_path.decode('utf-8'))):
            return row['node_id']
        c.close()
        return False

    def get_node_md5(self, node_path):
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        for row in c.execute("SELECT md5 FROM ajxp_index WHERE node_path LIKE ?", (node_path.decode('utf-8'))):
            return row['md5']
        c.close()
        return hashfile(self.base + node_path, hashlib.md5())


    def get_local_changes(self, seq_id, accumulator):

        print "Local sequence " + str(seq_id)
        last = seq_id
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        previous_node_id = -1
        previous_row = None
        orders = dict()
        orders['path'] = 0
        orders['content'] = 1
        orders['create'] = 2
        orders['delete'] = 3
        for row in c.execute("SELECT * FROM ajxp_changes LEFT JOIN ajxp_index "
                             "ON ajxp_changes.node_id = ajxp_index.node_id "
                             "WHERE seq > ? ORDER BY ajxp_changes.node_id, seq ASC", (seq_id,)):
            drow = dict(row)
            drow['node'] = dict()
            for att in ('mtime', 'md5', 'bytesize', 'node_path',):
                drow['node'][att] = row[att]
                drow.pop(att, None)
            if drow['node_id'] == previous_node_id:
                previous_row['target'] = drow['target']
                previous_row['seq'] = drow['seq']
                if orders[drow['type']] > orders[previous_row['type']]:
                    previous_row['type'] = drow['type']
            else:
                if previous_row is not None and (previous_row['source'] != previous_row['target'] or previous_row['type'] == 'content'):
                    previous_row['location'] = 'local'
                    accumulator.append(previous_row)
                previous_row = drow
                previous_node_id = drow['node_id']
            last = max(row['seq'], last)

        if previous_row is not None and (previous_row['source'] != previous_row['target'] or previous_row['type'] == 'content'):
            previous_row['location'] = 'local'
            accumulator.append(previous_row)

        conn.close()
        return last


class SqlEventHandler(FileSystemEventHandler):

    def __init__(self, pattern='*', basepath=''):
        super(SqlEventHandler, self).__init__()
        self.base = basepath
        self.pattern = pattern
        self.db = "data/pydio.sqlite"

    def remove_prefix(self, text):
        return text[len(self.base):] if text.startswith(self.base) else text

    def on_moved(self, event):
        print(event)
        print("Move noticed: " + event.event_type + " on file " + event.src_path + " at " + time.asctime())
        conn = sqlite3.connect(self.db)
        t = (
            self.remove_prefix(event.dest_path.decode('utf-8')),
            self.remove_prefix(event.src_path.decode('utf-8')),
        )
        conn.execute("UPDATE ajxp_index SET node_path=? WHERE node_path=?", t)
        conn.commit()
        conn.close()

    def on_created(self, event):
        print("Creation noticed: " + event.event_type +
                         " on file " + event.src_path + " at " + time.asctime())
        if event.is_directory:
            t = (
                self.remove_prefix(self.remove_prefix(event.src_path).decode('utf-8')),
                os.path.getsize(event.src_path),
                'directory',
                os.path.getmtime(event.src_path),
            )
        else:
            t = (
                self.remove_prefix(event.src_path.decode('utf-8')),
                os.path.getsize(event.src_path),
                hashfile(open(event.src_path, 'rb'), hashlib.md5()),
                os.path.getmtime(event.src_path),
            )
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO ajxp_index (node_path,bytesize,md5,mtime) VALUES (?,?,?,?)", t)
        conn.commit()
        conn.close()

    def on_deleted(self, event):
        print("Deletiong noticed: " + event.event_type +
                         " on file " + event.src_path + " at " + time.asctime())
        conn = sqlite3.connect(self.db)
        conn.execute("DELETE FROM ajxp_index WHERE node_path LIKE ?", (self.remove_prefix(event.src_path.decode('utf-8')) + '%',))
        conn.commit()
        conn.close()

    def on_modified(self, event):
        super(SqlEventHandler, self).on_modified(event)

        if event.is_directory:
            files_in_dir = [event.src_path+"/"+f for f in os.listdir(event.src_path)]
            if len(files_in_dir) > 0:
                modifiedFilename = max(files_in_dir, key=os.path.getmtime)
            else:
                return
            if os.path.isfile(modifiedFilename) and fnmatch.fnmatch(os.path.basename(modifiedFilename), self.pattern) and not os.path.basename(modifiedFilename):
                print "Modified file : %s" % modifiedFilename
                conn = sqlite3.connect(self.db)
                t = (os.path.getsize(modifiedFilename), hashfile(open(modifiedFilename, 'rb'), hashlib.md5()), os.path.getmtime(modifiedFilename), self.remove_prefix(modifiedFilename.decode('utf-8')),)
                conn.execute("UPDATE ajxp_index SET bytesize=?, md5=?, mtime=? WHERE node_path=?", t)
                conn.commit()
                conn.close()
        else:
            modifiedFilename = event.src_path
            print "Modified folder (ignore) : %s" % self.remove_prefix(modifiedFilename)
