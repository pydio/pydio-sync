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
"""Pydio : file synchronization for Pydio.

Usage:  main [options]

Options:
  -h --help           Show this screen.
  -s --server=<str>   Server URL incl. scheme & path [default: http://localhost]
  -d --dir            Local directory to be synchronized
  -w --wspace         ID or alias of remote workspace to be synchronized
  -r --rdir           Path to an existing workspace subfolder to be synchronized
  -u --user           User name
  -p --passwd         Password
  -x --proxy          E.g.: http::username::password::proxyIP::proxyPort::...::check_proxy_flag
  --flow=<str>        Sync direction.  Can be up, down, or [default: bi]
  -f --file           Path to JSON file containing job configurations
  -i --rdiff          Path to rdiff executable
  --api-user          Set the agent-API username (instead of random)
  --api-passwd        Set the agent-API password (instead of random)
  --api-addr=<str>    Set the agent IP address.  [default: 127.0.0.1]
  --api-port=<int>    Set the agent port.  [default: 5556]
  --diag              Run self-diagnostic suite
  --diag-http         Check server connection
  --save-cfg          *** Undocumented ***
  --extract-html      Utils for extracting HTML strings & compiling po to JSON
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

from pydio.utils.functions import get_user_home, guess_filesystemencoding
from pydio.job.job_config import JobConfig, JobsLoader
from pydio.job import manager
from pydio.utils.config_ports import PortsDetector
from pydio.utils.global_config import ConfigManager, GlobalConfigManager
from pydio.ui.web_api import PydioApi
from pydio.job.scheduler import PydioScheduler
from pydio.utils.i18n import PoProcessor

APP_NAME = "Pydio"
APP_DATA = dict(
    DEFAULT_DATA_PATH=appdirs.user_data_dir(APP_NAME, roaming=True),
    DEFAULT_PARENT_PATH=get_user_home(APP_NAME),
    DEFAULT_PORT=5556,
)


def init_logging():
    logging.disable(logging.NOTSET)

    if os.getenv("PYDIO_ENV") == "dev":
        lvl = logging.DEBUG
    else:
        lvl = logging.INFO

    log = logging.getLogger()
    log.setLevel(lvl)

    hdlr = logging.StreamHandler()
    hdlr.setLevel(lvl)

    fmt = logging.Formatter(
        "%(asctime)s - %(name)s - [ %(levelname)s ] - %(message)s'"
    )

    hdlr.setFormatter(fmt)
    log.addHandler(hdlr)


def init_application_data():
    """Initialize appdata directory in an OS-compliant way."""

    appname_dir = osp.join(APP_NAME, APP_NAME)
    default_dpath = APP_DATA["DEFAULT_DATA_PATH"]

    if sys.platform == "win32" and default_dpath.endswith(appname_dir):
        # Remove double folder Pydio/Pydio on windows
        APP_DATA["DEFAULT_DATA_PATH"] = default_dpath.replace(appname_dir, APP_NAME)
    elif sys.platform == "linux2":
        l = logging.getLogger(__name__)

        # According to XDG specification
        # http://standards.freedesktop.org/basedir-spec/basedir-spec-latest.html
        cfgdir = APP_DATA["config_dir"] = os.getenv('XDG_DATA_HOME')
        if cfgdir:
            l.info("Linux CONFIG DIR XDG_DATA_HOME: {0}".format(cfgdir))
        if not cfgdir:
            cfgdir = osp.expanduser("~/.local/share")
            l.info("Linux CONFIG DIR EXPANDED: {0}".format(cfgdir))
        APP_DATA["DEFAULT_DATA_PATH"] = default_dpath = osp.join(cfgdir, APP_NAME)
        l.info("Linux default data path: {0}".format(default_dpath))


def init_global_config(dpath):
    global_config_manager = GlobalConfigManager.Instance(configs_path=dpath)
    global_config_manager.configs_path = dpath
    global_config_manager.set_general_config(
        global_config_manager.default_settings
    )


class Application(object):
    """Pydio-Sync application class"""
    log = logging.getLogger('.'.join((__name__, "Application")))

    def __init__(self, jobs_root, jobs_loader, cfg, **kw):
        self.cfg = cfg
        self._jobs_root = jobs_root
        self.config_manager = ConfigManager.Instance(
            configs_path=self.jobs_root,  # use property to get decoded path
            data_path=APP_DATA["DEFAULT_PARENT_PATH"]
        )
        self.jobs_loader = jobs_loader
        if args.get("--rdiff"):
            self.config_manager.set_rdiff_path(args.pop("--rdiff"))

        self.log_release_info()

        self._ports_detector = self._configure_ports_detector()
        self._scheduler = PydioScheduler.Instance(
            jobs_root_path=self.jobs_root,
            jobs_loader=self.jobs_loader,
        )
        self._svr = PydioApi(
            self._ports_detector.get_port(),
            self._ports_detector.get_username(),
            self._ports_detector.get_password(),
            external_ip=kw["--api-addr"],
        )
        manager.api_server = self._svr

    @classmethod
    def from_cli_args(cls, **kw):
        jobs_root = cls.configure_jobs_root(kw)
        jobs_load = JobsLoader.Instance(data_path=jobs_root)

        job_config = JobConfig()
        job_config.load_from_cliargs(args)
        cfg = {job_config.id: job_config}
        if args.save_cfg:
            cls.log.info("Storing config in {0}".format(
                osp.join(jobs_root, 'configs.json')
            ))
            jobs_load.save_jobs(cfg)

        return cls(jobs_root, jobs_load, cfg, **kw)

    @classmethod
    def from_cfg_file(cls, **kw):
        jobs_root = cls.configure_jobs_root(kw)
        jobs_load = JobsLoader.Instance(data_path=jobs_root)

        fp = args["--file"]
        if fp and fp != '.':
            cls.log.info("Loading config from {0}".format(fp))
            jobs_load.config_file = fp
            jobs_load.load_config()

        cfg = jobs_load.get_jobs()
        return cls(jobs_root, jobs_load, cfg, **kw)

    @property
    def jobs_root(self):
        return self._jobs_root.decode(guess_filesystemencoding())

    @staticmethod
    def configure_jobs_root(kw):
        jroot = kw.get(
            "jobs_root",
            osp.join(osp.dirname(__file__), "data")
        )

        if not osp.isdir(jroot):
            jroot = APP_DATA["DEFAULT_DATA_PATH"].encode(guess_filesystemencoding())
            if not osp.isdir(jroot):
                os.makedirs(jroot)

                Application.log.debug("configuring first run")
                user_dir = get_user_home(APP_NAME)
                if not osp.exists(user_dir):
                    os.makedirs(user_dir)
                else:
                    from utils.favorites_manager import add_to_favorites
                    add_to_favorites(user_dir, APP_NAME)

        return jroot

    def run(self):
        thread.start_new_thread(self._svr.start_server, ())
        time.sleep(0.3)
        if not self._svr.running:
            raise RuntimeError("Cannot start web server, exiting application")
        self._scheduler.start_all()

    def halt(self):
        self._svr.shutdown_server()

    def log_release_info(self):
        vdat = self.config_manager.get_version_data()
        self.log.info("Version Number {0:s}".format(vdat["version"]))
        self.log.info("Release Date {0:s}".format(vdat["date"]))

    def configure_proxy(self):
        prx_args = args["--proxy"].split("::")
        n_prx_args = len(prx_args)
        if (n_prx_args % 5) not in (0, 1):
            self.log.error("Wrong number of parameters pased for proxy")
            return

        prx_cfg = {}
        for i in range(n_prx_args / 5):
            prx_cfg[prx_args[i * 5]] = {
                "username": prx_args[i * 5 + 1],
                "password": prx_args[i * 5 + 2],
                "hostname": prx_args[i * 5 + 3],
                "port": prx_args[i * 5 + 4]
            }

        self.config_manager.set_user_proxy(prx_cfg)

    def log_config_data(self):
        self.log.debug("data: {0}".format(json.dumps(
            self.cfg,
            default=JobConfig.encoder,
            indent=2,
        )))

    def _configure_ports_detector(self):
        ports_detector = PortsDetector(
            store_file=osp.join(self.jobs_root, "ports_config"),
            username=args["--api-user"],
            password=args["--api-passwd"],
            default_port=int(args["--api-port"]),
        )
        ports_detector.create_config_file()
        return ports_detector


def main(args):
    if args["--server"] and args["--dir"] and args["--wspace"]:
        app = Application.from_cli_args(**args)
    else:
        app = Application.from_cfg_file(**args)

    if args["--auto-start"]:
        import pydio.autostart
        pydio.autostart.setup(sys.argv[1:])
        return

    if args["--proxy"]:
        app.configure_proxy()
        return

    app.log_config_data()
    if args["--extract-html"]:
        extract_html(args["--extract-html"])
        return

    try:
        app.run()
        manager.wait()
    finally:
        app.halt()


def extract_html(extraction_method):
    from functools import partial
    from subprocess import check_output
    checkoutpt = partial(check_output, shell=True)

    logger = logging.getLogger(__name__)
    languages = ['fr', 'de', 'nl', 'it']

    root = osp.dirname(__file__)
    i18n = osp.join(root, "res/i18n")
    ui = osp.join(root, "ui")

    proc = PoProcessor()
    if extraction_method == "extract":
        html_strings = osp.join(i18n, "html_strings.py")
        count = proc.extract_all_html_strings(ui, html_strings)
        msg = "Wrote %i strings to html_strings.py.  Updating PO files."
        logger.log.info(msg % count)

        # nothing more to do
        cmd = ('xgettext --language=Python --keyword=_ '
               '--output=res/i18n/pydio.pot `find . -name "*.py"`')
        checkoutpt(cmd, cwd=root)

        for l in languages:
            # Sometimes fuzzy matching should be used but mostly results in
            # wrong translations
            cmd = "msgmerge -vU --no-fuzzy-matching {lang}.po pydio.pot"
            logger.log.info('Running %s'.format(cmd.format(lang=l)))
            checkoutpt(cmd, cwd=i18n)

    elif extraction_method == "compile":
        for l in languages:
            cmd = "msgfmt {lang}.po --output-file {lang}/LC_MESSAGES/pydio.mo"
            logger.log.info('Running %s' % cmd.format(lang=l))
            checkoutpt(cmd, cwd=i18n)

        proc.po_to_json(osp.join(i18n, "*.po", osp.join(ui, "app/i18n.js")))


if __name__ == "__main__":
    from docopt import docopt
    args = docopt(__doc__)

    init_logging()
    init_application_data()
    init_global_config(APP_DATA["DEFAULT_DATA_PATH"])

    main(args)
