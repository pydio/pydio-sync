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

import AppKit
import Quartz
import logging
import sys
from PyObjCTools import AppHelper

if getattr(sys, 'frozen', False):
    NSObject = AppKit.AppKit.NSObject
else:
    NSObject = AppKit.NSObject

class NSListenerObject(NSObject):

    def wsSessionResign(self):
        sessionInfo = Quartz.CGSessionCopyCurrentDictionary()
        uname = sessionInfo.get('kCGSSessionUserNameKey', '')
        logging.info("Session from "+uname+" resigned....")

    def wsSessionActive(self):
        sessionInfo = Quartz.CGSessionCopyCurrentDictionary()
        uname = sessionInfo.get('kCGSSessionUserNameKey', '')
        logging.info("Session from "+uname+" activated....")

def macos_stop_listening_events():
    AppHelper.callAfter(AppHelper.stopEventLoop)


def macos_listen_events():
    """Main Thread grabbing changes from both sides, computing the necessary changes to apply, and applying them"""

#   sessionInfo = Quartz.CGSessionCopyCurrentDictionary()
#   uname = sessionInfo.get('kCGSSessionUserNameKey', '')
#   uconsole = sessionInfo.get('kCGSSessionOnConsoleKey', 0)
#   ulogin = sessionInfo.get('kCGSSessionLoginDoneKey', 0)

    sessionInfo = Quartz.CGSessionCopyCurrentDictionary()
    uname = sessionInfo.get('kCGSSessionUserNameKey', '')
    logging.info("Current session is "+uname)


    logging.info("Listening for workspace events....")
    if hasattr(AppKit, 'AppKit'):
        wsNotifCenter = AppKit.AppKit.NSWorkspace.sharedWorkspace().notificationCenter()
    else:
        wsNotifCenter = AppKit.NSWorkspace.sharedWorkspace().notificationCenter()
    listener = NSListenerObject.new()

    wsNotifCenter.addObserver_selector_name_object_(listener, 'wsSessionResign',
                                                    'NSWorkspaceSessionDidResignActiveNotification', None)
    wsNotifCenter.addObserver_selector_name_object_(listener, 'wsSessionActive',
                                                    'NSWorkspaceSessionDidBecomeActiveNotification', None)

    AppHelper.runConsoleEventLoop(installInterrupt=True)


