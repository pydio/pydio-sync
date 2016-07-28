(function(){
    'use strict';
    angular.module('jobs')
    .factory('GeneralConfigs', ['$resource',
        function($resource){
            return $resource('/general_configs', {}, {
                query: {method:'GET', params:{}, isArray:false}
            });
        }])
    .controller('SettingsController', ['jobService', '$mdDialog', '$mdSidenav', '$mdBottomSheet', '$timeout', '$log', '$scope', 'GeneralConfigs', SettingsController]);
    /**
     * Controller for new jobs
     */
    function SettingsController(jobService, $mdDialog, $mdSidenav, mdBottomSheet, $timeout, $log, $scope, GeneralConfigs){
        // JS methods need to be exposed...
        var self = this;
        self._ = window.translate;

        // Load the general config from agent (http://localhost:5556/general_configs)
        var general_configs_data = GeneralConfigs.query({},
            function (){
                if(typeof(general_configs_data.update_info.enable_update_check) === "string"){
                    if(general_configs_data.update_info.enable_update_check === "true"){
                        general_configs_data.update_info.enable_update_check = true;
                    } else {
                        general_configs_data.update_info.enable_update_check = false;
                    }
                }
                $scope.general_configs_data = general_configs_data;
            }
        );
    }
})();
