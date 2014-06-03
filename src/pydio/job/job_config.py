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

import keyring
import json
import urlparse
import os
from pydio.utils.functions import Singleton

@Singleton
class JobsLoader():

    config_file = ''
    jobs = None
    data_path = None

    def __init__(self, data_path, config_file=None):
        self.data_path = data_path
        if not config_file:
            self.config_file = data_path + '/configs.json'
        else:
            self.config_file = config_file

    def contains_job(self, id):
        if self.jobs:
            if id in self.jobs:
                return True
        return False

    def load_config(self):
        if not os.path.exists(self.config_file):
            self.jobs = {}
            return
        with open(self.config_file) as fp:
            jobs = json.load(fp, object_hook=JobConfig.object_decoder)
            self.jobs = jobs

    def get_jobs(self):
        if self.jobs:
            return self.jobs
        jobs = {}
        if not self.config_file:
            return jobs
        self.load_config()
        return self.jobs

    def get_job(self, id_to_get):
        if not id in self.jobs:
            return "no job with this id"
        return self.jobs[id_to_get]

    def update_job(self, job):
        self.jobs[job.id] = job
        self.save_jobs()

    def delete_job(self, job_id):
        if self.jobs and job_id in self.jobs:
            del self.jobs[job_id]
            self.save_jobs()

    def save_jobs(self, jobs=None):
        if jobs:
            if self.jobs:
                self.jobs.update(jobs)
            else:
                self.jobs = jobs
        with open(self.config_file, "w") as fp:
            json.dump(self.jobs, fp, default=JobConfig.encoder, indent=2)

    def build_job_data_path(self, job_id):
        return self.data_path + '/' + job_id

    def clear_job_data(self, job_id, parent=False):
        job_data_path = self.build_job_data_path(job_id)
        if os.path.exists(job_data_path + "/sequences"):
            os.remove(job_data_path + "/sequences")
        if os.path.exists(job_data_path + "/pydio.sqlite"):
            os.remove(job_data_path + "/pydio.sqlite")
        if parent and os.path.exists(job_data_path):
            os.rmdir(job_data_path)



class JobConfig:

    def __init__(self):
        # define instance attributes
        self.server = ''
        self.directory = ''
        self.workspace = ''
        self.remote_folder = ''
        self.user_id = ''
        # Default values
        self.active = True
        self.direction = 'bi'
        self.monitor = True
        self.filters = dict(
            includes=['*'],
            excludes=['.*', '*/.*', '/recycle_bin*', '*.pydio_dl', '*.DS_Store', '.~lock.*']
        )

    def make_id(self):
        i = 1
        test_id = urlparse.urlparse(self.server).hostname + '-' + self.workspace + '-' + str(i)
        while JobsLoader.Instance().contains_job(test_id):
            test_id.replace(str(i), str(i+1))
        self.id = test_id

    def encoder(obj):
        if isinstance(obj, JobConfig):
            return {"__type__"      : 'JobConfig',
                    "server"        : obj.server,
                    "id"            : obj.id,
                    "workspace"     : obj.workspace,
                    "directory"     : obj.directory,
                    "remote_folder" : obj.remote_folder,
                    "user"          : obj.user_id,
                    "direction"     : obj.direction,
                    "active"        : obj.active}
        raise TypeError(repr(JobConfig) + " can't be encoded")

    def load_from_cliargs(self, args):
        self.server = args.server
        self.workspace = args.workspace
        self.directory = args.directory.rstrip('/').rstrip('\\')
        if args.remote_folder:
            self.remote_folder = args.remote_folder.rstrip('/').rstrip('\\')
        else:
            self.remote_folder = ''
        if args.password:
            keyring.set_password(self.server, args.user, args.password)
        self.user_id = args.user
        if args.direction:
            self.direction = args.direction
        self.make_id()
        self.__type__ = "JobConfig"

    @staticmethod
    def object_decoder(obj):
        if '__type__' in obj and obj['__type__'] == 'JobConfig':
            job_config = JobConfig()
            job_config.server = obj['server']
            job_config.directory = obj['directory'].rstrip('/').rstrip('\\')
            job_config.workspace = obj['workspace']
            if 'remote_folder' in obj:
                job_config.remote_folder = obj['remote_folder'].rstrip('/').rstrip('\\')
            if 'user' in obj:
                job_config.user_id = obj['user']
            if 'password' in obj:
                keyring.set_password(job_config.server, job_config.user_id, obj['password'])
            if 'filters' in obj:
                job_config.filters = obj['filters']
            if 'direction' in obj and obj['direction'] in ['up', 'down', 'bi']:
                job_config.direction = obj['direction']
            if 'monitor' in obj and obj['monitor'] in [True, False]:
                job_config.monitor = obj['monitor']
            if 'active' in obj and obj['active'] in [True, False]:
                job_config.active = obj['active']
            if 'id' not in obj:
                job_config.make_id()
            else:
                job_config.id = obj['id']
            return job_config
        return obj