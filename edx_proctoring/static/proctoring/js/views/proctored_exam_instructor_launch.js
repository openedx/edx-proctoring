var edx = edx || {};

(function (Backbone, $, _, gettext) {
    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};
    edx.instructor_dashboard.proctoring.ProctoredExamDashboardView = Backbone.View.extend({
        initialize: function (options) {
            this.setElement($('.student-review-dashboard-container'));
            this.tempate_url = '/static/proctoring/templates/dashboard.underscore';
            this.template = null;
            this.doRender = true;
            this.template_data = {
                dashboardURL: '/api/edx_proctoring/v1/instructor/' + this.$el.data('course-id')
            };
            var self = this;

            $('#proctoring-accordion').on('accordionactivate', function(event, ui) {
                self.render(ui);
            });
            /* Load the static template for rendering. */
            this.loadTemplateData();
        },
        loadTemplateData: function () {
            var self = this;
            $.ajax({url: self.tempate_url, dataType: "html"})
                .error(function (jqXHR, textStatus, errorThrown) {

                })
                .done(function (template_data) {
                    self.template = _.template(template_data);
                });
        },
        render: function (ui) {
            if (ui.newPanel.eq(this.$el)) {
                if (this.doRender) {
                    this.$el.html(this.template(this.template_data));
                    this.doRender = false;
                }
            }
        },
    });
    this.edx.instructor_dashboard.proctoring.ProctoredExamDashboardView = edx.instructor_dashboard.proctoring.ProctoredExamDashboardView;
}).call(this, Backbone, $, _, gettext);
