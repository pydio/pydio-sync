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
import sys
import logging
import os.path as osp

from pydio.job import manager
from pydio.utils.i18n import PoProcessor
from pydio.utils.global_config import GlobalConfigManager
from pydio.application import APP_NAME, APP_DATA, Application


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
        app.configure_proxy(args["--proxy"])
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
