function debug(){
    // adds a cute random color to the pydio brand header
    document.querySelector("a.navbar-brand").style.backgroundColor = '#'+Math.random().toString(16).slice(-6);
}

window.translate = function(string){
    var lang;
    if(window.PydioLangs){
        if(window.PydioEnvLanguages && window.PydioEnvLanguages.length && window.PydioLangs[window.PydioEnvLanguages[0]]){
            lang = window.PydioEnvLanguages[0];
        }else{
            var test = navigator.browserLanguage?navigator.browserLanguage:navigator.language;
            if(test && window.PydioLangs[test]) lang = test;
        }
        if(lang && window.PydioLangs[lang][string]){
            string = window.PydioLangs[lang][string];
        }

    }
    var i = 1;
    while(string.indexOf('%'+i) > -1 && arguments.length > i){
        string = string.replace('%'+i, arguments[i]);
        i++;
    }
    //debug(); // TODO:, FIXME: REMOVE FOR PRODUCTION
    return string;
}

angular.module('project', ['ngRoute', 'ngResource', 'ui.bootstrap', 'ui.bootstrap.progresscircle'])


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

    .factory('Endpoints', ['$resource',
        function($resource){
            return $resource('/resolve/:client_id', {}, {
                query: {method:'GET', params:{client_id:''}, isArray:false}
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
            if (sec == -1) return 'N/A';
            if (isNaN(parseFloat(sec)) || !isFinite(sec)) return sec;
            var d=new Date(0,0,0, 0, 0, Math.round(sec));
            if(d.getHours() || d.getMinutes()){
                return (d.getHours() ? d.getHours()+'h ' : '')+ (d.getMinutes() ? d.getMinutes()+'mn ':'');
            }else{
                return d.getSeconds() + 's';
            }
        }

    })

    .filter('moment', function(){

        return function(time_string){
            if(window.PydioEnvLanguages && window.PydioEnvLanguages.length){
                moment.locale(window.PydioEnvLanguages[0]);
            }else if(navigator.browserLanguage || navigator.language){
                moment.locale(navigator.browserLanguage?navigator.browserLanguage:navigator.language);
            }
            return moment(time_string).fromNow();
        }

    })

    .filter('basename', function(){

        return function(path){
            return path.split(/[\\/]/).pop();
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
            .when('/about', {
                controller:'ListCtrl',
                templateUrl:'about.html'
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
            .when('/change/:jobId', {
                controller:'EditCtrl',
                templateUrl:'edit_job.html'
            })
            .when('/new', {
                controller:'CreateCtrl',
                templateUrl:'01-Connection.html'
            })
            .when('/welcome', {
                controller:'CreateCtrl',
                templateUrl:'welcome.html'
            })
            .when('/logs/:jobId',{
                controller:'ListLogsCtrl',
                templateUrl:'logs.html'
            })
            .otherwise({
                redirectTo:'/'
            });
    })

    .controller('ListCtrl', function($scope, $window, $location, $timeout, Jobs, Logs, Conflicts, currentJob, Commands) {

        $scope.conflict_solver = {current:false,applyToAll:false};
        $scope._ = window.translate;
        $scope.progressCircleData = {
            value: 0
        };
        $scope.Math = window.Math;
        $scope.QtObject = window.PydioQtFileDialog;
        if (window.ui_config){
            $scope.ui_config = window.ui_config;
        }

        $scope.openLogs = function(){
          $scope.QtObject.openLogs();
        }

        $scope.openFile = function(source){
          var url = source.split('/');
          url = source.split('/', url.length - 1);
          url = url.join('/');
          $scope.QtObject.openUrl(url);
        };

        var t2;
        (function tickJobs() {
            var all = Jobs.query(function(){
                $scope.error = null;
                if(!all.length){
                    $location.path('/welcome');
                    return;
                }
                $scope.jobs = all;
                t2 = $timeout(tickJobs, 2000);
            }, function(response){
                if(!response.status){
                    $scope.error = window.translate('Ooops, cannot contact agent! Make sure it is running correctly, process will try to reconnect in 20s');
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

        var t0;
        var t1;

        $scope.openLogsForJob = function(jobId){

            $scope.opened_logs_panel = jobId;

            (function tickLog() {
                var all = Logs.query({job_id:jobId}, function(){
                    if($scope.opened_logs_panel != jobId) return;
                    $scope.error = null;
                    $scope.logs = all.logs;
                    $scope.running = all.running;
                    t0 = $timeout(tickLog, 2000);
                }, function(response){
                    if(!response.status){
                        if($scope.opened_logs_panel != jobId) return;
                        $scope.error = window.translate('Ooops, cannot contact agent! Make sure it is running correctly, process will try to reconnect in 20s');
                        t0 = $timeout(tickLog, 20000);
                    }
                });
            })();
            (function tickConflict() {
                var conflicts = Conflicts.query({job_id:jobId}, function(){
                    if($scope.opened_logs_panel != jobId) return;
                    $scope.conflicts = conflicts;
                    t1 = $timeout(tickConflict, 3000);
                });
            })();
            $scope.$on('$destroy', function(){
                if(t0) $timeout.cancel(t0);
                if(t1) $timeout.cancel(t1);
            });

        }

        $scope.closeLogs = function(){

            $scope.opened_logs_panel = null;
            $scope.logs = null;
            if(t0) $timeout.cancel(t0);
            if(t1) $timeout.cancel(t1);

        }

        $scope.solveConflict = function(nodeId, status){
            $scope.conflict_solver.current = null;
            var appToAll = $scope.conflict_solver.applyToAll;
            angular.forEach($scope.conflicts, function(conflict){
                if(!appToAll && conflict.node_id != nodeId) return;
                if(appToAll && conflict.status.indexOf('SOLVED:') === 0) return;
                conflict.status = status;
                conflict.job_id = $scope.opened_logs_panel;
                conflict.$save();
            });
        };

    })

    .controller('ListLogsCtrl', function($scope, $routeParams, $timeout, Jobs, Logs, Conflicts){
        $scope._ = window.translate;
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
                    $scope.error = window.translate('Ooops, cannot contact agent! Make sure it is running correctly, process will try to reconnect in 20s');
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

    .controller('CreateCtrl', function($scope, $location, $timeout, Jobs, Ws, currentJob, Endpoints) {

        if (window.ui_config){
            $scope.ui_config = window.ui_config;
        }

        $scope._ = window.translate;
        $scope.loading = false;
        $scope.error = null;

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
        if(currentJob.getJob() == null && ($location.path() == '/new' || $location.path() == '/welcome')){
            job = new Jobs();
            $scope.inline_protocol='https://';
            $scope.inline_host  = '';
            job.server          = 'https://';
            job.id              = 'new';
            job.remote_folder   = '';
            job.directory       = '';
            job.workspace       = '';
            job.frequency       = 'auto'; // auto, manual, time
            job.solve           = 'both'; // both, manual, local, remote
            job.direction       = 'bi'; // up, bi, down
            job.label           = 'New Job';
            job.hide_up_dir     = 'false'; // to hide buttons in gui
            job.hide_bi_dir     = 'false';  // to hide buttons in gui
            job.__type__        = 'JobConfig';

            $scope.job          = job;
            currentJob.setJob($scope.job);
        } else if ($scope.job && $scope.job.server){
            job = $scope.job = currentJob.getJob();
            $scope.inline_host = $scope.job.server;
            $scope.parseURL();
        } else if(currentJob.getJob() && !$scope.job){
            job = $scope.job = currentJob.getJob();
            $scope.inline_host = $scope.job.server;
            $scope.parseURL();
        }
        $scope.next = function(){
            $scope.loading = true;
            $scope.loadWorkspaces();
        }

        $scope.resolveClientId = function(){
            if(!$scope.job.client_id){
                return;
            }
            $scope.loading = true;
            $scope.error = null;
            Endpoints.get({
                client_id:job.client_id
            }, function(response){
                if (response['endpoints'] && response.endpoints.length){
                    $scope.job.server = response.endpoints[0].url;
                    try{
                        document.getElementById('dynasheet').href += '?';
                    }catch(e){}
                    $scope.loading = false;
                    $scope.error = null;
                    $timeout(function(){
                        document.getElementById('welcomeDiv').style['marginTop'] = '-200%';
                        $timeout(function(){
                            $location.path('/new');
                        }, 1000);
                    }, 700);
                    return;
                }else{

                }
            }, function(response){
                $scope.loading = false;
                $scope.error = response.data.message;
                $timeout(function(){
                    $scope.error = null;
                }, 7000);
            })
        };

        $scope.updateProtocol = function(protocol){
            $scope.inline_protocol = protocol;
            if($scope.job.server && $scope.inline_host){
                $scope.job.server = $scope.inline_protocol + $scope.inline_host;
            }
        };

        $scope.loadWorkspaces = function(){
            if($scope.job.id == 'new' && !$scope.job.password) {
                return;
            }
            $scope.job.workspace = '';
            Ws.get({
                job_id:'request',
                url:$scope.job.server,
                user:$scope.job.user,
                password:$scope.job.password,
                trust_ssl:$scope.job.trust_ssl?'true':'false'
            }, function(response){
                if(response.application_title){
                    job.application_title = response.application_title;
                }
                if(response.user_display_name){
                    job.user_display_name = response.user_display_name;
                }
                job.repositories = response.repositories.repo;
                $scope.loading = false;
                $location.path('/edit/new/step2');
            }, function(resp){
                if(resp.data && resp.data.error){
                    $scope.error = resp.data.error;
                }
                $scope.loading = false;
            });
        };

    })

    .controller('EditCtrl', function($scope, $location, $routeParams, $window, $timeout, Jobs, currentJob, Ws, Folders, Commands) {
        $scope._ = window.translate;
        if (window.ui_config){
            $scope.ui_config = window.ui_config;
        }

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
                trust_ssl:$scope.job.trust_ssl?'true':'false',
                ws:$scope.job.workspace
            }, function(resp){
                if(resp[0] && resp[0].error){
                    $scope.folders_loading_error = resp[0].error;
                }
                $scope.folders_loading = false;
            }, function(resp){
                $scope.folders_loading = false;
                $scope.folders_loading_error = window.translate('Error while loading folders!');
            });
        };

        $scope.QtObject = window.PydioQtFileDialog;

        $scope.openFile = function(source){
          var url = source.split('/');
          url = source.split('/', url.length - 1);
          url = url.join('/');
          $scope.QtObject.openUrl(url);
        };


        $scope.selectedWorkspace = window.translate('Select a workspace');

        $scope.OnWorkspaceClick = function(workspace) {
            if(workspace.label != $scope.selectedWorkspace){
                $scope.selectedWorkspace = workspace.label;
                $scope.job.repoObject = workspace;
                $scope.loadFolders();
            }
        };

        $scope.loadWorkspaces = function(){
            if($scope.job.id == 'new' && !$scope.job.password) {
                return;
            }
            Ws.get({
                job_id:'request',
                url:$scope.job.server,
                user:$scope.job.user,
                password:$scope.job.password,
                trust_ssl:$scope.job.trust_ssl?'true':'false'
            }, function(response){
                $scope.repositories = response.repositories.repo;
                if(response.application_title){
                    $scope.application_title = response.application_title;
                }
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
                res = window.prompt(window.translate('Full path to the local folder'));
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
            if($window.confirm(window.translate('Are you sure you want to delete this synchro? No data will be deleted'))){
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
                if($scope.job.application_title){
                    label = $scope.job.application_title + ' - ' + label;
                }
                $scope.job.label = label;
                if(!$scope.job.directory){
                    $scope.job.test_path = true;
                    $timeout(function(){
                        $scope.job.$save();
                    }, 600);
                    $scope.job.test_path = false;
                }
                if($scope.job.repoObject['@acl'] === 'r'){
                    $scope.job.direction = 'down';
                    $scope.job.hide_up_dir = 'true';
                    $scope.job.hide_bi_dir = 'true';
                    $scope.job.$save();
                }
                $location.path('/edit/new/step3');

            }else if(stepName == 'step3'){

                delete $scope.job.test_path;
                $scope.job.compute_sizes = true;
                $scope.job.$save();

                $scope.job.byte_size = window.translate('computing...')
                $scope.job.eta = window.translate('computing...')
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
                            if($scope.job.last_event && $scope.job.last_event.type == 'sync' && $scope.job.last_event.status == 'success'){
                                $location.path('/');
                                return;
                            }
                            if($scope.job.state){
                                if($scope.job.state.global.queue_length > 0 && $scope.job.state.global.queue_done >= (90 / 100 * $scope.job.state.global.queue_length)){
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