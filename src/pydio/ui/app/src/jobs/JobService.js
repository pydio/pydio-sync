(function(){
  'use strict';

  angular.module('jobs')
         .service('jobService', ['$q', JobService]);

  /**
   * Users DataService
   * Uses embedded, hard-coded data model; acts asynchronously to simulate
   * remote data service call(s).
   *
   * @returns {{loadAll: Function}}
   * @constructor
   */
  function JobService($q){
      var jobs = {
          'localhost-shared-ws-1':{
              'active' : false,
              'direction' : 'bi',
              'directory' : '/Users/thomas/Pydio/tests/TestsCharlesFat',
              'filters' : {'excludes': ['.*', '*/.*', '/recycle_bin*', '*.pydio_dl', '*.DS_Store', '.~lock.*', '~*', '*.xlk', '*.tmp'], 'includes': ['*']},
              'frequency' : 'auto',
              'hide_bi_dir' : 'false',
              'hide_down_dir' : 'false',
              'hide_up_dir' : 'false',
              'id' : '192.168.0.64-my-files',
              'label' : 'Pydio Enterprise - flash dat',
              'monitor' : true,
              'online_timer' : 10,
              'poolsize' : 4,
              'remote_folder' : '/flash dat',
              'server' : 'http://192.168.0.64',
              'server_configs' : "",
              'solve' : 'both',
              'start_time' : {'h': 0, 'm': 0},
              'timeout' : 20,
              'trust_ssl' : false,
              'user_id' : 'admin',
              'workspace' : 'my-files',
			  'status': 'Some how set this'
          },
          'localhost-shared-ws-2':{
              'active' : true,
              'direction' : 'bi',
              'directory' : '/Users/thomas/Pydio/tests/TestsCharlesFat',
              'filters' : {'excludes': ['.*', '*/.*', '/recycle_bin*', '*.pydio_dl', '*.DS_Store', '.~lock.*', '~*', '*.xlk', '*.tmp'], 'includes': ['*']},
              'frequency' : 'auto',
              'hide_bi_dir' : 'false',
              'hide_down_dir' : 'false',
              'hide_up_dir' : 'false',
              'id' : '192.168.0.64-my-files',
              'label' : 'Pydio 2 - dat',
              'monitor' : true,
              'online_timer' : 10,
              'poolsize' : 4,
              'remote_folder' : '/flash dat',
              'server' : 'http://192.168.0.64',
              'server_configs' : "",
              'solve' : 'both',
              'start_time' : {'h': 0, 'm': 0},
              'timeout' : 20,
              'trust_ssl' : false,
              'user_id' : 'admin',
              'workspace' : 'my-files',
			  'status': 'Some how set this'
          }
      };
	  var history = [{'filename': 'yolo.txt', 'notes': 'uploaded to /lol/yolo.txt'}, {'filename': 'Test.pdf', 'notes': 'Download from /lol/test.pdf'}];
	  var syncing = [{'filename': 'movie.mp4', 'notes': 'Uploading to /lol/'}, {'filename': 'bob.pdf', 'notes': 'Downloading from /lol/'}];
      var jobList = [];
      for(var i = 0; i< 10; i++){
          var u = {}
          u.name = 'Sync task ' + i;
          u.avatar = 'svg-' + i;
          u.progress = Math.random()*100;
          u.content = 'iahahahahhahahahah ahah ahah ahahahahah ';
          jobList.push(u);
      }
      // Promise-based API
      return {
          loadJobList : function() {
              // Simulate async nature of real remote calls
              return $q.when(jobList);
          },
			loadAllJobs : function() {
              // Simulate async nature of real remote calls
              return $q.when(jobs);
          }
      };
  }

})();
