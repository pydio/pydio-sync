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

import logging
import sys
import os

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)-7s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logging.getLogger().setLevel(logging.DEBUG)
logging.disable(logging.NOTSET)
logging.getLogger("requests").setLevel(logging.WARNING)

logging.debug("sys.path: %s", "\n\t".join(sys.path))
logging.debug("PYTHONPATH: %s", "\n\t".join(os.environ.get('PYTHONPATH', "").split(';')))
logging.debug("sys.getdefaultencoding(): %s" % sys.getdefaultencoding())
logging.debug("sys.getfilesystemencoding(): %s" % sys.getfilesystemencoding())
logging.debug("os.environ: \n\t%s" % "\n\t".join(sorted([k + ": " + v for k, v in os.environ.items()])))

#import locale
#logging.debug("locale.getdefaultlocale(): %s" % str(locale.getdefaultlocale()))
#if sys.platform != "win32":
#    logging.debug("locale.nl_langinfo(locale.CODESET): %s" % locale.nl_langinfo(locale.CODESET))

# this is an test import to see if encodings are bundled in the packaged pydio version
import encodings

# Most imports are placed after we have logged import path
# so we can easily debug import problems
# from flask import Flask
# from flask_restful import Api
import argparse
import json
import thread
import time
import pydio.monkeypatch
from pathlib import Path

if __name__ == "__main__":
    # You can run this module in to ways
    # 1. Directly:
    # This way this module is disconnected from other pydio modules and sys.path
    # does not facilitate import pydio, it need to bo corrected manually
    # 2. Via module argument "python -m"
    # Then there is nothing to change
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

from pydio.job.job_config import JobConfig, JobsLoader
from pydio.test.diagnostics import PydioDiagnostics
from pydio.utils.config_ports import PortsDetector
from pydio.utils.global_config import ConfigManager
from pydio.ui.web_api import PydioApi
from pydio.job.scheduler import PydioScheduler

DEFAULT_DATA_PATH = os.path.join(os.path.expanduser("~"), ".pydio_data")


def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser('Pydio Synchronization Tool')
    parser.add_argument('-s', '--server', help='Server URL, with http(s) and path to pydio', type=unicode,
                        default='http://localhost')
    parser.add_argument('-d', '--directory', help='Local directory', type=unicode, default=None)
    parser.add_argument('-w', '--workspace', help='Id or Alias of workspace to synchronize', type=unicode, default=None)
    parser.add_argument('-r', '--remote_folder', help='Path to an existing folder of the workspace to synchronize',
                        type=unicode, default=None)
    parser.add_argument('-u', '--user', help='User name', type=unicode, default=None)
    parser.add_argument('-p', '--password', help='Password', type=unicode, default=None)
    parser.add_argument('-dir', '--direction', help='Synchro Direction', type=str, default='bi')
    parser.add_argument('-f', '--file', type=unicode, help='Json file containing jobs configurations')
    parser.add_argument('-z', '--zmq_port', type=int,
                        help='Available port for zmq, both this port and this port +1 will be used', default=5556)
    parser.add_argument('-i', '--rdiff', type=unicode, help='Path to rdiff executable', default=None)
    parser.add_argument('--diag', help='Run self diagnostic', action='store_true', default=False)
    parser.add_argument('--diag-http', help='Check server connection', action='store_true', default=False)
    parser.add_argument('--diag-imports', help='Check imports and exit', action='store_true', default=False)
    parser.add_argument('--save-cfg', action='store_true', default=True)
    parser.add_argument('--extract_html', help='Utils for extracting HTML strings and compiling po files to json',
                        type=unicode, default=False)
    parser.add_argument('--auto-start', action='store_true')
    parser.add_argument('--auto_detect_port', type=bool, help='Auto detect available ports', default=False)
    parser.add_argument('-v', '--verbose', action='count', default=1)
    args, _ = parser.parse_known_args(argv)

    jobs_root_path = Path(__file__).parent / 'data'
    if not jobs_root_path.exists():
        jobs_root_path = Path(DEFAULT_DATA_PATH)
        if not jobs_root_path.exists():
            jobs_root_path.mkdir()

    setup_logging(args.verbose, jobs_root_path)

    if args.auto_start:
        import pydio.autostart

        pydio.autostart.setup(argv)
        return 0

    jobs_loader = JobsLoader.Instance(data_path=str(jobs_root_path))
    config_manager = ConfigManager.Instance(data_path=str(jobs_root_path))
    config_manager.set_rdiff_path(args.rdiff)

    if args.server and args.directory and args.workspace:
        job_config = JobConfig()
        job_config.load_from_cliargs(args)
        data = {job_config.id: job_config}
        if args.save_cfg:
            logging.info("Storing config in %s", str(jobs_root_path / 'configs.json'))
            jobs_loader.save_jobs(data)
    else:
        fp = args.file
        if fp and fp != '.':
            logging.info("Loading config from %s", fp)
            jobs_loader.config_file = fp
            jobs_loader.load_config()
        data = jobs_loader.get_jobs()

    logging.debug("data: %s" % json.dumps(data, default=JobConfig.encoder, indent=2))

    if args.diag_imports:
        # nothing more to do
        return sys.exit(0)

    if args.extract_html:
        from pydio.utils.i18n import PoProcessor
        proc = PoProcessor()
        if args.extract_html == 'extract':
            root = Path(__file__).parent
            count = proc.extract_all_html_strings(str(root / 'ui' / 'res' ), str(root / 'res' / 'i18n' / 'html_strings.py' ))
            logging.info('Wrote %i strings to html_strings.py - Now update PO files using standard tools' % count)
            # nothing more to do
        elif args.extract_html == 'compile':
            root = Path(__file__).parent
            proc.po_to_json(str(root / 'res' / 'i18n' / '*.po'), str(root / 'ui' / 'res' / 'i18n.js'))
        return sys.exit(0)

    if args.diag_http:
        keys = data.keys()
        if args.password:
            smoke_tests = PydioDiagnostics(
                data[keys[0]].server, data[keys[0]].workspace, data[keys[0]].remote_folder, data[keys[0]].user_id,
                args.password)
        else:
            smoke_tests = PydioDiagnostics(
                data[keys[0]].server, data[keys[0]].workspace, data[keys[0]].remote_folder, data[keys[0]].user_id)
        rc = smoke_tests.run()
        if rc != 0:
            logging.error("Diagnostics failed: %s %s" % (str(rc), smoke_tests.status_message))
        return sys.exit(rc)

    ports_detector = PortsDetector(args.zmq_port, args.auto_detect_port,
                                   store_file=str(jobs_root_path / 'ports_config'))
    ports_detector.create_config_file()

    scheduler = PydioScheduler.Instance(jobs_root_path=jobs_root_path, jobs_loader=jobs_loader)
    server = PydioApi(ports_detector.get_open_port('flask_api'))
    from pydio.job import manager
    manager.api_server = server

    try:

        thread.start_new_thread(server.start_server, ())
        time.sleep(0.3)
        if not server.running:
            logging.error('Cannot start web server, exiting application')
            sys.exit(1)
        scheduler.start_all()

    except (KeyboardInterrupt, SystemExit):
        server.shutdown_server()
        sys.exit()


def setup_logging(verbosity=None, application_path=None):

    if not application_path:
        import appdirs
        application_path = Path(str(appdirs.user_log_dir("pydio", "pydio")))
        if not application_path.exists():
            application_path.mkdir(parents=True)

    log_file = str(application_path / "pydio.log")

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
                'format': '%(asctime)s %(levelname)-7s %(thread)-5d %(threadName)-8s %(message)s',
                'datefmt': '%H:%M:%S',
            },
            # this will slow down the app a little, due to
            'verbose': {
                'format': '%(asctime)s %(levelname)-7s %(thread)-5d %(threadName)-8s %(filename)s:%(lineno)s | %(funcName)s | %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
        },
        'handlers': {
            'file': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'verbose',
                'backupCount': 8,
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
    #logging.info("Logging setup changed")
    logging.debug("verbosity: %s" % verbosity)


if __name__ == "__main__":
    main()
    from pydio.job import manager
    manager.wait()
