edx = edx || {};

(function(Backbone, $, _, gettext) {
    'use strict';

    var viewHelper, examStatusReadableFormat;
    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};
    examStatusReadableFormat = {
        eligible: gettext('Eligible'),
        created: gettext('Created'),
        download_software_clicked: gettext('Download Software Clicked'),
        ready_to_start: gettext('Ready to start'),
        ready_to_resume: gettext('Ready to resume'),
        started: gettext('Started'),
        ready_to_submit: gettext('Ready to submit'),
        declined: gettext('Declined'),
        timed_out: gettext('Timed out'),
        second_review_required: gettext('Second Review Required'),
        submitted: gettext('Submitted'),
        verified: gettext('Verified'),
        rejected: gettext('Rejected'),
        error: gettext('Error'),
        onboarding_missing: gettext('Onboarding Missing'),
        onboarding_pending: gettext('Onboarding Pending'),
        onboarding_failed: gettext('Onboarding Failed'),
        onboarding_expired: gettext('Onboarding Expired')
    };
    viewHelper = {
        getDateFormat: function(date) {
            if (date) {
                return new Date(date).toString('MMM dd, yyyy h:mmtt');
            } else {
                return '---';
            }
        },
        getExamAttemptStatus: function(status) {
            if (status in examStatusReadableFormat) {
                return examStatusReadableFormat[status];
            } else {
                return status;
            }
        }
    };
    edx.instructor_dashboard.proctoring.ProctoredExamAttemptView = Backbone.View.extend({
        initialize: function() {
            this.setElement($('.student-proctored-exam-container'));
            this.collection = new edx.instructor_dashboard.proctoring.ProctoredExamAttemptCollection();
            this.template_url = '/static/proctoring/templates/student-proctored-exam-attempts.underscore';
            this.model = new edx.instructor_dashboard.proctoring.ProctoredExamAttemptModel();
            this.course_id = this.$el.data('course-id');
            this.template = null;

            this.enable_exam_resume_proctoring_improvements =
                this.$el.data('enable-exam-resume-proctoring-improvements');
            this.enable_exam_resume_proctoring_improvements = this.enable_exam_resume_proctoring_improvements &&
                this.enable_exam_resume_proctoring_improvements.toLowerCase() === 'true';


            this.initial_url = this.collection.url;
            this.attempt_url = this.model.url;
            this.collection.url = this.initial_url + this.course_id;
            this.inSearchMode = false;
            this.searchText = '';

            /* re-render if the model changes */
            this.listenTo(this.collection, 'change', this.collectionChanged);

            /* Load the static template for rendering. */
            this.loadTemplateData();
        },
        events: {
            'click .remove-attempt': 'onRemoveAttempt',
            'click .resume-attempt': 'onResumeAttempt',
            'click li > a.target-link': 'getPaginatedAttempts',
            'click .search-attempts > span.search': 'searchAttempts',
            'click .search-attempts > span.clear-search': 'clearSearch',
            'click .action-more': 'toggleExamAttemptActionDropdownMenu'
        },
        toggleExamAttemptActionDropdownMenu: function(event) {
            edx.dashboard.dropdown.toggleExamAttemptActionDropdownMenu(event);
        },
        searchAttempts: function(event) {
            var searchText = $('#search_attempt_id').val();
            if (searchText !== '') {
                this.inSearchMode = true;
                this.searchText = searchText;
                this.collection.url = this.initial_url + this.course_id + '/search/' + searchText;
                this.hydrate();
                event.stopPropagation();
                event.preventDefault();
            }
        },
        clearSearch: function(event) {
            this.inSearchMode = false;
            this.searchText = '';
            this.collection.url = this.initial_url + this.course_id;
            this.hydrate();
            event.stopPropagation();
            event.preventDefault();
        },
        getPaginatedAttempts: function(event) {
            var $target = $(event.currentTarget);
            this.collection.url = $target.data('target-url');
            this.hydrate();
            event.stopPropagation();
            event.preventDefault();
        },
        getCSRFToken: function() {
            var cookieValue = null;
            var name = 'csrftoken';
            var cookie, cookies, i;
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
            var dataJson, startPage, endPage, data, html;
            if (this.template !== null) {
                dataJson = this.collection.toJSON()[0];

                // calculate which pages ranges to display
                // show no more than 5 pages at the same time
                startPage = dataJson.pagination_info.current_page - 2;

                if (startPage < 1) {
                    startPage = 1;
                }

                endPage = startPage + 4;

                if (endPage > dataJson.pagination_info.total_pages) {
                    endPage = dataJson.pagination_info.total_pages;
                }

                _.each(
                    dataJson.proctored_exam_attempts,
                    function(proctoredExamAttempt) {
                        var isProctored = proctoredExamAttempt.proctored_exam.is_proctored;
                        var isPractice = proctoredExamAttempt.proctored_exam.is_practice_exam;
                        var proctoredText = isPractice ? gettext('Practice') : gettext('Proctored');
                        // eslint-disable-next-line no-param-reassign
                        proctoredExamAttempt.exam_attempt_type = !isProctored ? gettext('Timed') : proctoredText;
                    }
                );

                data = {
                    proctored_exam_attempts: dataJson.proctored_exam_attempts,
                    pagination_info: dataJson.pagination_info,
                    attempt_url: dataJson.attempt_url,
                    inSearchMode: this.inSearchMode,
                    searchText: this.searchText,
                    start_page: startPage,
                    end_page: endPage,
                    enable_exam_resume_proctoring_improvements: this.enable_exam_resume_proctoring_improvements
                };
                _.extend(data, viewHelper);
                html = this.template(data);
                this.$el.html(html);
            }
        },
        onRemoveAttempt: function(event) {
            var $target, attemptId;
            var self = this;
            event.preventDefault();

            // confirm the user's intent
            // eslint-disable-next-line no-alert
            if (!confirm(gettext('Are you sure you want to remove this student\'s exam attempt?'))) {
                return;
            }
            $('body').css('cursor', 'wait');
            $target = $(event.currentTarget);
            attemptId = $target.data('attemptId');

            self.model.url = this.attempt_url + attemptId;
            self.model.fetch({
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                },
                type: 'DELETE',
                success: function() {
                    // fetch the attempts again.
                    self.hydrate();
                    $('body').css('cursor', 'auto');
                }
            });
        },
        onResumeAttempt: function(event) {
            var $target, attemptId, userId;
            var self = this;
            event.preventDefault();

            // confirm the user's intent
            // eslint-disable-next-line no-alert
            if (!confirm(gettext('Are you sure you want to resume this student\'s exam attempt?'))) {
                return;
            }
            $('body').css('cursor', 'wait');
            $target = $(event.currentTarget);
            attemptId = $target.data('attemptId');
            userId = $target.data('userId');

            self.model.url = this.attempt_url + attemptId;
            self.model.fetch({
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                },
                type: 'PUT',
                data: {
                    action: 'mark_ready_to_resume',
                    user_id: userId
                },
                success: function() {
                    // fetch the attempts again.
                    self.hydrate();
                    $('body').css('cursor', 'auto');
                }
            });
        }
    });
    this.edx.instructor_dashboard.proctoring.ProctoredExamAttemptView =
      edx.instructor_dashboard.proctoring.ProctoredExamAttemptView;
}).call(this, Backbone, $, _, gettext);
