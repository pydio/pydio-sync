#!/usr/bin/env python
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
"""Pydio : file synchronization for Pydio

Usage:
  main.py

Options:
  -h --help           Show this screen.
  -s --server=<str>   Server URL incl. scheme & path [default: http://localhost]
  -d --dir            Local directory to be synchronized
  -w --wspace         ID or alias of remote workspace to be synchronized
  -r --rdir           Path to an existing workspace subfolder to be synchronized
  -u --user           User name
  -p --passwd         Password
  -x --proxy          E.g.: http::username::password::proxyIP::proxyPort::...::check_proxy_flag
  --memprof           Generate the memory profile
  --flow=<str>        Sync direction.  Can be up, down, or [default: bi]
  -f --file           Path to JSON file containing job configurations
  -i --rdiff          Path to rdiff executable
  --api-user          Set the agent-API username (instead of random)
  --api-passwd        Set the agent-API password (instead of random)
  --api-addr=<str>    Set the agent IP address.  [default: 127.0.0.1]
  --api-port=<int>    Set the agent port.  [default: 5556]
  --diag              Run self-diagnostic suite
  --diag-http         Check server connection
  --diag-imports      Check imports & exit
  --save-cfg          *** Undocumented ***
  --extract_html      Utils for extracting HTML strings & compiling po to JSON
  --auto-start        *** Undocumented ***
  -v --verbosity      Logging verbosity level [default: 1]
"""

import os
import os.path as osp

import sys
import time
import json
import thread
import appdirs
import logging
import subprocess

from utils.functions import get_user_home, guess_filesystemencoding
from job.job_config import JobConfig, JobsLoader
from job import manager
from test.diagnostics import PydioDiagnostics
from utils.config_ports import PortsDetector
from utils.global_config import ConfigManager, GlobalConfigManager
from ui.web_api import PydioApi
from job.scheduler import PydioScheduler
from utils.i18n import PoProcessor
from utils.pydio_profiler import LogFile

try:
    import encodings as _
    logging.debug("Encodings installed:  {0}".format(_))
except ImportError:
    logging.error("Encodings not bundled with packaged pydio version. Exiting.")
    sys.exit(1)

if os.getenv("PYDIO_ENV") == "dev":
    _loglvl = logging.DEBUG
else:
    _loglvl = logging.INFO

# configure loggers
logging.basicConfig(
    level=_loglvl,
    format='%(asctime)s [%(levelname)-7s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logging.getLogger().setLevel(logging.DEBUG)
logging.disable(logging.NOTSET)
logging.getLogger("requests").setLevel(logging.WARNING)

# log PATH info
logging.debug("sys.path: %s", "\n\t".join(sys.path))
_python_path = os.getenv('PYTHONPATH', "").split(';')
logging.debug("PYTHONPATH: %s", "\n\t".join(_python_path))

# log encoding info
logging.debug("sys.getdefaultencoding(): %s" % sys.getdefaultencoding())
logging.debug("sys.getfilesystemencoding(): %s" % sys.getfilesystemencoding())

# log environment variables
_env = ("{k} : {v}".format(k, v) for (k, v) in os.environ.iteritems())
logging.debug("os.environ: \n\t%s" % "\n\t".join(sorted(_env)))


APP_NAME='Pydio'
DEFAULT_DATA_PATH = appdirs.user_data_dir(APP_NAME, roaming=True)
DEFAULT_PARENT_PATH = get_user_home(APP_NAME)
DEFAULT_PORT = 5556

if sys.platform == 'win32' and DEFAULT_DATA_PATH.endswith(osp.join(APP_NAME, APP_NAME)):
    # Remove double folder Pydio/Pydio on windows
    DEFAULT_DATA_PATH = DEFAULT_DATA_PATH.replace(osp.join(APP_NAME, APP_NAME), APP_NAME)
elif sys.platform == 'linux2':
    # According to XDG specification
    # http://standards.freedesktop.org/basedir-spec/basedir-spec-latest.html
    CONFIGDIR = os.getenv('XDG_DATA_HOME')
    if CONFIGDIR:
        logging.info('Linux CONFIG DIR XDG_DATA_HOME: ' + CONFIGDIR)
    if not CONFIGDIR:
        CONFIGDIR = osp.expanduser('~/.local/share')
        logging.info('Linux CONFIG DIR EXPANDED: ' + CONFIGDIR)
    DEFAULT_DATA_PATH = osp.join(CONFIGDIR, APP_NAME)
    logging.info('Linux DEFAULT_DATA_PATH: ' + DEFAULT_DATA_PATH)

global_config_manager = GlobalConfigManager.Instance(configs_path=DEFAULT_DATA_PATH)
global_config_manager.configs_path = DEFAULT_DATA_PATH
global_config_manager.set_general_config(global_config_manager.default_settings)


def _init_jobs_root():
    jobs_root_path = osp.join(osp.dirname(__file__), "data")
    if not osp.isdir(jobs_root_path):
        jobs_root_path = DEFAULT_DATA_PATH.encode(guess_filesystemencoding())
        if not osp.isdir(jobs_root_path):
            os.makedirs(jobs_root_path)

            logging.debug("configuring first run")
            user_dir = unicode(get_user_home(APP_NAME))
            if not osp.exists(user_dir):
                try:
                    os.makedirs(user_dir)
                except Exception as e:
                    logging.exception(e)  # TODO : maybe it's better to crash & burn?
            else:
                from utils.favorites_manager import add_to_favorites
                add_to_favorites(user_dir, APP_NAME)

def main(args):
    if args["--diag-imports"]:
        # If we made it here, imports didn't raise an exception,
        # so nothing more to do.
        return

    jobs_root = _init_jobs_root()
    setup_logging(args["--verbosity"], jobs_root)

    if args["--auto-start"]:
        import pydio.autostart
        pydio.autostart.setup(sys.argv[1:])
        return

    u_jobs_root_path = jobs_root.decode(guess_filesystemencoding())

    config_manager = ConfigManager.Instance(
        configs_path=u_jobs_root_path,
        data_path=DEFAULT_PARENT_PATH
    )

    jobs_loader = JobsLoader.Instance(data_path=u_jobs_root_path)
    config_manager.set_rdiff_path(args["--rdiff"])

    logging.info(
        "Product Version Number {0:s} and Version Date {1:s}".format(
            str(config_manager.get_version_data()['version']),
            str(config_manager.get_version_data()['date']))
        )

    if args["--proxy"]:
        data = None
        px_args = args["--proxy"].split("::")
        n_px_args = len(px_args)
        if (n_px_args % 5) in (0, 1):
            data = px_args
        else:
            logging.error("Wrong number of parameters pased for proxy")

        msg = {}
        for i in range(n_px_args / 5):
            msg[data[i * 5]] = {
                "username": data[i * 5 + 1],
                "password": data[i * 5 + 2],
                "hostname": data[i * 5 + 3],
                "port": data[i * 5 + 4]
            }
        # setting != testing, please
        config_manager.set_user_proxy(msg)
        return

    if args["--server"] and args["--dir"] and args["--wspace"]:
        job_config = JobConfig()
        job_config.load_from_cliargs(args)
        data = {job_config.id: job_config}
        if args.save_cfg:
            logging.info("Storing config in %s", osp.join(u_jobs_root_path, 'configs.json'))
            jobs_loader.save_jobs(data)
    else:
        fp = args["--file"]
        if fp and fp != '.':
            logging.info("Loading config from %s", fp)
            jobs_loader.config_file = fp
            jobs_loader.load_config()
        data = jobs_loader.get_jobs()

    datas = json.dumps(data, default=JobConfig.encoder, indent=2)
    logging.debug("data: %s" % datas)

    if args["--memprof"]:
        sys.stdout = LogFile('stdout')  # TODO fix this atrocity

    if args["--extract-html"]:
        proc = PoProcessor()
        languages = ['fr', 'de', 'nl', 'it']
        root = osp.dirname(__file__)
        if args["--extract-html"] == "extract":
            count = proc.extract_all_html_strings(
                osp.join(root, "ui"),
                osp.join(root, "res/i18n/html_strings.py")
            )
            logging.info(("Wrote %i strings to html_strings.py - "
                          "Now update PO files using standard tools") % count)

            # nothing more to do
            cmd = ('xgettext --language=Python --keyword=_ '
                   '--output=res/i18n/pydio.pot `find . -name "*.py"`')
            subprocess.check_output(cmd, shell=True, cwd=root)

            for l in languages:
                # Sometimes fuzzy matching should be used but mostly results in
                # wrong translations
                cmd = 'msgmerge -vU --no-fuzzy-matching ' + l + '.po pydio.pot'
                logging.info('Running ' + cmd)
                subprocess.check_output(cmd, cwd=osp.join(root, "res/i18n"), shell=True)

        elif args["--extract-html"] == "compile":
            for l in languages:
                cmd = "msgfmt {0}.po --output-file {0}/LC_MESSAGES/pydio.mo".format(l)
                logging.info('Running {0}'.format(cmd))
                subprocess.check_output(cmd, cwd=osp.join(root, "res/i18n"), shell=True)
            proc.po_to_json(osp.join(root, "res/i18n/*.po", osp.join(root, "ui/app/i18n.js")))

        return

    if args["--diag-http"]:
        keys = data.keys()
        smoke_test_args = [
            data[keys[0]].server,
            data[keys[0]].workspace,
            data[keys[0]].remote_folder,
            data[keys[0]].user_id,
        ]
        if args["--passwd"]:
            smoke_test_args.append(args["--passwd"])

        smoke_tests = PydioDiagnostics(*smoke_test_args)

        rc = smoke_tests.run()
        if rc != 0:
            msg = "Diagnostics failed: {0} {1}"
            logging.error(msg.format(rc, smoke_tests.status_message))

        return

    ports_detector = PortsDetector(
        store_file=osp.join(jobs_root, "ports_config"),
        username=args["--api-user"],
        password=args["--api-passwd"],
        default_port=args["--api-port"],
    )
    ports_detector.create_config_file()

    scheduler = PydioScheduler.Instance(
        jobs_root_path=jobs_root,
        jobs_loader=jobs_loader
    )

    server = PydioApi(
        ports_detector.get_port(),
        ports_detector.get_username(),
        ports_detector.get_password(),
        external_ip=args["--api-addr"]
    )
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
        application_path = appdirs.user_log_dir("pydio", "pydio")
        if not osp.isdir(application_path):
            os.makedirs(application_path)

    general_config = global_config_manager.get_general_config()

    log_file = osp.join(
        DEFAULT_DATA_PATH,
        str(general_config['log_configuration']['log_file_name'])
    )

    log_level_mapping = {
        'WARNING'  : logging.WARNING,
        'INFO'     : logging.INFO,
        'DEBUG'    : logging.DEBUG
    }
    genconf = general_config['log_configuration']['log_levels'].iteritems()
    levels = {int(k) : log_level_mapping[v] for (k, v) in genconf}

    level = levels.get(verbosity, logging.NOTSET)

    general_config['log_configuration']['disable_existing_loggers'] = bool(
        general_config['log_configuration']['disable_existing_loggers']
    )
    general_config['log_configuration']['handlers']['file']['filename'] = log_file
    general_config['log_configuration']['handlers']['console']['level'] = level

    configuration = general_config['log_configuration']

    from logging.config import dictConfig

    dictConfig(configuration)
    logging.debug("verbosity: %s" % verbosity)


if __name__ == "__main__":
    from docopt import docopt
    args = docopt(__doc__)

    main(args)
    manager.wait()
