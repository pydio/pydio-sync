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
from pydio.job.localdb import DBCorruptedException
from pydio.utils.pydio_profiler import pydio_profile


class EventLogger():

    def __init__(self, job_data_path=''):
        self.db = job_data_path + '/pydio.sqlite'
        if not os.path.exists(job_data_path):
            os.mkdir(job_data_path)
        if not os.path.exists(self.db):
            self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db)
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
        conn = sqlite3.connect(self.db)
        if uniq:
            try:
                sel = conn.execute('SELECT id FROM events WHERE type=?', (event_type, ))
                for r in sel:
                    insert = False
            except sqlite3.OperationalError as oe:
                raise DBCorruptedException(oe)

        try:
            date_time = str(datetime.datetime.now())
            if insert:
                conn.execute("INSERT INTO events('type', 'message', 'source', 'action', 'target', 'status', 'date') "
                             "VALUES (?, ?, ?, ?, ?, ?, ?)", (event_type, message, source, action, target, status, date_time))
            else:
                conn.execute("UPDATE events SET type=?, message=?, source=?, action=?, target=?, status=?, date=? "
                             " WHERE type=?", (event_type, message, source, action, target, status, date_time, event_type))

            conn.commit()
        except sqlite3.Error as e:
            logging.error('sql insert error while trying to log event : %s ' % (e.message,))
        conn.close()

    @pydio_profile
    def get_all(self, limit=10, offset=0, filter_type=None, filter_action=None):
        conn = sqlite3.connect(self.db)
        events = []
        try:
            c = conn.cursor()
            c.row_factory = sqlite3.Row
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
        except OperationalError as e:
            pass
        conn.close()
        return events

    @pydio_profile
    def consume_notification(self):
        events = self.get_all(1, 0, filter_type='notif')
        if len(events):
            conn = sqlite3.connect(self.db)
            conn.execute("DELETE FROM events WHERE type=?", ('notif',))
            conn.commit()
            conn.close()
            return events[0]
        return None

    def filter(self, filter, filter_parameter):
        logging.debug("Filtering logs on '%s' with filter '%s'" %(filter, filter_parameter))
        if filter=='type':
            return self.get_all_from_type(filter_parameter)
        elif filter=='action':
            return self.get_all_from_action(filter_parameter)
        elif filter=='status':
            return self.get_all_from_status(filter_parameter)
        else:
            return "No filter of this kind", 404

    @pydio_profile
    def get_all_from_type(self, type):
        type_list = ['local', 'remote']
        if type in type_list:
            logging.debug("type ok")
            conn = sqlite3.connect(self.db)
            c = conn.cursor()
            events = c.execute("SELECT * FROM events WHERE type = '%s' ORDER BY date DESC" % type).fetchall()
            c.close()
            return events
        else:
            return "No type of this kind", 404

    @pydio_profile
    def get_all_from_action(self, action):
        action_list = ['download', 'upload', 'move', 'mkdir', 'delete_folder', 'delete_file', 'delete']
        if action in action_list:
            conn = sqlite3.connect(self.db)
            c = conn.cursor()
            events = c.execute("SELECT * FROM events WHERE action = '%s' ORDER BY date DESC" % action).fetchall()
            c.close()
            return events
        else:
            return "No action of this kind", 404

    @pydio_profile
    def get_all_from_status(self, status):
        status_list = ['in_progress', 'done', 'undefined']
        if status in status_list:
            conn = sqlite3.connect(self.db)
            c = conn.cursor()
            events = c.execute("SELECT * FROM events WHERE status = '%s' ORDER BY date DESC" % status).fetchall()
            c.close()
            return events
        else:
            return "No status of this kind", 404