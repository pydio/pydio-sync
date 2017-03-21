module.exports = function(grunt) {
    grunt.initConfig({

        copy: {
            material: {
                expand: true,
                src: 'node_modules/angular-material/angular-material.min.css',
                dest: 'app/assets/',
                flatten:true
            },
            materialicons: {
                expand: true,
                src: 'node_modules/material-design-icons/iconfont/*',
                dest: 'app/assets/md',
                flatten:true
            },
        },


        uglify: {
            options: {
                mangle: false,
                compress: {
                    hoist_funs: false
                }
            },
            js: {
                files: {
                    'app/bundle.min.js': [
                        'node_modules/angular/angular.min.js',
                        'node_modules/angular-animate/angular-animate.min.js',
                        'node_modules/angular-aria/angular-aria.min.js',
                        'node_modules/angular-material/angular-material.min.js',
                        'node_modules/angular-resource/angular-resource.min.js',
                        'node_modules/angular-route/angular-route.min.js',
                    ]
                }
            }
        }

    });

    grunt.loadNpmTasks('grunt-contrib-uglify');
    grunt.loadNpmTasks('grunt-contrib-copy');
    grunt.registerTask('default', [
        'copy:material',
        'copy:materialicons',
        'uglify:js'
    ]);
};
