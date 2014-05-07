# coding=utf-8
# Created 2014 by Janusz Skonieczny

# coding=utf-8
from datetime import datetime
import logging
import subprocess
import os
import sys


# logging.basicConfig(format='%(asctime)s %(levelname)-7s %(module)s.%(funcName)s - %(message)s')
logging.basicConfig(format='%(asctime)s %(message)s')
logging.getLogger().setLevel(logging.DEBUG)
logging.disable(logging.NOTSET)

ROOT = os.path.dirname(__file__)
VE_NAME = ".distve"
VE_HOME = os.path.join(ROOT, VE_NAME)
is_win = (sys.platform == 'win32')

def create_virtualenv():
    import virtualenv
    # execfile(virtualenv, dict(__file__=virtualenv, )
    virtualenv.logger = virtualenv.Logger([(virtualenv.Logger.level_for_integer(2), sys.stdout)])
    # We need access to global packages for silently installed PyQt4
    # see below for more info
    is_PyQt_installed_globally = True
    virtualenv.create_environment(VE_HOME, clear=True, site_packages=is_PyQt_installed_globally)


def activate_virtualenv():
    # Activate Virtual Environment
    commands = "Scripts" if is_win else "bin"
    activate_this = os.path.join(os.path.dirname(os.path.abspath(__file__)), VE_NAME, commands, "activate_this.py")
    import virtualenv
    virtualenv.logger.notify("Activating: %s" % activate_this)
    execfile(activate_this, dict(__file__=activate_this))
    # this is required for Pip to run subprocess on the VE python
    # instead of the default one, the one used to call this script
    executable = sys.executable.rsplit(os.path.sep)[-1]
    sys.executable = os.path.join(os.path.dirname(os.path.abspath(__file__)), VE_NAME, commands, executable)


def print_path():
    from pip.locations import running_under_virtualenv
    logging.debug("running_under_virtualenv(): %s" % running_under_virtualenv())
    logging.debug("sys.prefix: %s", repr(sys.prefix))
    logging.debug("sys.executable: %s", repr(sys.executable))
    logging.debug("sys.path")  # = %s", repr(sys.path))
    for s in sys.path:
        logging.info("\t%s" % s)
    for s in os.environ.get('PYTHONPATH', "").split(';'):
        logging.info("\t%s" % s)
    # logging.debug("sys.modules.keys() = %s", repr(sys.modules.keys()))
    # for s in sys.modules.keys():
    #     print "\t%s" % s


def install_requirements():
    # Install requirements
    import pip
    logging.debug("pip: %s" % pip.__file__)
    # target = os.path.join(os.path.dirname(os.path.abspath(__file__)), VE_NAME, "lib", "site-packages")
    # args = "install -r requirements.txt --target {}".format(target)  # this will install to the right place but will not look for dependencies in this place
    args = "install -r requirements.txt -vvv"
    pip.main(args.split(" "))
    if is_win:
        logging.debug("Touching pywin32 installed by easy_install")
        pip.main("install pywin32".split(" "))


def install_pywin32():
    from setuptools.command import easy_install
    logging.debug("easy_install: %s" % easy_install.__file__)
    pywin32 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arch", "pywin32-218.win32-py2.7.exe")
    logging.debug("pywin32: %s" % pywin32)
    easy_install.main([pywin32])


def build_installer():
    src = os.path.join(ROOT, "src")
    app = os.path.join(src, "pydio", "main.py")
    # PyInstaller.main.run(["--onefile", "--windowed", "--noconsole", app])
    # PyInstaller.main.run(["--onefile --name=pydio", app])
    hooks = os.path.join(ROOT, "pyi_hooks")

    name = "pydio-sync-agent"

    if "BUILD_VCS_NUMBER" in os.environ:
        # if a build system variable is present build with descriptive name
        # TODO: 07.05.14 wooyek We need fo factor a release workflow. Will it be automatic or human triggered?
        # Not sure this should live here, but the less depends on build server setup the better
        vcs_number = os.environ.get("BUILD_VCS_NUMBER", "hashmissing")
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        name = "{}-{}-{}".format(name, ts, vcs_number)

    # debugging build, multiple files
    # args = "--name=pydio --hidden-import=pydio --onedir --debug --additional-hooks-dir={} --paths={} {}".format(hooks, src, app)

    # production build, one file
    args = "--name=pydio --hidden-import=pydio --onefile --name={} --debug --additional-hooks-dir={} --paths={} {}".format(name, hooks, src, app)

    # makespec command does not support passing custom arguments we need to override sys.argv
    argv = sys.argv
    sys.argv = argv[0:1] + args.split(" ")
    import PyInstaller.cliutils.makespec
    logging.info("Running PyInstaller.cliutils.makespec %s", args)
    PyInstaller.cliutils.makespec.run()
    sys.argv = argv

    spec = os.path.join(ROOT, name + ".spec")
    import PyInstaller.main
    logging.info("Running PyInstaller.main %s", spec)
    PyInstaller.main.run(["--noconfirm", "--clean", spec])
    return name


def install_qt():

    # PyQt4 installer does not well support silent install
    # Install destination INSTDIR that could normally be set by argument:
    # /D=<path here>
    # is overridden based on the Python install dir taken from registry
    # PYQT_PYTHON_HK, there is no documented way to override this behaviour
    # thus making silent install to another directory (eg. inside VE) impossible

    try:
        from PyQt4 import QtGui, uic, QtCore
        logging.info("PyQt4 already is available, not installing…")
        return
    except ImportError:
        pass

    qt = os.path.join(ROOT, "arch", "PyQt4-4.10.4-gpl-Py2.7-Qt4.8.5-x32.exe")
    call = "{} /S /D={}".format(qt, VE_HOME)
    logging.debug("Install PyQt4: %s" % call)

    try:
        # this will not elevate privileges but will not require to launch a new process
        rc = subprocess.call(call.split(" "))
        if rc != 0:
            logging.info("PyQt binary install requires elevated privileges. If install fails, try running it with admin privileges.")
            sys.exit(rc)
    except WindowsError as ex:
        logging.error(ex, exc_info=True)
        logging.warn("PyQt binary install requires elevated privileges. If install fails, try running it with admin privileges.")
        sys.exit(ex.errno)

    # this will elevate privileges but will not will not wait for new process to finish
    # call = call.split(" ")
    # import win32com.shell.shell as shell
    # shell.ShellExecuteEx(lpVerb='runas', lpFile=call[0], lpParameters=" ".join(call[1:]))


def diagnostics(name):
    binary = os.path.join(ROOT, "dist", (name + ".exe") if is_win else name)
    cmd = binary + " --file . --diag --diag-http"
    rc = subprocess.call(cmd.split(" "))
    if rc != 0:
        logging.error("Self diagnostics have failed")
        sys.exit(rc)

if __name__ == "__main__":
    logging.debug("sys.platform: %s" % sys.platform)

    import argparse
    parser = argparse.ArgumentParser(description='Build script for Pydio')
    parser.add_argument('cmd', metavar='cmd', help='a command to run', default="all")

    args = parser.parse_args(args=sys.argv[1:] or ["all"])
    if args.cmd != "all":
        # getattr(__module__, args.cmd)()
        print_path()
        globals()[args.cmd]()
        sys.exit(0)

    create_virtualenv()
    activate_virtualenv()
    print_path()
    if is_win:
        install_pywin32()
    install_requirements()
    # install_qt()
    name = build_installer()
    diagnostics(name)






