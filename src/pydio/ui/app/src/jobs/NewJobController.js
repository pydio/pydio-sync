
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
    .factory('Folders', ['$resource',
        function($resource){
            return $resource('/folders/:job_id/', {}, {
                query: {method:'GET', params:{
                    job_id:'',
                    url   :'',
                    ws    :'',
                    user  :'',
                    password:'',
                    subdir:''
                }, isArray:true}
            });
        }])
    .controller('NewJobController', ['jobService', '$mdDialog', '$mdSidenav', '$mdBottomSheet', '$timeout', '$log', '$scope', '$mdToast', 'Ws', 'Folders', NewJobController]);
    /**
     * Controller for new jobs
     */
    function NewJobController(jobService, $mdDialog, $mdSidenav, mdBottomSheet, $timeout, $log, $scope, $mdToast, Ws, Folders){
        // JS methods need to be exposed...
        var self = this;

        $scope.hide = function() {
          $mdDialog.hide();
        };
        $scope.cancel = function() {
          $mdDialog.cancel();
        };
        $scope.answer = function(answer) {
          $mdDialog.hide(answer);
        };
        $scope._ = window.translate;
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

        self.loadFolders = function(){
            $scope.loading = true;
            self.folders = Folders.query({
                job_id:'request',
                url:self.job.server,
                user:self.job.user,
                password:self.job.password,
                trust_ssl:self.job.trust_ssl?'true':'false',
                ws:self.job.workspace['@repositorySlug']
            }, function(resp){
                if(resp[0] && resp[0].error){
                    self.toastError(resp[0].error);
                }
                $scope.loading = false;
            }, function(resp){
                $scope.loading = false;
                self.toastError(window.translate('Error while loading folders!'));
            })
        }

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
                var error;
                if(resp.data && resp.data.error){
                    error = resp.data.error;
                } else {
                    error = "Connection problem"
                }
                self.toastError(error)
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

        self.clearNewFolder = function(){
            // the following block should be factored into a clean function. #RefactorMe
            if(typeof(self.job) !== "undefined" && typeof(self.job.new_remote_folder) !== "undefined"){ // delete if exists
                var path = self.job.new_remote_folder['@filename'];
                if (path[0]== "/") // remove leading /
                    path = path.substr(1, path.length);
                var pathitems = path.split("/");
                var nextnode = {};
                for (var j in pathitems) {
                    pathitems[j] = "/" + pathitems[j];
                    if (j > 0) {
                        pathitems[j] = pathitems[j-1] + pathitems[j];
                        for (var i in nextnode['tree']){
                            if (typeof(nextnode['tree'][i]) !== "undefined" && pathitems[j] == nextnode['tree'][i]['@filename']){
                                if (pathitems.length-1 == j){
                                    nextnode['tree'].splice(i, 1);
                                } else {
                                    nextnode = nextnode['tree'][i];
                                }
                            }
                        }
                    } else {
                        var exit = false;
                        for (var i in self.folders) { // find root
                            if (self.folders[i]['@filename'] == pathitems[0]) {
                                if (pathitems.length == 1){
                                    console.log("DELETE")
                                    self.folders[i]['tree'].splice(self.folders[i]['tree'].indexOf(self.job.new_remote_folder), 1);
                                    exit = true;
                                } else {
                                    nextnode = self.folders[i];
                                }
                                break;
                            }
                        }
                        if (exit)
                            break;
                    }
                }
            }
            self.job.new_remote_folder = undefined;
        }

        self.newFolder = function (data){
            self.clearNewFolder();
            self.job.new_remote_folder = {'@filename':data['@filename'] + '/untitled folder', '@text': 'untitled folder', 'PydioSyncNewNode': true};
            // the following block should be factored into a clean function. #RefactorMe
            var path = data['@filename'];
            if (path[0]== "/") // remove leading /
                path = path.substr(1, path.length);
            var pathitems = path.split("/");
            var nextnode = {};
            for (var j in pathitems) {
                pathitems[j] = "/" + pathitems[j];
                if (j > 0) {
                    pathitems[j] = pathitems[j-1] + pathitems[j];
                    for (var i in nextnode['tree']){
                        if (typeof(nextnode['tree']) !== "undefined" && typeof(nextnode['tree'][i]) !== "undefined" && pathitems[j] == nextnode['tree'][i]['@filename']){
                            //console.log(nextnode['tree'][i]);
                            if (pathitems.length-1 == j){
                                if (typeof(nextnode['tree'][i]['tree']) === "undefined" || typeof(nextnode['tree'][i]['tree']) == Boolean){
                                    nextnode['tree'][i]['tree'] = [];
                                }
                                nextnode['tree'][i]['tree'].push(self.job.new_remote_folder);
                            } else {
                                nextnode = nextnode['tree'][i];
                            }
                        }
                    }
                } else {
                    var exit = false;
                    for (var i in self.folders) { // find root
                        if (self.folders[i]['@filename'] == pathitems[0]) {
                            if (pathitems.length == 1){
                                if (typeof(self.folders[i]['tree']) === "undefined" || typeof(self.folders[i]) == Boolean){
                                    self.folders[i]['tree'] = [];
                                }
                                self.folders[i]['tree'].push(self.job.new_remote_folder);
                                exit = true;
                            } else {
                                nextnode = self.folders[i];
                            }
                            break;
                        }
                    }
                    if (exit)
                        break;
                }
            }
        }

        self.displaySubFolders = function(path){
            /* path subfolder name to refresh how to get the parent's ?
            */
            //console.log('Fetch ls ' + path);
            $scope.loading = true;
            var subfolders = Folders.query({
                job_id:'request',
                url:self.job.server,
                user:self.job.user,
                password:self.job.password,
                trust_ssl:self.job.trust_ssl?'true':'false',
                ws:self.job.workspace['@repositorySlug'],
                subdir:path
            }, function(resp){
                console.log(resp)
                if(resp[0] && resp[0].error){
                     self.toastError(resp[0].error);
                }
                $scope.loading = false;
                // insert the tree where it belongs... Replace an array inside an array of maps
                // the following block should be factored into a clean function. #RefactorMe
                if (path[0]== "/") // remove leading /
                    path = path.substr(1, path.length);
                var pathitems = path.split("/");
                var nextnode = {};
                for (var j in pathitems) {
                    pathitems[j] = "/" + pathitems[j];
                    if (j > 0) {
                        pathitems[j] = pathitems[j-1] + pathitems[j];
                        for (var i in nextnode['tree']){
                            if (typeof(nextnode['tree']) !== "undefined" && typeof(nextnode['tree'][i]) !== "undefined" && pathitems[j] == nextnode['tree'][i]['@filename']){
                                console.log(nextnode['tree'][i]);
                                if (pathitems.length-1 == j){
                                    nextnode['tree'][i]['tree'] = subfolders;
                                } else {
                                    nextnode = nextnode['tree'][i];
                                }
                            }
                        }
                    } else {
                        var exit = false;
                        for (var i in self.folders) { // find root
                            if (self.folders[i]['@filename'] == pathitems[0]) {
                                if (pathitems.length == 1){
                                    self.folders[i]['tree'] = subfolders;
                                    exit = true;
                                } else {
                                    nextnode = self.folders[i];
                                }
                                break;
                            }
                        }
                        if (exit)
                            break;
                    }
                }
            }, function(resp){
                $scope.loading = false;
                self.toastError(window.translate('Error while loading folders!'));
            });
        }



        self.toastError = function ( error ){
            $mdToast.show({
                      hideDelay   : 9000,
                      position    : 'bottom right',
                      controller  : this,
                      template    : '<md-toast><span class="md-toast-text" style="color:red" flex>' + error + '</span></md-toast>'
                });
        }
        self.doneWithEnter = function(ev, step){
            if (ev.keyCode == 13)
                $scope.step = step;
        }
    }

})();

