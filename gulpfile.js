// eslint-disable-next-line no-redeclare
/* global path:false */

const gulp = require('gulp');
const karma = require('karma').server;
const path = require('path');

/**
 * Run test once and exit
 */
gulp.task('test', (done) => {
  'use strict';

  karma.start({
    configFile: path.join(__dirname, '/karma.conf.js'),
    singleRun: true,
  }, done);
});

/**
 * Watch for file changes and re-run tests on each change
 */
gulp.task('tdd', (done) => {
  'use strict';

  karma.start({
    configFile: path.join(__dirname, '/karma.conf.js'),
  }, done);
});

gulp.task('default', gulp.series('tdd'));

/**
 * Run test in debug mode
 */
gulp.task('debug', (done) => {
  'use strict';

  karma.start({
    configFile: path.join(__dirname, '/karma.conf.js'),
    singleRun: false,
  }, done);
});
