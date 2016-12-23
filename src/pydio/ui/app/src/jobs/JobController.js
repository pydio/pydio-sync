(function(){

  angular.module('jobs', ['ngResource', 'ngRoute'])
        .service('SelectedJobService', function () {
            var job;
            return job;
        })
        .service('ShowGeneralSettings', function () {
            var show;
            return true;
        })
        .service('NewJobService', function(){
            var newjob;
            return newjob;
        })
        .factory('Jobs', ['$resource',
            function($resource){
                return $resource('/jobs/:job_id/', {}, {
                    query: {method:'GET', params:{job_id:''}, isArray:true}
                });
        }])
        .factory('JobsWithId', ['$resource',
            // get the jobs in a nice map[job_id] -> job
            function($resource){
                return $resource('/jobs/:job_id', {}, {
                    query: {method:'GET', params:{job_id:'',with_id:true}}
                });
        }])
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
                return (d.getHours() ? d.getHours()+'h ' : '')+ (d.getMinutes() ? d.getMinutes()+'min ':'');
            }else{
                return d.getSeconds() + 's';
            }
        }
        })
       .filter('twoLetters', function(){
            // Fancy two letter somewhat random extractor my-files -> MF
            return function(input){
                if(typeof(input) === "undefined")
                    return "?¿"
                var output;
                var pos = input.indexOf('-')
                if ( pos > -1 && input.length > pos+1){
                    output = (input[0] + input[pos+1]).toUpperCase()
                } else {
                    if (input.length >= 2)
                        output = input.substr(0, 2).toUpperCase()
                    else
                        output = input.substr(0, 2).toUpperCase()
                }
                return output
            }
       })
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
       .config(['$routeProvider',
            function($routeProvider){
               $routeProvider.when("/about", {
                    controllerAs: "SC",
                    controller: "SettingsController",
                    templateUrl: "about.html",
               })
               .when("/settings", {
                    controller: "SettingsController",
                    controllerAs: "SC",
                    templateUrl: "./src/jobs/view/general_configs.html",
               })
               .when('/share/:layout/:jobId/:itemType/:itemPath', {
                    //:example sample get request would be like
                    //http://localhost:5556/res/index.html#/share/standard/id-my-files/file/abc%5Chello.txt
                    controller:'ShareCtrl',
                    templateUrl:'./src/jobs/view/share.html'
                })
                .when('/share/response/:layout', {
                    controller:'ShareCtrl',
                    templateUrl:'./src/jobs/view/share_response.html'
                })
            }
            ])
       .controller('JobController', [
          '$routeParams', 'jobService', '$location', '$mdSidenav', '$mdBottomSheet', '$timeout', '$log', '$scope', '$mdToast', '$mdDialog', '$mdColors', 'Jobs', 'Commands', 'JobsWithId', 'SelectedJobService', 'NewJobService', 'ShowGeneralSettings', 'Ws', 'Endpoints', JobController
       ])

  /**
   * Main Controller for the Angular Material Starter App
   * @param $scope
   * @param $mdSidenav
   * @param avatarsService
   * @constructor
   */
  function JobController( $routeParams, jobService, $location, $mdSidenav, $mdBottomSheet, $timeout, $log, $scope, $mdToast, $mdDialog, $mdColors, Jobs, Commands, JobsWithId, SelectedJobService, NewJobService, ShowGeneralSettings, Ws, Endpoints ) {
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
        return string;
    }

    primarycolor = $mdColors.getThemeColor(pydiotheme.base + '-' + pydiotheme.hue);

    $scope._ = window.translate;
    var self = this;

    SelectedJobService.job = null;
    $scope.selected = SelectedJobService;
    self.toggleList = toggleSideNav;
    self.toggleGeneralSettings = toggleGeneralSettings;

    // Load all jobs
    self.syncing = jobService.syncing;
    self.history = jobService.history;
    self.currentNavItem = 'history';
    $scope.pathes = {};
    $scope.jobs = Jobs.query();
    self.jobs = $scope.jobs;

    self.menuOpened = false;
    $scope.application_title = window.translate("PydioSync"); // TODO: FETCH ME BABY
    $scope.$on('$mdMenuClose', function(){ self.menuOpened = false});

    $scope.SHOW_INTERFACE = ($location.url().indexOf('share') == -1) // HACKY... hide interface when showing the /share page
    $scope.showAllJobs = updateShowAllJobs()
    // /settings trick
    ShowGeneralSettings.show = false;
    $scope.ShowGeneralSettings = ShowGeneralSettings;

    function updateShowAllJobs(){
        return ($location.url().indexOf('about') != -1) || ($location.url().indexOf('settings') != -1)
    }
    self.fake_data = {"tasks":{"current":[{"node":{"bytesize":100000000,"mtime":1467037750,"md5":"5bf234610827e29cb0436122415d4821","node_path":"/JENE/omg/jaja/lefile100MB"},"target":"/JENE/omg/jaja/lefile100MB","total_size":100001132,"bytesize":100000000,"bytes_sent":40,"content":1,"source":"NULL","total_bytes_sent":48367468,"location":"local","progress":3,"row_id":166,"type":"create","md5":"5bf234610827e29cb0436122415d4821"}],"total":5},"global":{"total_time":5.003995,"last_transfer_rate":24365888.264299262,"status_indexing":0,"queue_bytesize":-3280,"queue_start_time":2.774535,"eta":-0.000021983704444345575,"queue_length":5,"queue_done":5.0000219662499905}}

    var t0;
    (function tickJobs() {
        var tmpJobs = Jobs.query(function(){
                    $scope.error = null;
                    // TODO: Merge new jobs events instead of replacing all jobs, to avoid flickering.
                    if ( !self.menuOpened ){
                        self.jobs = tmpJobs;
                        if (typeof($scope.jobs) == "undefined")
                            $scope.jobs = tmpJobs;
                        if(SelectedJobService.job){
                            for (var i in self.jobs){
                                if(self.jobs[i].id === SelectedJobService.job.id){
                                    // update some fields to the selected job, not all fields can be merge (at least during job settings edit)
                                    SelectedJobService.job.state = self.jobs[i].state
                                    SelectedJobService.job.last_event = self.jobs[i].last_event
                                    SelectedJobService.job.running = self.jobs[i].running
                                    if (SelectedJobService.job.running && SelectedJobService.job.state)
                                        SelectedJobService.job.progress = 100 * parseFloat(SelectedJobService.job.state.global.queue_done) / parseFloat(SelectedJobService.job.state.global.queue_length)
                                } else {
                                    // merges everything -> bug when editing
                                    for (var field in self.jobs[i]){
                                        if (['$get', '$save', '$query', '$remove', '$delete', 'toJSON'].indexOf(field) === -1)
                                            $scope.jobs[i][field] = self.jobs[i][field]
                                    }
                                }
                            }
                        } else {
                            for (var i in self.jobs){
                             // merges everything -> bug when editing
                                for (var field in self.jobs[i]){
                                    if (['$get', '$save', '$query', '$remove', '$delete', 'toJSON'].indexOf(field) === -1)
                                        $scope.jobs[i][field] = self.jobs[i][field]
                                }
                            }
                        }
                    }
                }, function(response){
                        $scope.error = window.translate('Ooops, cannot contact agent! Make sure it is running correctly, process will try to reconnect in 20s');
                        $mdToast.show(
                          $mdToast.simple()
                            .textContent($scope.error)
                            .hideDelay(3000)
                        );
                });
        t0 = $timeout(tickJobs, 2000);
    })()

    // *********************************
    // Internal methods
    // *********************************

    /**
     * Hide or Show the 'left' sideNav area
     */
    function toggleSideNav() {
      $mdSidenav('left').toggle();
    }

    self.selectJob = function selectJob ( job ) {
        self.currentNavItem = 'history';
        $scope.showAllJobs = false;
        ShowGeneralSettings.show = false;
        SelectedJobService.job = angular.isNumber(job) ? $scope.jobs[job] : job;
        SelectedJobService.job.repositories = [{"label": SelectedJobService.job.workspace}];
    }

    self.showJobs = function(){
        $scope.showAllJobs = true
    }

    self.newSyncTask = function (ev){
        $mdDialog.show({
            controller: 'NewJobController',
            controllerAs: 'NJC',
            templateUrl: './src/jobs/view/newjob.html',
            parent: angular.element(document.body),
            targetEvent: ev,
            clickOutsideToClose:true
        })
        .then(function(answer) {
            $scope.status = 'You said the information was "' + answer + '".';
        }, function() {
            $scope.status = 'You cancelled the dialog.';
        });
    };
    window.onload = function (){
        //toggleSideNav();
        if ($scope.jobs.length == 1)
            self.selectJob(0)
        else $scope.showAllJobs = true;
    }


    function toggleGeneralSettings(){
        ShowGeneralSettings.show = !ShowGeneralSettings.show
    }

    $scope.applyCmd = function(cmd){
        Commands.query({cmd:cmd, job_id:SelectedJobService.job.id}, function(){
            var newJobs = Jobs.query({}, function(){
                $scope.jobs = newJobs
            });
        });
    }

    $scope.applyCmdToJob = function(cmd, job){
        Commands.query({cmd:cmd, job_id:job.id}, function(){
            var newJobs = Jobs.query({}, function(){
                $scope.jobs = newJobs
            });
        });
        //console.log($scope.jobs)
    }

    self.menuClick = function(index, action){
        SelectedJobService.job = $scope.jobs[index]
        self.menuOpened = false
        switch (action){
            case 'info':
                //console.log('info ' + index)
                $scope.showNewTask = false
                $scope.showAllJobs = false
                ShowGeneralSettings.show = false
                self.currentNavItem = 'history';
            break
            case 'start':
                //console.log('start ' + index)
                $scope.applyCmd('enable')
            break
            case 'resume':
                //console.log('resume ' + index)
                $scope.applyCmd('resume')
            break
            case 'stop':
                //console.log('stop ' + index)
                $scope.applyCmd('disable')
            break
            case 'settings':
                //console.log('settings ' + index)
                $scope.showNewTask = false
                $scope.showAllJobs = false
                ShowGeneralSettings.show = false
                self.currentNavItem = "settings"
            break
            case 'pause':
                //console.log('pause ' + index)
                $scope.applyCmd('pause')

        }
    }

    self.showWorkspacePicker = function(){
        $scope.loading = true;
        if(!SelectedJobService.job.password) {
            self.toastError(window.translate('You must provide your password.'))
            $scope.loading = false;
            return;
        }

        Ws.get({
            job_id:'request',
            url:SelectedJobService.job.server,
            user:SelectedJobService.job.user,
            password:SelectedJobService.job.password,
            trust_ssl:SelectedJobService.job.trust_ssl?'true':'false'
        }, function(response){
            if(response.application_title){
                SelectedJobService.job.application_title = response.application_title;
            }
            if(response.user_display_name){
                SelectedJobService.job.user_display_name = response.user_display_name;
            }
            var ret = [] // clean up response
            for (var i in response.repositories.repo){
                if (typeof(response.repositories.repo[i]["@repositorySlug"]) !== "undefined" && response.repositories.repo[i]["@meta_syncable_REPO_SYNCABLE"] === "true" ){
                    ret.push(response.repositories.repo[i])
                }
            }
            SelectedJobService.job.repositories = ret;
            $scope.loading = false;
        }, function(resp){
            console.log(resp)
            if(resp.data && resp.data.error){
                $scope.error = resp.data.error;
            } else {
                $scope.error = "Connection problem"
            }
            $mdToast.show({
                  hideDelay   : 9000,
                  position    : 'bottom right',
                  controller  : function(){},
                  template    : '<md-toast><span class="md-toast-text" style="" flex>' + $scope.error + '</span></md-toast>'
            });
            $scope.loading = false;
        });
    }

    self.showConfirmDelete = function(ev) {
        // Appending dialog to document.body to cover sidenav in docs app
        var confirm = $mdDialog.confirm()
              .title(window.translate('Are you sure you want to delete this synchro?'))
              .textContent(window.translate('Only PydioSync internal files will be deleted. None of your files.'))
              .ariaLabel('Confirm Delete')
              .targetEvent(ev)
              .ok(window.translate('DELETE'))
              .cancel(window.translate('CANCEL'));
        $mdDialog.show(confirm).then(function() {
            // DO DELETE
            Jobs.delete({job_id:SelectedJobService.job.id},function(){
                $scope.showAllJobs = true;
            });
        }, function() {
            // CANCEL
        });
    };

    self.showConfirmResync = function(ev) {
        // Appending dialog to document.body to cover sidenav in docs app
        var confirm = $mdDialog.confirm()
              .title(window.translate('Are you sure you want to do a Resync?'))
              .textContent(window.translate('Resyncing consists in scanning all your local files as well as list all the files in your workspace.'))
              .ariaLabel('Confirm Resync')
              .targetEvent(ev)
              .ok(window.translate('RESYNC'))
              .cancel(window.translate('CANCEL'));
        $mdDialog.show(confirm).then(function() {
            Commands.query({cmd:"resync", job_id:SelectedJobService.job.id}, function(){
                //console.log("THIS WILL RESYNC")
                $location.path('/')
            });
        }, function() {
            // CANCEL
        });
    };

    self.revertJob = function (){
        // query and restore values from configs.json
        var orig = JobsWithId.query({}, function(){
            for (var a in EDITABLE_FIELDS){
                SelectedJobService.job[EDITABLE_FIELDS[a]] = orig[SelectedJobService.job.id][EDITABLE_FIELDS[a]]
            }
        })
    }

    self.doSave = function(){
        SelectedJobService.job.$save();
    }

    self.showTodo = function(content){
        $mdToast.show({
                          hideDelay   : 3000,
                          position    : 'bottom right',
                          controller  : function(){},
                          template    : '<md-toast><span class="md-toast-text" style="color:yellow" flex>' + content + '</span></md-toast>'
                    });
        }
    // add field names here to check
    var EDITABLE_FIELDS = ['label', 'server', 'user', 'password', 'directory', 'workspace', 'frequency', 'timeout', 'poolsize', 'direction', 'solve', 'trust_ssl'];
    var tm;
    (function checkModified(){
        // display SAVE REVERT when necessary
        if(typeof($scope.isModified) === "undefined")
            $scope.isModified = false;
        if (self.jobs && self.currentNavItem && self.currentNavItem === 'settings'){
            var foundJob = false;
            var nowModified = false;
            for(var i in self.jobs){
                if(self.jobs[i].id === SelectedJobService.job.id){
                    foundJob = true;
                    for (var a in EDITABLE_FIELDS){
                        if(self.jobs[i][EDITABLE_FIELDS[a]] !== SelectedJobService.job[EDITABLE_FIELDS[a]]){
                            //console.log(b + " - " + self.jobs[i][names[a]] + " " + self.selected[names[a]])
                            nowModified = true;
                        }
                    }
                }
                if(foundJob){
                    if(nowModified)
                        $scope.isModified = true;
                    if($scope.isModified && !nowModified){
                        $scope.isModified = false;
                    }
                    break;
                }
            }
        }
        tm = $timeout(checkModified, 700);
    })()

    /* JS - Qt interactions */
    if (typeof(qt) !== 'undefined'){
        new QWebChannel(qt.webChannelTransport, function(channel) {
            self.pydiouijs = channel.objects.pydiouijs; // useful for debug
            self.PydioQtFileDialog = channel.objects.PydioQtFileDialog;
        })
    }
    self.openDirChooser = function(ev){
        var res;
        if(!self.PydioQtFileDialog) {
            res = window.prompt(window.translate('Full path to the local folder'));
        }else{
            res = self.PydioQtFileDialog.getPath(); /* Execution of this function in Qt is asynchronous... See polling below */
        }
        SelectedJobService.job.directory = res;
        var pollres;
        function pollResult(){
            // poll for Folder selection finished
            if(typeof(SelectedJobService.job.directory) === "undefined"){
                self.PydioQtFileDialog.getDirectory()
                SelectedJobService.job.directory = window.PydioDirectory
                pollres = $timeout(pollResult, 700)
                $scope.conflicts = []
            }
        }
        pollResult()
     }

    self.toastError = function ( error ){
        $mdToast.show({
                  hideDelay   : 4000,
                  position    : 'bottom right',
                  controller  : function(){},
                  template    : '<md-toast><span class="md-toast-text" style="" flex>' + error + '</span></md-toast>'
            });
    }

    self.openFolder = function(dir){
        if(!self.PydioQtFileDialog) {
            self.showTodo(window.translate('Open dir'));
        } else {
            self.PydioQtFileDialog.openUrl(dir+'/')
        }
    }

    $scope.showErrorMessage = function(ev, message) {
        $mdDialog.show(
          $mdDialog.alert()
            .clickOutsideToClose(true)
            .title(window.translate('There was an Error'))
            .textContent(message)
            .ariaLabel('Error Message')
            .ok('OK')
            .targetEvent(ev)
        );
    };

    $scope.resolveClientId = function(){
        $scope.loading = true;
        $scope.error_ws = null;
        if (!self.client_id){
            $scope.error_ws = "Null Client ID"
            console.log($scope.error_ws)
        }
        Endpoints.get({
            client_id:self.client_id
        }, function(response){
            self.ws = {}
            $scope.Content = response;
            if (response['endpoints'] && response.endpoints.length){
                //console.log(response)
                pydiotheme.base = response["vanity"]["splash_bg_color"]
                pydiotheme.base = response["vanity"]["main_tint"]
                // DRAFT for theme
                //response["vanity"]["application_name"]
                //response["vanity"]["splash_image"]
                //response["support"]["info_panel"]
                /*$mdThemingProvider.theme('default')
                              .primaryPalette(pydiotheme.base, {'default': pydiotheme.hue})
                              .accentPalette(pydiotheme.accent);*/
                //reload the theme
                //$mdThemingProvider.theme('default').reload('default');
                NewJobService.server = response.endpoints[0].url;
                try{
                    document.getElementById('dynasheet').href += '?';
                }catch(e){}
                console.log("Everything seems fine so far.")
                $scope.loading = false;
                $timeout(function(){
                    document.getElementById('welcomeDiv').style['marginTop'] = '-200%';
                    $timeout(function(){
                        $mdDialog.show({
                            controller: 'NewJobController',
                            controllerAs: 'NJC',
                            templateUrl: './src/jobs/view/newjob.html',
                            parent: angular.element(document.body),
                            clickOutsideToClose:false
                        }

                    )
                    .then(function(answer) {
                        $scope.status = 'You said the information was "' + answer + '".';
                    }, function() {
                        $scope.status = 'You cancelled the dialog.';
                    });
                        //$location.path('/new');
                    }, 1000);
                }, 700);
                return;
            }else{

            }
        }, function(response){
            $scope.loading = false;
            $scope.error_ws = response.data.message;
            $timeout(function(){
                $scope.error_ws = null;
            }, 7000);
        })
    };

    $scope.resolveWithEnter = function(ev){
        if(ev.keyCode == 13)
            $scope.resolveClientId();
    }

  } // End of Controller
})();
