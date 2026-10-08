edx = edx || {};

(function(Backbone) {
    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};

    edx.instructor_dashboard.proctoring.ProctoredExamAllowanceModel = Backbone.Model.extend({
        url: '/api/edx_proctoring/v1/proctored_exam/allowance'

    });
    this.edx.instructor_dashboard.proctoring.ProctoredExamAllowanceModel =
      edx.instructor_dashboard.proctoring.ProctoredExamAllowanceModel;
}).call(this, Backbone);
