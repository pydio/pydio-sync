from flask import Flask
from flask_restful import Api

from flask import request, redirect
from flask.ext.restful import Resource
from pydio.job.job_config import JobConfig, JobsLoader
from pydio.job.EventLogger import EventLogger
from pydio.job.localdb import LocalDbHandler
from pydio.job.scheduler import PydioScheduler
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

    def __init__(self, server_port):
        self.port = server_port
        self.app = Flask(__name__, static_folder = 'res', static_url_path='/res')
        super(PydioApi, self).__init__(self.app)
        self.add_resource(JobManager, '/','/jobs', '/jobs/<string:job_id>')
        self.add_resource(WorkspacesManager, '/ws/<string:job_id>')
        self.add_resource(FoldersManager, '/folders/<string:job_id>')
        self.add_resource(LogManager, '/jobs/<string:job_id>/logs')
        self.add_resource(ConflictsManager, '/jobs/<string:job_id>/conflicts', '/jobs/conflicts')
        self.add_resource(CmdManager, '/cmd/<string:cmd>/<string:job_id>', '/cmd/<string:cmd>')

    def start_server(self):
        self.app.run(port=self.port)

class WorkspacesManager(Resource):

    def get(self, job_id):
        if job_id != 'request':
            jobs = JobsLoader.Instance().get_jobs()
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


class FoldersManager(Resource):

    def get(self, job_id):
        if job_id != 'request':
            jobs = JobsLoader.Instance().get_jobs()
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


class JobManager(Resource):

    loader = None

    def post(self):
        jobs = JobsLoader.Instance().get_jobs()
        json_req = request.get_json()
        new_job = JobConfig.object_decoder(json_req)
        JobsLoader.Instance().update_job(new_job)
        scheduler = PydioScheduler.Instance()
        scheduler.reload_configs()
        scheduler.disable_job(new_job.id)
        if not 'toggle_status' in json_req:
            JobsLoader.Instance().clear_job_data(new_job.id)
        scheduler.enable_job(new_job.id)
        return JobConfig.encoder(new_job)

    def get(self, job_id = None):
        if request.path == '/':
            return redirect("/res/index.html", code=302)
        jobs = JobsLoader.Instance().get_jobs()
        if not job_id:
            std_obj = []
            for k in jobs:
                data = JobConfig.encoder(jobs[k])
                self.enrich_job(data, k)
                std_obj.append(data)
            return std_obj
        logging.info("Job ID : "+job_id)
        data = JobConfig.encoder(jobs[job_id])
        self.enrich_job(data, job_id)
        return data

    def enrich_job(self, job_data, job_id):
        running = PydioScheduler.Instance().is_job_running(job_id)
        job_data['running'] = running
        logger = EventLogger(JobsLoader.Instance().build_job_data_path(job_id))
        job_data['last_events'] = logger.get_all(2,0)
        if running:
            job_data['state'] = PydioScheduler.Instance().get_job_progress(job_id)

    def delete(self, job_id):
        job_config = JobsLoader.Instance().get_jobs()[job_id]
        JobsLoader.Instance().delete_job(job_id)
        scheduler = PydioScheduler.Instance()
        scheduler.reload_configs()
        scheduler.disable_job(job_id)
        JobsLoader.Instance().clear_job_data(job_id, parent=True)
        return job_id + "deleted", 204


class ConflictsManager(Resource):

    def post(self):
        json_conflict = request.get_json()
        job_id = json_conflict['job_id']
        if not job_id in JobsLoader.Instance().get_jobs():
            return "Can't find any job config with this ID.", 404

        dbHandler = LocalDbHandler(JobsLoader.Instance().build_job_data_path(job_id))
        dbHandler.update_node_status(json_conflict['node_path'], json_conflict['status'])
        return json_conflict

    def get(self, job_id):
        if not job_id in JobsLoader.Instance().get_jobs():
            return "Can't find any job config with this ID.", 404

        dbHandler = LocalDbHandler(JobsLoader.Instance().build_job_data_path(job_id))
        return dbHandler.list_conflict_nodes()


class LogManager(Resource):

    def __init__(self):
        self.events = {}

    def get(self, job_id):
        if not job_id in JobsLoader.Instance().get_jobs():
            return "Can't find any job config with this ID.", 404

        logger = EventLogger(JobsLoader.Instance().build_job_data_path(job_id))
        if not request.args:
            logs = logger.get_all(20,0)
        else:
            filter = request.args.keys()[0]
            filter_parameter = request.args.get(filter)
            logs = logger.filter(filter, filter_parameter)

        tasks = PydioScheduler.Instance().get_job_progress(job_id)
        return {"logs":logs, "running":tasks}


class CmdManager(Resource):

    def get(self, cmd, job_id):
        if job_id:
            PydioScheduler.Instance().handle_job_signal(self, cmd, job_id)
        else:
            PydioScheduler.Instance().handle_generic_signal(self, cmd)
        return ('success',)