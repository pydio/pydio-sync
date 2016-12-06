#
# Copyright 2007-2016 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
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

import sqlite3
import logging
import json
import time
try:
    from pydio.utils.global_config import GlobalConfigManager
    from pydio.job.change_processor import ChangeProcessor
except:
    from utils.global_config import GlobalConfigManager
    from job.change_processor import ChangeProcessor

class ChangeHistory():
    """
    Easy log keeping of processed changes, allows for identification of failed <> success transfers
    Writing should only be done by the owner thread, reading can be done by anyone but in order to avoid db lock
    it should be done carefully.
    """
    def __init__(self, filename, local_sdk, remote_sdk, job_config, db_handler):
        """
        :param filename: the sqlite file name to store data in
        :param sdk: a remote Pydio SDK
        :param local_sdk: a local SDK
        :return:
        """
        self.filename = filename
        self.conn = sqlite3.connect(filename, timeout=60)  # TIME OUT IS USELESS CAUSE IT STILL LOCKS
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            'CREATE TABLE IF NOT EXISTS changes (row_id INTEGER PRIMARY KEY AUTOINCREMENT, seq_id INTEGER, node_path TEXT, location TEXT, '
            'type TEXT, source TEXT, target TEXT, content INTEGER, md5 TEXT, bytesize INTEGER, status TEXT, last_try INTEGER)')
        self.conn.execute("CREATE INDEX IF NOT EXISTS changes_seq_id ON changes (seq_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS changes_location ON changes (location)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS changes_type ON changes (type)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS changes_source ON changes (source)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS changes_target ON changes (target)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS changes_md5 ON changes (md5)")
        #self.conn.execute("CREATE INDEX IF NOT EXISTS changes_status ON ajxp_changes (status)") # PROBABLY NOT A GOOD IDEA
        self.cursor = self.conn.cursor()
        self.LOCKED = False
        self.remote_sdk = remote_sdk
        self.local_sdk = local_sdk
        self.job_config = job_config
        self.db_handler = db_handler

    def insert_change(self, change, status):
        logging.info(change)
        try:
            if not (change['node'] is not None and change['node']['node_path'] is not None):
                change['node'] = {'node_path': "DELETED"}
            self.cursor.execute("INSERT INTO changes (seq_id, node_path, location, type, source, target, content, md5,"
                                " bytesize, status, last_try) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                (change['row_id'], change['node']['node_path'], change['location'], change['type'],
                                 change['source'], change['target'], change['content'],
                                 change['md5'], change['bytesize'], status, int(time.time())))
        except sqlite3.OperationalError:
            logging.info("DB locked")


    def close(self):
        self.conn.close()

    def safe(self, func):
        def f(self):
            if self.LOCKED:
                return None
            else:
                self.LOCKED = True
                a = func()
                self.LOCKED = False
                return a
        return f

    def get_all(self):
        if self.LOCKED:
            yield None
        else:
            self.LOCKED = True
            conn = sqlite3.connect(self.filename, timeout=60)  # TIME OUT IS USELESS CAUSE IT STILL LOCKS
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM changes")
            i = cursor.fetchone()
            while i is not None:
                yield self.dbToJSON(i)
                i = cursor.fetchone()
            self.LOCKED = False
            conn.close()

    def get_all_failed(self, format='json'):
        if self.LOCKED:
            yield None
        else:
            self.LOCKED = True
            conn = sqlite3.connect(self.filename, timeout=60)  # TIME OUT IS USELESS CAUSE IT STILL LOCKS
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM changes WHERE status = 'FAILED'")
            i = cursor.fetchone()
            while i is not None:
                if format == 'json':
                    yield self.dbToJSON(i)
                else:
                    yield i
                i = cursor.fetchone()
            self.LOCKED = False
            conn.close()

    def get_all_success(self):
        if self.LOCKED:
            yield None
        else:
            self.LOCKED = True
            conn = sqlite3.connect(self.filename, timeout=60)  # TIME OUT IS USELESS CAUSE IT STILL LOCKS
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM changes WHERE status = 'SUCCESS'")
            i = cursor.fetchone()
            while i is not None:
                yield self.dbToJSON(i)
                i = cursor.fetchone()
            self.LOCKED = False
            conn.close()

    def dbToJSON(self, item):
        return json.dumps({'seq_id': item['seq_id'], 'location': item['location'], 'type': item['type'],
                           'source': item['source'], 'target': item['target'], 'content': item['content'],
                           'md5': item['md5'], 'bytesize': item['bytesize'], 'status': item['status']})

    """
    TODO: Worker thread to retry all failed changes
    """
    def consolidate(self):
        logging.info("Checking history for failed changes and retry.")
        for failed_change in self.get_all_failed(format='raw'):
            try:
                # convert to change processor expected dict
                node = {'node_path': failed_change['node_path'], 'md5': failed_change['md5'], 'bytesize': failed_change['bytesize'], 'last_try': failed_change['last_try']}
                change = {
                    'location': failed_change['location'],
                    'type': failed_change['type'],
                    'content': failed_change['content'],
                    'md5': failed_change['md5'],
                    'source': failed_change['source'],
                    'target': failed_change['target'],
                    'node': node
                }
                # serialize success
                logging.info("Should reprocess " + str(change))
                processor = ChangeProcessor(change, None, self.job_config, self.local_sdk, self.remote_sdk, self.db_handler, None)
                processor.process_change()
                # TODO handle output of tried change
                cursor = self.conn.cursor()
                cursor.execute("UPDATE changes SET status = ?, last_try = ? WHERE seq_id = ?", ('SUCCESS', int(time.time()), failed_change['seq_id']))
            except Exception as e:
                logging.exception(e)
        try:
            self.conn.commit()
        except Exception as e:
            logging.exception(e)
