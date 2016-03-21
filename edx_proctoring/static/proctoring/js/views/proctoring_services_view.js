var edx = edx || {};

(function (Backbone, $, _) {
    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};

    edx.instructor_dashboard.proctoring.ProctoringServicesView = Backbone.View.extend({
        initialize: function () {

            this.collection = new edx.instructor_dashboard.proctoring.ProctoringServicesCollection();
            this.proctoredExamCollection = new edx.instructor_dashboard.proctoring.ProctoredExamCollection();
            /* unfortunately we have to make some assumptions about what is being set up in HTML */
            this.setElement($('.proctoring-services-container'));
            this.course_id = this.$el.data('course-id');

            /* this should be moved to a 'data' attribute in HTML */
            this.template_url = '/static/proctoring/templates/proctoring_services.underscore';
            this.template = null;
            this.initial_url = this.collection.url;
            /* re-render if the model changes */

            /* Load the static template for rendering. */
            this.loadTemplateData();

            this.proctoredExamCollection.url = this.proctoredExamCollection.url + this.course_id;
            this.collection.url = this.initial_url + this.course_id;

        },
        events: {
            'change #proctoring-select': 'changeProctoringService',
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
        changeProctoringService: function (event) {
            var element = $(event.currentTarget);
            var proctor = element.val()
            var self = this;
            self.collection.fetch(
                {
                    headers: {
                        "X-CSRFToken": this.getCSRFToken()
                    },
                    type: 'PUT',
                    data: {
                        'proctoring_service': proctor,
                    },
                    success: function () {
                        alert("Proctoring service has successfully changed.");
                        self.hydrate();
                    }
                }
            );
            event.stopPropagation();
            event.preventDefault();
        },
        /*
         This entry point is required for Instructor Dashboard
         See setup_instructor_dashboard_sections() in
         instructor_dashboard.coffee (in edx-platform)
         */
        constructor: function (section) {
            /* the Instructor Dashboard javascript expects this to be set up */
            $(section).data('wrapper', this);

            this.initialize({});
        },
        onClickTitle: function () {
            // called when this is selected in the instructor dashboard
            return;
        },
        loadTemplateData: function () {
            var self = this;
            $.ajax({url: self.template_url, dataType: "html"})
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
                var self = this;
                var html = this.template({data:this .collection.toJSON()[0]});
                this.$el.html(html);
            }
        },
    });
    this.edx.instructor_dashboard.proctoring.ProctoringServicesView = edx.instructor_dashboard.proctoring.ProctoringServicesView;
}).call(this, Backbone, $, _);
