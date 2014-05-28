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
from pydio.job import run_loop
import zmq
import logging
import time
from pydispatch import dispatcher
from pydio import COMMAND_SIGNAL, PROGRESS_SIGNAL, PUBLISH_SIGNAL

class ZmqBus():

    def __init__(self, ports_detector):
        self.ports_detector = ports_detector


    def open(self):
        context = zmq.Context()

        self.rep_socket = context.socket(zmq.REP)
        port = self.ports_detector.get_open_port("command_socket")
        self.rep_socket.bind("tcp://*:%s" % port)

        self.pub_socket = context.socket(zmq.PUB)
        port = self.ports_detector.get_open_port("pub_socket")
        self.pub_socket.bind("tcp://*:%s" % port)

        dispatcher.connect(self.publish_signal, signal=PUBLISH_SIGNAL, sender=dispatcher.Any)


    def set_control_threads(self, control_threads):
        self.control_threads = control_threads


    def publish_signal(self, channel, message):
        self.pub_socket.send_string(channel+'/'+message)

    @run_loop
    def listen_to_REP(self):
        message = str(self.rep_socket.recv())
        reply = "undefined reply"
        logging.info('Received message from REP socket ' + message)
        parts = message.split(' ', 2)
        if message.startswith('PAUSE'):
            logging.info("SHOULD PAUSE")
            if len(parts) > 1 and int(parts[1]) in self.control_threads:
                self.control_threads[int(parts[1])].pause()
                if not t.is_running():
                    reply = "PAUSED"
            else:
                for t in self.control_threads:
                    t.pause()
                    if not t.is_running():
                        reply = "PAUSED"
        elif message.startswith('START'):
            logging.info("SHOULD START")
            if len(parts) > 1 and int(parts[1]) in self.control_threads:
                self.control_threads[int(parts[1])].resume()
                reply = "RUNNING"
            else:
                for t in self.control_threads:
                    t.resume()
                    reply = "RUNNING"

        elif str(message).startswith('RELOAD') and len(parts) > 1 and int(parts[1]) in self.control_threads:
            # Todo: implement the reload of the config data
            pass
        elif message == 'LIST-JOBS':
            data = []
            for t in self.control_threads:
                data.append(t.job_config.server + ' - ' + t.job_config.directory)
            reply = json.dumps(data)

        try:
            self.rep_socket.send(reply)
        except Exception as e:
            logging.error(e)


    @run_loop
    def pinger(self):
        logging.info("Send ping to UI...")
        try:
            self.pub_socket.send_string("ping/")
        except Exception as e:
            logging.error(e)
        time.sleep(10)


