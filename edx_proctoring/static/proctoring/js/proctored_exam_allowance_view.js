var edx = edx || {};

(function(Backbone, $, _) {
    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = {};

    edx.instructor_dashboard.proctoring.ProctoredExamAllowanceView = Backbone.View.extend({
        initialize: function (options) {
            this.$el = options.el;
            this.model = options.model;
            this.temPlateUrl = options.allowance_template_url;
            this.template = null;

            /* re-render if the model changes */
            this.listenTo(this.model,'change', this.modelChanged);

            /* make the async call to the backend REST API */
            /* after it loads, the listenTo event will file and */
            /* will call into the rendering */
            //this.model.fetch();
            this.loadTemplateData();
        },
        loadTemplateData: function(){
            var self = this;
            $.ajax({url: self.temPlateUrl, dataType: "html"})
            .error(function(jqXHR, textStatus, errorThrown){

            })
            .done(function(template_data) {
                self.template  = _.template(template_data);
                self.render()
            });
        },
        modelChanged: function() {
            //this.render();
        },
        render: function () {
            if (this.template !== null) {
                var html = this.template();
                this.$el.html(html);
                this.$el.show();
            }
            return this;
        }
    });
    this.edx.instructor_dashboard.proctoring.ProctoredExamAllowanceView = edx.instructor_dashboard.proctoring.ProctoredExamAllowanceView;
}).call(this, Backbone, $, _);
