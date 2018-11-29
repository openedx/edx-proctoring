
// Add ability to turn coverage off when the tests are run in debug mode
var sourcePreprocessors = 'coverage';

function isDebug(argument) {
    'use strict';

    return argument === 'debug';
}
if (process.argv.some(isDebug)) {
    sourcePreprocessors = [];
}


module.exports = function(config) {
    'use strict';

    config.set({

        basePath: '',

        // plugins required for running the karma tests
        plugins: [
            'karma-jasmine',
            'karma-jasmine-jquery',
            'karma-jasmine-jquery',
            'karma-chrome-launcher',
            'karma-phantomjs-launcher',
            'karma-coverage',
            'karma-sinon'
        ],

        // start the browser
        browsers: ['PhantomJS'],

        // frameworks to use
        frameworks: ['jasmine-jquery', 'jasmine', 'sinon'],

        // patterns to load all files in child folders
        files: [
            'edx_proctoring/static/proctoring/spec/proctored_exam_global_vars.js',
            'node_modules/babel-polyfill/dist/polyfill.js', // polyfills for e.g. Promises
            'edx_proctoring/static/proctoring/js/vendor/i18n.js',
            'edx_proctoring/static/proctoring/js/vendor/jquery.js',
            'edx_proctoring/static/proctoring/js/vendor/underscore.js',
            'edx_proctoring/static/proctoring/js/vendor/backbone.js',
            'edx_proctoring/static/proctoring/js/vendor/date.js',
            'edx_proctoring/static/proctoring/js/models/*.js',
            'edx_proctoring/static/proctoring/js/collections/*.js',
            'edx_proctoring/static/proctoring/js/views/*.js',
            'edx_proctoring/static/proctoring/spec/*.js'
        ],

        // preprocess matching files before serving them to the browser
        // available preprocessors: https://npmjs.org/browse/keyword/karma-preprocessor
        preprocessors: {
            'edx_proctoring/static/proctoring/js/models/*.js': sourcePreprocessors,
            'edx_proctoring/static/proctoring/js/collections/*.js': sourcePreprocessors,
            'edx_proctoring/static/proctoring/js/views/*.js': sourcePreprocessors
        },

        // test results reporter to use
        // possible values: 'dots', 'progress'
        // available reporters: https://npmjs.org/browse/keyword/karma-reporter
        reporters: ['progress', 'coverage'],

        coverageReporter: {
            dir: 'build',
            subdir: 'coverage-js',
            reporters: [
                {type: 'html', subdir: 'coverage-js/html'},
                {type: 'cobertura', file: 'coverage.xml'},
                {type: 'text-summary'}
            ]
        },

        // enable / disable colors in the output (reporters and logs)
        colors: true,

        // level of logging
        // possible values: config.LOG_DISABLE ||
        //                  config.LOG_ERROR ||
        //                  config.LOG_WARN ||
        //                  config.LOG_INFO ||
        //                  config.LOG_DEBUG
        logLevel: config.LOG_INFO,


        // enable / disable watching file and executing tests whenever any file changes
        autoWatch: true,

        captureTimeout: 60000,

        // Continuous Integration mode
        // if true, Karma captures browsers, runs the tests and exits
        singleRun: false

    });
};

