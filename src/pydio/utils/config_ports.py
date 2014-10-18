#
# Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
# This file is part of Pydio.
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
# Get needed open ports on the system and save it to a config file that will be used to
# sync the client/UI connection ports

class PortsDetector():


    def __init__(self, zmq_port, auto_detect, store_file):
        self.zmq_port = zmq_port - 1
        self.auto_detect = auto_detect
        self.store = store_file

    def get_open_port(self, socket_name):
        if self.auto_detect:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("",0))
            s.listen(1)
            port = s.getsockname()[1]
            s.close()
        else:
            self.zmq_port += 1
            port = self.zmq_port
        self.save_config(socket_name, port)
        return port

    def create_config_file(self):
        with open(self.store, 'w') as config_file:
            config_file.write("Pydio port config file \n")


    def save_config(self, socket_name, port_to_save):
        with open(self.store, 'a') as config_file:
            config_file.write(socket_name + ':' + str(port_to_save) + "\n")