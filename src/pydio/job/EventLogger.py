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
import datetime
import logging


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
        cursor.execute("create table events (id INTEGER PRIMARY KEY AUTOINCREMENT, type text, message text, source text,"
                       "target text, action text, status text, date text)")
        conn.close()

    def log_state(self, message, status):
        self.log('sync', message, 'loop', status)

    def log(self, type, message, action, status, source='', target=''):
        try:
            date_time = str(datetime.datetime.now())
            conn = sqlite3.connect(self.db)
            conn.execute("INSERT INTO events('type', 'message', 'source', 'action', 'target', 'status', 'date') "
                         "VALUES (?, ?, ?, ?, ?, ?, ?)", (type, message, source, action, target, status, date_time))
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            print 'sql insert error : ', e.args[0]

    def get_all(self, limit=-1, offset=0):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        if limit > 0:
            c.execute("SELECT * FROM events ORDER BY date DESC LIMIT ?,?", (offset, limit))
        else:
            c.execute("SELECT * FROM events ORDER BY date DESC")
        events = c.fetchall()
        c.close()
        return events

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