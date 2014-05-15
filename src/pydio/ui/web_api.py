from flask import request, jsonify
from flask.ext.restful import Resource
from pydio.job import job_config

jobs = {}

class JobManager(Resource):

    def post(self):
        json_req = request.get_json()
        test_job = job_config.JobConfig.object_decoder(json_req)
        jobs[test_job.id] = test_job
        return job_config.JobConfig.encoder(test_job)

    def get(self, job_id = None):
        if not job_id:
            std_obj = []
            for k in jobs:
                std_obj.append(job_config.JobConfig.encoder(jobs[k]))
            return std_obj
        return job_config.JobConfig.encoder(jobs[job_id])

    def delete(self, job_id):
        del jobs[job_id]
        return job_id + "deleted", 204

#curl --data '{"__type__" : "JobConfig", "id" : 1, "server" : "http://localhost", "workspace" : "ws-watched", "directory" : "/Users/charles/Documents/SYNCTESTS/subfolder", "remote_folder" : "/test", "user" : "Administrator", "password" : "xxxxxx", "direction" : "bi", "active" : true}' http://localhost:5000/jobs  --header 'Content-Type: application/json' --header 'Accept: application/json'