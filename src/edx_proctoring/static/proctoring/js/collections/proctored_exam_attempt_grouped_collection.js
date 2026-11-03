edx = edx || {};
(function(Backbone) {
    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};

    edx.instructor_dashboard.proctoring.ProctoredExamAttemptGroupedCollection = Backbone.Collection.extend({
        /* model for a collection of ProctoredExamAttempt */
        model: edx.instructor_dashboard.proctoring.ProctoredExamAttemptModel,
        url: '/api/edx_proctoring/v1/proctored_exam/attempt/grouped/course_id/'
    });
    this.edx.instructor_dashboard.proctoring.ProctoredExamAttemptGroupedCollection =
      edx.instructor_dashboard.proctoring.ProctoredExamAttemptGroupedCollection;
}).call(this, Backbone);
