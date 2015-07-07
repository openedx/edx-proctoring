var edx = edx || {};

(function(Backbone, $, _) {
    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};

    edx.instructor_dashboard.proctoring.ProctoredExamAllowanceView = Backbone.View.extend({
        initialize: function (options) {
            this.collection = new edx.instructor_dashboard.proctoring.ProctoredExamAllowanceCollection();

            /* unfortunately we have to make some assumptions about what is being set up in HTML */
            this.$el = $('.special-allowance-container');
            this.course_id = this.$el.data('course-id');

            /* this should be moved to a 'data' attribute in HTML */
            this.tempate_url = '/static/proctoring/templates/add-allowance.underscore';
            this.template = null;

            /* re-render if the model changes */
            this.listenTo(this.collection, 'change', this.collectionChanged);

            /* make the async call to the backend REST API */
            /* after it loads, the listenTo event will file and */
            /* will call into the rendering */
            this.loadTemplateData();

            this.collection.url = this.collection.url + '/' + this.course_id;

        },
        /*
            This entry point is required for Instructor Dashboard
            See setup_instructor_dashboard_sections() in
            instructor_dashboard.coffee (in edx-platform)
        */
        constructor: function(section){
            /* the Instructor Dashboard javascript expects this to be set up */
            $(section).data('wrapper', this);

            this.initialize({});
        },
        onClickTitle: function(){
            // called when this is selected in the instructor dashboard
            return;
        },
        loadTemplateData: function(){
            var self = this;
            $.ajax({url: self.tempate_url, dataType: "html"})
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
}).call(this, Backbone, $, _);
