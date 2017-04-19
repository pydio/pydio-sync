#
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
#  The latest code can be found at <http://pyd.io/>.
#

import keyring
import json
import urlparse
import os
import logging
import platform
import unicodedata
try:
    from pydio.utils.functions import Singleton
except ImportError:
    from utils.functions import Singleton


class JobsLoader(object):
    __metaclass__ = Singleton

    config_file = ''
    jobs = None
    data_path = None

    def __init__(self, data_path, config_file=None):
        self.data_path = data_path
        if not config_file:
            self.config_file = os.path.join(data_path, 'configs.json')
        else:
            self.config_file = config_file

    def __contains__(self, id):
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
        if not id_to_get in self.jobs:
            raise Exception("Cannot find job with id %s" % id_to_get)
        return self.jobs[id_to_get]

    def update_job(self, job):
        self.jobs[job.id] = job
        if not os.path.exists(job.directory):
            os.makedirs(job.directory)
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
        return os.path.join(self.data_path, job_id)

    def clear_job_data(self, job_id, parent=False):
        job_data_path = self.build_job_data_path(job_id)
        if os.path.exists(os.path.join(job_data_path, "sequences")):
            os.unlink(os.path.join(job_data_path, "sequences"))
        if os.path.exists(os.path.join(job_data_path, "pydio.sqlite")):
            os.unlink(os.path.join(job_data_path, "pydio.sqlite"))
        if parent and os.path.exists(job_data_path):
            import shutil
            shutil.rmtree(job_data_path)


class JobConfig(object):
    __type__ = "JobConfig"

    def __init__(self, **kw):
        # define instance attributes
        self.id = None  # type int; to-be-initialized

        self.server = kw.get('server', '')
        self.directory = kw.get('directory', '')
        self.workspace = kw.get('workspace', '')
        self.remote_folder = kw.get('remote_folder', '')
        self.user_id = kw.get('user_id', '')
        self.label = kw.get('label', '')
        # Default values
        self.server_configs = kw.get("server_configs", None)
        self.active = kw.get("active", True)
        self.direction = kw.get("direction", "bi")
        self.frequency = kw.get("frequency", 'auto')
        self.start_time = kw.get("start_time", {'h': 0, 'm': 0})
        self.solve = kw.get("solve", 'manual')
        self.monitor = kw.get("monitor", True)
        self.trust_ssl = kw.get("trust_ssl", False)
        self.filters = dict(
            includes=['*'],

            # ***** Exclude Patterns *****
            # .* --> used to store configurations for different applications (.pydio_id, .bashrc, .mozilla)
            #  /recycle_bin* --> recycle bin
            # '~*' --> temp doc files
            # '*.xlk' --> temp excel files
            # '*.tmp' --> windows temp files
            # ~lock.* --> temp lock files
            # .DS_Store --> stores metadata information in mac
            excludes=['.*', '*/.*', '/recycle_bin*', '*.pydio_dl', '*.DS_Store', '.~lock.*', '~*', '*.xlk', '*.tmp']
        )

        self.timeout = kw.get("timeout", 20)  # TODO units???

        self.hide_up_dir = kw.get("hide_up_dir", "false")  # TODO:  use bool
        self.hide_bi_dir = kw.get("hide_bi_dir", 'false')
        self.hide_down_dir = kw.get("hide_down_dir", 'false')

        self.poolsize = kw.get("poolsize", 4)

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def make_id(self):
        i = 1
        base_id = urlparse.urlparse(self.server).hostname + '-' + self.workspace
        test_id = base_id
        while test_id in JobsLoader():
            test_id = base_id + '-' + str(i)
            i += 1
        self.id = test_id

    @staticmethod
    def encoder(self):
        return {"__type__": 'JobConfig',
                "server": self.server,
                "id": self.id,
                "label": self.label if self.label else self.id,
                "workspace": self.workspace,
                "directory": self.directory,
                "remote_folder": self.remote_folder,
                "user": self.user_id,
                "direction": self.direction,
                "frequency": self.frequency,
                "solve": self.solve,
                "start_time": self.start_time,
                "trust_ssl":self.trust_ssl,
                "active": self.active,
                "filters": self.filters,
                "timeout": self.timeout,
                "hide_up_dir": self.hide_up_dir,
                "hide_bi_dir": self.hide_bi_dir,
                "hide_down_dir": self.hide_down_dir,
                "poolsize": self.poolsize
                }

    def load_from_cliargs(self, args):
        self.server = args.server
        self.workspace = args.workspace
        self.directory = args.directory.rstrip('/').rstrip('\\')
        if args.remote_folder:
            self.remote_folder = args.remote_folder.rstrip('/').rstrip('\\')
        else:
            self.remote_folder = ''
        if args.password:
            try:
                keyring.set_password(self.server, args.user, args.password)
            except keyring.errors.PasswordSetError as e:
                logging.error("Error while storing password in keychain, should we store it cyphered in the config?")
        self.user_id = args.user
        if args.direction:
            self.direction = args.direction
        self.make_id()

    @staticmethod
    def object_decoder(d):
        if d.get("__type__") == "JobConfig":
            job_config = JobConfig()
            job_config["server"] = d['server']
            job_config["directory"] = d['directory'].rstrip('/').rstrip('\\')
            if os.name in ["nt", "ce"]:
                job_config["directory"] = job_config["directory"].replace('/', '\\')
            job_config["workspace"] = d['workspace']
            if 'remote_folder' in d:
                job_config["remote_folder"] = d['remote_folder'].rstrip('/').rstrip('\\')
            if 'user' in d:
                job_config["user_id"] = d['user']
            if 'label' in d:
                job_config["label"] = d['label']
            if 'password' in d:
                try:
                    keyring.set_password(job_config["server"], job_config["user_id"], d['password'])
                except keyring.errors.PasswordSetError as e:
                    logging.error(
                        "Error while storing password in keychain, should we store it cyphered in the config?")
            if 'filters' in d:
                if platform.system() == "Darwin":
                    if isinstance(d['filters']['excludes'], list):
                        job_config["filters"]['excludes'] = []
                        for e in d['filters']['excludes']:
                            job_config["filters"]['excludes'].append(unicodedata.normalize('NFD', e))
                    elif isinstance(d['filters']['excludes'], str):
                        job_config["filters"]['excludes'] = unicodedata.normalize('NFD', d['filters']['excludes'])
                    if isinstance(d['filters']['includes'], list):
                        job_config["filters"]['includes'] = []
                        for i in d['filters']['includes']:
                            job_config["filters"]['includes'].append(unicodedata.normalize('NFD', i))
                    elif isinstance(d['filters']['includes'], str):
                        job_config["filters"]['includes'] = unicodedata.normalize('NFD', d['filters']['includes'])
                else:
                    job_config["filters"] = d['filters']
            if 'direction' in d and d['direction'] in ['up', 'down', 'bi']:
                job_config["direction"] = d['direction']
            if 'trust_ssl' in d and d['trust_ssl'] in [True, False]:
                job_config["trust_ssl"] = d['trust_ssl']
            if 'monitor' in d and d['monitor'] in [True, False]:
                job_config["monitor"] = d['monitor']
            if 'frequency' in d and d['frequency'] in ['auto', 'manual', 'time']:
                job_config["frequency"] = d['frequency']
                if job_config["frequency"] == 'time' and 'start_time' in d:
                    job_config["start_time"] = d['start_time']
            if 'solve' in d and d['solve'] in ['manual', 'remote', 'local', 'both']:
                job_config["solve"] = d['solve']
            if 'active' in d and d['active'] in [True, False]:
                job_config["active"] = d['active']
            if 'id' not in d:
                job_config["make_id"]()
            else:
                job_config["id"] = d['id']
            if 'timeout' in d:
                try:
                    job_config["timeout"] = int(d['timeout'])
                except ValueError:
                    job_config["timeout"] = 20
            else:
                job_config["timeout"] = 20
            if job_config["frequency"] == 'auto' or job_config["frequency"] == 'time':
                job_config["monitor"] = True
            else:
                job_config["monitor"] = False
            if 'hide_up_dir' in d:
                job_config["hide_up_dir"] = d['hide_up_dir']
            if 'hide_bi_dir' in d:
                job_config["hide_bi_dir"] = d['hide_bi_dir']
            if 'hide_down_dir' in d:
                job_config["hide_down_dir"] = d['hide_down_dir']
            if 'poolsize' in d:
                job_config["poolsize"] = d['poolsize']
            else:
                job_config["poolsize"] = 4
            if 'poll_interval' in d:
                job_config["online_timer"] = d['poll_interval']
            else:
                job_config["online_timer"] = 10
            return job_config
        return d
