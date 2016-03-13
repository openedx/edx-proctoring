var edx = edx || {};
(function(Backbone) {

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};

    edx.instructor_dashboard.proctoring.ProctoringServicesCollection = Backbone.Collection.extend({
        /* model for a collection of ProctoringServices */
        model: edx.instructor_dashboard.proctoring.ProctoringServicesModel,
        url: '/api/edx_proctoring/v1/proctoring_services/'
    });
    this.edx.instructor_dashboard.proctoring.ProctoringServicesCollection = edx.instructor_dashboard.proctoring.ProctoringServicesCollection;
}).call(this, Backbone);
