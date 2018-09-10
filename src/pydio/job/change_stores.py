#
# Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
# This file is part of Pydio.
#
# Pydio is free software: you can redistribute it and/or modify
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

import json
import logging
import fnmatch
import math
import ntpath
import os
import sqlite3
import time

try:
    from pydio.job.change_utils import flatten
    from pydio.sdkremote.pydio_exceptions import InterruptException
    from pydio.utils.pydio_profiler import pydio_profile
    from pydio.utils.global_config import GlobalConfigManager
except ImportError:
    from job.change_utils import flatten
    from sdkremote.pydio_exceptions import InterruptException
    from utils.pydio_profiler import pydio_profile
    from utils.global_config import GlobalConfigManager
from threading import Thread

try:
    import resource
    import humanize
except ImportError:
    pass


class SqliteChangeStore():
    conn = None
    DEBUG = False

    def __init__(self, filename, includes, excludes, poolsize=4, local_sdk=None, remote_sdk=None, job_config=None,
                 db_handler=None):
        self.db = filename
        self.includes = includes
        self.excludes = excludes
        self.create = False
        global_config_manager = GlobalConfigManager.Instance(configs_path=os.path.dirname(os.path.dirname(filename)))
        # Increasing the timeout (default 5 seconds), to avoid database is locked error
        self.timeout = global_config_manager.get_general_config()['max_wait_time_for_local_db_access']
        if not os.path.exists(self.db):
            self.create = True
        self.last_commit = time.time()
        self.local_sdk = local_sdk
        self.remote_sdk = remote_sdk
        self.pendingoperations = []
        self.job_config = job_config

    def open(self):
        try:
            self.conn = sqlite3.connect(self.db, timeout=self.timeout)
            self.conn.row_factory = sqlite3.Row
            if self.create:
                self.conn.execute(
                    'CREATE TABLE ajxp_changes (row_id INTEGER PRIMARY KEY AUTOINCREMENT , seq_id, location TEXT, '
                    'type TEXT, source TEXT, target TEXT, content INTEGER, md5 TEXT, bytesize INTEGER, data TEXT)')
                self.conn.execute(
                    "CREATE TABLE ajxp_last_buffer ( id INTEGER PRIMARY KEY AUTOINCREMENT, location TEXT, type TEXT, "
                    "source TEXT, target TEXT, bytesize INTEGER, md5 TEXT)")
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
                try:
                    c = self.conn.cursor()
                    c.execute("SELECT md5, bytesize FROM ajxp_last_buffer")
                    c.close()
                except:
                    self.conn.execute("ALTER TABLE ajxp_last_buffer ADD COLUMN bytesize INTEGER")
                    self.conn.execute("ALTER TABLE ajxp_last_buffer ADD COLUMN md5 TEXT")
                    self.conn.commit()

                self.conn.execute("vacuum")
            self.conn.commit()
        except sqlite3.OperationalError as oe:
            # Catch Database locked errors and try again
            logging.exception(oe)
            time.sleep(.5)
            self.open()

    def __len__(self):
        return self.get_row_count()

    @pydio_profile
    def get_row_count(self, location='all'):
        if location == 'all':
            res = self.conn.execute("SELECT count(row_id) FROM ajxp_changes")
        else:
            res = self.conn.execute("SELECT count(row_id) FROM ajxp_changes WHERE location=?", (location,))
        count = res.fetchone()
        if self.DEBUG:
            logging.info("Changes store count #" + str(count[0]))
        return count[0]

    @pydio_profile
    def process_changes_with_callback(self, callback):
        c = self.conn.cursor()

        res = c.execute('SELECT * FROM ajxp_changes WHERE md5="directory" AND location="local" '
                        'AND type="create" ORDER BY source,target')

        mkdirs = []
        ids = []
        for row in res:
            r = self.sqlite_row_to_dict(row, load_node=False)
            ids.append(str(r['row_id']))
            mkdirs.append(r['target'])
        splitsize = 10
        for i in range(0, int(math.ceil(float(len(mkdirs)) / float(splitsize)))):
            callback({'type': 'bulk_mkdirs', 'location': 'local', 'pathes': mkdirs[i * splitsize:(i + 1) * splitsize]})
            ids_list = str(','.join(ids[i * splitsize:(i + 1) * splitsize]))
            self.conn.execute('DELETE FROM ajxp_changes WHERE row_id IN (' + ids_list + ')')
        self.conn.commit()

        res = c.execute('SELECT * FROM ajxp_changes WHERE md5="directory" ORDER BY source,target')
        for row in res:
            try:
                output = callback(self.sqlite_row_to_dict(row, load_node=True))
                if output:
                    self.conn.execute('DELETE FROM ajxp_changes WHERE row_id=?', (row['row_id'],))
            except InterruptException as e:
                break
        self.conn.commit()

        # now go to the rest
        res = c.execute('SELECT * FROM ajxp_changes ORDER BY seq_id ASC')
        rows_to_process = []
        try:
            for row in res:
                rows_to_process.append(self.sqlite_row_to_dict(row, load_node=True))
        except Exception as e:
            logging.exception(e)
            logging.info("Failed to decode " + str(row))
            raise SystemExit

        for r in rows_to_process:
            try:
                logging.debug('PROCESSING CHANGE WITH ROW ID %i' % r['row_id'])
                already_processed = False

                location = 'remote' if r['location'] == 'local' else 'local'
                if (r['type'] == 'content' or r['type'] == 'create') and r['md5'] != 'directory' :
                    search_result = self.conn.execute("SELECT * FROM ajxp_last_buffer WHERE location=? AND "
                                              "(type='create' OR type='content') AND target=? AND "
                                              "bytesize=? AND md5=? LIMIT 1",
                                              (location, r['target'], r['bytesize'], r['md5']))

                    for row in search_result:
                        already_processed = True
                        break
                    search_result.close()

                    if already_processed:
                        self.conn.execute('DELETE FROM ajxp_changes WHERE row_id=?', (r['row_id'],))
                        continue

                output = callback(r)
                if output:
                    self.conn.execute('DELETE FROM ajxp_changes WHERE row_id=?', (r['row_id'],))
            except InterruptException as e:
                break

    @pydio_profile
    def list_changes(self, cursor=0, limit=5, where=''):
        c = self.conn.cursor()
        sql = 'SELECT * FROM ajxp_changes ORDER BY seq_id LIMIT ?,?'
        if where:
            sql = 'SELECT * FROM ajxp_changes WHERE ' + where + ' ORDER BY seq_id LIMIT ?,?'
        res = c.execute(sql, (cursor, limit))
        changes = []
        for row in res:
            changes.append(self.sqlite_row_to_dict(row, load_node=True))
        if (self.DEBUG):
            self.debug("")
        return changes

    @pydio_profile
    def sum_sizes(self, where=''):
        c = self.conn.cursor()
        sql = 'SELECT SUM(bytesize) as total FROM ajxp_changes'
        if where:
            sql = 'SELECT SUM(bytesize) as total FROM ajxp_changes WHERE ' + where
        res = c.execute(sql)
        total = 0.0
        for row in res:
            if row['total']:
                total = float(row['total'])
        if (self.DEBUG):
            logging.info("Total size of changes:" + str(total) + " bytes")
        return total

    def commonprefix(self, path_list):
        return os.path.commonprefix(path_list).rpartition('/')[0]

    @pydio_profile
    def find_modified_parents(self):
        sql = 'SELECT * FROM ajxp_changes t1 ' \
              '     WHERE type="create" ORDER BY target ASC'
        c = self.conn.cursor()
        res = c.execute(sql)
        parents = []
        common_parents = []
        for row in res:
            r = self.sqlite_row_to_dict(row)
            dir_path = os.path.dirname(row['target'])
            parent_found = False
            for stored in parents:
                common_pref = self.commonprefix([stored + '/', dir_path + '/'])
                if common_pref != '/':
                    parents.remove(stored)
                    parents.append(common_pref)
                    parent_found = True
                    break
            if not parent_found:
                parents.append(dir_path)

        # common_parents.append(self.commonprefix(parents))
        self.conn.commit()
        if (self.DEBUG):
            logging.info("Modified parents after the prevous operation:")
            for parent in parents:
                logging.info(parent)
        return parents

    @pydio_profile
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
                                    (row['location'], row['type'], row['source'].replace("\\", "/") + "/%"))
        self.conn.commit()
        logging.debug('[change store] Pruning %i rows', res.rowcount)
        if (self.DEBUG):
            self.debug("Pruning folder moves")

    @pydio_profile
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

        if (self.DEBUG):
            self.debug("Removing duplicated changes (both sides)")

    @pydio_profile
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
        if (self.DEBUG):
            self.debug("Detecting and removing echoes")

    @pydio_profile
    def delete_copies(self):
        sql = 'DELETE from ajxp_changes WHERE row_id NOT IN (SELECT max(row_id) from ajxp_changes GROUP BY location, type, source, target, content, md5, bytesize having COUNT(*) > 0 ORDER BY row_id)'
        cursor = self.conn.cursor()
        res = cursor.execute(sql)
        self.conn.commit()
        logging.debug('[change store] Echo : pruned %i rows', res.rowcount)
        if (self.DEBUG):
            self.debug("Detecting and removing copies")

    @pydio_profile
    def detect_win_moves(self):
        sql = "SELECT c2.source, c1.target, c1.md5 FROM (SELECT * FROM `ajxp_changes` WHERE `type`='create') as c1, (SELECT * FROM `ajxp_changes` WHERE `type`='delete') as c2 WHERE c1.`md5`=c2.`md5` AND c1.`location`=c2.`location`;"
        moves = []
        cursor = self.conn.cursor()
        res = cursor.execute(sql)

        for row in res:
            d = dict(row)
            if "c2.source" not in d or "c1.target" not in d:
                continue

            source = d["c2.source"]
            target = d["c1.target"]
            hash = d["c1.md5"]

            source_name = ntpath.basename(source)
            target_name = ntpath.basename(target)
            if source_name == target_name:
                moves.append((source, target, hash, source_name, target_name))
        cursor.close()

        for (s, t, h, sn, tn) in moves:
            self.conn.execute("DELETE FROM `ajxp_changes` WHERE type='delete' AND md5=? AND `source` LIKE ?",
                              (h, "%/" + sn))
            self.conn.execute(
                "UPDATE `ajxp_changes` SET `source`=?, `type`='path' WHERE type='create' AND md5=? AND `target` LIKE ?",
                (s, h, "%/" + tn))
        self.conn.commit()

    @pydio_profile
    def clean_echoes(self):
        sql = "SELECT * FROM `ajxp_changes`;"
        cursor = self.conn.cursor()
        res = cursor.execute(sql)
        changes = []
        for row in res:
            d = dict(row)
            changes.append(d)
        cursor.close()

        for c in changes:
            if self.echo_match(c["location"], c):
                self.conn.execute("DELETE FROM `ajxp_changes` WHERE location=? AND type=? AND source=? AND target=?",
                                  (c["location"], c["type"], c["source"], c["target"]))
        self.conn.commit()

    @pydio_profile
    def detect_unnecessary_changes(self):
        local = self.get_row_count('local')
        rem = self.get_row_count('remote')
        logging.debug("[detect unnecessary] LOCAL CHANGES: " + str(local) + " REMOTE CHANGES " + str(rem))
        bulk_size = 400
        ids_to_delete = []
        for i in range(0, int(math.ceil(float(local) / float(bulk_size)))):
            ids_to_delete = ids_to_delete + self.filter_w_stat('local', self.local_sdk, self.remote_sdk, i * bulk_size,
                                                               bulk_size)
        for j in range(0, int(math.ceil(float(rem) / float(bulk_size)))):
            ids_to_delete = ids_to_delete + self.filter_w_stat('remote', self.remote_sdk, self.local_sdk, j * bulk_size,
                                                               bulk_size)

        res = self.conn.execute('DELETE FROM ajxp_changes WHERE row_id IN (' + str(','.join(ids_to_delete)) + ')')
        logging.debug('[change store] Filtering unnecessary changes : pruned %i rows', res.rowcount)
        self.conn.commit()
        if (self.DEBUG):
            self.debug("Detecting unnecessary changes")

    @pydio_profile
    def filter_w_stat(self, location, sdk, opposite_sdk, offset=0, limit=1000):
        # Load 'limit' changes and filter them
        c = self.conn.cursor()
        res = c.execute('SELECT * FROM ajxp_changes WHERE location=? ORDER BY source,target LIMIT ?,?',
                        (location, offset, limit))
        changes = []
        for row in res:
            changes.append(self.sqlite_row_to_dict(row))

        test_stats = []
        for c in changes:
            if c['source'] != 'NULL': test_stats.append(c['source'])
            if c['target'] != 'NULL': test_stats.append(c['target'])
        test_stats = list(set(test_stats))
        opposite_stats = None
        local_stats = None
        # bulk_stat formatting problem >> recursion
        if len(test_stats):
            local_stats = sdk.bulk_stat(test_stats, with_hash=True)
            opposite_stats = opposite_sdk.bulk_stat(test_stats, with_hash=True)
        to_remove = filter(lambda it: self.filter_change(it, local_stats, opposite_stats), changes)
        return map(lambda row: str(row['row_id']), to_remove)

    @pydio_profile
    def clean_and_detect_conflicts(self, status_handler):

        # transform solved conflicts into process operation
        def handle_solved(node):
            if node['status'] == 'SOLVED:KEEPREMOTE':
                # remove local operation
                self.conn.execute('DELETE from ajxp_changes WHERE location=? AND target=?',
                                  ('local', node['node_path'].replace('\\', '/')))
            elif node['status'] == 'SOLVED:KEEPLOCAL':
                # remove remote operation
                self.conn.execute('DELETE from ajxp_changes WHERE location=? AND target=?',
                                  ('remote', node['node_path'].replace('\\', '/')))
            elif node['status'] == 'SOLVED:KEEPBOTH':
                # logging.info("[DEBUG] work in progress -- keepboth " + node['node_path'])
                # remove conflict from table, effect: FILES out of sync,
                # self.conn.execute('DELETE from ajxp_changes WHERE location=? AND target=?', ('remote', node['node_path'].replace('\\', '/')))
                self.local_sdk.duplicateWith(node['node_path'], self.job_config.user_id)
                self.conn.execute('DELETE from ajxp_changes WHERE location=? AND target=?',
                                  ('local', node['node_path'].replace('\\', '/')))

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
                try:
                    status_handler.update_node_status(path, 'CONFLICT', self.sqlite_row_to_dict(row, load_node=True))
                except Exception as e:
                    logging.exception(e)
                    logging.info("Problem with " + path)

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

    @pydio_profile
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

            # If it does not exist on the original side, there might be an indexing problem,
            # Do we ignore it?
            # if my_stat and not item['target'] in my_stat:
            #    return True

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
        else:  # MOVE
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

    def buffer_real_operation(self, location, type, source, target, bytesize=0, md5=""):
        location = 'remote' if location == 'local' else 'local'
        try:
            self.conn.execute(
                "INSERT INTO ajxp_last_buffer (type,location,source,target,bytesize,md5) VALUES (?,?,?,?, ?, ?)",
                (type, location, source.replace("\\", "/"), target.replace("\\", "/"), bytesize, md5))
            self.conn.commit()
        except sqlite3.ProgrammingError:
            self.threaded_buffer_real_operation(type, location, source, target)

    def buffer_real_operation_from_change(self, change):
        change['location'] = 'remote' if change['location'] == 'local' else 'local'
        location = change['location']
        source = change['source']
        target = change['target']
        bytesize = int(change['bytesize'])
        md5 = change['md5']

        try:
            self.conn.execute(
                "INSERT INTO ajxp_last_buffer (type,location,source,target,bytesize,md5) VALUES (?,?,?,?, ?, ?)",
                (type, location, source.replace("\\", "/"), target.replace("\\", "/")), bytesize, md5)
            self.conn.commit()
        except sqlite3.ProgrammingError:
            self.threaded_buffer_real_operation(type, location, source, target)

    def bulk_buffer_real_operation(self, bulk):
        if bulk:
            for operation in bulk:
                location = operation['location']
                location = 'remote' if location == 'local' else 'local'
                self.conn.execute("INSERT INTO ajxp_last_buffer (type,location,source,target) VALUES (?,?,?,?)", (
                    operation['type'], location, operation['source'].replace("\\", "/"),
                    operation['target'].replace("\\", "/")))
            self.conn.commit()

    class operation():
        pass

    def threaded_buffer_real_operation(self, type, location, source, target):
        op = self.operation()
        op.type = type
        op.location = location
        op.source = source
        op.target = target
        self.pendingoperations.append(op)

    def process_pending_changes(self):
        """ Updates the buffer with the operations treated
        """
        # TODO lock
        # logging.info("Processing pending changes (" + str(len(self.pendingoperations)) + ")")
        while len(self.pendingoperations) > 0:
            op = self.pendingoperations.pop()
            # self.buffer_real_operation(op.location, op.type, op.source, op.target)
            self.conn.execute("INSERT INTO ajxp_last_buffer (type,location,source,target) VALUES (?,?,?,?)",
                              (op.type, op.location, op.source.replace("\\", "/"), op.target.replace("\\", "/")))
        self.conn.commit()

    def clear_operations_buffer(self):
        """nbrows = 0
        for r in self.conn.execute('SELECT * FROM ajxp_last_buffer'):
            txt = u""
            for c in r:
                if type(c) == unicode:
                    txt += c
                else:
                    txt += str(c)
                txt += "|"
            logging.info(txt)
            nbrows += 1
        logging.info("$$ About to clear %d rows of ajxp_last_buffer", nbrows)"""
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
        except KeyError as ke:
            pass
        try:
            import platform, unicodedata
            if platform.system() == "Darwin" and stats:
                return stats[unicodedata.normalize('NFC', unicode(path))]
        except KeyError as ke:
            logging.exception(ke)

        if location == 'remote':
            return self.remote_sdk.stat(path, with_hash)
        else:
            return self.local_sdk.stat(path, with_hash=True)

    @pydio_profile
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
        if self.conn is not None:
            self.conn.close()
            self.conn = None
            logging.debug("Change Store closed")

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

    @pydio_profile
    def store(self, location, seq_id, change):
        # if location == 'local':
        #    print change['type'], " : ", change['source'], " => ", change['target']
        if change is None:
            return

        if self.filter_path(change['source']) or self.filter_path(change['target']):
            return

        if change.has_key('node') and change['node'].has_key('md5'):
            md5 = change['node']['md5']
        elif change.has_key('node') and change["node"] is not None and change['node'].has_key('deleted_md5'):
            md5 = change['node']['deleted_md5']
        else:
            md5 = ''
        if change.has_key('node') and change['node'].has_key('bytesize'):
            bytesize = change['node']['bytesize']
        elif change.has_key('node') and change['node'].has_key('bytesize') == 0:
            # Fixing the bug: Instead of assigning the bytesize of the empty file to null, it should be set to zero, it
            # prevents from the errors on file size comparison.
            bytesize = 0
        else:
            bytesize = ''

        content = 0
        if md5 != 'directory' and (change['type'] == 'content' or change['type'] == 'create'):
            content = 1
        data = (
            seq_id,
            location,
            change['type'],
            change['source'].replace("\\", "/").rstrip('/'),
            change['target'].replace("\\", "/").rstrip('/'),
            content,
            md5,
            bytesize,
            json.dumps(change)
        )
        self.conn.execute("INSERT INTO ajxp_changes (seq_id, location, type, source, target, content, md5,"
                          " bytesize, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", data)

    def remove(self, location, seq_id):
        self.conn.execute("DELETE FROM ajxp_changes WHERE location=? AND seq_id=?", (location, seq_id))

    def remove_based_on_location(self, location):
        self.conn.execute("DELETE FROM ajxp_changes WHERE location=?", (location,))
        self.conn.commit()

    # showing the changes store state
    def debug(self, after=""):
        logging.info(2 * "\n" + 15 * "#")
        logging.info("changes store after : " + after)
        res = self.conn.execute("SELECT * FROM ajxp_changes")
        for row in res:
            logging.info(
                "\t" + row['location'] + "\t|\tsource =>" + row["source"] + "\t " + "target =>" + row['target'])
        logging.info("\n" + 15 * "#" + 2 * "\n")

    def sync(self):
        self.conn.commit()

    @pydio_profile
    def echo_match(self, location, change):
        # if location == 'remote':
        #    pass

        source = change['source'].replace("\\", "/")
        target = change['target'].replace("\\", "/")
        action = change['type']
        for row in self.conn.execute(
                "SELECT id FROM ajxp_last_buffer WHERE type=? AND location=? AND source=? AND target=?",
                (action, location, source, target)):
            logging.info('MATCHING ECHO FOR RECORD %s - %s - %s - %s' % (location, action, source, target,))
            # Now delete it - it should not be matched twice
            self.conn.execute("DELETE FROM ajxp_last_buffer WHERE id=?", (row[0],))
            return True
        return False

    @pydio_profile
    def flatten_and_store(self, location, row, last_info=None):
        first, second = flatten(location, row, last_info)
        if first:
            self.store(location, first['seq'], first)
        if second:
            self.store(location, second['seq'], second)

    @pydio_profile
    def update_pending_status(self, status_handler, local_seq):
        res = self.conn.execute('SELECT seq_id FROM ajxp_changes WHERE seq_id >' + str(local_seq) + ' ORDER BY seq_id')
        list_seq_ids = [str(row[0]) for row in res]
        status_handler.update_bulk_node_status_as_pending(list_seq_ids)
