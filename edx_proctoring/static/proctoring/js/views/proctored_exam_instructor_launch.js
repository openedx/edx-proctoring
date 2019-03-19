edx = edx || {};

(function(Backbone, $, _) {
    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};
    edx.instructor_dashboard.proctoring.ProctoredExamDashboardView = Backbone.View.extend({
        initialize: function() {
            var self = this;
            this.setElement($('.student-review-dashboard-container'));
            this.tempate_url = '/static/proctoring/templates/dashboard.underscore';
            this.iframeHTML = null;
            this.doRender = true;
            this.context = {
                dashboardURL: '/api/edx_proctoring/v1/instructor/' + this.$el.data('course-id')
            };

            $('#proctoring-accordion').on('accordionactivate', function(event, ui) {
                self.render(ui);
            });
            /* Load the static template for rendering. */
            this.loadTemplateData();
        },
        loadTemplateData: function() {
            var self = this;
            $.ajax({url: self.tempate_url, dataType: 'html'})
                .done(function(templateHtml) {
                    self.iframeHTML = _.template(templateHtml)(self.context);
                });
        },
        render: function(ui) {
            if (ui.newPanel.eq(this.$el) && this.doRender && this.iframeHTML) {
                this.$el.html(this.iframeHTML);
                this.doRender = false;
            }
        }
    });
    this.edx.instructor_dashboard.proctoring.ProctoredExamDashboardView =
        edx.instructor_dashboard.proctoring.ProctoredExamDashboardView;
}).call(this, Backbone, $, _);
