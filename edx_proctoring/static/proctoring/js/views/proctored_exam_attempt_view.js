var edx = edx || {};

(function (Backbone, $, _, gettext) {
    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};
    var examStatusReadableFormat = {
        eligible: gettext('Eligible'),
        created: gettext('Created'),
        download_software_clicked: gettext('Download Software Clicked'),
        ready_to_start: gettext('Ready to start'),
        started: gettext('Started'),
        ready_to_submit: gettext('Ready to submit'),
        declined: gettext('Declined'),
        timed_out: gettext('Timed out'),
        second_review_required: gettext('Second Review Required'),
        submitted: gettext('Submitted'),
        verified: gettext('Verified'),
        rejected: gettext('Rejected'),
        error: gettext('Error')
    };
    var viewHelper = {
        getDateFormat: function(date) {
            if (date) {
                return new Date(date).toString('MMM dd, yyyy h:mmtt');
            }
            else {
                return '---';
            }

        },
        getExamAttemptStatus: function(status) {
            if (status in examStatusReadableFormat) {
                return examStatusReadableFormat[status]
            }
            else {
                return status
            }
        }
    };
    edx.instructor_dashboard.proctoring.ProctoredExamAttemptView = Backbone.View.extend({
        initialize: function (options) {
            this.setElement($('.student-proctored-exam-container'));
            this.collection = new edx.instructor_dashboard.proctoring.ProctoredExamAttemptCollection();
            this.tempate_url = '/static/proctoring/templates/student-proctored-exam-attempts.underscore';
            this.model = new edx.instructor_dashboard.proctoring.ProctoredExamAttemptModel();
            this.course_id = this.$el.data('course-id');
            this.template = null;

            this.initial_url = this.collection.url;
            this.attempt_url = this.model.url;
            this.collection.url = this.initial_url + this.course_id;
            this.inSearchMode = false;
            this.searchText = "";

            /* re-render if the model changes */
            this.listenTo(this.collection, 'change', this.collectionChanged);

            /* Load the static template for rendering. */
            this.loadTemplateData();
        },
        events: {
            "click .remove-attempt": "onRemoveAttempt",
            'click li > a.target-link': 'getPaginatedAttempts',
            'click .search-attempts > span.search': 'searchAttempts',
            'click .search-attempts > span.clear-search': 'clearSearch'
        },
        searchAttempts: function(event) {
            var searchText = $('#search_attempt_id').val();
            if (searchText !== "") {
                this.inSearchMode = true;
                this.searchText = searchText;
                this.collection.url = this.initial_url + this.course_id + "/search/" + searchText;
                this.hydrate();
                event.stopPropagation();
                event.preventDefault();
            }
        },
        clearSearch: function(event) {
            this.inSearchMode = false;
            this.searchText = "";
            this.collection.url = this.initial_url + this.course_id;
            this.hydrate();
            event.stopPropagation();
            event.preventDefault();
        },
        getPaginatedAttempts: function(event) {
            var target = $(event.currentTarget);
            this.collection.url = target.data('target-url');
            this.hydrate();
            event.stopPropagation();
            event.preventDefault();
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

                var data_json = this.collection.toJSON()[0];

                // calculate which pages ranges to display
                // show no more than 5 pages at the same time
                var start_page = data_json.pagination_info.current_page - 2;

                if (start_page < 1) {
                    start_page = 1;
                }

                var end_page = start_page + 4;

                if (end_page > data_json.pagination_info.total_pages) {
                    end_page = data_json.pagination_info.total_pages;
                }

                _.each(data_json.proctored_exam_attempts, function(proctored_exam_attempt) {
                    if (proctored_exam_attempt.proctored_exam.is_proctored) {
                        if (proctored_exam_attempt.proctored_exam.is_practice_exam) {
                            proctored_exam_attempt.exam_attempt_type = gettext('Practice');
                        } else {
                            proctored_exam_attempt.exam_attempt_type = gettext('Proctored');
                        }
                    } else {
                        proctored_exam_attempt.exam_attempt_type = gettext('Timed');
                    }
                });

                var data = {
                    proctored_exam_attempts: data_json.proctored_exam_attempts,
                    pagination_info: data_json.pagination_info,
                    attempt_url: data_json.attempt_url,
                    inSearchMode: this.inSearchMode,
                    searchText: this.searchText,
                    start_page: start_page,
                    end_page: end_page
                };
                _.extend(data, viewHelper);
                var html = this.template(data);
                this.$el.html(html);
           }
        },
        onRemoveAttempt: function (event) {
            event.preventDefault();

            // confirm the user's intent
            if (!confirm(gettext('Are you sure you want to remove this student\'s exam attempt?'))) {
                return;
            }
            $('body').css('cursor', 'wait');
            var $target = $(event.currentTarget);
            var attemptId = $target.data("attemptId");

            var self = this;
            self.model.url = this.attempt_url + attemptId;
            self.model.fetch( {
                headers: {
                    "X-CSRFToken": this.getCSRFToken()
                },
                type: 'DELETE',
                success: function () {
                    // fetch the attempts again.
                    self.hydrate();
                    $('body').css('cursor', 'auto');
                }
            });
        }
    });
    this.edx.instructor_dashboard.proctoring.ProctoredExamAttemptView = edx.instructor_dashboard.proctoring.ProctoredExamAttemptView;
}).call(this, Backbone, $, _, gettext);
