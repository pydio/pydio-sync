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

    .filter('bytes', function() {
        return function(bytes, precision) {
            if (bytes == 0) return bytes;
            if (isNaN(parseFloat(bytes)) || !isFinite(bytes)) return bytes;
            if (typeof precision === 'undefined') precision = 1;
            var units = ['bytes', 'kB', 'MB', 'GB', 'TB', 'PB'],
                number = Math.floor(Math.log(bytes) / Math.log(1024));
            return (bytes / Math.pow(1024, Math.floor(number))).toFixed(precision) +  ' ' + units[number];
        }
    })

    .filter('seconds', function(){

        return function(sec){
            if (isNaN(parseFloat(sec)) || !isFinite(sec)) return sec;
            var d=new Date(0,0,0);
            d.setSeconds(+sec);
            return (d.getHours() ? d.getHours()+'h ' : '')+d.getMinutes()+'mn '+d.getSeconds();
        }

    })

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
                templateUrl:'02-Workspace.html'
            })
            .when('/edit/:jobId/step1', {
                controller:'EditCtrl',
                templateUrl:'01-Connection.html'
            })
            .when('/edit/:jobId/step2', {
                controller:'EditCtrl',
                templateUrl:'02-Workspace.html'
            })
            .when('/edit/:jobId/step3', {
                controller:'EditCtrl',
                templateUrl:'03-Advanced.html'
            })
            .when('/edit/:jobId/step4', {
                controller:'EditCtrl',
                templateUrl:'04-Launcher.html'
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

    .controller('ListCtrl', function($scope, $location, $timeout, Jobs, currentJob, Commands) {

        var t2;
        (function tickJobs() {
            var all = Jobs.query(function(){
                $scope.error = null;
                if(!all.length){
                    $location.path('/new');
                    return;
                }
                $scope.jobs = all;
                t2 = $timeout(tickJobs, 2000);
            }, function(response){
                if(!response.status){
                    $scope.error = 'Ooops, cannot contact agent! Make sure it\'s running correctly, we\'ll try to reconnect in 20s';
                    t2 = $timeout(tickJobs, 20000);
                }
            });
        })();

        $scope.$on('$destroy', function(){
            $timeout.cancel(t2);
        });
        /*
        $scope.jobs = Jobs.query(function(resp){
            if(!resp.length) $location.path('/new');
        });
        */
        currentJob.setJob(null);
        $scope.applyCmd = function(cmd, jobId){
            Commands.query({cmd:cmd, job_id:jobId}, function(){
                var newJobs = Jobs.query({}, function(){
                    $scope.jobs = newJobs;
                });
            });
        }

        $scope.toggleJobActive = function(jobId){
            angular.forEach($scope.jobs, function(j){
                if(j.id != jobId) return;
                j.active = !j.active;
                j.toggle_status = true;
                j.$save(function(){
                    $scope.applyCmd((j.active?'enable':'disable'), jobId);
                });
            });
        };

    })

    .controller('ListLogsCtrl', function($scope, $routeParams, $timeout, Jobs, Logs, Conflicts){
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
        $scope.title = $routeParams.jobId;
        $scope.job = Jobs.get({job_id:$routeParams.jobId});
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

    .controller('CreateCtrl', function($scope, $location, $timeout, Jobs, Ws, currentJob) {

        $scope.parseURL = function(){
            if(!$scope.inline_host) return;

            if ($scope.inline_host.indexOf('http://') === 0){
                $scope.inline_protocol = 'http://';
                $scope.inline_host = $scope.inline_host.substr(7)
            } else if ($scope.inline_host.indexOf('https://') === 0){
                $scope.inline_protocol = 'https://';
                $scope.inline_host = $scope.inline_host.substr(8)
            }
            $scope.job.server = $scope.inline_protocol + $scope.inline_host
        };

        var job;
        if(currentJob.getJob() == null){
            job = new Jobs();
            $scope.inline_protocol='https://';
            $scope.inline_host='';
            job.id = 'new';
            job.remote_folder = '';
            job.directory = '';
            job.workspace = '';
            job.direction = 'bi';
            job.label = 'New Job';
            job.__type__ = 'JobConfig'
            $scope.job = job;
            currentJob.setJob($scope.job);
        }else{
            job = $scope.job = currentJob.getJob();
            $scope.inline_host = $scope.job.server;
            $scope.parseURL();
        }
        $scope.next = function(){
            $scope.loading = true;
            $scope.loadWorkspaces();
        }

        $scope.loadWorkspaces = function(){
            if($scope.job.id == 'new' && !$scope.job.password) {
                return;
            }
            $scope.job.workspace = '';
            Ws.get({
                job_id:'request',
                url:$scope.job.server,
                user:$scope.job.user,
                password:$scope.job.password
            }, function(response){
                job.repositories = response.repositories.repo;
                $scope.loading = false;
                $location.path('/edit/new/step2');
            }, function(resp){
                if(resp.data && resp.data.message){
                    $scope.error = resp.data.message;
                } else if(resp.statusText){
                    $scope.error = resp.status;
                }
                $scope.loading = false;
            });
        };

    })

    .controller('EditCtrl', function($scope, $location, $routeParams, $window, $timeout, Jobs, currentJob, Ws, Folders, Commands) {

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
            }, function(resp){
                if(resp[0] && resp[0].error){
                    $scope.folders_loading_error = resp[0].error;
                }
                $scope.folders_loading = false;
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

        $scope.toggleJobActive = function(){
            $scope.job.active = !$scope.job.active;
            Commands.query({cmd:($scope.job.active?'enable':'disable'), job_id:$scope.job.id}, function(){
                $location.path('/')
            });
        };

        $scope.deleteJob = function(){
            if($window.confirm('Are you sure you want to delete this synchro? No data will be deleted')){
                Jobs.delete({job_id:$scope.job.id},function(){
                    $location.path('/')
                });
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
            if(!$scope.job.repositories) {
                $scope.loadWorkspaces();
            }else{
                $scope.repositories = $scope.job.repositories
                if($scope.job.workspace) $scope.loadFolders()
            }
        }

        $scope.save = function(stepName) {
            if($scope.job.repoObject){
                $scope.job.workspace = $scope.job.repoObject['@repositorySlug'];
            }
            var basename = function(path){
                return path.split(/[\\/]/).pop();
            };
            if($scope.job.id == 'new' && stepName && stepName == 'step2') {
                var label;
                if($scope.job.remote_folder && $scope.job.remote_folder != '/'){
                    label = basename($scope.job.remote_folder);
                }else{
                    label = $scope.job.repoObject['label'];
                }
                $scope.job.label = label;
                if(!$scope.job.directory){
                    $scope.job.test_path = true;
                    $scope.job.$save();
                    $scope.job.test_path = false;
                }

                $location.path('/edit/new/step3');
            }else if(stepName == 'step3'){

                delete $scope.job.test_path;
                $scope.job.compute_sizes = true;
                $scope.job.$save();

                $scope.job.byte_size = 'computing...'
                $scope.job.eta = 'computing...'
                $location.path('/edit/new/step4');

            }else if(stepName == 'step4'){


                delete $scope.job.compute_sizes;
                delete $scope.job.id;
                $scope.job.$save(function(){

                    // Update reads
                    var t2;
                    var job_id = $scope.job.id;
                    (function tickJob() {
                        var j = Jobs.get({job_id:job_id}, function(){
                            $scope.job = j;
                            if($scope.job.state){
                                if($scope.job.state.global.queue_length > 0 && $scope.job.state.global.queue_done == $scope.job.state.global.queue_length){
                                    $location.path('/');
                                    return;
                                }
                                $scope.job = j;
                                $scope.job.state.progress = 100 * parseFloat($scope.job.state.global.queue_done) / parseFloat($scope.job.state.global.queue_length)
                            }
                            t2 = $timeout(tickJob, 1000);
                        });
                    })();
                    $scope.$on('$destroy', function(){
                        $timeout.cancel(t2);
                    });

                });


            }else{
                $scope.job.$save();
                $location.path('/');
            }
        };
    });