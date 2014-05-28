from flask import request, redirect
from flask.ext.restful import Resource
from pydio.job.job_config import JobConfig
from pydio.job.EventLogger import EventLogger
from pydio.job.localdb import LocalDbHandler
import json
import requests
import keyring
import xmltodict
import types
import logging
from collections import OrderedDict

class JobsLoader():

    config_file = ''
    jobs = None

    def __init__(self, config_file):
        self.config_file = config_file

    def get_jobs(self):
        if self.jobs:
            return self.jobs
        jobs = {}
        if not self.config_file:
            return jobs
        with open(self.config_file) as fp:
            jobs = json.load(fp, object_hook=JobConfig.object_decoder)
            self.jobs = jobs
        return jobs

    def save_jobs(self, jobs):
        self.jobs.update(jobs)
        with open(self.config_file, "w") as fp:
            json.dump(self.jobs, fp, default=JobConfig.encoder, indent=2)


class WorkspacesManager(Resource):

    def get(self, job_id):
        if job_id != 'request':
            jobs = self.loader.get_jobs()
            if not job_id in jobs:
                return {"error":"Cannot find job"}
            job = jobs[job_id]

            url = job.server + '/api/pydio/state/user/repositories?format=json'
            auth = (job.user_id, keyring.get_password(job.server, job.user_id))
        else:
            args = request.args
            base = args['url'].rstrip('/')
            url = base + '/api/pydio/state/user/repositories?format=json'
            if 'password' in args:
                auth = (args['user'], args['password'])
            else:
                auth = (args['user'], keyring.get_password(base, args['user']))

        resp = requests.get(url,stream = True,auth=auth)
        data = json.loads(resp.content)
        return data

    @classmethod
    def make_ws_manager(cls, loader):
        cls.loader = loader
        return cls

class FoldersManager(Resource):

    def get(self, job_id):
        if job_id != 'request':
            jobs = self.loader.get_jobs()
            if not job_id in jobs:
                return {"error":"Cannot find job"}
            job = jobs[job_id]
            url = job.server + '/api/'+job.workspace+'/ls/?options=d&recursive=true'
            auth = (job.user_id, keyring.get_password(job.server, job.user_id))
        else:
            args = request.args
            base = args['url'].rstrip('/')
            url = base + '/api/'+args['ws']+'/ls/?options=d&recursive=true'
            if 'password' in args:
                auth = (args['user'], args['password'])
            else:
                auth = (args['user'], keyring.get_password(base, args['user']))

        resp = requests.get( url, stream = True, auth=auth )
        o = xmltodict.parse(resp.content)
        if not 'tree' in o or 'message' in o['tree']:
            return [{'error':'Cannot load workspace'}];
        if not 'tree' in o['tree']:
            return []
        if isinstance(o['tree']['tree'], types.DictType):
            return [o['tree']['tree']]
        return o['tree']['tree']

    @classmethod
    def make_folders_manager(cls, loader):
        cls.loader = loader
        return cls



class JobManager(Resource):

    loader = None

    def post(self):
        jobs = self.loader.get_jobs()
        json_req = request.get_json()
        new_job = JobConfig.object_decoder(json_req)
        jobs[new_job.id] = new_job
        self.loader.save_jobs(jobs)
        return JobConfig.encoder(new_job)

    def get(self, job_id = None):
        if request.path == '/':
            return redirect("/res/index.html", code=302)
        jobs = self.loader.get_jobs()
        if not job_id:
            std_obj = []
            for k in jobs:
                std_obj.append(JobConfig.encoder(jobs[k]))
            return std_obj
        logging.info("Job ID : "+job_id)
        return JobConfig.encoder(jobs[job_id])

    def delete(self, job_id):
        jobs = self.loader.get_jobs()
        del jobs[job_id]
        return job_id + "deleted", 204

    @classmethod
    def make_job_manager(cls, loader):
        cls.loader = loader
        return cls

class ConflictsManager(Resource):

    def post(self):
        json_conflict = request.get_json()
        job_id = json_conflict['job_id']
        if not job_id in self.loader.get_jobs():
            return "Can't find any job config with this ID.", 404

        dbHandler = LocalDbHandler(str(self.data_path)+ '/' + job_id)
        dbHandler.update_node_status(json_conflict['node_path'], json_conflict['status'])
        return json_conflict

    def get(self, job_id):
        if not job_id in self.loader.get_jobs():
            return "Can't find any job config with this ID.", 404

        dbHandler = LocalDbHandler(str(self.data_path)+ '/' + job_id)
        return dbHandler.list_conflict_nodes()

    @classmethod
    def make_conflicts_manager(cls, loader, data_path):
        cls.loader = loader
        cls.data_path = data_path
        return cls

class LogManager(Resource):

    def __init__(self):
        self.events = {}

    def get(self, job_id):
        if job_id in self.loader.get_jobs():
            logger = EventLogger(str(self.data_path)+ '/' + job_id)
            if not request.args:
                return logger.get_all()
            else:
                filter = request.args.keys()[0]
                filter_parameter = request.args.get(filter)
                return logger.filter(filter, filter_parameter)
        else:
            return "Can't find any job config with this ID.", 404

    @classmethod
    def make_log_manager(cls, loader, data_path):
        cls.loader = loader
        cls.data_path = data_path
        return cls