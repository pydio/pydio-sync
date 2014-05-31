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
import logging
from collections import OrderedDict
from pydispatch import dispatcher
from pydio import PUBLISH_SIGNAL, PROGRESS_SIGNAL, COMMAND_SIGNAL, JOB_COMMAND_SIGNAL

class PydioApi(Api):

    def __init__(self, jobs_loader, jobs_root_path, server_port, pydio_scheduler):
        self.port = server_port
        self.app = Flask(__name__, static_folder = 'res', static_url_path='/res')
        super(PydioApi, self).__init__(self.app)
        job_manager = JobManager.make_job_manager(jobs_loader, pydio_scheduler)
        ws_manager = WorkspacesManager.make_ws_manager(jobs_loader)
        folders_manager = FoldersManager.make_folders_manager(jobs_loader)
        logs_manager = LogManager.make_log_manager(jobs_loader, jobs_root_path)
        conflicts_manager = ConflictsManager.make_conflicts_manager(jobs_loader, jobs_root_path)
        cmd_manager = CmdManager.make_cmd_manager(pydio_scheduler)
        self.add_resource(job_manager, '/','/jobs', '/jobs/<string:job_id>')
        self.add_resource(ws_manager, '/ws/<string:job_id>')
        self.add_resource(folders_manager, '/folders/<string:job_id>')
        self.add_resource(logs_manager, '/jobs/<string:job_id>/logs')
        self.add_resource(conflicts_manager, '/jobs/<string:job_id>/conflicts', '/jobs/conflicts')
        self.add_resource(CmdManager, '/cmd/<string:cmd>/<string:job_id>', '/cmd/<string:cmd>')

    def start_server(self):
        self.app.run(port=self.port)

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
        if 'repositories' in data and 'repo' in data['repositories'] and isinstance(data['repositories']['repo'], types.DictType):
            data['repositories']['repo'] = [data['repositories']['repo']]

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
        logging.info(json_req)
        new_job = JobConfig.object_decoder(json_req)
        jobs[new_job.id] = new_job
        self.loader.save_jobs(jobs)
        self.scheduler.reload_configs()
        return JobConfig.encoder(new_job)

    def get(self, job_id = None):
        if request.path == '/':
            return redirect("/res/index.html", code=302)
        jobs = self.loader.get_jobs()
        if not job_id:
            std_obj = []
            for k in jobs:
                data = JobConfig.encoder(jobs[k])
                data['running'] = self.scheduler.is_job_running(k)
                std_obj.append(data)
            return std_obj
        logging.info("Job ID : "+job_id)
        data = JobConfig.encoder(jobs[job_id])
        data['running'] = self.scheduler.is_job_running(job_id)
        return data

    def delete(self, job_id):
        jobs = self.loader.get_jobs()
        del jobs[job_id]
        self.loader.save_jobs(jobs)
        self.scheduler.reload_configs()
        return job_id + "deleted", 204

    @classmethod
    def make_job_manager(cls, loader, scheduler):
        cls.loader = loader
        cls.scheduler = scheduler
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

class CmdManager(Resource):

    def get(self, cmd, job_id):
        if job_id:
            self.scheduler.handle_job_signal(self, cmd, job_id)
        else:
            self.scheduler.handle_generic_signal(self, cmd)
        return ('success',)

    @classmethod
    def make_cmd_manager(cls, scheduler):
        cls.scheduler = scheduler
        return cls
