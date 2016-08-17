
(function(){
    'use strict';
    angular
    .module('jobs')
    .factory('Ws', ['$resource',
        function($resource){
            return $resource('/ws/:job_id/', {}, {
                query: {method:'GET', params:{
                    job_id:''
                }}
            });
        }])
    .controller('NewJobController', ['jobService', '$mdDialog', '$mdSidenav', '$mdBottomSheet', '$timeout', '$log', '$scope', '$mdToast', 'Ws', NewJobController]);
    /**
     * Controller for new jobs
     */
    function NewJobController(jobService, $mdDialog, $mdSidenav, mdBottomSheet, $timeout, $log, $scope, $mdToast, Ws){
        // JS methods need to be exposed...
        var self = this;
        self.toggleNewJobConfig = toggleNewJobConfig;
        self.showURLTip = showURLTip;

        self.job = {};
        self.job.user = "pydio";
        self.job.password = "pydiopassword";
        self.job.server = "https://localhost:7443/";
        self.job.local_folder = "/Users/thomas/Pydio/tests/oneMoreTest";
        self.job.remote_folder = "/";
        self.job.total_size = 12002020;
        self.job.eta = 111232123;
        function showURLTip (ev) {
            var titleMessage = '<h2 style="padding: 10px;">How can I find my server URL?</h2>'
            var subMessage = '<p style="padding: 10px;">The server URL is the adress that you can see in your browser when accessing Pydio via the web. It starts with http or https depending on your server configuration. If you are logged in Pydio and you see the last part of the URL starting with "ws-", remove this part and only keep the beginning (see image below).</p>'
            var img = '<md-content flex layout-padding><img class="img-thumbnail" src="assets/images/ServerURL.png" alt="Server url help" style="max-width: 400px; max-height: 400px;"></md-content>'
            $mdDialog.show({
                template: titleMessage + img + subMessage,
                clickOutsideToClose: true
            });
        };
        function toggleNewJobConfig(){
            $scope.showNewTask = !$scope.showNewTask; // doesn't work, wrong scope
        }
        self.addNewJob = function(){
            //$scope.job.$save()
            console.log(self.job)
        }
        self.loadWorkspaces = function(){
            $scope.loading = true;
            if(self.job.id == 'new' && !self.job.password) {
                return;
            }
            self.job.workspace = '';
            Ws.get({
                job_id:'request',
                url:self.job.server,
                user:self.job.user,
                password:self.job.password,
                trust_ssl:self.job.trust_ssl?'true':'false'
            }, function(response){
                if(response.application_title){
                    self.job.application_title = response.application_title;
                }
                if(response.user_display_name){
                    self.job.user_display_name = response.user_display_name;
                }
                var ret = [] // clean up response
                for (var i in response.repositories.repo){
                    if (typeof(response.repositories.repo[i]["@repositorySlug"]) !== "undefined" && response.repositories.repo[i]["@meta_syncable_REPO_SYNCABLE"] === "true" ){
                        ret.push(response.repositories.repo[i])
                    }
                }
                self.job.repositories = ret;
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
                      controller  : this,
                      template    : '<md-toast><span class="md-toast-text" style="color:red" flex>' + $scope.error + '</span></md-toast>'
                });
                $scope.loading = false;
            });
        };

        self.showFolderPicker = function (ev){
            console.log('yolo')
            // Appending dialog to document.body to cover sidenav in docs app
            var confirm = $mdDialog.prompt()
              .title('Path to an existing folder on your computer')
              .textContent('')
              .placeholder('')
              .ariaLabel('Path to folder')
              .targetEvent(ev)
              .ok('Choose')
              .clickOutsideToClose('true');
            $mdDialog.show(confirm).then(function(result) {
              self.job.local_folder = result;
            }, function() {
              self.job.local_folder = 'You didn\'t name your dog.';
            });
        };
    }
})();
