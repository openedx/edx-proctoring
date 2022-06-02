edx = edx || {};

(Backbone => {
  'use strict';

  edx.instructor_dashboard = edx.instructor_dashboard || {};
  edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};

  edx.instructor_dashboard.proctoring.ProctoredExamAttemptModel = Backbone.Model.extend({
    url: '/api/edx_proctoring/v1/proctored_exam/attempt/',

  });
  const proctoredExamAttemptModel = edx.instructor_dashboard.proctoring.ProctoredExamAttemptModel;
  this.edx.instructor_dashboard.proctoring.ProctoredExamAttemptModel = proctoredExamAttemptModel;
}).call(this, Backbone);
