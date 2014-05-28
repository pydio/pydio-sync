#
#  Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
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
from pydio.job.continous_merger import ContinuousDiffMerger
from pydispatch import dispatcher
from pydio import PUBLISH_SIGNAL, PROGRESS_SIGNAL, COMMAND_SIGNAL

class PydioManager():

    def __init__(self, job_configs, jobs_root_path):
        self.control_threads = []
        self.job_configs = job_configs
        self.jobs_root_path = jobs_root_path

    def startAll(self):

        for job_config in self.job_configs:
            if not job_config.active:
                continue

            job_data_path = self.jobs_root_path / job_config.uuid()
            if not job_data_path.exists():
                job_data_path.mkdir(parents=True)
            job_data_path = str(job_data_path)

            merger = ContinuousDiffMerger(job_config, job_data_path=job_data_path)
            try:
                merger.start()
                self.control_threads.append(merger)
            except (KeyboardInterrupt, SystemExit):
                merger.stop()

    def wire_events(self):
        dispatcher.connect(self.handle_signal, signal=COMMAND_SIGNAL, send=dispatcher.Any)
        pass

    def handle_signal(self, command, job_id):
        pass

    def start_job(self, job_config):
        pass

    def stop_job(self, job_id):
        pass

    def reload_job(self, job_id):
        pass

