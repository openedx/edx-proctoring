/* globals accessible_modal:false */
edx = edx || {};

($ => {
  'use strict';

  const actionToMessageTypesMap = {
    submit: {
      promptEventName: 'endExamAttempt',
      successEventName: 'examAttemptEnded',
      failureEventName: 'examAttemptEndFailed',
    },
    start: {
      promptEventName: 'startExamAttempt',
      successEventName: 'examAttemptStarted',
      failureEventName: 'examAttemptStartFailed',
    },
    ping: {
      promptEventName: 'ping',
      successEventName: 'echo',
      failureEventName: 'pingFailed',

    },
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
      '.content-wrapper',
    );
    $('#accessible-error-modal #confirm_open_button').click();
    $('#accessible-error-modal .message-title').html(message);
    $('#accessible-error-modal #acessible-error-title').html(title);
    $('#accessible-error-modal .ok-button')
      .html(gettext('OK'))
      .off('click.closeModal')
      .on('click.closeModal', () => {
        $('#accessible-error-modal .close-modal').click();
      });
  }

  function createWorker(url) {
    const blob = new Blob([`importScripts('${url}');`], { type: 'application/javascript' });
    const blobUrl = window.URL.createObjectURL(blob);
    return new Worker(blobUrl);
  }

  function workerPromiseForEventNames(eventNames) {
    return timeout => {
      const proctoringBackendWorker = createWorker(edx.courseware.proctored_exam.configuredWorkerURL);
      return new Promise((resolve, reject) => {
        const responseHandler = e => {
          if (e.data.type === eventNames.successEventName) {
            proctoringBackendWorker.removeEventListener('message', responseHandler);
            proctoringBackendWorker.terminate();
            resolve();
          } else {
            reject(e.data.error);
          }
        };
        proctoringBackendWorker.addEventListener('message', responseHandler);
        proctoringBackendWorker.postMessage({ type: eventNames.promptEventName, timeout });
      });
    };
  }

  function workerTimeoutPromise(timeoutMilliseconds) {
    const message = `worker failed to respond after ${timeoutMilliseconds}ms`;
    return new Promise((resolve, reject) => {
      setTimeout(() => {
        reject(Error(message));
      }, timeoutMilliseconds);
    });
  }

  // Update the state of the attempt
  function updateExamAttemptStatusPromise(actionUrl, action) {
    return () => Promise.resolve($.ajax({
      url: actionUrl,
      type: 'PUT',
      data: {
        action,
      },
    }));
  }

  function reloadPage() {
    window.location.reload();
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
    return () => {
      accessibleError(title, message);
    };
  }

  edx.courseware = edx.courseware || {};
  edx.courseware.proctored_exam = edx.courseware.proctored_exam || {};
  edx.courseware.proctored_exam.updateStatusHandler = () => {
    const $this = $(this);
    const actionUrl = $this.data('change-state-url');
    const action = $this.data('action');
    updateExamAttemptStatusPromise(actionUrl, action)()
      .then(reloadPage)
      .catch(errorHandlerGivenMessage(
        $this,
        gettext('Error Ending Exam'),
        gettext(
          'Something has gone wrong ending your exam. '
                    + 'Please reload the page and start again.',
        ),
      ));
  };
  edx.courseware.proctored_exam.examStartHandler = e => {
    const $this = $(this);
    const actionUrl = $this.data('change-state-url');
    const action = $this.data('action');
    const shouldUseWorker = window.Worker && edx.courseware.proctored_exam.configuredWorkerURL;
    const pingInterval = edx.courseware.proctored_exam.ProctoringAppPingInterval;
    let startIntervalInMilliseconds;
    if (pingInterval) {
      startIntervalInMilliseconds = pingInterval * 1000;
    }

    e.preventDefault();
    e.stopPropagation();

    setActionButtonLoadingState($this);

    if (shouldUseWorker) {
      workerPromiseForEventNames(actionToMessageTypesMap[action])(startIntervalInMilliseconds)
        .then(updateExamAttemptStatusPromise(actionUrl, action))
        .then(reloadPage)
        .catch(errorHandlerGivenMessage(
          $this,
          gettext('Error Starting Exam'),
          gettext(
            'Something has gone wrong starting your exam. '
            + 'Please double-check that the application is running.',
          ),
        ));
    } else {
      updateExamAttemptStatusPromise(actionUrl, action)()
        .then(reloadPage)
        .catch(errorHandlerGivenMessage(
          $this,
          gettext('Error Starting Exam'),
          gettext(
            'Something has gone wrong starting your exam. '
            + 'Please reload the page and start again.',
          ),
        ));
    }
  };
  edx.courseware.proctored_exam.examEndHandler = () => {
    const $this = $(this);
    const actionUrl = $this.data('change-state-url');
    const action = $this.data('action');
    const shouldUseWorker = window.Worker
                          && edx.courseware.proctored_exam.configuredWorkerURL
                          && action === 'submit';
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
            'Something has gone wrong ending your exam. '
                        + 'Please double-check that the application is running.',
          ),
        ));
    } else {
      updateExamAttemptStatusPromise(actionUrl, action)()
        .then(reloadPage)
        .catch(errorHandlerGivenMessage(
          $this,
          gettext('Error Ending Exam'),
          gettext(
            'Something has gone wrong ending your exam. '
            + 'Please reload the page and start again.',
          ),
        ));
    }
  };
  edx.courseware.proctored_exam.checkExamAttemptStatus = attemptStatusPollURL => new Promise((resolve, reject) => {
    $.ajax(attemptStatusPollURL).success((data) => {
      if (data.status) {
        resolve(data.status);
      } else {
        reject();
      }
    }).fail(() => {
      reject();
    });
  });
  edx.courseware.proctored_exam.endExam = attemptStatusPollURL => {
    const shouldUseWorker = window.Worker
                          && edx.courseware.proctored_exam.configuredWorkerURL;
    if (shouldUseWorker) {
      // todo would like to double-check the exam is ended on the LMS before proceeding
      return edx.courseware.proctored_exam.checkExamAttemptStatus(attemptStatusPollURL)
        .then((status) => {
          if (status === 'submitted') {
            return workerPromiseForEventNames(actionToMessageTypesMap.submit)();
          }
          return Promise.reject();
        });
    }
    return Promise.resolve();
  };
  edx.courseware.proctored_exam.pingApplication = timeoutInSeconds => {
    const TIMEOUT_BUFFER_SECONDS = 10;
    const workerPingTimeout = timeoutInSeconds - TIMEOUT_BUFFER_SECONDS; // 10s buffer for worker to respond
    return Promise.race([
      workerPromiseForEventNames(actionToMessageTypesMap.ping)(workerPingTimeout * 1000),
      workerTimeoutPromise(timeoutInSeconds * 1000),
    ]);
  };
  edx.courseware.proctored_exam.accessibleError = accessibleError;
}).call(this, $);
