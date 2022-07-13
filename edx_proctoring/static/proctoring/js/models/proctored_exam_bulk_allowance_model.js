edx = edx || {};

(Backbone => {
  'use strict';

  edx.instructor_dashboard = edx.instructor_dashboard || {};
  edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};

  edx.instructor_dashboard.proctoring.ProctoredExamBulkAllowanceModel = Backbone.Model.extend({
    url: '/api/edx_proctoring/v1/proctored_exam/bulk_allowance',

  });
  const bulkAllowanceModel = edx.instructor_dashboard.proctoring.ProctoredExamBulkAllowanceModel;
  this.edx.instructor_dashboard.proctoring.ProctoredExamBulkAllowanceModel = bulkAllowanceModel;
}).call(this, Backbone);
