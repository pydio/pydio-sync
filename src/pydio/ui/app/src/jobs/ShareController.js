var share_details;

(function(){
    angular.module('jobs')
    .service('shareFile', function() {
        var objectValue = {
            'fileName':'',
            'shareLink':'',
            'shareJobId':'',
            'existingLinkFlag':''
            };
        return {
            get: function() {
                return objectValue;
            },
            set: function(key, value) {
                objectValue[key] = value;
            }
        }
    })
    .factory('Share', ['$resource',
        function($resource){
            return $resource('/share/:job_id/', {}, {
                query: {method:'GET', params:{
                    action:'',
                    job_id:'',
                    ws_label:'',
                    ws_description:'',
                    password:'',
                    expiration:'',
                    downloads:'',
                    can_read:'',
                    can_download:'',
                    relative_path:'',
                    link_handler: '',
                    can_write: '',
                    checkExistingLinkFlag:''
                }, isArray:false},
                unshare: {method:'GET', params:{
                    job_id:'',
                    action:'unshare',
                    path:''
                }, isArray:false}
            });
        }])
    .controller('ShareCtrl', ['$scope', '$window', '$route', '$location', '$routeParams', 'Share', 'shareFile', ShareCtrl]);
    function ShareCtrl($scope, $window, $route, $location, $routeParams, Share, shareFile) {
        $scope._ = window.translate;
        $scope.share_preview = true;
        $scope.share_download_checkbox = true;
        $scope.share_allowed_downloads = 0;
        $scope.can_write = false;
        $scope.share_expire_in = 0;

        if (window.ui_config){
            $scope.ui_config = window.ui_config;
        }
        // Display the view based on the type of layout
        if($routeParams.layout == "miniview" || document.URL.indexOf("minivew") > -1) {
            if (document.getElementsByTagName("body")[0].className.indexOf("miniview") == -1)
                document.getElementsByTagName("body")[0].className += "miniview";
                // disable right click reload
                document.getElementsByTagName("body")[0].setAttribute("oncontextmenu", "return false");
                $scope.miniview = true;
        } else {
            var sharediv = document.getElementById("shareDiv");
            if (sharediv)
                sharediv.setAttribute("style", "margin-top:80px !important;");
        }

        $scope.updateProgBar = function (){
            try {
                $scope.loading = true;
                document.getElementById("shareDiv").style = "display:none !important;";
                var progbar = document.getElementById("progbar");
                var newval = parseInt(progbar.style.width)*1.3;
                progbar.style = "width:" + newval + "%";
                progbar.setAttribute('aria-valuenow', newval);
            } catch (error){
             //
            }
        }
        $scope.startProgBar = function () {
            $scope.updateProgBar();
            $scope.timer = window.setInterval($scope.updateProgBar, 200);
        }
        $scope.stopProgBar = function (){
            clearInterval($scope.timer);
        }

        $scope.QtObject = window.PydioQtFileDialog;

        // Enable write flag if the item is a folder
        if($routeParams.itemType == "folder"){
            $scope.can_write = true;
        }

        // Check if a shared link already exists for the selected item.
        function checkExistingLink(){
            var res;
            shareFile.set('fileName',$routeParams.itemPath)
            shareFile.set('shareJobId',$routeParams.jobId)

            res = Share.query({
                action:'share',
                job_id: $routeParams.jobId,
                relative_path: $routeParams.itemPath,
                checkExistingLinkFlag:'true'
            }, function(){
                if(res.existingLinkFlag == 'true') {
                    shareFile.set('shareLink',res.link)
                    shareFile.set('existingLinkFlag','true')
                    $location.path('/share/response/' + $routeParams.layout);
                }
               }
            );
        };

        // This condition to avoid checkExistingLink to be called from response page as it uses same
        if($routeParams.jobId){
            $scope.share_filename = $routeParams.itemPath;
            checkExistingLink();
        }

        // Generate the share link for the selected item.
        $scope.generateLink = function(){
            $scope.startProgBar();
            var res;

            res = Share.query({
                action:'share',
                job_id:$routeParams.jobId,
                ws_label:$routeParams.itemPath.replace(/^.*[\\\/]/, ''),
                ws_description:$scope.share_description,
                password:$scope.share_password,
                expiration:$scope.share_expire_in,
                downloads:$scope.share_allowed_downloads,
                can_read:$scope.share_preview,
                can_download:$scope.share_download_checkbox,
                relative_path: $routeParams.itemPath,
                link_handler: $scope.share_link_handler,
                can_write: $scope.share_upload_checkbox
            }, function(){
                shareFile.set('shareLink',res.link)
                $location.path('/share/response/' + $routeParams.layout);
                $scope.stopProgBar();
                }
            );
        };

        // GetShareLink shares the details with share response page
        $scope.GetShareLink = function(){
            share_details = shareFile.get();
            $scope.share_link = share_details['shareLink'];
            $scope.existingLinkFlag = share_details['existingLinkFlag'];
            $scope.share_filename = share_details['fileName'];
            $scope.checkResponseFlag = (share_details['shareLink'].substring(0, 4)=='http')
        };

        // File browser
        $scope.openFile = function(){
            var res;
            if(!window.PydioQtFileDialog) {
                res = window.prompt(window.translate('Full path to the local folder'));
            }else{
                res = $routeParams.itemPath;
            }
            if(res){
                $scope.share_filename = res;
            }
        };

        //Un-share the selected item.
        $scope.unShareLink = function(){
            $scope.share_details = shareFile.get();
            res = Share.unshare({
                job_id:$scope.share_details['shareJobId'],
                action:'unshare',
                path: $scope.share_details['fileName']
            }, function(){
                 if($routeParams.layout == "miniview" || document.URL.indexOf("minivew") > -1) {
                    $scope.miniview_done = true;
                 } else {
                    $location.path('/');
                 }
               }
            );
        };

        $scope.copyToClipBoard = function(value){
            // check if the text can be copied from QT's copy to clip board else show error message
            try {
                JC.PydioQtFileDialog.copyToClipBoard(value);
                $scope.copyToClipBoardFlag = true;
            } catch (err) {
                try {
                    interOp.callSwift(value);
                    window.webkit.messageHandlers.swift.postMessage({body: value});
                    $scope.copyToClipBoardFlag = true;
                } catch (err) {
                    console.log("Copy to clipboard is not possible while using web browser");
                }
            }
        };
    } // end of controller
    })();