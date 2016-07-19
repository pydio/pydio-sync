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
        self.job.user = "lol";
        self.job.password = "lolpasssword";
        self.job.server = "http://company.lol/";
        self.job.local_folder = "/Users/lol/Pydio/My Files";
        self.job.remote_folder = "/Sync";
        self.job.total_size = 12002020;
        self.job.eta = 111232123;
        function showURLTip (ev) {
            // Appending dialog to document.body to cover sidenav in docs app
            // Modal dialogs should fully cover application
            // to prevent interaction outside of dialog
            console.log('Show tooltip');
            $mdDialog.show(
              $mdDialog.alert()
                .parent(angular.element(document.querySelector('#popupContainer')))
                .clickOutsideToClose(true)
                .title('This is an alert title')
                .textContent('You can specify some description text in here.')
                .ariaLabel('Alert Dialog Demo')
                .ok('Got it!')
                .targetEvent(ev)
            );
        };
        function toggleNewJobConfig(){
            $scope.showNewTask = !$scope.showNewTask; // doesn't work, wrong scope
        }
    }
})();
