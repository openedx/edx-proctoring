var edx = edx || {};

(function(Backbone, $, _) {
    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};

    edx.instructor_dashboard.proctoring.ProctoredExamAllowanceView = Backbone.View.extend({
        initialize: function (options) {
            this.$el = options.el;
            this.collection = new edx.instructor_dashboard.proctoring.ProctoredExamAllowanceCollection();
            this.course_id = options.course_id;
            this.temPlateUrl = options.allowance_template_url;
            this.template = null;

            /* re-render if the model changes */
            this.listenTo(this.collection, 'change', this.collectionChanged);

            /* make the async call to the backend REST API */
            /* after it loads, the listenTo event will file and */
            /* will call into the rendering */
            this.loadTemplateData();

            this.collection.url = this.collection.url + '/' + this.course_id;

        },
        loadTemplateData: function(){
            var self = this;
            $.ajax({url: self.temPlateUrl, dataType: "html"})
            .error(function(jqXHR, textStatus, errorThrown){

            })
            .done(function(template_data) {
                self.template  = _.template(template_data);
                self.hydrate();
            });
        },
        hydrate: function() {
            /* This function will load the bound collection */

            /* add and remove a class when we do the initial loading */
            /* we might - at some point - add a visual element to the */
            /* loading, like a spinner */
            var self = this;
            this.collection.fetch({
                success: function(){
                    self.render();
                }
            });
        },
        collectionChanged: function() {
            this.hydrate();
        },
        render: function () {
            if (this.template !== null) {
                var html = this.template(this.collection.toJSON());
                this.$el.html(html);
                this.$el.show();
            }
        }
    });
    this.edx.instructor_dashboard.proctoring.ProctoredExamAllowanceView = edx.instructor_dashboard.proctoring.ProctoredExamAllowanceView;
}).call(this, Backbone, $, _);
