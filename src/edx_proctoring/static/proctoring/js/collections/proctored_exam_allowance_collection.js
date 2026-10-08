edx = edx || {};
(function(Backbone) {
    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};

    edx.instructor_dashboard.proctoring.ProctoredExamAllowanceCollection = Backbone.Collection.extend({
        /* model for a collection of ProctoredExamAllowance */
        model: edx.instructor_dashboard.proctoring.ProctoredExamAllowanceModel,
        url: '/api/edx_proctoring/v1/proctored_exam/'
    });
    this.edx.instructor_dashboard.proctoring.ProctoredExamAllowanceCollection =
        edx.instructor_dashboard.proctoring.ProctoredExamAllowanceCollection;
}).call(this, Backbone);
