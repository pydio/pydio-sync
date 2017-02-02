# -*- coding: utf-8 -*-
# Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
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

import logging
import sys
import os
try:
    import pydio.monkeypatch
    import pydio.utils.functions
    from pydio.utils.functions import get_user_home, guess_filesystemencoding
    from pydio.job.job_config import JobConfig, JobsLoader
    from pydio.test.diagnostics import PydioDiagnostics
    from pydio.utils.config_ports import PortsDetector
    from pydio.utils.global_config import ConfigManager, GlobalConfigManager
    from pydio.ui.web_api import PydioApi
    from pydio.job.scheduler import PydioScheduler
    from pydio.job import manager
    from pydio.utils.i18n import PoProcessor
    from pydio.utils.pydio_profiler import LogFile
except ImportError:
    # This allows to run manually python main.py
    from utils.functions import get_user_home, guess_filesystemencoding
    import utils.functions
    import monkeypatch
    from job.job_config import JobConfig, JobsLoader
    from job import manager
    from test.diagnostics import PydioDiagnostics
    from utils.config_ports import PortsDetector
    from utils.global_config import ConfigManager, GlobalConfigManager
    from ui.web_api import PydioApi
    from job.scheduler import PydioScheduler
    from utils.i18n import PoProcessor
    from utils.pydio_profiler import LogFile

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


import appdirs
APP_NAME='Pydio'
DEFAULT_DATA_PATH = appdirs.user_data_dir(APP_NAME, roaming=True)

if sys.platform == 'win32' and DEFAULT_DATA_PATH.endswith(os.path.join(APP_NAME, APP_NAME)):
    # Remove double folder Pydio/Pydio on windows
    DEFAULT_DATA_PATH = DEFAULT_DATA_PATH.replace(os.path.join(APP_NAME, APP_NAME), APP_NAME)
elif sys.platform == 'linux2':
    # According to XDG specification
    # http://standards.freedesktop.org/basedir-spec/basedir-spec-latest.html
    CONFIGDIR = os.getenv('XDG_DATA_HOME')
    if CONFIGDIR:
        logging.info('Linux CONFIG DIR XDG_DATA_HOME: ' + CONFIGDIR)
    if not CONFIGDIR:
        CONFIGDIR = os.path.expanduser('~/.local/share')
        logging.info('Linux CONFIG DIR EXPANDED: ' + CONFIGDIR)
    DEFAULT_DATA_PATH = os.path.join(CONFIGDIR, APP_NAME)
    logging.info('Linux DEFAULT_DATA_PATH: ' + DEFAULT_DATA_PATH)

global_config_manager = GlobalConfigManager.Instance(configs_path=DEFAULT_DATA_PATH)
global_config_manager.configs_path = DEFAULT_DATA_PATH
global_config_manager.set_general_config(global_config_manager.default_settings)

DEFAULT_PARENT_PATH = get_user_home(APP_NAME)

def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser('Pydio Synchronization Tool')
    # Pass a server configuration via arguments
    parser.add_argument('-s', '--server', help='Server URL, with http(s) and path to pydio', type=unicode,
                        default='http://localhost')
    parser.add_argument('-d', '--directory', help='Local directory', type=unicode, default=None)
    parser.add_argument('-w', '--workspace', help='Id or Alias of workspace to synchronize', type=unicode, default=None)
    parser.add_argument('-r', '--remote_folder', help='Path to an existing folder of the workspace to synchronize',
                        type=unicode, default=None)
    parser.add_argument('-u', '--user', help='User name', type=unicode, default=None)
    parser.add_argument('-p', '--password', help='Password', type=unicode, default=None)
    parser.add_argument('-px', '--proxy', help='Enter like http::username::password::proxyIP::proxyPort::...::check_proxy_flag '
                        'By default proxy connection test happens, to avoid mention 0 or False', type=unicode, default=None)
    parser.add_argument('-mp', '--memory_profile', help="To Generate the memory profile :: use <<-mp True >> as argument",
                        type=unicode, default=False)
    parser.add_argument('-dir', '--direction', help='Synchro Direction', type=str, default='bi')
    # Pass a configuration file
    parser.add_argument('-f', '--file', type=unicode, help='Json file containing jobs configurations')
    # Pass a path to rdiff binary
    parser.add_argument('-i', '--rdiff', type=unicode, help='Path to rdiff executable', default=None)
    # Configure API access
    parser.add_argument('--api_user', help='Set the agent API username (instead of random)', type=unicode, default=None)
    parser.add_argument('--api_password', help='Set the agent API password (instead of random)', type=unicode, default=None)
    parser.add_argument('--api_address', help='Set the agent IP address. By default, no address means that local '
                                              'access only is allowed.', type=str, default=None)
    parser.add_argument('--api_port', help='Set the agent port. By default, will try to use 5556, and if not '
                                           'available will switch to another port.', type=int, default=5556)
    parser.add_argument('--diag', help='Run self diagnostic', action='store_true', default=False)
    parser.add_argument('--diag-http', help='Check server connection', action='store_true', default=False)
    parser.add_argument('--diag-imports', help='Check imports and exit', action='store_true', default=False)
    parser.add_argument('--save-cfg', action='store_true', default=True)
    parser.add_argument('--extract_html', help='Utils for extracting HTML strings and compiling po files to json',
                        type=unicode, default=False)
    parser.add_argument('--auto-start', action='store_true')
    parser.add_argument('-v', '--verbose', action='count', default=1)
    args, _ = parser.parse_known_args(argv)

    jobs_root_path = Path(__file__).parent / 'data'
    if not jobs_root_path.exists():
        jobs_root_path = Path(DEFAULT_DATA_PATH.encode(guess_filesystemencoding()))
        if not jobs_root_path.exists():
            jobs_root_path.mkdir(parents=True)
            # This is a first start
            user_dir = unicode(get_user_home(APP_NAME))
            if not os.path.exists(user_dir):
                try:
                    os.mkdir(user_dir)
                except Exception as e:
                    logging.exception(e)
                    pass
            if os.path.exists(user_dir):
                try:
                    from pydio.utils.favorites_manager import add_to_favorites
                except ImportError:
                    from utils.favorites_manager import add_to_favorites
                add_to_favorites(user_dir, APP_NAME)

    setup_logging(args.verbose, jobs_root_path)

    if args.auto_start:
        try:
            import pydio.autostart
        except ImportError:
            import autostart
        pydio.autostart.setup(argv)
        return 0

    u_jobs_root_path = str(jobs_root_path).decode(guess_filesystemencoding())
    config_manager = ConfigManager.Instance(configs_path=u_jobs_root_path, data_path=DEFAULT_PARENT_PATH)

    jobs_loader = JobsLoader.Instance(data_path=u_jobs_root_path)
    config_manager.set_rdiff_path(args.rdiff)

    logging.info(
        "Product Version Number {0:s} and Version Date {1:s}".format(str(config_manager.get_version_data()['version']),
                                                                str(config_manager.get_version_data()['date'])))

    if args.proxy is not None:
        data = args.proxy.split('::') if len(args.proxy.split('::'))%5 in range(0, 2) else logging.error("Wrong number of parameters pased for proxy")
        msg = {}
        for i in range(len(args.proxy.split('::'))/5):
            msg[data[i*5]] = {"username": data[i*5+1], "password": data[i*5+2], "hostname": data[i*5+3], "port": data[i*5+4]}
        proxy_flag = data[-1] if len(args.proxy.split('::'))%5 == 1 else True  # default true
        # setting != testing, please
        config_manager.set_user_proxy(msg)
        return 0

    if args.server and args.directory and args.workspace:
        job_config = JobConfig()
        job_config.load_from_cliargs(args)
        data = {job_config.id: job_config}
        if args.save_cfg:
            logging.info("Storing config in %s", os.path.join(u_jobs_root_path, 'configs.json'))
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

    if args.memory_profile:
        sys.stdout = LogFile('stdout')

    if args.extract_html:
        proc = PoProcessor()
        if args.extract_html == 'extract':
            root = Path(__file__).parent
            count = proc.extract_all_html_strings(str(root / 'ui' ), str(root / 'res' / 'i18n' / 'html_strings.py' ))
            logging.info('Wrote %i strings to html_strings.py - Now update PO files using standard tools' % count)
            # nothing more to do
        elif args.extract_html == 'compile':
            root = Path(__file__).parent
            proc.po_to_json(str(root / 'res' / 'i18n' / '*.po'), str(root / 'ui' / 'app' / 'i18n.js'))
        logging.info("XGETTEXT, TODO automate")
        logging.info("Merge po files, TODO automate")
        logging.info("MSGFMT, TODO automate")
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

    ports_detector = PortsDetector(store_file=str(jobs_root_path / 'ports_config'), username=args.api_user,
                                   password=args.api_password, default_port=args.api_port)
    ports_detector.create_config_file()

    scheduler = PydioScheduler.Instance(jobs_root_path=jobs_root_path, jobs_loader=jobs_loader)
    server = PydioApi(ports_detector.get_port(), ports_detector.get_username(),
        ports_detector.get_password(), external_ip=args.api_address)
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

    general_config = global_config_manager.get_general_config()

    log_file = os.path.join(DEFAULT_DATA_PATH, str(general_config['log_configuration']['log_file_name']))

    log_level_mapping ={'WARNING'  : logging.WARNING,
                        'INFO'     : logging.INFO,
                        'DEBUG'    : logging.DEBUG
                       }

    levels = dict((int(k), log_level_mapping[v]) for k, v in general_config['log_configuration']['log_levels'].items())
    level = levels.get(verbosity, logging.NOTSET)

    general_config['log_configuration']['disable_existing_loggers'] = bool(general_config['log_configuration']['disable_existing_loggers'])
    general_config['log_configuration']['handlers']['file']['filename'] = log_file
    general_config['log_configuration']['handlers']['console']['level'] = level

    configuration = general_config['log_configuration']

    from logging.config import dictConfig

    dictConfig(configuration)
    logging.debug("verbosity: %s" % verbosity)


if __name__ == "__main__":
    main()
    manager.wait()
