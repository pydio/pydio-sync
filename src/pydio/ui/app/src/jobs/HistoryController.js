
(function(){
  'use strict';
  angular.module('jobs')
  .factory('Logs', ['$resource',
    function($resource){
        return $resource('/jobs/:job_id/logs', {}, {
            query: {method:'GET', params:{job_id:''}, isArray:false}
        });
    }])
  .factory('Conflicts', ['$resource',
    function($resource){
        return $resource('/jobs/:job_id/conflicts', {}, {
            query: {method:'GET', params:{job_id:''}, isArray:true}
            });
    }])
  .filter('thedatefilter', function() {
    return function(input){
        return input.replace(/\..*/, '')
    }
  })
  .filter('basename', function(){
        return function(path){
            return path.split(/[\\/]/).pop();
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
  .controller('HistoryController', ['$mdDialog', '$mdSidenav', '$mdBottomSheet', '$timeout', '$log', '$scope', 'Logs', 'Conflicts', 'SelectedJobService', HistoryController]);

  function HistoryController( $mdDialog, $mdSidenav, mdBottomSheet, $timeout, $log, $scope, Logs, Conflicts, SelectedJobService ){

    var self = this;
    $scope.logs = undefined;
    var t0;
    var t1;
    var t2;

    (function tickSelected(){
        // invalidate logs when current selected job changes
        if ($scope.selected !== SelectedJobService.job)
            $scope.logs = undefined;
        t2 = $timeout(tickSelected, 100);
    }
    )();

    (function tickLog() {
        if(SelectedJobService.job){
            $scope.selected = SelectedJobService.job;
            var all = Logs.query({job_id:SelectedJobService.job.id}, function(){
                $scope.error = null;
                // TODO: Merge new log events instead of replacing all logs, to avoid flickering.
                $scope.logs = all.logs;
                if(all.running.tasks){
                    console.log(all.running.tasks.current)
                    // REMOVE ME FOR PROD
                    if (all.running.tasks.current.length != 0)
                        $scope.running = all.running;
                }
                if(typeof(all.running) !== 'undefined' && typeof(all.running.current) !== 'undefined'){
                    if(all.running["current"].length > 0)
                        console.log(all)
                }
            }, function(response){
                if(!response.status){
                    $scope.error = window.translate('Ooops, cannot contact agent! Make sure it is running correctly, process will try to reconnect in 20s');
                }
                console.log(response)
            });
        }
        t0 = $timeout(tickLog, 4000);
    })();

    (function tickConflict() {

        if(SelectedJobService.job && SelectedJobService.job.id){
            var conflicts = Conflicts.query({job_id:SelectedJobService.job.id}, function(){
                $scope.conflicts = conflicts;
            });
        }
        t1 = $timeout(tickConflict, 3000);
    })();

    $scope.$on('$destroy', function(){
        $timeout.cancel(t0);
        $timeout.cancel(t1);
    });

    $scope.showChangeDetails = function (item, event){
        var icon = item.type == 'remote' ? '<i class="material-icons change-history-icon">cloud_upload</i>' : '<i class="material-icons change-history-icon">cloud_download</i>'
        var titleMessage = '<div class="history-more-info"><div layout="row" flex>' + icon + '<span style="margin: 3px 0 3px 0;">&nbsp;' + item.message + "</span></div>"
        var subMessage = '<div layout="row" flex><i class="material-icons change-history-icon">history</i><span style="margin-top: 3px;">&nbsp;' + item.date.replace(/\..*/, '') + '</span></div>' + '</div>'
        $mdDialog.show({
            template: titleMessage + subMessage,
            clickOutsideToClose: true
        });
    }
    $scope.openFile = function(item, event){
        $mdDialog.show(
          $mdDialog.alert()
            .clickOutsideToClose(true)
            .title('To do')
            .textContent('Call Python OR QT with target ' + item.target + ' - or src ' + item.src)
            .ariaLabel('Alert Dialog Demo')
            .ok('Ok...')
        );
    }

    $scope.conflict_solver = {current:false,applyToAll:false}
    $scope.solveConflict = function(nodeId, status){
        $scope.conflict_solver.current = null;
        var appToAll = $scope.conflict_solver.applyToAll;
        angular.forEach($scope.conflicts, function(conflict){
            if(!appToAll && conflict.node_id != nodeId) return;
            if(appToAll && conflict.status.indexOf('SOLVED:') === 0) return;
            conflict.status = status;
            conflict.job_id = selected.id;
            conflict.$save();
        });
    };
  }
})();