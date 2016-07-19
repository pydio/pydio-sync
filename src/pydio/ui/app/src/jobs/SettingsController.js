(function(){
    'use strict';
    angular.module('jobs').controller('SettingsController', ['jobService', '$mdDialog', '$mdSidenav', '$mdBottomSheet', '$timeout', '$log', '$scope', SettingsController]);
    /**
     * Controller for new jobs
     */
    function SettingsController(jobService, $mdDialog, $mdSidenav, mdBottomSheet, $timeout, $log, $scope){
        // JS methods need to be exposed...
        var self = this;
        $scope._ = window.translate;
        self._ = window.translate;
    }
})();
