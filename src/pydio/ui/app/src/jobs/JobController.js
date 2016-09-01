(function(){

  angular.module('jobs', ['ngResource'])
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
       .controller('JobController', [
          'jobService', '$mdSidenav', '$mdBottomSheet', '$timeout', '$log', '$scope', '$mdToast', '$mdDialog', 'Jobs', 'Commands', 'JobsWithId',
          JobController
       ])

  /**
   * Main Controller for the Angular Material Starter App
   * @param $scope
   * @param $mdSidenav
   * @param avatarsService
   * @constructor
   */
  function JobController( jobService, $mdSidenav, $mdBottomSheet, $timeout, $log, $scope, $mdToast, $mdDialog, Jobs, Commands, JobsWithId ) {
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

    $scope._ = window.translate;
    var self = this;

    self.selected     = null;
    self.toggleList   = toggleSideNav;
    self.makeContact  = makeContact;
    self.toggleGeneralSettings = toggleGeneralSettings;

    // Load all jobs
    self.syncing = jobService.syncing;
    self.history = jobService.history;
    self.currentNavItem = 'history';
    $scope.pathes = {};
    $scope.jobs = Jobs.query();
    self.jobs = $scope.jobs;

    self.menuOpened = false;
    $scope.$on('$mdMenuClose', function(){ self.menuOpened = false});

    self.fake_data = {"tasks":{"current":[{"node":{"bytesize":100000000,"mtime":1467037750,"md5":"5bf234610827e29cb0436122415d4821","node_path":"/JENE/omg/jaja/lefile100MB"},"target":"/JENE/omg/jaja/lefile100MB","total_size":100001132,"bytesize":100000000,"bytes_sent":40,"content":1,"source":"NULL","total_bytes_sent":48367468,"location":"local","progress":3,"row_id":166,"type":"create","md5":"5bf234610827e29cb0436122415d4821"}],"total":5},"global":{"total_time":5.003995,"last_transfer_rate":24365888.264299262,"status_indexing":0,"queue_bytesize":-3280,"queue_start_time":2.774535,"eta":-0.000021983704444345575,"queue_length":5,"queue_done":5.0000219662499905}}

    var t0;
    (function tickJobs() {
        var tmpJobs = Jobs.query(function(){
                    $scope.error = null;
                    // TODO: Merge new jobs events instead of replacing all jobs, to avoid flickering.
                    if ( !self.menuOpened ){
                        self.jobs = tmpJobs;
                        $scope.jobs = tmpJobs;
                        if(self.selected && self.selected.state){
                            for (var i in self.jobs){
                                if(self.jobs[i].id === self.selected.id){
                                    self.selected.state = self.jobs[i].state;
                                }
                            }
                            self.selected.progress = 100 * parseFloat(self.selected.state.global.queue_done) / parseFloat(self.selected.state.global.queue_length)
                        }
                        /*for (var index in self.jobs)
                            if (self.jobs[index].id === self.selected.id)
                                console.log(self.jobs[index].state)*/
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
    /*
    self.jobList        = [ ];
    jobService.loadJobList().then(
        function( jobList ) {
            self.jobList    = [].concat(jobList);
            self.selected = jobList[0];
        }
    );
    jobService.loadAllJobs().then(
        function(jobs){
            self.jobs = jobs;
        }
    );
    */
    // *********************************
    // Internal methods
    // *********************************

    /**
     * Hide or Show the 'left' sideNav area
     */
    function toggleSideNav() {
      $mdSidenav('left').toggle();
    }

    /**
     * Select the current avatars
     * @param menuId
     */
    self.selectJob = function selectJob ( job ) {
        $scope.currentNavItem = 'history';
        $scope.showAllJobs = false;
        $scope.showGeneralSettings = false;
        self.selected = angular.isNumber(job) ? $scope.jobs[job] : job;
        $scope.selected = self.selected; // hack to pass info around...
    }

    self.showJobs = function(){
        $scope.showAllJobs = true
    }
    /**
     * Show the Contact view in the bottom sheet
     */
    function makeContact(selectedUser) {

        $mdBottomSheet.show({
          controllerAs  : "vm",
          templateUrl   : './src/users/view/listjob.html',
          controller    : [ '$mdBottomSheet', JobListController],
          parent        : angular.element(document.getElementById('content'))
        }).then(function(clickedItem) {
          $log.debug( clickedItem.name + ' clicked!');
        });

        /**
         * User ContactSheet controller
         */
        function JobListController( $mdBottomSheet ) {
          this.user = selectedUser;
          this.contactUser = function(action) {
            // The actually contact process has not been implemented...
            // so just hide the bottomSheet

            $mdBottomSheet.hide(action);
          };
        }
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
        $scope.showGeneralSettings = !$scope.showGeneralSettings
    }

    $scope.applyCmd = function(cmd){
        // uses global variable $scope.selected
        Commands.query({cmd:cmd, job_id:$scope.selected.id}, function(){
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
        $scope.selected = $scope.jobs[index]
        self.menuOpened = false
        self.selected = $scope.selected
        switch (action){
            case 'info':
                console.log('info ' + index)
                $scope.showNewTask = false
                $scope.showAllJobs = false
                $scope.showGeneralSettings = false
                self.currentNavItem = 'history';
            break
            case 'start':
                console.log('start ' + index)
                $scope.applyCmd('enable')
            break
            case 'stop':
                console.log('stop ' + index)
                $scope.applyCmd('disable')
            break
            case 'settings':
                console.log('settings ' + index)
                $scope.showNewTask = false
                $scope.showAllJobs = false
                $scope.showGeneralSettings = false
                self.currentNavItem = "settings"
            break
            case 'pause':
                console.log('pause ' + index)
                $scope.applyCmd('pause')

        }
    }

    self.showWorkspacePicker = function(){
        $scope.loading = true;
        if(!self.selected.password) {
            return;
        }
        self.job.workspace = '';
        Ws.get({
            job_id:'request',
            url:self.selected.server,
            user:self.selected.user,
            password:self.selected.password,
            trust_ssl:self.selected.trust_ssl?'true':'false'
        }, function(response){
            if(response.application_title){
                self.selected.application_title = response.application_title;
            }
            if(response.user_display_name){
                self.selected.user_display_name = response.user_display_name;
            }
            var ret = [] // clean up response
            for (var i in response.repositories.repo){
                if (typeof(response.repositories.repo[i]["@repositorySlug"]) !== "undefined" && response.repositories.repo[i]["@meta_syncable_REPO_SYNCABLE"] === "true" ){
                    ret.push(response.repositories.repo[i])
                }
            }
            self.selected.repositories = ret;
            $scope.loading = false;
            $scope.step = 'step2';
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
        $mdDialog.show(
            $mdDialog.alert()
            .clickOutsideToClose(true)
            .title('Choose a workspace')
            .textContent('<md-select>Select workspace<md-select>')
            .ariaLabel('Select workspace')
            .ok('Ok...')
        )
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
            Jobs.delete({job_id:self.selected.id},function(){
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
            Commands.query({cmd:"resync", job_id:self.selected.id}, function(){
                //console.log("THIS WILL RESYNC")
                $location.path('/')
            });
        }, function() {
            // CANCEL
        });
    };

    self.revertJob = function (){
        var orig = JobsWithId.query({}, function(){
            self.selected = orig[self.selected.id] })
    }

    self.doSave = function(){
        self.selected.$save();
    }

    $scope.$watch(self.selected, function() { console.log('Modified') }, true);
    self.showTodo = function(content){
        $mdToast.show({
                          hideDelay   : 3000,
                          position    : 'bottom right',
                          controller  : function(){},
                          template    : '<md-toast><span class="md-toast-text" style="color:yellow" flex>' + content + '</span></md-toast>'
                    });
        }
    }
})();
