#
#  Copyright 2007-2015 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
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
from contextlib import closing

def check_structure_sqlite_file(filename):
    """Structure check of the Sqlite file based on the header content via
    Magic Header String (Every valid SQLite database file begins with these 16 bytes)
    Ref: http://www.sqlite.org/fileformat.html#database_header

    :param filename: name of sqlite file
    :type filename: str
    """
    from os.path import getsize

    if getsize(filename) < 100: # SQLite database file header is 100 bytes
        return False

    with open(filename, 'rb') as fd:
        header = fd.read(100)

    return header[:16].encode('hex') == "53514c69746520666f726d6174203300"

def check_integrity_sqlite_file(filename):
    """Integrity check of the entire database. The integrity_check pragma looks for
    out-of-order records, missing pages, malformed records, missing index entries,
    and UNIQUE and NOT NULL constraint errors.
    #Ref: http://www.sqlite.org/pragma.html#pragma_integrity_check

    :param filename: name of sqlite file
    :type filename: str
    """
    with closing(sqlite3.connect(filename)) as conn:
        with closing(conn.cursor()) as cursor:
            try:
                cursor.execute('PRAGMA integrity_check;')
                return True if cursor.fetchone()[0] == 'ok' else cursor.fetchall()
            except sqlite3.DatabaseError:
                return False

def check_sqlite_file(filename):
    from os.path import isfile
    from pydio.job.localdb import DBCorruptedException

    if not isfile(filename):
        return False

    res = check_structure_sqlite_file(filename)
    if not res:
        raise DBCorruptedException(res)
    else:
        res = check_integrity_sqlite_file(filename)
        if not res:
            raise DBCorruptedException(res)
        return True