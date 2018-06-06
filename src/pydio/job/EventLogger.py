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
import os
import sys
from pathlib import *
import datetime
import logging
import time
try:
    from pydio.job.localdb import DBCorruptedException, ClosingCursor
    from pydio.utils.pydio_profiler import pydio_profile
    from pydio.utils.global_config import GlobalConfigManager
except ImportError:
    from job.localdb import DBCorruptedException, ClosingCursor
    from utils.pydio_profiler import pydio_profile
    from utils.global_config import GlobalConfigManager


class EventLogger():

    def __init__(self, job_data_path=''):
        self.db = job_data_path + '/pydio.sqlite'
        if not os.path.exists(job_data_path):
            os.mkdir(job_data_path)
        # Fetch the local db access timeout
        global_config_manager = GlobalConfigManager.Instance(configs_path=job_data_path)
        self.timeout = global_config_manager.get_general_config()['max_wait_time_for_local_db_access']
        if not os.path.exists(self.db):
            self.init_db()

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

    def log_state(self, message, status):
        self.log('sync', message, 'loop', status, uniq=True)

    def log_notif(self, message, status):
        self.log('notif', message, 'loop', status, uniq=True)

    @pydio_profile
    def log(self, event_type, message, action, status, source='', target='', uniq=False):
        insert = True
        conn = sqlite3.connect(self.db, timeout=self.timeout)
        if uniq:
            try:
                sel = conn.execute('SELECT id FROM events WHERE type=?', (event_type, ))
                for r in sel:
                    insert = False
            except sqlite3.OperationalError as oe:
                conn.close()
                raise DBCorruptedException(oe)

        try:
            date_time = str(datetime.datetime.now())
            if insert:
                conn.execute("INSERT INTO events('type', 'message', 'source', 'action', 'target', 'status', 'date') "
                             "VALUES (?, ?, ?, ?, ?, ?, ?)", (event_type, message, source, action, target, status, date_time))
            else:
                conn.execute("UPDATE events SET message=?, source=?, action=?, target=?, status=?, date=? "
                             " WHERE type=?", (message, source, action, target, status, date_time, event_type))

            conn.commit()
        except sqlite3.OperationalError as e:
            logging.error('sql insert error while trying to log event : %s ' % (e.message,))
            conn.close()
            time.sleep(.05)
            self.log(event_type, message, action, status, source, target, uniq)
        conn.close()

    @pydio_profile
    def get_all(self, limit=10, offset=0, filter_type=None, filter_action=None):
        events = []
        with ClosingCursor(self.db, timeout=self.timeout) as c:
            if filter_type:
                res = c.execute("SELECT * FROM events WHERE type=? ORDER BY date DESC LIMIT ?,?", (filter_type, offset, limit))
            elif filter_action:
                res = c.execute("SELECT * FROM events WHERE action=? ORDER BY date DESC LIMIT ?,?", (filter_action, offset, limit))
            else:
                res = c.execute("SELECT * FROM events WHERE type!=? ORDER BY date DESC LIMIT ?,?", ('notif', offset, limit))

            for event in res:
                events.append({
                    'id': event['id'],
                    'type': event['type'],
                    'message': event['message'],
                    'source': event['source'],
                    'action': event['action'],
                    'target': event['target'],
                    'status': event['status'],
                    'date': event['date']
                })
        return events

    @pydio_profile
    def consume_notification(self):
        events = self.get_all(1, 0, filter_type='notif')
        if len(events):
            with ClosingCursor(self.db, timeout=self.timeout, write=True, withCommit=True) as conn:
                conn.execute("DELETE FROM events WHERE type=?", ('notif',))
            return events[0]
        return None

    def filter(self, filter, filter_parameter):
        logging.debug("Filtering logs on '%s' with filter '%s'" %(filter, filter_parameter))
        if filter == 'type':
            return self.get_all_from_type(filter_parameter)
        elif filter == 'action':
            return self.get_all_from_action(filter_parameter)
        elif filter == 'status':
            return self.get_all_from_status(filter_parameter)
        else:
            return "No filter of this kind", 404

    @pydio_profile
    def get_all_from_type(self, type):
        with ClosingCursor(self.db, timeout=self.timeout) as c:
            type_list = ['local', 'remote']
            if type in type_list:
                return c.execute("SELECT * FROM events WHERE type = '%s' ORDER BY date DESC" % type).fetchall()
            else:
                return "No type of this kind", 404

    @pydio_profile
    def get_all_from_action(self, action):
        action_list = ['download', 'upload', 'move', 'mkdir', 'delete_folder', 'delete_file', 'delete']
        if action in action_list:
            with ClosingCursor(self.db, timeout=self.timeout) as c:
                return c.execute("SELECT * FROM events WHERE action = '%s' ORDER BY date DESC" % action).fetchall()
        else:
            return "No action of this kind", 404

    @pydio_profile
    def get_all_from_status(self, status):
        status_list = ['in_progress', 'done', 'undefined']
        if status in status_list:
            with ClosingCursor(self.db, timeout=self.timeout) as c:
                return c.execute("SELECT * FROM events WHERE status = '%s' ORDER BY date DESC" % status).fetchall()
        else:
            return "No status of this kind", 404

    @pydio_profile
    def get_last_action(self):
        """
        :return: [last row from events]
        """
        res = []
        with ClosingCursor(self.db, timeout=self.timeout) as c:
            return c.execute("SELECT * FROM events ORDER BY id DESC LIMIT 1").fetchall()