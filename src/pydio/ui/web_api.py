from flask import Flask
from flask_restful import Api

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
from collections import OrderedDict

class PydioApi(Api):

    def __init__(self, jobs_root_path, server_port):
        self.port = server_port
        jobs_loader = JobsLoader(str(jobs_root_path / 'configs.json'))
        self.app = Flask(__name__, static_folder = 'res', static_url_path='/res')
        super(PydioApi, self).__init__(self.app)
        job_manager = JobManager.make_job_manager(jobs_loader)
        ws_manager = WorkspacesManager.make_ws_manager(jobs_loader)
        folders_manager = FoldersManager.make_folders_manager(jobs_loader)
        logs_manager = LogManager.make_log_manager(jobs_loader, jobs_root_path)
        conflicts_manager = ConflictsManager.make_conflicts_manager(jobs_loader, jobs_root_path)
        self.add_resource(job_manager, '/','/jobs', '/jobs/<string:job_id>')
        self.add_resource(ws_manager, '/ws/<string:job_id>')
        self.add_resource(folders_manager, '/folders/<string:job_id>')
        self.add_resource(logs_manager, '/jobs/<string:job_id>/logs')
        self.add_resource(conflicts_manager, '/jobs/<string:job_id>/conflicts', '/jobs/conflicts')

    def start_server(self):
        self.app.run(port=self.port)

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
        if request.path == '/':
            return redirect("/res/index.html", code=302)
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