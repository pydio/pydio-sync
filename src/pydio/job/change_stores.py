#
# Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
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
import json

class AbstractChangeStore():
    def open(self):
        pass

    def close(self):
        pass

    def store(self):
        pass

    def sync(self):
        pass


class SqliteChangeStore():

    def __init__(self, filename):
        self.db = filename

    def open(self):
        self.conn = sqlite3.connect(self.db)
        cursor = self.conn.cursor()
        cursor.execute("create table changes (seq_id INTEGER PRIMARY KEY AUTOINCREMENT, path text, data text)")

    def close(self):
        self.conn.close()

    def store(self, change):
        key = change['source'] if change['source'] != 'NULL' else change['target']
        self.conn.execute("INSERT INTO changes ('seq_id', 'path', 'data') VALUES (?, ?, ?)",
                          (change['seq'], key, json.dumps(change)))
        #self.conn.commit()

    def sync(self):
        self.conn.commit()