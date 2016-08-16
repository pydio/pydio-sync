// USELESS for now
(function(){
    'use strict';
    angular.module('jobs').controller('NewJobController', ['jobService', '$mdDialog', '$mdSidenav', '$mdBottomSheet', '$timeout', '$log', '$scope', NewJobController]);
    /**
     * Controller for new jobs
     */
    function NewJobController(jobService, $mdDialog, $mdSidenav, mdBottomSheet, $timeout, $log, $scope){
        // JS methods need to be exposed...
        var self = this;
        self.toggleNewJobConfig = toggleNewJobConfig;
        self.showURLTip = showURLTip;

        self.job = {};
        self.job.user = "pydio";
        self.job.password = "pydiopassword";
        self.job.server = "http://localhost:7443/";
        self.job.local_folder = "/Users/thomas/Pydio/tests/oneMoreTest";
        self.job.remote_folder = "/";
        self.job.total_size = 12002020;
        self.job.eta = 111232123;
        function showURLTip (ev) {
            var titleMessage = '<h2>How can I find my server URL?</h2>'
            var subMessage = '<p>The server URL is the adress that you can see in your browser when accessing Pydio via the web. It starts with http or https depending on your server configuration. If you are logged in Pydio and you see the last part of the URL starting with "ws-", remove this part and only keep the beginning (see image below).</p>'
            var img = '<img class="img-thumbnail" src="images/ServerURL.png" alt="Server url help" style="max-width: 100%; max-height: 400px;">'
            $mdDialog.show({
                template: titleMessage + subMessage,
                clickOutsideToClose: true
            });
        };
        function toggleNewJobConfig(){
            $scope.showNewTask = !$scope.showNewTask; // doesn't work, wrong scope
        }
    }
})();
