edx = edx || {};

(function(Backbone) {
    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};

    edx.instructor_dashboard.proctoring.ProctoredExamAttemptModel = Backbone.Model.extend({
        url: '/api/edx_proctoring/v1/proctored_exam/attempt/'

    });
    this.edx.instructor_dashboard.proctoring.ProctoredExamAttemptModel =
      edx.instructor_dashboard.proctoring.ProctoredExamAttemptModel;
}).call(this, Backbone);
