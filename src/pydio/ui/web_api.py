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
import sys
import os
from pathlib import *
from collections import OrderedDict

class PydioApi(Api):

    def __init__(self, server_port):
        self.port = server_port
        if getattr(sys, 'frozen', False):
            static_folder = str( (Path(sys._MEIPASS)) / 'ui' / 'res' )
        else:
            static_folder = 'res'
        logging.debug('Starting Flask server with following static folder : '+ static_folder)
        self.app = Flask(__name__, static_folder = static_folder, static_url_path='/res')
        self.app.logger.setLevel(logging.DEBUG)
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
            url = base + '/api/'+args['ws']+'/ls/?options=d&recursive=true&max_depth=2'
            if 'password' in args:
                auth = (args['user'], args['password'])
            else:
                auth = (args['user'], keyring.get_password(base, args['user']))

        resp = requests.get( url, stream = True, auth=auth )
        o = xmltodict.parse(resp.content)
        if not 'tree' in o or 'message' in o['tree']:
            return [{'error':'Cannot load workspace'}]
        if not 'tree' in o['tree']:
            return []
        if isinstance(o['tree']['tree'], types.DictType):
            return [o['tree']['tree']]
        return o['tree']['tree']


class JobManager(Resource):

    loader = None

    def post(self):
        JobsLoader.Instance().get_jobs()
        json_req = request.get_json()
        new_job = JobConfig.object_decoder(json_req)

        if 'test_path' in json_req:
            from os.path import expanduser
            json_req['directory'] = expanduser("~") + '/Pydio/' + json_req['repoObject']['label']
            return json_req
        elif 'compute_sizes' in json_req:
            dl_rate = 2 * 1024 * 1024
            up_rate = 0.1 * 1024 * 1024
            # COMPUTE REMOTE SIZE
            from pydio.sdk.remote import PydioSdk
            sdk = PydioSdk(json_req['server'], json_req['workspace'], json_req['remote_folder'], '',
                           auth=(json_req['user'], json_req['password']))
            up = [0.0]
            def callback(location, seq_id, change):
                if "node" in change and change["node"]["md5"] != "directory" and change["node"]["bytesize"]:
                    up[0] += float(change["node"]["bytesize"])
            sdk.changes_stream(0, callback)
            # COMPUTE LOCAL SIZE
            down = 0.0
            if os.path.exists(json_req['directory']):
                for dirpath, dirnames, filenames in os.walk(json_req['directory']):
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        try:
                            down += os.path.getsize(fp)
                        except OSError:
                            pass

            json_req['byte_size'] = up[0] + down
            json_req['eta'] = up[0] * 8 / up_rate + down * 8 / dl_rate
            return json_req

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
        data = JobConfig.encoder(jobs[job_id])
        self.enrich_job(data, job_id)
        return data

    def enrich_job(self, job_data, job_id):
        running = PydioScheduler.Instance().is_job_running(job_id)
        job_data['running'] = running
        logger = EventLogger(JobsLoader.Instance().build_job_data_path(job_id))
        last_events = logger.get_all(1, 0)
        if len(last_events):
            job_data['last_event'] = last_events.pop()
        if running:
            job_data['state'] = PydioScheduler.Instance().get_job_progress(job_id)

    def delete(self, job_id):
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
        try:
            job_config = JobsLoader.Instance().get_job(job_id)
        except Exception:
            return "Can't find any job config with this ID.", 404

        dbHandler = LocalDbHandler(JobsLoader.Instance().build_job_data_path(job_id))
        dbHandler.update_node_status(json_conflict['node_path'], json_conflict['status'])
        if not dbHandler.count_conflicts() and job_config.active:
            t = PydioScheduler.Instance().get_thread(job_id)
            if t:
                t.start_now()
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
            if cmd == 'enable' or cmd == 'disable':
                job_config = JobsLoader.Instance().get_job(job_id)
                job_config.active = True if cmd == 'enable' else False
                JobsLoader.Instance().update_job(job_config)
                PydioScheduler.Instance().reload_configs()
            PydioScheduler.Instance().handle_job_signal(self, cmd, job_id)
        else:
            PydioScheduler.Instance().handle_generic_signal(self, cmd)
        return ('success',)