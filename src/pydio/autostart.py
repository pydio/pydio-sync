# coding=utf-8
# Created 2014 by Janusz Skonieczny
import logging
import sys
import os


def setup(argv):
    script = os.path.abspath(sys.argv[0])
    executable = sys.executable  # TODO: 01.04.14 wooyek Make sure it's pythonw to run without console
    call = "{} {} {}".format(executable, script, " ".join(argv))
    call = call.replace("--auto-start", "")
    logging.info("Setting up auto start on system startup: %s", call)
    globals()["_setup_"+sys.platform](call)


def _setup_win32(call):
    import _winreg as winreg
    key_name = """Software\Microsoft\Windows\CurrentVersion\Run"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_name, winreg.KEY_WRITE)
    except EnvironmentError:
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_name)
    try:
        winreg.SetValueEx(key, "pydio", None, winreg.REG_SZ, str(call))
    except WindowsError as ex:
        logging.warning("An error occurred during Windows registry change, ensure this process has admin privileges.")
        raise
    winreg.CloseKey(key)
