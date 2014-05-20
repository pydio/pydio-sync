from flask import request, jsonify
from flask.ext.restful import Resource
from pydio.job.job_config import JobConfig
import json
import requests
import keyring
import xmltodict
import types
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
            data = json.load(fp, object_hook=JobConfig.object_decoder)
        if data:
            for j in data:
                jobs[j.uuid()] = j
            self.jobs = jobs
        return jobs

    def save_jobs(self, jobs):
        self.jobs = None
        all_jobs = []
        for k in jobs:
            all_jobs.append(JobConfig.encoder(jobs[k]))
        with open(self.config_file, "w") as fp:
            json.dump(all_jobs, fp, indent=2)


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
        test_job = JobConfig.object_decoder(json_req)
        jobs[test_job.id] = test_job
        self.loader.save_jobs(jobs)
        jobs = self.loader.get_jobs()
        return JobConfig.encoder(test_job)

    def get(self, job_id = None):
        jobs = self.loader.get_jobs()
        if not job_id:
            std_obj = []
            for k in jobs:
                std_obj.append(JobConfig.encoder(jobs[k]))
            return std_obj
        return JobConfig.encoder(jobs[job_id])

    def delete(self, job_id):
        jobs = self.loader.get_jobs()
        del jobs[job_id]
        return job_id + "deleted", 204

    @classmethod
    def make_job_manager(cls, loader):
        cls.loader = loader
        return cls

        #curl --data '{"__type__" : "JobConfig", "id" : 1, "server" : "http://localhost", "workspace" : "ws-watched", "directory" : "/Users/charles/Documents/SYNCTESTS/subfolder", "remote_folder" : "/test", "user" : "Administrator", "password" : "xxxxxx", "direction" : "bi", "active" : true}' http://localhost:5000/jobs  --header 'Content-Type: application/json' --header 'Accept: application/json'