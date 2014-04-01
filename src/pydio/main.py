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

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logging.getLogger().setLevel(logging.DEBUG)
logging.disable(logging.NOTSET)
logging.getLogger("requests").setLevel(logging.WARNING)

logging.debug("sys.path: %s", "\n\t".join(sys.path))
logging.debug("PYTHONPATH: %s", "\n\t".join(os.environ.get('PYTHONPATH', "").split(';')))

# Most imports are placed after we have logged import path
# so we can easily debug import problems

import argparse
import json
import thread
from pathlib import Path
import zmq

if __name__ == "__main__":
    pydio_module = os.path.dirname(os.path.abspath(__file__))
    logging.debug("sys.platform: %s" % sys.platform)
    if sys.platform == "win32":
        pydio_module = pydio_module.replace("/", "\\")
    logging.debug("pydio_module: %s" % pydio_module)
    if pydio_module in sys.path:
        # if this module was run directly it will mess up imports
        # we need to correct sys.path
        logging.debug("Removing from sys.path: %s" % pydio_module)
        sys.path.remove(pydio_module)
        logging.debug("Prepending to sys.path: %s" % os.path.dirname(pydio_module))
        sys.path.insert(0, os.path.dirname(pydio_module))

from pydio.job.continous_merger import ContinuousDiffMerger
from pydio.job.job_config import JobConfig

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".pydio.json")


def main(argv=sys.argv[1:]):

    setup_logging()

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
    parser.add_argument('--save-cfg', action='store_true')
    parser.add_argument('--auto-start', action='store_true')
    args, _ = parser.parse_known_args(argv)

    jobs_root_path = Path(__file__).parent / 'data'

    if args.auto_start:
        import pydio.autostart
        pydio.autostart.setup(argv)
        return 0

    data = []
    if args.file or not argv:
        fp = args.file or CONFIG_FILE
        logging.info("Loading config from %s", fp)
        with open(fp) as fp:
            data = json.load(fp, object_hook=JobConfig.object_decoder)
    else:
        job_config = JobConfig()
        job_config.load_from_cliargs(args)
        data = (job_config,)
        if args.save_cfg:
            logging.info("Storing config in %s", CONFIG_FILE)
            with open(CONFIG_FILE, 'w') as fp:
                cfg = job_config.__dict__
                cfg["__type__"] = "JobConfig"  # this is needed for the hoo above to work properly.
                cfg.pop("save_cfg", None)
                cfg.pop("auto_start", None)
                json.dump((cfg,), fp, indent=2)

    context = zmq.Context()
    pub_socket = context.socket(zmq.PUB)
    pub_socket.bind("tcp://*:%s" % args.zmq_port)

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
        rep_socket.bind("tcp://*:%s" % (args.zmq_port + 1))
        def listen_to_REP():
            while True:
                message = str(rep_socket.recv())
                logging.info('Received message from REP socket ' + message)
                parts = message.split(' ', 2)
                msg = 'status updated'
                if message.startswith('PAUSE'):
                    logging.info("SHOULD PAUSE")
                    if len(parts) > 1 and int(parts[1]) in controlThreads:
                        controlThreads[int(parts[1])].pause()
                    else:
                        for t in controlThreads:
                            t.pause()
                elif message.startswith('START'):
                    logging.info("SHOULD START")
                    if len(parts) > 1 and int(parts[1]) in controlThreads:
                        controlThreads[int(parts[1])].resume()
                    else:
                        for t in controlThreads:
                            t.resume()
                elif str(message).startswith('RELOAD') and len(parts) > 1 and int(parts[1]) in controlThreads:
                    # Todo: implement the reload of the config data
                    pass
                elif message == 'LIST-JOBS':
                    data = []
                    for t in controlThreads:
                        data.append(t.job_config.server + ' - ' + t.job_config.directory)
                    msg = json.dumps(data)

                try:
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


def setup_logging():
    import appdirs
    location = Path(str(appdirs.user_log_dir("pydio", "pydio")))
    if not location.exists():
        location.mkdir(parents=True)
    log_file = str(location / "pydio.log")

    configuration = {
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'short': {
                'format': '%(asctime)s %(message)s',
                'datefmt': '%H:%M:%S',
            },
            # this will slow down the app a little, due to
            'verbose': {
                'format': '%(asctime)s %(levelname)-7s %(filename)s:%(lineno)s | %(funcName)s | %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
        },
        'handlers': {
            'file': {
                'level': 'DEBUG',
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'verbose',
                'backupCount': 3,
                'maxBytes': 4194304,  # 4MB
                'filename': log_file
            },
            'console': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
                'formatter': 'short',
            },
        },
        'root': {
            'level': 'DEBUG',
            'handlers': ['console', 'file'],
        }

    }
    import logging.config
    logging.config.dictConfig(configuration)
    logging.info("Logging setup changed")


if __name__ == "__main__":
    rc = main()
    if rc is not None:
        sys.exit(0)
