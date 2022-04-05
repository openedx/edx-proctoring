/* global path:false */

var gulp = require('gulp');
var karma = require('karma').server;
var path = require('path');

/**
 * Run test once and exit
 */
gulp.task('test', function(done) {
    'use strict';

    karma.start({
        configFile: path.join(__dirname, '/karma.conf.js'),
        singleRun: true
    }, done);
});

/**
 * Watch for file changes and re-run tests on each change
 */
gulp.task('tdd', function(done) {
    'use strict';

    karma.start({
        configFile: path.join(__dirname, '/karma.conf.js')
    }, done);
});

gulp.task('default', ['tdd']);


/**
 * Run test in debug mode
 */
gulp.task('debug', function(done) {
    'use strict';

    karma.start({
        configFile: path.join(__dirname, '/karma.conf.js'),
        singleRun: false
    }, done);
});
