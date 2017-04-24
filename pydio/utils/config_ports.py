#
# Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
# This file is part of Pydio.
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
# Get needed open ports on the system and save it to a config file that will be used to
# sync the client/UI connection ports
import random, string

def random_string(n=16):
    charspace = string.ascii_letters + string.digits
    return ''.join([random.choice(charspace) for n in xrange(n)])

class PortsDetector(object):
    def __init__(self, store_file, username=None, password=None, default_port=5556):
        self.store = store_file
        self.default_port = default_port
        if username:
            self._username = username
        else:
            self._username = random_string()
        if password:
            self._password = password
        else:
            self._password = random_string()

    @property
    def port(self):
        if self._default_port_ok():
            self.save_config(self.default_port)
            return self.default_port
        else:
            port = self.get_open_port()
            self.save_config(port)
            return port

    @property
    def username(self):
        return self._username

    @property
    def password(self):
        return self._password

    def _default_port_ok(self):
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.1)
        result = sock.connect_ex(('127.0.0.1', self.default_port))
        if result == 0:
            return False
        return True

    def get_open_port(self):
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("",0))
        s.listen(1)
        port = s.getsockname()[1]
        s.close()
        return port

    def create_config_file(self):
        with open(self.store, 'w') as config_file:
            config_file.write("Pydio port config file \n")

    def save_config(self, port_to_save):
        with open(self.store, 'a') as config_file:
            line = "pydio:{p}:{usr}:{pwd}\n".format(
                p=port_to_save, usr=self.username, pwd=self.password
            )
            config_file.write(line)
