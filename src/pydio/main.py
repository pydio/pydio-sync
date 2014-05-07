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

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)-7s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logging.getLogger().setLevel(logging.DEBUG)
logging.disable(logging.NOTSET)
logging.getLogger("requests").setLevel(logging.WARNING)

logging.debug("sys.path: %s", "\n\t".join(sys.path))
logging.debug("PYTHONPATH: %s", "\n\t".join(os.environ.get('PYTHONPATH', "").split(';')))

# Most imports are placed after we have logged import path
# so we can easily debug import problems

import argparse
import json
import zmq
import thread
from pathlib import Path

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

DEFAULT_CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".pydio.json")


from pydio.job.continous_merger import ContinuousDiffMerger
from pydio.job.job_config import JobConfig
from pydio.test.diagnostics import PydioDiagnostics
from pydio.test import config_ports


def main(argv=sys.argv[1:]):


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
    parser.add_argument('--diag', help='Run self diagnostic', action='store_true', default=False)
    parser.add_argument('--diag-http', help='Check server connection', action='store_true', default=False)
    parser.add_argument('--save-cfg', action='store_true')
    parser.add_argument('--auto-start', action='store_true')
    parser.add_argument('-v', '--verbose', action='count', )
    args, _ = parser.parse_known_args(argv)

    setup_logging(args.verbose)

    jobs_root_path = Path(__file__).parent / 'data'

    if args.auto_start:
        import pydio.autostart
        pydio.autostart.setup(argv)
        return 0

    data = []
    if args.file or not argv:
        fp = args.file
        if not fp or fp == '.':
            fb = DEFAULT_CONFIG_FILE
        logging.info("Loading config from %s", fp)
        with open(fp) as fp:
            data = json.load(fp, object_hook=JobConfig.object_decoder)
    else:
        job_config = JobConfig()
        job_config.load_from_cliargs(args)
        data = (job_config,)
        if args.save_cfg:
            logging.info("Storing config in %s", DEFAULT_CONFIG_FILE)
            with open(DEFAULT_CONFIG_FILE, 'w') as fp:
                # TODO: 07.05.14 wooyek This should be taken care of in the JobConfig
                cfg = job_config.__dict__.copy()
                cfg["__type__"] = "JobConfig"  # this is needed for the hoo above to work properly.
                cfg.pop("save_cfg", None)
                cfg.pop("auto_start", None)
                cfg["user"] = cfg.pop("user_id", None)
                json.dump((cfg,), fp, indent=2)

    logging.debug("data: %s" % json.dumps(data[0].__dict__, indent=2))

    if args.diag_http:
        smoke_tests = PydioDiagnostics(
            data[0].server, data[0].workspace, data[0].remote_folder, data[0].user_id)
        return sys.exit(smoke_tests.run())


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


def setup_logging(verbosity=None):
    import appdirs
    location = Path(str(appdirs.user_log_dir("pydio", "pydio")))
    if not location.exists():
        location.mkdir(parents=True)
    log_file = str(location / "pydio.log")

    levels = {
        0: logging.WARNING,
        1: logging.INFO,
        2: logging.DEBUG,
    }
    level = levels.get(verbosity, logging.NOTSET)

    configuration = {
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'short': {
                'format': '%(asctime)s %(levelname)-7s %(thread)-5d %(message)s',
                'datefmt': '%H:%M:%S',
            },
            # this will slow down the app a little, due to
            'verbose': {
                'format': '%(asctime)s %(levelname)-7s %(thread)-5d %(filename)s:%(lineno)s | %(funcName)s | %(message)s',
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
                'level': level,
                'class': 'logging.StreamHandler',
                'formatter': 'short',
            },
        },
        'root': {
            'level': 'DEBUG',
            'handlers': ['console', 'file'],
        }

    }
    from logging.config import dictConfig
    dictConfig(configuration)
    logging.info("Logging setup changed")
    logging.debug("verbosity: %s" % verbosity)


if __name__ == "__main__":
    main()
