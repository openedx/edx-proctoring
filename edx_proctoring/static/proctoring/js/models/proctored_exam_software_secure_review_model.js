var edx = edx || {};

(function(Backbone) {

    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};

    edx.instructor_dashboard.proctoring.ProctoredExamSoftwareSecureReview = Backbone.Model.extend({
        url: '/api/edx_proctoring/v1/proctored_exam/software_secure_review/attempt/'

    });
    this.edx.instructor_dashboard.proctoring.ProctoredExamSoftwareSecureReview = edx.instructor_dashboard.proctoring.ProctoredExamSoftwareSecureReview;
}).call(this, Backbone);
