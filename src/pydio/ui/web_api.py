#
# Copyright 2007-2014 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
# This file is part of Pydio.
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

from flask import Flask
from flask_restful import Api

from flask import request, redirect, Response
from flask.ext.restful import Resource
from requests.exceptions import SSLError, ProxyError, TooManyRedirects, ChunkedEncodingError, ContentDecodingError, \
    InvalidSchema, InvalidURL, Timeout, RequestException
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
from pydio.utils.global_config import ConfigManager
from pydio.utils.functions import connection_helper
from pydio.utils import i18n
_ = i18n.language.ugettext

class PydioApi(Api):

    def __init__(self, server_port):
        self.port = server_port
        self.running = False
        if getattr(sys, 'frozen', False):
            static_folder = str( (Path(sys._MEIPASS)) / 'ui' / 'res' )
        else:
            static_folder = 'res'
        logging.debug('Starting Flask server with following static folder : '+ static_folder)
        self.app = Flask(__name__, static_folder=static_folder, static_url_path='/res')
        self.app.logger.setLevel(logging.ERROR)
        l = logging.getLogger("werkzeug")
        if l:
            l.setLevel(logging.ERROR)
        super(PydioApi, self).__init__(self.app)
        self.add_resource(JobManager, '/', '/jobs', '/jobs/<string:job_id>')
        self.add_resource(WorkspacesManager, '/ws/<string:job_id>')
        self.add_resource(FoldersManager, '/folders/<string:job_id>')
        self.add_resource(LogManager, '/jobs/<string:job_id>/logs')
        self.add_resource(ConflictsManager, '/jobs/<string:job_id>/conflicts', '/jobs/conflicts')
        self.add_resource(CmdManager, '/cmd/<string:cmd>/<string:job_id>', '/cmd/<string:cmd>')
        self.app.add_url_rule('/res/i18n.js', 'i18n', self.serve_i18n_file)

    def serve_i18n_file(self):
        s = ''
        from pydio.utils.i18n import get_languages
        import json
        languages = get_languages()
        short_lang = []
        for l in languages:
            short_lang.append(l.split('_')[0])

        if getattr(sys, 'frozen', False):
            static_folder = (Path(sys._MEIPASS)) / 'ui' / 'res'
        else:
            static_folder = Path(__file__).parent / 'res'

        with open(str(static_folder / 'i18n.js')) as js:
            for line in js:
                s += line

        s += '\n'
        s += 'window.PydioEnvLanguages = ' + json.dumps(short_lang) + ';'
        resp = Response(response=s,
                        status=200,
                        mimetype="text/javascript")
        return resp

    def start_server(self):
        try:
            self.running = True
            self.app.run(port=self.port)
        except Exception:
            self.running = False
            logging.exception("Error while starting web server")

    def shutdown_server(self):
        logging.debug("Shutdown api server: %s" % self.app)
        with self.app.test_request_context():
            func = request.environ.get('werkzeug.server.shutdown')
            if func is None:
                raise RuntimeError('Not running with the Werkzeug Server')
            func()

class WorkspacesManager(Resource):

    def get(self, job_id):
        if job_id != 'request':
            jobs = JobsLoader.Instance().get_jobs()
            if not job_id in jobs:
                return {"error": "Cannot find job"}
            job = jobs[job_id]

            url = job.server + '/api/pydio/state/user/repositories?format=json'
            auth = (job.user_id, keyring.get_password(job.server, job.user_id))
            verify = not job.trust_ssl
        else:
            args = request.args
            base = args['url'].rstrip('/')
            verify = False if args['trust_ssl'] == 'true' else True
            url = base + '/api/pydio/state/user/repositories?format=json'
            if 'password' in args:
                auth = (args['user'], args['password'])
            else:
                auth = (args['user'], keyring.get_password(base, args['user']))

        if verify and "REQUESTS_CA_BUNDLE" in os.environ:
            verify = os.environ["REQUESTS_CA_BUNDLE"]
        try:
            resp = requests.get(url,stream=True,auth=auth,verify=verify)
            resp.raise_for_status()
            data = json.loads(resp.content)
            if 'repositories' in data and 'repo' in data['repositories']:
                if isinstance(data['repositories']['repo'], types.DictType):
                    data['repositories']['repo'] = [data['repositories']['repo']]
                data['repositories']['repo'] = filter(lambda x: not x['@access_type'].startswith('ajxp_'), data['repositories']['repo'])
            return data
        except requests.HTTPError:
            r = resp.status_code
            message = "Couldn't load your workspaces, check your server !"
            if r == 404:
                message = "Server not found, is it up and has Pydio installed ?"
            elif r == 401:
                message = "Check your login and password"
            elif r == 403:
                message = "Access to the server is forbidden"
            elif r == 500 or r == 408:
                message = "Server seems to be down..."
            logging.debug("Error while loading workspaces : " + message)
            return {'error': message}, resp.status_code
        except SSLError as rt:
            logging.error(rt.message)
            return {'error': _("An SSL error happened! Is your server using a self-signed certificate? In that case please check 'Trust SSL certificate'")}, 400
        except ProxyError as rt:
            logging.error(rt.message)
            return {'error': _('A proxy error happened, please check the logs')}, 400
        except TooManyRedirects as rt:
            logging.error(rt.message)
            return {'error': _('Connection error: too many redirects')}, 400
        except ChunkedEncodingError as rt:
            logging.error(rt.message)
            return {'error': _('Chunked encoding error, please check the logs')}, 400
        except ContentDecodingError as rt:
            logging.error(rt.message)
            return {'error': _('Content Decoding error, please check the logs')}, 400
        except InvalidSchema as rt:
            logging.error(rt.message)
            return {'error': _('Http connection error: invalid schema.')}, 400
        except InvalidURL as rt:
            logging.error(rt.message)
            return {'error': _('Http connection error: invalid URL.')}, 400
        except Timeout as to:
            logging.error(to)
            return {'error': _('Connection timeout!')}, 400
        except RequestException as ree:
            logging.error(ree.message)
            return {'error': _('Cannot resolve domain!')}, 400


class FoldersManager(Resource):

    def get(self, job_id):
        if job_id != 'request':
            jobs = JobsLoader.Instance().get_jobs()
            if not job_id in jobs:
                return {"error":"Cannot find job"}
            job = jobs[job_id]
            url = job.server + '/api/'+job.workspace+'/ls/?options=d&recursive=true'
            auth = (job.user_id, keyring.get_password(job.server, job.user_id))
            verify = not job.trust_ssl
        else:
            args = request.args
            base = args['url'].rstrip('/')
            verify = False if args['trust_ssl'] == 'true' else True
            url = base + '/api/'+args['ws']+'/ls/?options=d&recursive=true&max_depth=2'
            if 'password' in args:
                auth = (args['user'], args['password'])
            else:
                auth = (args['user'], keyring.get_password(base, args['user']))

        if verify and "REQUESTS_CA_BUNDLE" in os.environ:
            verify = os.environ["REQUESTS_CA_BUNDLE"]
        resp = requests.get( url, stream = True, auth=auth, verify=verify)
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
            trust_ssl = False
            if 'trust_ssl' in json_req:
                trust_ssl = json_req['trust_ssl']
            sdk = PydioSdk(json_req['server'], json_req['workspace'], json_req['remote_folder'], '',
                           auth=(json_req['user'], json_req['password']),
                           device_id=ConfigManager.Instance().get_device_id(),
                           skip_ssl_verify=trust_ssl)
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
                std_obj.append({'is_connected_to_internet': connection_helper.internet_ok})
            return std_obj
        data = JobConfig.encoder(jobs[job_id])
        self.enrich_job(data, job_id)
        data.append({'is_connected_to_internet': connection_helper.internet_ok})
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

    def get(self, cmd, job_id=None):
        if job_id:
            if cmd == 'enable' or cmd == 'disable':
                job_config = JobsLoader.Instance().get_job(job_id)
                job_config.active = True if cmd == 'enable' else False
                JobsLoader.Instance().update_job(job_config)
                PydioScheduler.Instance().reload_configs()
            PydioScheduler.Instance().handle_job_signal(self, cmd, job_id)
        else:
            return PydioScheduler.Instance().handle_generic_signal(self, cmd)
        return ('success',)
