edx = edx || {};

(function(Backbone, $, _) {
    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};

    edx.instructor_dashboard.proctoring.ProctoredExamAllowanceView = Backbone.View.extend({
        initialize: function() {
            this.allowance_types = [
                ['additional_time_granted', gettext('Additional Time (minutes)')],
                ['review_policy_exception', gettext('Review Policy Exception')]
            ];

            this.collection = new edx.instructor_dashboard.proctoring.ProctoredExamAllowanceCollection();
            this.proctoredExamCollection = new edx.instructor_dashboard.proctoring.ProctoredExamCollection();
            /* unfortunately we have to make some assumptions about what is being set up in HTML */
            this.setElement($('.special-allowance-container'));
            this.course_id = this.$el.data('course-id');

            /* this should be moved to a 'data' attribute in HTML */
            this.template_url = '/static/proctoring/templates/course_allowances.underscore';
            this.template = null;
            this.initial_url = this.collection.url;
            this.allowance_url = this.initial_url + 'allowance';
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
        getCSRFToken: function() {
            var cookieValue = null;
            var name = 'csrftoken';
            var cookies, cookie, i;
            if (document.cookie && document.cookie !== '') {
                cookies = document.cookie.split(';');
                for (i = 0; i < cookies.length; i += 1) {
                    cookie = jQuery.trim(cookies[i]);
                    // Does this cookie string begin with the name we want?
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        },
        removeAllowance: function(event) {
            var $element = $(event.currentTarget);
            var userID = $element.data('user-id');
            var examID = $element.data('exam-id');
            var key = $element.data('key-name');
            var self = this;
            self.collection.url = this.allowance_url;
            self.collection.fetch(
                {
                    headers: {
                        'X-CSRFToken': this.getCSRFToken()
                    },
                    type: 'DELETE',
                    data: {
                        exam_id: examID,
                        user_id: userID,
                        key: key
                    },
                    success: function() {
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
        constructor: function(section) {
            /* the Instructor Dashboard javascript expects this to be set up */
            $(section).data('wrapper', this);

            this.initialize({});
        },
        onClickTitle: function() {
            // called when this is selected in the instructor dashboard

        },
        loadTemplateData: function() {
            var self = this;
            $.ajax({url: self.template_url, dataType: 'html'})
                .done(function(templateData) {
                    self.template = _.template(templateData);
                    self.hydrate();
                });
        },
        hydrate: function() {
            /* This function will load the bound collection */

            /* add and remove a class when we do the initial loading */
            /* we might - at some point - add a visual element to the */
            /* loading, like a spinner */
            var self = this;
            self.collection.fetch({
                success: function() {
                    self.render();
                }
            });
        },
        collectionChanged: function() {
            this.hydrate();
        },
        render: function() {
            var self = this;
            var key, i, html;
            if (this.template !== null) {
                this.collection.each(function(item) {
                    key = item.get('key');
                    for (i = 0; i < self.allowance_types.length; i += 1) {
                        if (key === self.allowance_types[i][0]) {
                            item.set('key_display_name', self.allowance_types[i][1]);
                            break;
                        }
                    }
                    if (!item.has('key_display_name')) {
                        item.set('key_display_name', key);
                    }
                });
                html = this.template({proctored_exam_allowances: this.collection.toJSON()});
                this.$el.html(html);
            }
        },
        showAddModal: function(event) {
            var self = this;
            self.proctoredExamCollection.fetch({
                success: function() {
                    // eslint-disable-next-line no-new
                    new edx.instructor_dashboard.proctoring.AddAllowanceView({
                        course_id: self.course_id,
                        proctored_exams: self.proctoredExamCollection.toJSON(),
                        proctored_exam_allowance_view: self,
                        allowance_types: self.allowance_types
                    });
                }
            });
            event.stopPropagation();
            event.preventDefault();
        }
    });
    this.edx.instructor_dashboard.proctoring.ProctoredExamAllowanceView =
        edx.instructor_dashboard.proctoring.ProctoredExamAllowanceView;
}).call(this, Backbone, $, _);
