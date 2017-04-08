#
# Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
# This file is part of Pydio.
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
import os
import os.path as osp

import logging

from pydispatch import dispatcher

from pydio.job.continous_merger import ContinuousDiffMerger
from pydio import COMMAND_SIGNAL, JOB_COMMAND_SIGNAL
from pydio.utils.pydio_profiler import pydio_profile
from pydio.utils.functions import Singleton, guess_filesystemencoding
from pydio.job import manager


@Singleton
class PydioScheduler(object):
    def __init__(self, jobs_root_path, jobs_loader):
        self.control_threads = {}
        self.jobs_loader = jobs_loader
        self.job_configs = jobs_loader.get_jobs()
        self.jobs_root_path = jobs_root_path
        dispatcher.connect(self.handle_job_signal, signal=JOB_COMMAND_SIGNAL, sender=dispatcher.Any)
        dispatcher.connect(self.handle_generic_signal, signal=COMMAND_SIGNAL, sender=dispatcher.Any)

    @pydio_profile
    def start_all(self):
        for job_id in self.job_configs:
            logging.debug("Starting job {0}".format(job_id))
            job_config = self.job_configs[job_id]
            self.start_from_config(job_config)

    def pause_all(self):
        for job_id in self.control_threads:
            #merger = self.control_threads[job_id]
            #merger.stop()
            self.pause_job(job_id)

    @pydio_profile
    def start_job(self, job_id):
        config = self.get_config(job_id)
        if not config:
            return
        thread = self.get_thread(job_id)
        if not thread:
            self.start_from_config(config)
        else:
            thread.start_now()

    @pydio_profile
    def start_from_config(self, job_config):
        if not job_config.active:
            return

        job_data_path = osp.join(self.jobs_root_path, job_config.id)
        if not osp.isdir(job_data_path):
            os.makedirs(job_data_path)
        job_data_path = job_data_path.decode(guess_filesystemencoding())

        merger = ContinuousDiffMerger(job_config, job_data_path=job_data_path)
        try:
            merger.start()
            self.control_threads[job_config.id] = merger
        except (KeyboardInterrupt, SystemExit):
            merger.stop()

    @pydio_profile
    def is_job_running(self, job_id):
        thread = self.get_thread(job_id)
        if not thread:
            return False
        return thread.is_running()

    @pydio_profile
    def get_job_progress(self, job_id):
        thread = self.get_thread(job_id)
        if not thread:
            return False
        return {
            "global": thread.get_global_progress(),
            "tasks": thread.get_current_tasks(),
            "websocket": thread.get_websocket_status()
        }

    @pydio_profile
    def pause_job(self, job_id):
        thread = self.get_thread(job_id)
        if not thread:
            return
        logging.info("should pause job : %s" %job_id)
        thread.pause()

    @pydio_profile
    def enable_job(self, job_id):
        thread = self.get_thread(job_id)
        if thread:
            thread.start_now()
        elif job_id in self.job_configs:
            self.start_from_config(self.job_configs[job_id])

    @pydio_profile
    def disable_job(self, job_id):
        thread = self.get_thread(job_id)
        if not thread:
            return
        thread.stop()
        self.control_threads.pop(job_id, None)

    def handle_job_signal(self, sender, command, job_id):
        if command == 'start' or command == 'resume':
            self.start_job(job_id)
        elif command == 'pause':
            self.pause_job(job_id)
        elif command == 'enable':
            self.enable_job(job_id)
        elif command == 'disable':
            self.disable_job(job_id)
        elif command == "resync":
            self.disable_job(job_id)
            logging.info("R E S Y N C " + job_id)
            # delete databases
            job_folder = osp.join(str(self.jobs_root_path), job_id)
            for file in os.listdir(job_folder):
                if file in ["pydio.sqlite", "changes.sqlite", "sequences", "history.sqlite", "pydio.sqlite-journal", "changes.sqlite-journal"]:
                    try:
                        os.unlink(osp.join(job_folder, file))
                    except Exception as e:
                        logging.exception(e)
            self.enable_job(job_id)
            self.start_job(job_id)

    def handle_generic_signal(self, sender, command):
        if command == 'reload-configs':
            self.reload_configs()
        elif command == 'pause-all':
            self.pause_all()
            self.reload_configs()
        elif command == 'start-all':
            self.start_all()
        elif command == 'exit':
            logging.info("SHOULD EXIT")
            manager.stop_all()
        else:
            return "This command doesn't exist", 404
        return "success"

    def get_config(self, job_id):
        if job_id in self.job_configs:
            return self.job_configs[job_id]
        return False

    def get_thread(self, job_id):
        if job_id in self.control_threads:
            return self.control_threads[job_id]
        return False

    def reload_configs(self):
        logging.debug("[Scheduler] Reloading config")
        self.jobs_loader.load_config()
        self.job_configs = self.jobs_loader.get_jobs()
