# coding=utf-8
# Created 2014 by Janusz Skonieczny 
import logging
import sys
import os
import multiprocessing
import win32service
import win32api
import win32serviceutil
import win32event
import servicemanager

name = "Pydio"
description = "Pydio is an open source software that turns instantly any server (on premise, NAS, cloud IaaS or PaaS) into a file sharing platform for your company. It is an alternative to SaaS Boxes and Drives, with more control, safety and privacy, and favorable TCOs."


def service_target():
    """
    This is a pydio.main wrapper used by the ServiceFramework to startup the app.
    """
    logging.info("Running service target")
    import pydio.main
    pydio.main.main()


class ApplicationSvc(win32serviceutil.ServiceFramework):
    # you can NET START/STOP the service by the following name
    _svc_name_ = name
    # this text shows up as the service name in the Service Control Manager (SCM)
    _svc_display_name_ = name
    # this text shows up as the description in the SCM
    _svc_description_ = description

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        # create an event to listen for stop requests on
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        logging.debug("ApplicationSvc init done")

    def SvcStop(self):
        logging.debug("Attempting to stop service")
        # tell the SCM we're shutting down
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        # fire the stop event
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        logging.debug("Attempting to start service")
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE, servicemanager.PYS_SERVICE_STARTED, (self._svc_name_, ''))
        servicemanager.LogInfoMsg(os.getcwd())
        service_target()

    def _fork_service_process(self):
        """
        Will run service main in a separate process.
        """
        logging.info("Forking process")
        server = multiprocessing.Process(target=service_target)
        server.start()

        # if the stop event hasn't been fired keep looping
        logging.info("Entering service wait loop")
        rc = None
        while rc != win32event.WAIT_OBJECT_0:
            # block for 5 seconds and listen for a stop event
            rc = win32event.WaitForSingleObject(self.hWaitStop, 5000)
            logging.debug("rc: %s" % rc)

        server.terminate()
        server.join()


# called when we're being shut down
def ctrlHandler(ctrlType):
    logging.debug("Shutdown: %s", ctrlType)
    return True


if __name__ == '__main__':
    win32api.SetConsoleCtrlHandler(ctrlHandler, True)
    win32serviceutil.HandleCommandLine(ApplicationSvc)

