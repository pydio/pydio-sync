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

import logging
import sys
import os
import sys
import argparse
import json
import zmq
import thread

from job.continous_merger import ContinuousDiffMerger
from job.job_config import JobConfig
from test.smoke_test import SmokeTests
from test import config_ports


def main(args=sys.argv[1:]):
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    logging.getLogger("requests").setLevel(logging.WARNING)

    parser = argparse.ArgumentParser('Pydio Synchronization Tool')
    parser.add_argument('-s', '--server', help='Server URL, with http(s) and path to pydio', type=unicode, default='http://localhost')
    parser.add_argument('-d', '--directory', help='Local directory', type=unicode, default=None)
    parser.add_argument('-w', '--workspace', help='Id or Alias of workspace to synchronize', type=unicode, default=None)
    parser.add_argument('-r', '--remote_folder', help='Path to an existing folder of the workspace to synchronize', type=unicode, default=None)
    parser.add_argument('-u', '--user', help='User name', type=unicode, default=None)
    parser.add_argument('-p', '--password', help='Password', type=unicode, default=None)
    parser.add_argument('-dir', '--direction', help='Synchro Direction', type=str, default='bi')
    parser.add_argument('-f', '--file', type=unicode, help='Json file containing jobs configurations')
    parser.add_argument('-z', '--zmq_port', type=int, help='Available port for zmq, both this port and this port +1 will be used', default=5556)
    parser.add_argument('-st', '--smoke_test', help='runs smoke tests', action='store_true', default=False)
    args, _ = parser.parse_known_args(args)
    from pathlib import Path
    jobs_root_path = Path(__file__).parent / 'data'

    if args.smoke_test:
        smoke_tests = SmokeTests(
            args.server, args.workspace, args.remote_folder, args.user)
        smoke_tests.run()
        return

    data = []
    if args.file:
        with open(args.file) as data_file:
            data = json.load(data_file, object_hook=JobConfig.object_decoder)
    if not len(data):
        job_config = JobConfig()
        job_config.load_from_cliargs(args)
        data = (job_config,)


    config_ports.create_config_file()
    context = zmq.Context()
    pub_socket = context.socket(zmq.PUB)
    port = config_ports.get_open_port("pub_socket")
    pub_socket.bind("tcp://*:%s" % port)

    try:
        controlThreads = []
        for job_config in data:
            if not job_config.active:
                continue

            job_data_path = jobs_root_path / job_config.uuid()
            if not job_data_path.exists():
                job_data_path.mkdir(parents=True)
            job_data_path = str(job_data_path)

            merger = ContinuousDiffMerger(job_config, job_data_path=job_data_path, pub_socket=pub_socket)
            try:
                merger.start()
                controlThreads.append(merger)
            except (KeyboardInterrupt, SystemExit):
                merger.stop()

        rep_socket = context.socket(zmq.REP)
        port = config_ports.get_open_port("command_socket")
        rep_socket.bind("tcp://*:%s" % port)

        watch_socket = context.socket(zmq.REP)
        port = config_ports.get_open_port("watch_socket")
        watch_socket.bind("tcp://*:%s" % port)
        def listen_to_REP():
            while True:
                message = str(rep_socket.recv())
                reply = "undefined reply"
                logging.info('Received message from REP socket ' + message)
                parts = message.split(' ', 2)
                if message.startswith('PAUSE'):
                    logging.info("SHOULD PAUSE")
                    if len(parts) > 1 and int(parts[1]) in controlThreads:
                        controlThreads[int(parts[1])].pause()
                        if not t.is_running():
                            reply = "PAUSED"
                    else:
                        for t in controlThreads:
                            t.pause()
                            if not t.is_running():
                                reply = "PAUSED"
                elif message.startswith('START'):
                    logging.info("SHOULD START")
                    if len(parts) > 1 and int(parts[1]) in controlThreads:
                        controlThreads[int(parts[1])].resume()
                        reply = "RUNNING"
                    else:
                        for t in controlThreads:
                            t.resume()
                            reply = "RUNNING"

                elif str(message).startswith('RELOAD') and len(parts) > 1 and int(parts[1]) in controlThreads:
                    # Todo: implement the reload of the config data
                    pass
                elif message == 'LIST-JOBS':
                    data = []
                    for t in controlThreads:
                        data.append(t.job_config.server + ' - ' + t.job_config.directory)
                    reply = json.dumps(data)

                try:
                    rep_socket.send(reply)
                except Exception as e:
                    logging.error(e)

        def listen_to_watcher():
            while True:
                message = str(watch_socket.recv())
                logging.info("Received ping from watcher :" + message)
                for t in controlThreads:
                    if not t.is_running():
                        reply = "PAUSED"
                    else:
                        reply = "RUNNING"
                try:
                    watch_socket.send(reply)
                except Exception as e:
                    logging.error(e)
        # Create thread as follows
        try:
            thread.start_new_thread(listen_to_REP, ())
            thread.start_new_thread(listen_to_watcher(), ())
        except Exception as e:
            logging.error(e)

    except (KeyboardInterrupt, SystemExit):
        sys.exit()

if __name__ == "__main__":
    main()
