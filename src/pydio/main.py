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

import keyring
import slugify
import json
import zmq
import thread

logging.basicConfig(format='%(asctime)s %(message)s')
logging.getLogger().setLevel(logging.DEBUG)
logging.disable(logging.NOTSET)

logging.debug("sys.path")  # = %s", repr(sys.path))
for s in sys.path:
    logging.info("\t%s" % s)
logging.debug("PYTHONPATH")  # = %s", repr(sys.path))
for s in os.environ.get('PYTHONPATH', "").split(';'):
    logging.info("\t%s" % s)

from job.continous_merger import ContinuousDiffMerger
from job.local_watcher import LocalWatcher


def main(args=sys.argv[1:]):
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    logging.getLogger("requests").setLevel(logging.WARNING)

    logging.debug("args: %s" % args)

    parser = argparse.ArgumentParser('Pydio Synchronization Tool')
    parser.add_argument('-s', '--server', help='Server URL, with http(s) and path to pydio', type=unicode, default='http://localhost')
    parser.add_argument('-d', '--directory', help='Local directory', type=unicode, default=None)
    parser.add_argument('-w', '--workspace', help='Id or Alias of workspace to synchronize', type=unicode, default=None)
    parser.add_argument('-r', '--remote_folder', help='Path to an existing folder of the workspace to synchronize', type=unicode, default=None)
    parser.add_argument('-u', '--user', help='User name', type=unicode, default=None)
    parser.add_argument('-p', '--password', help='Password', type=unicode, default=None)
    parser.add_argument('-f', '--file', type=unicode)
    args, _ = parser.parse_known_args(args)

    data = []
    if args.file:
        with open(args.file) as data_file:
            data = json.load(data_file)
    if not len(data):
        data = (vars(args),)

    context = zmq.Context()
    pub_socket = context.socket(zmq.PUB)
    pub_socket.bind("tcp://*:%s" % 5556)

    try:
        controlThreads = []
        for job_param in data:
            if 'inactive' in job_param and job_param['inactive']:
                continue
            if job_param['password']:
                keyring.set_password(job_param['server'], job_param['user'], job_param['password'])

            from pathlib import Path
            job_data_path = Path(__file__).parent / 'data' / str(slugify.slugify(job_param['server']) + '-' + slugify.slugify(job_param['workspace']))
            # TODO
            # Add more parameter to the slug, or create subfolders: remote_folder, username must be taken into account.
            if not job_data_path.exists():
                job_data_path.mkdir(parents=True)
            job_data_path = str(job_data_path)

            remote_folder = ''
            if job_param['remote_folder']:
                remote_folder = job_param['remote_folder'].rstrip('/')

            directory = Path(str(job_param['directory'])).resolve()
            if not directory.exists():
                directory.mkdir(parents=True)
            directory = str(directory)

            logging.info("Sync directory: %s", directory)

            watcher = LocalWatcher(directory, includes=['*'], excludes=['.*','recycle_bin'], data_path=job_data_path)
            merger = ContinuousDiffMerger(local_path=directory, remote_ws=job_param['workspace'],
                                          sdk_url=job_param['server'], job_data_path=job_data_path,
                                          remote_folder=remote_folder, sdk_user_id=job_param['user'],
                                          pub_socket=pub_socket)
            try:
                watcher.start()
                merger.start()
                controlThreads.append(merger)
            except (KeyboardInterrupt, SystemExit):
                merger.stop()
                watcher.stop()

        rep_socket = context.socket(zmq.REP)
        rep_socket.bind("tcp://*:%s" % 5557)
        def listen_to_REP():
            while True:
                message = rep_socket.recv()
                logging.info('Received message from REP socket ' + message)
                if message == 'PAUSE':
                    logging.info("SHOULD PAUSE")
                    for t in controlThreads:
                        t.pause()
                elif message == 'START':
                    logging.info("SHOULD START")
                    for t in controlThreads:
                        t.resume()
                try:
                    msg = 'status updated'
                    rep_socket.send(msg)
                except Exception as e:
                    logging.error(e)

        # Create thread as follows
        try:
           thread.start_new_thread( listen_to_REP, () )
        except Exception as e:
           logging.error(e)

    except (KeyboardInterrupt, SystemExit):
        sys.exit()

if __name__ == "__main__":
    main()
