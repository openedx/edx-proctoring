var edx = edx || {};

(function($) {
  'use strict';

  var ONE_MINUTE_MS = 60000;

  var actionToMessageTypesMap = {
    'submit': {
      promptEventName: 'endExamAttempt',
      successEventName: 'examAttemptEnded',
      failureEventName: 'examAttemptEndFailed'
    },
    'start': {
      promptEventName: 'startExamAttempt',
      successEventName: 'examAttemptStarted',
      failureEventName: 'examAttemptStartFailed'
    },
    'ping': {
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
       "#accessible-error-modal #confirm_open_button",
       "#accessible-error-modal .close-modal",
       "#accessible-error-modal",
       ".content-wrapper"
     );
     $("#accessible-error-modal #confirm_open_button").click();
     $("#accessible-error-modal .message-title").html(message);
     $('#accessible-error-modal #acessible-error-title').html(title);
     $("#accessible-error-modal .ok-button")
       .html(gettext("OK"))
       .off('click.closeModal')
       .on('click.closeModal', function(){
         $("#accessible-error-modal .close-modal").click();
       });
  };


  function workerPromiseForEventNames(eventNames) {
    return function() {
      var proctoringBackendWorker = new Worker(edx.courseware.proctored_exam.configuredWorkerURL);
      return new Promise(function(resolve, reject) {
        var responseHandler = function(e) {
          if (e.data.type === eventNames.successEventName) {
            proctoringBackendWorker.removeEventListener('message', responseHandler);
            proctoringBackendWorker.terminate();
            resolve();
          } else {
            reject();
          }
        };
        proctoringBackendWorker.addEventListener('message', responseHandler);
        proctoringBackendWorker.postMessage({ type: eventNames.promptEventName});
      });
    };
  }

  function timeoutPromise(timeoutMilliseconds) {
    return new Promise(function(resolve, reject) {
      setTimeout(reject, timeoutMilliseconds);
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
  edx.courseware.proctored_exam.examStartHandler = function(e) {
    e.preventDefault();
    e.stopPropagation();

    var $this = $(this);
    var actionUrl = $this.data('change-state-url');
    var action = $this.data('action');

    setActionButtonLoadingState($this);

    var shouldUseWorker = window.Worker && edx.courseware.proctored_exam.configuredWorkerURL;
    if(shouldUseWorker) {
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

    $(window).unbind('beforeunload');

    var $this = $(this);
    var actionUrl = $this.data('change-state-url');
    var action = $this.data('action');

    setActionButtonLoadingState($this);

    var shouldUseWorker = window.Worker &&
                          edx.courseware.proctored_exam.configuredWorkerURL &&
                          action === "submit";
    if(shouldUseWorker) {

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
  }
  edx.courseware.proctored_exam.pingApplication = function(timeoutInSeconds) {
    return Promise.race([
      workerPromiseForEventNames(actionToMessageTypesMap.ping)(),
      timeoutPromise(timeoutInSeconds * 1000)
    ]);
  }
  edx.courseware.proctored_exam.accessibleError = accessibleError;
}).call(this, $);
