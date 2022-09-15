/* globals ProctoredExamModel:false */
edx = edx || {};
(function(Backbone) {
    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};

    edx.instructor_dashboard.proctoring.ProctoredExamCollection = Backbone.Collection.extend({
        /* model for a collection of ProctoredExamAllowance */
        model: ProctoredExamModel,
        url: '/api/edx_proctoring/v1/proctored_exam/exam/course_id/'
    });
    this.edx.instructor_dashboard.proctoring.ProctoredExamCollection =
      edx.instructor_dashboard.proctoring.ProctoredExamCollection;
}).call(this, Backbone);
