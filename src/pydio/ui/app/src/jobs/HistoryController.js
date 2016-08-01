
(function(){
  'use strict';

  // Prepare the 'users' module for subsequent registration of controllers and delegates
  angular.module('jobs')
  .factory('Logs', ['$resource',
    function($resource){
        return $resource('/jobs/:job_id/logs', {}, {
            query: {method:'GET', params:{job_id:''}, isArray:false}
        });
    }])
  .controller('HistoryController', ['$mdDialog', '$mdSidenav', '$mdBottomSheet', '$timeout', '$log', '$scope', 'Logs', HistoryController]);

  function HistoryController( $mdDialog, $mdSidenav, mdBottomSheet, $timeout, $log, $scope, Logs){
       var self = this;
       //self.selected = $scope.selected;
        self.loadLogs = loadLogs;
        var tO;
        var t1;
        (function tickLog() {
            if(typeof($scope.selected) !== 'undefined'){
                var all = Logs.query({job_id:$scope.selected.id}, function(){
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
            }
        })();
        /*(function tickConflict() {
        var conflicts = Conflicts.query({job_id:$scope.selected.id}, function(){
            $scope.conflicts = conflicts;
            t1 = $timeout(tickConflict, 3000);
        });
        })();*/
        $scope.$on('$destroy', function(){
            $timeout.cancel(tO);
            $timeout.cancel(t1);
        });

        function loadLogs(){
            console.log('Yolo clicked');
            var all = Logs.query({job_id:$scope.selected.id}, function(){
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
        }

  }
})();