angular.module('project', ['ngRoute', 'ngResource'])


    .factory('Jobs', ['$resource',
        function($resource){
            return $resource('/jobs/:job_id/', {}, {
                query: {method:'GET', params:{job_id:''}, isArray:true}
            });
        }])

    .factory('Logs', ['$resource',
        function($resource){
            return $resource('/jobs/:job_id/logs', {}, {
                query: {method:'GET', params:{job_id:''}, isArray:false}
            });
        }])

    .factory('Conflicts', ['$resource',
        function($resource){
            return $resource('/jobs/:job_id/conflicts', {}, {
                query: {method:'GET', params:{job_id:''}, isArray:true}
            });
        }])

    .factory('Commands', ['$resource',
        function($resource){
            return $resource('/cmd/:cmd/:job_id', {}, {
                query: {method:'GET', params:{job_id:''}, isArray:true}
            });
        }])

    .service('currentJob', function() {
        var objectValue = null;
        return {
            getJob: function() {
                return objectValue;
            },
            setJob: function(value) {
                objectValue = value;
            }
        }
    })

    .factory('Ws', ['$resource',
        function($resource){
            return $resource('/ws/:job_id/', {}, {
                query: {method:'GET', params:{
                    job_id:''
                }}
            });
        }])

    .factory('Folders', ['$resource',
        function($resource){
            return $resource('/folders/:job_id/', {}, {
                query: {method:'GET', params:{
                    job_id:'',
                    url   :'',
                    ws    :'',
                    user  :'',
                    password:''
                }, isArray:true}
            });
        }])

    .config(function($routeProvider) {
        $routeProvider
            .when('/', {
                controller:'ListCtrl',
                templateUrl:'list.html'
            })
            .when('/edit/:jobId/full', {
                controller:'EditCtrl',
                templateUrl:'03-Workspace.html'
            })
            .when('/edit/:jobId/step1', {
                controller:'EditCtrl',
                templateUrl:'01-Connection.html'
            })
            .when('/edit/:jobId/step2', {
                controller:'EditCtrl',
                templateUrl:'02-Credentials.html'
            })
            .when('/edit/:jobId/step3', {
                controller:'EditCtrl',
                templateUrl:'03-Workspace.html'
            })
            .when('/summary/:jobId', {
                controller:'EditCtrl',
                templateUrl:'04-Summary.html'
            })
            .when('/new', {
                controller:'CreateCtrl',
                templateUrl:'01-Connection.html'
            })
            .when('/logs/:jobId',{
                controller:'ListLogsCtrl',
                templateUrl:'logs.html'
            })
            .otherwise({
                redirectTo:'/'
            });
    })

    .controller('ListCtrl', function($scope, $location, Jobs, currentJob, Commands) {
        $scope.jobs = Jobs.query(function(resp){
            if(!resp.length) $location.path('/new');
        });
        currentJob.setJob(null);
        $scope.toggleJobActive = function(jobId){
            angular.forEach($scope.jobs, function(j){
                if(j.id != jobId) return;
                j.active = !j.active;
                j.$save(function(){
                    Commands.query({cmd:(j.active?'enable':'disable'), job_id:jobId}, function(){
                        var newJobs = Jobs.query({}, function(){
                            $scope.jobs = newJobs;
                        });
                    });
                });
            });
        };
        $scope.deleteJob = function(jobId){
            angular.forEach($scope.jobs, function(j){
                if(j.id != jobId) return;
                j.active = !j.active;
                j.$delete({job_id:jobId});
            });
        };
        $scope.applyCmd = function(cmd, jobId){
            Commands.query({cmd:cmd, job_id:jobId}, function(){
                var newJobs = Jobs.query({}, function(){
                    $scope.jobs = newJobs;
                });
            });
        }

    })

    .controller('ListLogsCtrl', function($scope, $routeParams, $timeout, Logs, Conflicts){
        var tO;
        var t1;
        (function tickLog() {
            var all = Logs.query({job_id:$routeParams.jobId}, function(){
                $scope.error = null;
                $scope.logs = all.logs;
                $scope.running = all.running;
                tO = $timeout(tickLog, 2000);
            }, function(response){
                if(!response.status){
                    $scope.error = 'Ooops, cannot contact agent! Make sure it\'s running correctly, we\'ll try to reconnect in 20s';
                    tO = $timeout(tickLog, 20000);
                }
            });
        })();
        (function tickConflict() {
            var conflicts = Conflicts.query({job_id:$routeParams.jobId}, function(){
                $scope.conflicts = conflicts;
                t1 = $timeout(tickConflict, 3000);
            });
        })();
        $scope.$on('$destroy', function(){
            $timeout.cancel(tO);
            $timeout.cancel(t1);
        });
        $scope.job_id = $routeParams.jobId;
        $scope.solveConflict = function(nodeId, status){
            angular.forEach($scope.conflicts, function(conflict){
                if(conflict.node_id != nodeId) return;
                conflict.status = status;
                conflict.job_id = $routeParams.jobId;
                conflict.$save();
            });
        };
    })

    .controller('CreateCtrl', function($scope, $location, $timeout, Jobs, currentJob) {
        var job = new Jobs();
        job.id = 'new';
        job.remote_folder = '/';
        job.directory = '';
        job.workspace = '';
        job.__type__ = 'JobConfig'
        $scope.job = job;
        currentJob.setJob($scope.job);
    })

    .controller('EditCtrl', function($scope, $location, $routeParams, Jobs, currentJob, Ws, Folders) {
        $scope.loadFolders = function(){
            if($scope.job.repoObject && $scope.job.repoObject['@repositorySlug'] != $scope.job.workspace){
                $scope.job.workspace = $scope.job.repoObject['@repositorySlug'];
            }
            $scope.folders_loading = true;
            $scope.folders_loading_error = '';
            $scope.folders = Folders.query({
                job_id:'request',
                url:$scope.job.server,
                user:$scope.job.user,
                password:$scope.job.password,
                ws:$scope.job.workspace
            }, function(resp){
                if(resp[0] && resp[0].error){
                    $scope.folders_loading_error = resp[0].error;
                }
                $scope.folders_loading = false;
            });
        };

        $scope.loadWorkspaces = function(){
            if($scope.job.id == 'new' && !$scope.job.password) {
                return;
            }
            Ws.get({
                job_id:'request',
                url:$scope.job.server,
                user:$scope.job.user,
                password:$scope.job.password
            }, function(response){
                $scope.repositories = response.repositories.repo;
                angular.forEach($scope.repositories, function(r){
                    if(r['@repositorySlug'] == $scope.job.workspace){
                        $scope.job.repoObject = r;
                    }
                });
                $scope.loadFolders();
            });
        };

        $scope.openDirChooser = function(){

            var res;
            if(!window.PydioQtFileDialog) {
                res = window.prompt('Full path to the local folder');
            }else{
                res = window.PydioQtFileDialog.getPath();
            }
            if(res){
                $scope.job.directory = res;
            }

        };

        $scope.pathes = {};
        $scope.jobs = Jobs.query();
        if(!currentJob.getJob()){
            currentJob.setJob(Jobs.get({
                job_id:$routeParams.jobId
            }, function(resp){
                $scope.job = resp;
                //$scope.loadWorkspaces();
            }));
        }else{
            $scope.job = currentJob.getJob();
            if($scope.job.id == 'new') {
                $scope.loadWorkspaces();
            }
        }

        $scope.save = function() {
            if($scope.job.repoObject){
                $scope.job.workspace = $scope.job.repoObject['@repositorySlug'];
            }
            if($scope.job.id == 'new') {
                delete $scope.job.id;
                $scope.job.$save(function(resp){
                    $location.path('/summary/'+resp.id);
                });
            }else{
                $scope.job.$save();
                $location.path('/');
            }
        };
    });