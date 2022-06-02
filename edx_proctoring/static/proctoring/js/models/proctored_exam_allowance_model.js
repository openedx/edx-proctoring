edx = edx || {};

(Backbone => {
  'use strict';

  edx.instructor_dashboard = edx.instructor_dashboard || {};
  edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};

  edx.instructor_dashboard.proctoring.ProctoredExamAllowanceModel = Backbone.Model.extend({
    url: '/api/edx_proctoring/v1/proctored_exam/allowance',

  });
  const proctoredExamAllowanceModel = edx.instructor_dashboard.proctoring.ProctoredExamAllowanceModel;
  this.edx.instructor_dashboard.proctoring.ProctoredExamAllowanceModel = proctoredExamAllowanceModel;
}).call(this, Backbone);
