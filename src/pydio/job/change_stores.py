#
# Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
# This file is part of Pydio.
#
# Pydio is free software: you can redistribute it and/or modify
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
import json
import os
import logging
import fnmatch

from pydio.sdk.exceptions import InterruptException


class SqliteChangeStore():
    conn = None

    def __init__(self, filename, includes, excludes):
        self.db = filename
        self.includes = includes
        self.excludes = excludes
        self.create = False
        if not os.path.exists(self.db):
            self.create = True

    def open(self):
        self.conn = sqlite3.connect(self.db)
        self.conn.row_factory = sqlite3.Row
        if self.create:
            self.conn.execute(
                'CREATE TABLE ajxp_changes (row_id INTEGER PRIMARY KEY AUTOINCREMENT , seq_id, location TEXT, '
                'type TEXT, source TEXT, target TEXT, content INTEGER, md5 TEXT, bytesize INTEGER, data TEXT)')
            self.conn.execute(
                "CREATE TABLE ajxp_last_buffer ( id INTEGER PRIMARY KEY AUTOINCREMENT, location TEXT, type TEXT, "
                "source TEXT, target TEXT )")
            self.conn.execute("CREATE INDEX changes_seq_id ON ajxp_changes (seq_id)")
            self.conn.execute("CREATE INDEX changes_location ON ajxp_changes (location)")
            self.conn.execute("CREATE INDEX changes_type ON ajxp_changes (type)")
            self.conn.execute("CREATE INDEX changes_source ON ajxp_changes (source)")
            self.conn.execute("CREATE INDEX changes_target ON ajxp_changes (target)")
            self.conn.execute("CREATE INDEX changes_md5 ON ajxp_changes (md5)")
            self.conn.execute("CREATE INDEX buffer_location ON ajxp_last_buffer (location)")
            self.conn.execute("CREATE INDEX buffer_type ON ajxp_last_buffer (type)")
            self.conn.execute("CREATE INDEX buffer_source ON ajxp_last_buffer (source)")
            self.conn.execute("CREATE INDEX buffer_target ON ajxp_last_buffer (target)")
        else:
            self.conn.execute("DELETE FROM ajxp_changes")
        self.conn.commit()


    def __len__(self):
        return self.get_row_count()

    def get_row_count(self, type='all'):
        if type == 'all':
            res = self.conn.execute("SELECT count(row_id) FROM ajxp_changes")
        else:
            res = self.conn.execute("SELECT count(row_id) FROM ajxp_changes WHERE type=?", (type,))
        count = res.fetchone()
        return count[0]

    def process_changes_with_callback(self, callback):
        c = self.conn.cursor()

        res = c.execute('SELECT * FROM ajxp_changes WHERE md5="directory" ORDER BY source,target')
        for row in res:
            try:
                callback(self.sqlite_row_to_dict(row, load_node=True))
                self.conn.execute('DELETE FROM ajxp_changes WHERE row_id=?', (row['row_id'],))
            except InterruptException as e:
                break
        self.conn.commit()

        #now go to the rest
        res = c.execute('SELECT * FROM ajxp_changes ORDER BY source,target')
        for row in res:
            try:
                callback(self.sqlite_row_to_dict(row, load_node=True))
                self.conn.execute('DELETE FROM ajxp_changes WHERE row_id=?', (row['row_id'],))
            except InterruptException as e:
                break
        self.conn.commit()

    def list_changes(self, cursor=0, limit=5, where=''):
        c = self.conn.cursor()
        sql = 'SELECT * FROM ajxp_changes ORDER BY source,target LIMIT ?,?'
        if where:
            sql = 'SELECT * FROM ajxp_changes WHERE ' + where + ' ORDER BY source,target LIMIT ?,?'
        res = c.execute(sql, (cursor, limit))
        changes = []
        for row in res:
            changes.append(self.sqlite_row_to_dict(row, load_node=True))
        return changes

    def sum_sizes(self, where=''):
        c = self.conn.cursor()
        sql = 'SELECT SUM(bytesize) as total FROM ajxp_changes ORDER BY source,target'
        if where:
            sql = 'SELECT SUM(bytesize) as total FROM ajxp_changes WHERE ' + where + ' ORDER BY source,target'
        res = c.execute(sql)
        total = 0.0
        for row in res:
            if row['total']:
                total = float(row['total'])
        return total


    def prune_folders_moves(self):
        sql = 'SELECT * FROM ajxp_changes t1 ' \
              '     WHERE (type="delete" OR type="path") ' \
              '     AND EXISTS( ' \
              '         SELECT * FROM ajxp_changes t2 WHERE t2.type=t1.type AND t2.location=t1.location ' \
              '                 AND t2.source LIKE t1.source || "/%" )'
        c = self.conn.cursor()
        res = c.execute(sql)
        for row in res:
            r = self.sqlite_row_to_dict(row)
            res = self.conn.execute("DELETE FROM ajxp_changes WHERE location=? AND type=? AND source LIKE ?",
                                    (row['location'], row['type'], row['source'] + "/%"))
            logging.debug('[change store] Pruning %i rows', res.rowcount)
        self.conn.commit()

    def dedup_changes(self):
        """
        Remove changes that are found on both sides, except content > conflict
        :return:
        """
        sql = 'DELETE FROM ajxp_changes' \
              '     WHERE row_id IN( ' \
              '         SELECT row_id ' \
              '             FROM ajxp_changes t1 ' \
              '                 WHERE EXISTS (' \
              '                     SELECT * ' \
              '                     FROM ajxp_changes t2 ' \
              '                     WHERE t1.location <> t2.location ' \
              '                     AND   t1.content == 0 ' \
              '                     AND   t1.type = t2.type ' \
              '                     AND   t1.source = t2.source ' \
              '                     AND   t1.target = t2.target ' \
              '                     AND   t1.content = t2.content ' \
              '                 )' \
              '             )'
        res = self.conn.execute(sql)
        self.conn.commit()
        logging.debug('[change store] Dedup: pruned %i rows', res.rowcount)

    def filter_out_echoes_events(self):
        """
        Remove changes that are found in ajxp_last_buffer : echoes from last cycle
        Except content modifications > conflict
        :return:
        """
        sql = 'DELETE FROM ajxp_changes' \
              '     WHERE row_id IN( ' \
              '         SELECT row_id ' \
              '             FROM ajxp_changes t1 ' \
              '                 WHERE t1.content == 0 ' \
              '                 AND EXISTS (' \
              '                     SELECT * ' \
              '                     FROM ajxp_last_buffer t2 ' \
              '                     WHERE t1.location == t2.location ' \
              '                     AND   t1.type = t2.type ' \
              '                     AND   t1.source = t2.source ' \
              '                     AND   t1.target = t2.target ' \
              '                 )' \
              '             )'
        cursor = self.conn.cursor()
        res = cursor.execute(sql)
        self.conn.commit()
        logging.debug('[change store] Echo : pruned %i rows', res.rowcount)


    def detect_unnecessary_changes(self, local_sdk, remote_sdk):
        self.local_sdk = local_sdk
        self.remote_sdk = remote_sdk
        self.filter_w_stat('local', self.local_sdk, self.remote_sdk)
        self.filter_w_stat('remote', self.remote_sdk, self.local_sdk)
        self.conn.commit()

    def filter_w_stat(self, location, sdk, opposite_sdk, offset=0, limit=1000):
        # Load 'limit' changes and filter them
        c = self.conn.cursor()
        res = c.execute('SELECT * FROM ajxp_changes WHERE location=? LIMIT ?,?', (location, offset, limit))
        changes = []
        for row in res:
            changes.append(self.sqlite_row_to_dict(row))

        test_stats = []
        for c in changes:
            if c['source'] != 'NULL': test_stats.append(c['source'])
            if c['target'] != 'NULL': test_stats.append(c['target'])
        test_stats = list(set(test_stats))
        opposite_stats = None
        # bulk_stat formatting problem >> recursion
        if len(test_stats):
            local_stats = sdk.bulk_stat(test_stats, with_hash=True)
            opposite_stats = opposite_sdk.bulk_stat(test_stats, with_hash=True)

        to_remove = filter(lambda it: self.filter_change(it, local_stats, opposite_stats), changes)
        ids = map(lambda row: str(row['row_id']), to_remove)
        res = self.conn.execute('DELETE FROM ajxp_changes WHERE row_id IN (' + str(','.join(ids)) + ')')
        logging.debug('[change store] RealFilter : pruned %i rows', res.rowcount)

    def clean_and_detect_conflicts(self, status_handler):

        # transform solved conflicts into process operation
        def handle_solved(node):
            if node['status'] == 'SOLVED:KEEPREMOTE':
                # remove local operation
                self.conn.execute('DELETE from ajxp_changes WHERE location=? AND target=?',
                                  ('local', node['node_path']))
            elif node['status'] == 'SOLVED:KEEPLOCAL':
                # remove remote operation
                self.conn.execute('DELETE from ajxp_changes WHERE location=? AND target=?',
                                  ('remote', node['node_path']))

        status_handler.list_solved_nodes_w_callback(handle_solved)
        self.conn.commit()

        sql = '         SELECT * ' \
              '                 FROM ajxp_changes t1 ' \
              '                 WHERE EXISTS (' \
              '                     SELECT * ' \
              '                     FROM ajxp_changes t2 ' \
              '                     WHERE t1.location <> t2.location ' \
              '                     AND   t1.target != "NULL" AND t1.target = t2.target ' \
              '                     AND (  ' \
              '                         t1.md5 != t2.md5 OR ( t1.md5 != "directory" AND t1.bytesize != t2.bytesize) ' \
              '                     )   ' \
              '                 )'
        res = self.conn.execute(sql)
        conflicts = 0
        for row in res:
            if row['location'] == 'remote':
                conflicts += 1
                path = row['target']
                logging.debug('[change store] Storing CONFLICT on node %s' % path)
                status_handler.update_node_status(path, 'CONFLICT', self.sqlite_row_to_dict(row, load_node=True))

        return conflicts

    def sqlite_row_to_dict(self, sqlrow, load_node=False):
        keys = ('row_id', 'location', 'source', 'target', 'type', 'content', 'md5', 'bytesize')
        change = {}
        for key in keys:
            change[key] = sqlrow[key]
        if load_node:
            data = json.loads(sqlrow['data'])
            change['node'] = data['node']
        return change

    def filter_change(self, item, my_stat=None, other_stats=None):
        """
        Try to detect if a change can be ignored, depending on the state of the "target". For example, if a delete
        is registered and the file already cannot be found, we can just ignore it.
        :param item:change item
        :param my_stat:stats of the files on the same side as source
        :param other_stats:stats of the files of the other side
        :return:
        """

        location = item['location']
        opposite = 'local' if item['location'] == 'remote' else 'remote'
        res = False
        if item['type'] == 'create' or item['type'] == 'content':
            # If it does not exist on remote side, skip
            test_stat = self.stat_path(item['target'], location=opposite, stats=other_stats, with_hash=True)
            if not test_stat:
                return False
            # If it exists but is a directory, it won't change
            if item['md5'] == 'directory':
                res = True
            # If it exists and has same size, ok
            elif test_stat['size'] == item['bytesize'] and 'hash' in test_stat and test_stat['hash'] == item['md5']:
                res = True
        elif item['type'] == 'delete':
            # Shall we really delete it?
            loc_stat = self.stat_path(item['source'], location=location, stats=my_stat)
            if loc_stat:
                res = True
            # Shall we delete if already absent? no!
            test_stat = self.stat_path(item['source'], location=opposite, stats=other_stats)
            if not test_stat:
                res = True
        else:  #MOVE
            source_stat = self.stat_path(item['source'], location=opposite, stats=other_stats)
            target_stat = self.stat_path(item['target'], location=opposite, stats=other_stats, with_hash=True)
            if not target_stat or source_stat:
                return False
            elif item['md5'] == 'directory':
                res = True
            elif target_stat['size'] == item['bytesize'] and 'hash' in target_stat and target_stat['hash'] == item[
                'md5']:
                res = True

        if res:
            if item['type'] != 'delete':
                logging.debug('[' + location + '] Filtering out ' + item['type'] + ': ' + item['target'])
            else:
                logging.debug('[' + location + '] Filtering out ' + item['type'] + ' ' + item['source'])
            return True

        return False


    def buffer_real_operation(self, location, type, source, target):
        location = 'remote' if location == 'local' else 'local'
        self.conn.execute("INSERT INTO ajxp_last_buffer (type,location,source,target) VALUES (?,?,?,?)",
                          (type, location, source, target))
        self.conn.commit()


    def clear_operations_buffer(self):
        self.conn.execute("DELETE FROM ajxp_last_buffer")
        self.conn.commit()


    def stat_path(self, path, location, stats=None, with_hash=False):
        """
        Stat a path, calling the correct SDK depending on the location passed.
        :param path:Node path
        :param location:"remote" or "local"
        :param stats: if they were already previously bulk_loaded, will just look for the path in that dict()
        :param with_hash:bool ask for content hash or not
        :return:
        """
        try:
            if stats:
                return stats[path]
        except KeyError:
            pass

        if location == 'remote':
            return self.remote_sdk.stat(path, with_hash)
        else:
            return self.local_sdk.stat(path, with_hash=True)

    def get_min_seq(self, location, success=False):
        res = self.conn.execute("SELECT min(seq_id) FROM ajxp_changes WHERE location=?", (location,))
        for row in res:
            if not row[0]:
                return -1
            else:
                if success:
                    return row[0]
                else:
                    return row[0] - 1
        return -1

    def close(self):
        self.conn.close()

    def massive_store(self, location, changes):
        for seq_id in changes['data']:
            change = changes['data'][seq_id]
            self.store(location, seq_id, change)
        self.sync()

    def filter_path(self, path):
        if path == 'NULL':
            return False
        base = os.path.basename(path)
        for i in self.includes:
            if not fnmatch.fnmatch(base, i):
                return True
        for e in self.excludes:
            if fnmatch.fnmatch(base, e):
                return True
        for e in self.excludes:
            if (e.startswith('/') or e.startswith('*/')) and fnmatch.fnmatch(path, e):
                return True

    def store(self, location, seq_id, change):

        if self.filter_path(change['source']) or self.filter_path(change['target']):
            return

        if change['node'] and change['node']['md5']:
            md5 = change['node']['md5']
        else:
            md5 = ''
        if change['node'] and change['node']['bytesize']:
            bytesize = change['node']['bytesize']
        else:
            bytesize = ''
        content = 0
        if md5 != 'directory' and (change['type'] == 'content' or change['type'] == 'create'):
            content = 1
        data = (
            seq_id,
            location,
            change['type'],
            change['source'].rstrip('/'),
            change['target'].rstrip('/'),
            content,
            md5,
            bytesize,
            json.dumps(change)
        )
        self.conn.execute("INSERT INTO ajxp_changes (seq_id, location, type, source, target, content, md5,"
                          " bytesize, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", data)

    def remove(self, location, seq_id):
        self.conn.execute("DELETE FROM ajxp_changes WHERE location=? AND seq_id=?", (location, seq_id))


    def sync(self):
        self.conn.commit()