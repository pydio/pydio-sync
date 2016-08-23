(function(){

  angular.module('jobs', ['ngResource'])
        .factory('Jobs', ['$resource',
            function($resource){
                return $resource('/jobs/:job_id/', {}, {
                    query: {method:'GET', params:{job_id:''}, isArray:true}
                });
        }])
        .factory('JobsWithId', ['$resource',
            function($resource){
                return $resource('/jobs/:job_id', {}, {
                    query: {method:'GET', params:{job_id:'',with_id:true}}
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
    $scope._ = window.translate;
    var self = this;

    self.selected     = null;
    self.selectJob   = selectJob;
    self.toggleList   = toggleSideNav;
    self.makeContact  = makeContact;
    self.newSyncTask = newSyncTask;
    self.changeSelected = changeSelected;
    self.toggleGeneralSettings = toggleGeneralSettings;

    // Load all jobs
    self.syncing = jobService.syncing;
    self.history = jobService.history;
    $scope.pathes = {};
    $scope.jobs = Jobs.query();
    self.jobs = $scope.jobs;

    self.menuOpened = false;
    $scope.$on('$mdMenuClose', function(){ self.menuOpened = false});

    var t0;
    (function tickJobs() {
        var tmpJobs = Jobs.query(function(){
                    console.log('tick')
                    $scope.error = null;
                    // TODO: Merge new jobs events instead of replacing all jobs, to avoid flickering.
                    if ( !self.menuOpened ){
                        console.log('refresh')
                        self.jobs = tmpJobs;
                        $scope.jobs = tmpJobs;
                    }
                }, function(response){
                    if( !response.status ){
                        $scope.error = window.translate('Ooops, cannot contact agent! Make sure it is running correctly, process will try to reconnect in 20s');
                        $mdToast.show(
                          $mdToast.simple()
                            .textContent($scope.error)
                            .hideDelay(3000)
                        );
                    }
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
    function selectJob ( job ) {
        $scope.currentNavItem = 'history';
        $scope.showAllJobs = false;
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
    jobService.currentNavItem = 'history';
    function newSyncTask(){
        $scope.showNewTask = !$scope.showNewTask
        $scope.showAllJobs = false
        $scope.showGeneralSettings = false
    }
    window.onload = function (){
        //toggleSideNav();
        if ($scope.jobs.length == 1)
            changeSelected(0)
        else $scope.showAllJobs = true;
    }

    /**
        $scope toggles, bad practice probably
    */
    function changeSelected(item){
        selectJob(item)
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
        console.log($scope.jobs)
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
                $scope.currentNavItem = 'history';

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
                $scope.currentNavItem = "settings"
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
                  controller  : self,
                  template    : '<md-toast><span class="md-toast-text" style="color:red" flex>' + $scope.error + '</span></md-toast>'
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
  }
})();
