var edx = edx || {};

(function (Backbone, $, _) {
    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};

    edx.instructor_dashboard.proctoring.ProctoredExamAttemptView = Backbone.View.extend({
        initialize: function (options) {
            this.$el = options.el;
            this.collection = options.collection;
            this.tempate_url = options.template_url;
            this.course_id = this.$el.data('course-id');
            this.template = null;

            this.initial_url = this.collection.url;
            this.collection.url = this.initial_url + this.course_id;

            /* re-render if the model changes */
            this.listenTo(this.collection, 'change', this.collectionChanged);

            /* Load the static template for rendering. */
            this.loadTemplateData();
        },
        events: {

        },
        getCSRFToken: function () {
            var cookieValue = null;
            var name = 'csrftoken';
            if (document.cookie && document.cookie != '') {
                var cookies = document.cookie.split(';');
                for (var i = 0; i < cookies.length; i++) {
                    var cookie = jQuery.trim(cookies[i]);
                    // Does this cookie string begin with the name we want?
                    if (cookie.substring(0, name.length + 1) == (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        },
        loadTemplateData: function () {
            var self = this;
            $.ajax({url: self.tempate_url, dataType: "html"})
                .error(function (jqXHR, textStatus, errorThrown) {

                })
                .done(function (template_data) {
                    self.template = _.template(template_data);
                    self.hydrate();
                });
        },
        hydrate: function () {
            /* This function will load the bound collection */

            /* add and remove a class when we do the initial loading */
            /* we might - at some point - add a visual element to the */
            /* loading, like a spinner */
            var self = this;
            self.collection.fetch({
                success: function () {
                    self.render();
                }
            });
        },
        collectionChanged: function () {
            this.hydrate();
        },
        render: function () {
            if (this.template !== null) {
                var html = this.template({proctored_exam_attempts: this.collection.toJSON()[0].proctored_exam_attempts});
                this.$el.html(html);
                this.$el.show();
            }
        }
    });
    this.edx.instructor_dashboard.proctoring.ProctoredExamAttemptView = edx.instructor_dashboard.proctoring.ProctoredExamAttemptView;
}).call(this, Backbone, $, _);
