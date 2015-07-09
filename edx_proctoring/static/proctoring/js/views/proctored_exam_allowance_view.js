var edx = edx || {};

(function (Backbone, $, _) {
    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};

    edx.instructor_dashboard.proctoring.ProctoredExamAllowanceView = Backbone.View.extend({
        initialize: function (options) {
            this.collection = new edx.instructor_dashboard.proctoring.ProctoredExamAllowanceCollection();
            this.proctoredExamCollection = new edx.instructor_dashboard.proctoring.ProctoredExamCollection();
            /* unfortunately we have to make some assumptions about what is being set up in HTML */
            this.setElement($('.special-allowance-container'));
            this.course_id = this.$el.data('course-id');

            /* this should be moved to a 'data' attribute in HTML */
            this.tempate_url = '/static/proctoring/templates/course_allowances.underscore';
            this.template = null;
            this.allowance_url = this.collection.url + 'allowance';
            this.initial_url = this.collection.url;
            /* re-render if the model changes */
            this.listenTo(this.collection, 'change', this.collectionChanged);

            /* Load the static template for rendering. */
            this.loadTemplateData();

            this.proctoredExamCollection.url = this.proctoredExamCollection.url + this.course_id;
            this.collection.url = this.initial_url + this.course_id + '/allowance';

        },
        events: {
            'click #add-allowance': 'showAddModal',
            'click .remove_allowance': 'removeAllowance'
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
        removeAllowance: function (event) {
            var element = $(event.currentTarget);
            var userID = element.data('user-id');
            var examID = element.data('exam-id');
            var key = element.data('key-name');
            var self = this;
            self.collection.url = this.allowance_url;
            self.collection.fetch(
                {
                    headers: {
                        "X-CSRFToken": this.getCSRFToken()
                    },
                    type: 'DELETE',
                    data: {
                        'exam_id': examID,
                        'user_id': userID,
                        'key': key
                    },
                    success: function () {
                        // fetch the allowances again.
                        self.collection.url = self.initial_url + self.course_id + '/allowance';
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
                var html = this.template({proctored_exam_allowances: this.collection.toJSON()});
                this.$el.html(html);
                this.$el.show();
            }
        },
        showAddModal: function (event) {
            var self = this;
            self.proctoredExamCollection.fetch({
                success: function () {
                    var add_allowance_view = new edx.instructor_dashboard.proctoring.AddAllowanceView({
                        course_id: self.course_id,
                        proctored_exams: self.proctoredExamCollection.toJSON(),
                        proctored_exam_allowance_view: self
                    });
                }
            });
            event.stopPropagation();
            event.preventDefault();
        }
    });
}).call(this, Backbone, $, _);
