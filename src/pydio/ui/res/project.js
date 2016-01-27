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
    .factory('Proxy', ['$resource',
        function($resource){return $resource('/proxy', {}, {query:{method:'GET'}, isArray: false});}])
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

    .service('shareFile', function() {
        var objectValue = {
            'fileName':'',
            'shareLink':'',
            'shareJobId':'',
            'existingLinkFlag':''
            };
        return {
            get: function() {
                return objectValue;
            },
            set: function(key, value) {
                objectValue[key] = value;
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

    .factory('GeneralConfigs', ['$resource',
        function($resource){
            return $resource('/general_configs', {}, {
                query: {method:'GET', params:{}, isArray:false}
            });
        }])

    .factory('Share', ['$resource',
        function($resource){
            return $resource('/share/:job_id/', {}, {
                query: {method:'GET', params:{
                    action:'',
                    job_id:'',
                    ws_label:'',
                    ws_description:'',
                    password:'',
                    expiration:'',
                    downloads:'',
                    can_read:'',
                    can_download:'',
                    relative_path:'',
                    link_handler: '',
                    can_write: '',
                    checkExistingLinkFlag:''
                }, isArray:false},
                unshare: {method:'GET', params:{
                    job_id:'',
                    action:'unshare',
                    path:''
                }, isArray:false}
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
            .when('/share/:layout/:jobId/:itemType/:itemPath', {
                //:example sample get request would be like
                //http://localhost:5556/res/index.html#/share/standard/54.254.418.47-my-files/file/abc%5Chello.txt
                controller:'ShareCtrl',
                templateUrl:'share.html'
            })
            .when('/share/response/:layout', {
                controller:'ShareCtrl',
                templateUrl:'share_response.html'
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
            .when('/settings',{
                controller:'SettingsCtrl',
                templateUrl:'settings.html'
            })
            .when('/general_configs', {
                controller:'GeneralConfigCtrl',
                templateUrl:'general_configs.html'
            })
            .otherwise({
                redirectTo:'/'
            });
    })

    .controller('ListCtrl', function($scope, $window, $location, $timeout, Jobs, Logs, Conflicts, currentJob, Commands) {
        $scope._ = window.translate;
        if (window.ui_config){
            $scope.ui_config = window.ui_config;
        }
        $scope.conflict_solver = {current:false,applyToAll:false};
        $scope.progressCircleData = {
            value: 0
        };
        $scope.Math = window.Math;
        $scope.QtObject = window.PydioQtFileDialog;

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
        if (window.ui_config){
            $scope.ui_config = window.ui_config;
        }
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
        $scope._ = window.translate;
        if (window.ui_config){
            $scope.ui_config = window.ui_config;
        }
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
            job.hide_down_dir   = 'false';  // to hide buttons in gui
            job.timeout         = '20';
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
        $scope.nextWithEnter = function(ev){
            if (ev.keyCode == 13)
                $scope.next();
        }
        $scope.resolveWithEnter = function(ev){
            if(ev.keyCode == 13)
                $scope.resolveClientId();
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
        $scope.doneWithEnter = function(ev){
            if (ev.keyCode == 13)
                $scope.save('step2');
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
                if($scope.job.repoObject['@acl'] === 'r'){ // custom GUI for ACL
                    $scope.job.direction = 'down';
                    $scope.job.hide_up_dir = 'true';
                    $scope.job.hide_bi_dir = 'true';
                } else if ($scope.job.repoObject['@acl'] === 'w'){
                    $scope.job.direction = 'up';
                    $scope.job.hide_down_dir = 'true';
                    $scope.job.hide_bi_dir = 'true';
                }
                $scope.job.$save();
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
                // Check if the type of include and excludes are in the form of string(
                // usually the case when we save the configuration), change it to array type
                if(typeof($scope.job.filters.includes) == "string") {
                    $scope.job.filters.includes = $scope.job.filters.includes.split(',');
                }
                if(typeof($scope.job.filters.excludes) == "string") {
                    $scope.job.filters.excludes = $scope.job.filters.excludes.split(',');
                }
                $scope.job.$save();
                $location.path('/');
            }
        };
    })

     .controller('ShareCtrl', function($scope, $window, $route, $location, $routeParams, Share, shareFile) {
        $scope._ = window.translate;
        $scope.share_preview = true;
        $scope.share_download_checkbox = true;
        $scope.share_allowed_downloads = 0;
        $scope.can_write = false;
        $scope.share_expire_in = 0;

        if (window.ui_config){
            $scope.ui_config = window.ui_config;
        }
        // Display the view based on the type of layout
        if($routeParams.layout == "miniview" || document.URL.indexOf("minivew") > -1) {
            if (document.getElementsByTagName("body")[0].className.indexOf("miniview") == -1)
                document.getElementsByTagName("body")[0].className += "miniview";
                // disable right click reload
                document.getElementsByTagName("body")[0].setAttribute("oncontextmenu", "return false");
                $scope.miniview = true;
        } else {
            var sharediv = document.getElementById("shareDiv");
            if (sharediv)
                sharediv.setAttribute("style", "margin-top:80px !important;");
        }

        $scope.updateProgBar = function (){
            try {
                $scope.showprogbar = true;
                document.getElementById("shareDiv").style = "display:none !important;";
                var progbar = document.getElementById("progbar");
                var newval = parseInt(progbar.style.width)*1.3;
                progbar.style = "width:" + newval + "%";
                progbar.setAttribute('aria-valuenow', newval);
            } catch (error){
             //
            }
        }
        $scope.startProgBar = function () {
            $scope.updateProgBar();
            $scope.timer = window.setInterval($scope.updateProgBar, 200);
        }
        $scope.stopProgBar = function (){
            clearInterval($scope.timer);
        }

        $scope.QtObject = window.PydioQtFileDialog;

        // Enable write flag if the item is a folder
        if($routeParams.itemType == "folder"){
            $scope.can_write = true;
        }

        // Check if a shared link already exists for the selected item.
        checkExistingLink = function(){
            var res;
            shareFile.set('fileName',$routeParams.itemPath)
            shareFile.set('shareJobId',$routeParams.jobId)

            res = Share.query({
                action:'share',
                job_id: $routeParams.jobId,
                relative_path: $routeParams.itemPath,
                checkExistingLinkFlag:'true'
            }, function(){
                if(res.existingLinkFlag == 'true') {
                    shareFile.set('shareLink',res.link)
                    shareFile.set('existingLinkFlag','true')
                    $location.path('/share/response/' + $routeParams.layout);
                }
               }
            );
        };

        // This condition to avoid checkExistingLink to be called from response page as it uses same
        if($routeParams.jobId){
            $scope.share_filename = $routeParams.itemPath;
            checkExistingLink();
        }

        // Generate the share link for the selected item.
        $scope.generateLink = function(){
            $scope.startProgBar();
            var res;

            res = Share.query({
                action:'share',
                job_id:$routeParams.jobId,
                ws_label:$routeParams.itemPath.replace(/^.*[\\\/]/, ''),
                ws_description:$scope.share_description,
                password:$scope.share_password,
                expiration:$scope.share_expire_in,
                downloads:$scope.share_allowed_downloads,
                can_read:$scope.share_preview,
                can_download:$scope.share_download_checkbox,
                relative_path: $routeParams.itemPath,
                link_handler: $scope.share_link_handler,
                can_write: $scope.share_upload_checkbox
            }, function(){
                shareFile.set('shareLink',res.link)
                $location.path('/share/response/' + $routeParams.layout);
                $scope.stopProgBar();
                }
            );
        };

        // GetShareLink shares the details with share response page
        $scope.GetShareLink = function(){
            share_details = shareFile.get();
            $scope.share_link = share_details['shareLink'];
            $scope.existingLinkFlag = share_details['existingLinkFlag'];
            $scope.share_filename = share_details['fileName'];
            $scope.checkResponseFlag = (share_details['shareLink'].substring(0, 4)=='http')
        };

        // File browser
        $scope.openFile = function(){
            var res;
            if(!window.PydioQtFileDialog) {
                res = window.prompt(window.translate('Full path to the local folder'));
            }else{
                res = $routeParams.itemPath;
            }
            if(res){
                $scope.share_filename = res;
            }
        };

        //Un-share the selected item.
        $scope.unShareLink = function(){
            share_details = shareFile.get();
            res = Share.unshare({
                job_id:share_details['shareJobId'],
                action:'unshare',
                path: share_details['fileName']
            }, function(){
                 if($routeParams.layout == "miniview" || document.URL.indexOf("minivew") > -1) {
                    $scope.miniview_done = true;
                 } else {
                    $location.path('/');
                 }
               }
            );
        };

        $scope.copyToClipBoard = function(value){
            // check if the text can be copied from QT's copy to clip board else show error message
            try {
                $scope.QtObject.copyToClipBoard(value);
            } catch (err) {
                try {
                    interOp.callSwift(value);
                    window.webkit.messageHandlers.swift.postMessage({body: value});
                } catch (err) {
                    console.log("Copy to clipboard is not possible while using web browser");
                }
            }
        };
    })

    .controller('SettingsCtrl', function($scope, $routeParams, $timeout, $location, Jobs, Logs, Conflicts, Proxy){
        $scope._ = window.translate;
        if (window.ui_config){
            $scope.ui_config = window.ui_config;
        }
        var proxies = Proxy.query(function(){
            proxies.http.password = "";
            proxies.https.password = "";
            proxies.https.url = proxies.https.hostname + ":" + proxies.https.port;
            proxies.http.url = proxies.http.hostname + ":" + proxies.http.port;
            // check for a nice gui, in the model?!
            if (proxies.https.url === ":") proxies.https.url = "";
            if (proxies.http.url === ":") proxies.http.url = "";
            $scope.proxies = proxies;
        });

        $scope.save = function(param){
            console.log("Am I called?");
        };
        $scope.updateProxy = function (){
            function cutHostPort(url, hostOrPort){
                // removes https:// from url if present, @hostOrPort: 0 for host, 1 for port
                url = url.replace("http://", "");
                url = url.replace("https://", "");
                var res = url.split(':')[hostOrPort];
                return res == undefined ? "" : res;
            }
            // recover port & host from url
            proxies.http.hostname = cutHostPort(proxies.http.url, 0);
            proxies.https.hostname = cutHostPort(proxies.https.url, 0);
            proxies.http.port = cutHostPort(proxies.http.url, 1);
            proxies.https.port = cutHostPort(proxies.https.url, 1);
            proxies.http.active = proxies.https.active;
            // store, delete, post and restore url
            var temp = proxies.http.url;
            var temps = proxies.https.url;
            proxies.http.url = undefined;
            proxies.https.url = undefined;
            // P O S T
            proxies.$save();
            proxies.https.url = temps;
            proxies.http.url = temp;
            $location.path('/');
        }
    })

    .controller('GeneralConfigCtrl', function($scope, $routeParams, $location, GeneralConfigs, Proxy){
        $scope._ = window.translate;

        if (window.ui_config){
            $scope.ui_config = window.ui_config;
        }

        // Load the general config from agent (http://localhost:5556/general_configs)
        general_configs_data = GeneralConfigs.query({},
            function (){
            $scope.general_configs_data=general_configs_data;
            });

        // Post the modified general config to agent
        $scope.SaveGeneralConfig = function() {

            general_configs_data.$save();

            if($scope.ui_config.login_mode == 'alias') {
                // if proxy part is not really modified, then don't update the existing proxy settings
                if((proxies.http.password == "" && proxies.http.hostname != "") || (proxies.https.password == "" && proxies.https.hostname != "")) {
                    console.log('proxy password is empty')
                    if(proxies.https.active == 'false') {
                        proxies.http.active = proxies.https.active;
                        // Now save the parameters
                        proxies.$save();
                    }
                }
                else {
                    function cutHostPort(url, hostOrPort){
                        // removes https:// from url if present, @hostOrPort: 0 for host, 1 for port
                        url = url.replace("http://", "");
                        url = url.replace("https://", "");
                        var res = url.split(':')[hostOrPort];
                        return res == undefined ? "" : res;
                    }
                    // recover port & host from url
                    proxies.http.hostname = cutHostPort(proxies.http.url, 0);
                    proxies.https.hostname = cutHostPort(proxies.https.url, 0);
                    proxies.http.port = cutHostPort(proxies.http.url, 1);
                    proxies.https.port = cutHostPort(proxies.https.url, 1);
                    proxies.http.active = proxies.https.active;

                    // Now save the parameters
                    proxies.$save();
                }
            }
            $location.path('/');
        }

        // do the proxy query only for workspaces
        if($scope.ui_config.login_mode == 'alias') {
            proxies = Proxy.query(function(){
                proxies.http.password = "";
                proxies.https.password = "";
                proxies.https.url = proxies.https.hostname + ":" + proxies.https.port;
                proxies.http.url = proxies.http.hostname + ":" + proxies.http.port;
                // check for a nice gui, in the model?!
                if (proxies.https.url === ":") proxies.https.url = "";
                if (proxies.http.url === ":") proxies.http.url = "";
                $scope.proxies = proxies;
            })
        }

        $scope.about_page = function() {
            $location.path('/about');
        };
    });
