/* globals accessible_modal:false */
edx = edx || {};

(function($) {
    'use strict';

    var actionToMessageTypesMap = {
        submit: {
            promptEventName: 'endExamAttempt',
            successEventName: 'examAttemptEnded',
            failureEventName: 'examAttemptEndFailed'
        },
        start: {
            promptEventName: 'startExamAttempt',
            successEventName: 'examAttemptStarted',
            failureEventName: 'examAttemptStartFailed'
        },
        ping: {
            promptEventName: 'ping',
            successEventName: 'echo',
            failureEventName: 'pingFailed'

        }
    };

    /**
   * Launch modals, handling a11y focus behavior
   *
   * Note: don't try to leverage this for the heartbeat; the DOM
   * structure this depends on doesn't live everywhere that handler
   * needs to live
   */
    function accessibleError(title, message) {
        accessible_modal(
            '#accessible-error-modal #confirm_open_button',
            '#accessible-error-modal .close-modal',
            '#accessible-error-modal',
            '.content-wrapper'
        );
        $('#accessible-error-modal #confirm_open_button').click();
        $('#accessible-error-modal .message-title').html(message);
        $('#accessible-error-modal #acessible-error-title').html(title);
        $('#accessible-error-modal .ok-button')
            .html(gettext('OK'))
            .off('click.closeModal')
            .on('click.closeModal', function() {
                $('#accessible-error-modal .close-modal').click();
            });
    }

    function createWorker(url) {
        var blob = new Blob(["importScripts('" + url + "');"], {type: 'application/javascript'});
        var blobUrl = window.URL.createObjectURL(blob);
        return new Worker(blobUrl);
    }

    function workerPromiseForEventNames(eventNames) {
        return function(timeout) {
            var proctoringBackendWorker = createWorker(edx.courseware.proctored_exam.configuredWorkerURL);
            return new Promise(function(resolve, reject) {
                var responseHandler = function(e) {
                    if (e.data.type === eventNames.successEventName) {
                        proctoringBackendWorker.removeEventListener('message', responseHandler);
                        proctoringBackendWorker.terminate();
                        resolve();
                    } else {
                        reject(e.data.error);
                    }
                };
                proctoringBackendWorker.addEventListener('message', responseHandler);
                proctoringBackendWorker.postMessage({type: eventNames.promptEventName, timeout: timeout});
            });
        };
    }

    function workerTimeoutPromise(timeoutMilliseconds) {
        var message = 'worker failed to respond after ' + timeoutMilliseconds + 'ms';
        return new Promise(function(resolve, reject) {
            setTimeout(function() {
                reject(Error(message));
            }, timeoutMilliseconds);
        });
    }

    // Update the state of the attempt
    function updateExamAttemptStatusPromise(actionUrl, action) {
        return function() {
            return Promise.resolve($.ajax({
                url: actionUrl,
                type: 'PUT',
                data: {
                    action: action
                }
            }));
        };
    }

    function reloadPage() {
        location.reload();
    }

    function setActionButtonLoadingState($button) {
        $button.prop('disabled', true);
        $button.html($button.data('loading-text'));
    }

    function setActionButtonSteadyState($button) {
        $button.prop('disabled', false);
        $button.html($button.data('cta-text'));
    }

    function errorHandlerGivenMessage($button, title, message) {
        setActionButtonSteadyState($button);
        return function() {
            accessibleError(title, message);
        };
    }


    edx.courseware = edx.courseware || {};
    edx.courseware.proctored_exam = edx.courseware.proctored_exam || {};
    edx.courseware.proctored_exam.updateStatusHandler = function() {
        var $this = $(this);
        var actionUrl = $this.data('change-state-url');
        var action = $this.data('action');
        updateExamAttemptStatusPromise(actionUrl, action)()
            .then(reloadPage)
            .catch(errorHandlerGivenMessage(
                $this,
                gettext('Error Ending Exam'),
                gettext(
                    'Something has gone wrong ending your exam. ' +
                    'Please reload the page and start again.'
                )
            ));
    };
    edx.courseware.proctored_exam.examStartHandler = function(e) {
        var $this = $(this);
        var actionUrl = $this.data('change-state-url');
        var action = $this.data('action');
        var shouldUseWorker = window.Worker && edx.courseware.proctored_exam.configuredWorkerURL;

        e.preventDefault();
        e.stopPropagation();

        setActionButtonLoadingState($this);

        if (shouldUseWorker) {
            workerPromiseForEventNames(actionToMessageTypesMap[action])()
                .then(updateExamAttemptStatusPromise(actionUrl, action))
                .then(reloadPage)
                .catch(errorHandlerGivenMessage(
                    $this,
                    gettext('Error Starting Exam'),
                    gettext(
                        'Something has gone wrong starting your exam. ' +
            'Please double-check that the application is running.'
                    )
                ));
        } else {
            updateExamAttemptStatusPromise(actionUrl, action)()
                .then(reloadPage)
                .catch(errorHandlerGivenMessage(
                    $this,
                    gettext('Error Starting Exam'),
                    gettext(
                        'Something has gone wrong starting your exam. ' +
            'Please reload the page and start again.'
                    )
                ));
        }
    };
    edx.courseware.proctored_exam.examEndHandler = function() {
        var $this = $(this);
        var actionUrl = $this.data('change-state-url');
        var action = $this.data('action');
        var shouldUseWorker = window.Worker &&
                          edx.courseware.proctored_exam.configuredWorkerURL &&
                          action === 'submit';
        $(window).unbind('beforeunload');

        setActionButtonLoadingState($this);

        if (shouldUseWorker) {
            updateExamAttemptStatusPromise(actionUrl, action)()
                .then(workerPromiseForEventNames(actionToMessageTypesMap[action]))
                .then(reloadPage)
                .catch(errorHandlerGivenMessage(
                    $this,
                    gettext('Error Ending Exam'),
                    gettext(
                        'Something has gone wrong ending your exam. ' +
                        'Please double-check that the application is running.'
                    )
                ));
        } else {
            updateExamAttemptStatusPromise(actionUrl, action)()
                .then(reloadPage)
                .catch(errorHandlerGivenMessage(
                    $this,
                    gettext('Error Ending Exam'),
                    gettext(
                        'Something has gone wrong ending your exam. ' +
            'Please reload the page and start again.'
                    )
                ));
        }
    };
    edx.courseware.proctored_exam.checkExamAttemptStatus = function(attemptStatusPollURL) {
        return new Promise(function(resolve, reject) {
            $.ajax(attemptStatusPollURL).success(function(data) {
                if (data.status) {
                    resolve(data.status);
                } else {
                    reject();
                }
            }).fail(function() {
                reject();
            });
        });
    };
    edx.courseware.proctored_exam.endExam = function(attemptStatusPollURL) {
        var shouldUseWorker = window.Worker &&
                          edx.courseware.proctored_exam.configuredWorkerURL;
        if (shouldUseWorker) {
            // todo would like to double-check the exam is ended on the LMS before proceeding
            return edx.courseware.proctored_exam.checkExamAttemptStatus(attemptStatusPollURL)
                .then(function(status) {
                    if (status === 'submitted') {
                        return workerPromiseForEventNames(actionToMessageTypesMap.submit)();
                    }
                    return Promise.reject();
                });
        } else {
            return Promise.resolve();
        }
    };
    edx.courseware.proctored_exam.pingApplication = function(timeoutInSeconds) {
        var TIMEOUT_BUFFER_SECONDS = 10;
        var workerPingTimeout = timeoutInSeconds - TIMEOUT_BUFFER_SECONDS; // 10s buffer for worker to respond
        return Promise.race([
            workerPromiseForEventNames(actionToMessageTypesMap.ping)(workerPingTimeout * 1000),
            workerTimeoutPromise(timeoutInSeconds * 1000)
        ]);
    };
    edx.courseware.proctored_exam.accessibleError = accessibleError;
}).call(this, $);
