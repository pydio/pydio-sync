angular.module('project', ['ngRoute', 'ngResource'])


    .factory('Jobs', ['$resource',
        function($resource){
            return $resource('/jobs/:job_id/', {}, {
                query: {method:'GET', params:{job_id:''}, isArray:true}
            });
        }])

    .service('currentJob', function() {
        var objectValue = null;
        return {
            getJob: function() {
                return objectValue;
            },
            setJob: function(value) {
                objectValue = value;
            }
        }
    })

    .factory('Ws', ['$resource',
        function($resource){
            return $resource('/ws/:job_id/', {}, {
                query: {method:'GET', params:{
                    job_id:'',
                    url   :'',
                    user  :'',
                    password:''
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
                    password:''
                }, isArray:true}
            });
        }])

    .config(function($routeProvider) {
        $routeProvider
            .when('/', {
                controller:'ListCtrl',
                templateUrl:'list.html'
            })
            .when('/edit/:jobId/full', {
                controller:'EditCtrl',
                templateUrl:'03-Workspace.html'
            })
            .when('/edit/:jobId/step1', {
                controller:'EditCtrl',
                templateUrl:'01-Connection.html'
            })
            .when('/edit/:jobId/step2', {
                controller:'EditCtrl',
                templateUrl:'02-Credentials.html'
            })
            .when('/edit/:jobId/step3', {
                controller:'EditCtrl',
                templateUrl:'03-Workspace.html'
            })
            .when('/summary/:jobId', {
                controller:'EditCtrl',
                templateUrl:'04-Summary.html'
            })
            .when('/new', {
                controller:'CreateCtrl',
                templateUrl:'01-Connection.html'
            })
            .otherwise({
                redirectTo:'/'
            });
    })

    .controller('ListCtrl', function($scope, $location, Jobs, currentJob) {
        $scope.jobs = Jobs.query(function(resp){
            if(!resp.length) $location.path('/new');
        });
        currentJob.setJob(null);
    })

    .controller('CreateCtrl', function($scope, $location, $timeout, Jobs, currentJob) {
        var job = new Jobs();
        job.id = 'new';
        job.remote_folder = '/';
        job.directory = '/Path/to/local';
        job.workspace = 'ws-watched';
        job.__type__ = 'JobConfig'
        $scope.job = job;
        currentJob.setJob($scope.job);
    })

    .controller('EditCtrl', function($scope, $location, $routeParams, Jobs, currentJob, Ws, Folders) {
        if(!currentJob.getJob()){
            currentJob.setJob(Jobs.get({
                job_id:$routeParams.jobId
            }));
        }
        $scope.jobs = Jobs.query();
        $scope.job = currentJob.getJob();
        Ws.get({
            job_id:$routeParams.jobId
        }, function(response){
            $scope.repositories = response.repositories.repo;
            angular.forEach($scope.repositories, function(r){
                if(r['@repositorySlug'] == $scope.job.workspace){
                    $scope.job.repoObject = r;
                }
            });
        });
        $scope.folders = Folders.query({
            job_id:$routeParams.jobId
        });

        $scope.save = function() {
            if($scope.job.repoObject){
                $scope.job.workspace = $scope.job.repoObject['@repositorySlug'];
            }
            if($scope.job.id == 'new') {
                delete $scope.job.id;
                $scope.job.$save(function(resp){
                    $location.path('/summary/'+resp.id);
                });
            }else{
                $scope.job.$save();
                $location.path('/summary/'+$scope.job.id);
            }
        };
    });