var edx = edx || {};

(function(Backbone) {

    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};

    edx.instructor_dashboard.proctoring.ProctoringServicesModel = Backbone.Model.extend({
        url: '/api/edx_proctoring/v1/proctoring_services/'

    });
    this.edx.instructor_dashboard.proctoring.ProctoringServicesModel = edx.instructor_dashboard.proctoring.ProctoringServicesModel;
}).call(this, Backbone);
