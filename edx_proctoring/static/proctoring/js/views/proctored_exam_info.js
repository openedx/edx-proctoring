(function(Backbone, $) {
    'use strict';

    var examStatusReadableFormat, notStartedText, startedText, submittedText;

    edx.courseware = edx.courseware || {};
    edx.courseware.proctored_exam = edx.courseware.proctored_exam || {};

    notStartedText = {
        status: gettext('Not Started'),
        message: gettext('You have not started your onboarding exam.')
    };
    startedText = {
        status: gettext('Started'),
        message: gettext('You have started your onboarding exam.')
    };
    submittedText = {
        status: gettext('Submitted'),
        message: gettext('You have submitted your onboarding exam.')
    };

    examStatusReadableFormat = {
        created: notStartedText,
        download_software_clicked: notStartedText,
        ready_to_start: notStartedText,
        started: startedText,
        ready_to_submit: startedText,
        second_review_required: submittedText,
        submitted: submittedText,
        verified: {
            status: gettext('Verified'),
            message: gettext('Your onboarding exam has been approved in this course.')
        },
        rejected: {
            status: gettext('Rejected'),
            message: gettext('Your onboarding exam has been rejected. Please retry onboarding.')
        },
        error: {
            status: gettext('Error'),
            message: gettext('An error has occurred during your onboarding exam. Please retry onboarding.')
        },
        other_course_approved: {
            status: gettext('Approved in Another Course'),
            message: gettext('Your onboarding exam has been approved in another course.'),
            detail: gettext(
                'If your device has changed, we recommend that you complete this ' +
                'course\'s onboarding exam in order to ensure that your setup ' +
                'still meets the requirements for proctoring.'
            )
        },
        expiring_soon: {
            status: gettext('Expiring Soon'),
            message: gettext(
                'Your onboarding profile has been approved in another course. ' +
                'However, your onboarding status is expiring soon. Please ' +
                'complete onboarding again to ensure that you will be ' +
                'able to continue taking proctored exams.'
            )
        }
    };

    edx.courseware.proctored_exam.ProctoredExamInfo = Backbone.View.extend({
        initialize: function() {
            this.course_id = this.$el.data('course-id');
            this.username = this.$el.data('username');
            this.model.url = this.model.url + '?course_id=' + encodeURIComponent(this.course_id);
            if (this.username) {
                this.model.url = this.model.url + '&username=' + encodeURIComponent(this.username);
            }
            this.template_url = '/static/proctoring/templates/proctored-exam-info.underscore';
            this.status = '';

            this.loadTemplateData();
        },

        updateCss: function() {
            var $el = $(this.el);
            var color = '#b20610';
            if (['verified', 'other_course_approved'].includes(this.status)) {
                color = '#008100';
            } else if (['submitted', 'second_review_required', 'expiring_soon'].includes(this.status)) {
                color = '#0d4e6c';
            }

            $el.find('.proctoring-info').css({
                padding: '10px',
                border: '1px solid #e7e7e7',
                'border-top': '5px solid ' + color,
                'margin-bottom': '15px'
            });

            $el.find('.onboarding-status').css({
                'font-weight': 'bold',
                'margin-bottom': '15px'
            });

            $el.find('.onboarding-status-message').css({
                'margin-bottom': '15px'
            });

            $el.find('.onboarding-status-detail').css({
                'font-size': '0.8rem',
                'margin-bottom': '15px'
            });

            $el.find('.action').css({
                display: 'block',
                'font-weight': '600',
                'text-align': 'center',
                'text-decoration': 'none',
                padding: '15px 20px',
                border: 'none'
            });

            $el.find('.action-onboarding').css({
                color: '#ffffff',
                background: '#98050e',
                'margin-bottom': '15px'
            });

            $el.find('.action-onboarding-practice').css({
                color: '#ffffff',
                background: '#0075b4',
                'margin-bottom': '15px'
            });

            $el.find('.action-disabled').css({
                background: '#b4b6bd'
            });

            $el.find('.action-info-link').css({
                border: '1px solid #0d4e6c'
            });
        },

        getExamAttemptText: function(status) {
            if (status in examStatusReadableFormat) {
                return examStatusReadableFormat[status];
            } else {
                return {status: status || 'Not Started', message: ''};
            }
        },

        isExpiringSoon: function(expirationDate) {
            var today = new Date();
            var expirationDateObject = new Date(expirationDate);
            // Return true if the expiration date is within 28 days
            return today.getTime() > expirationDateObject.getTime() - 2419200000;
        },

        shouldShowExamLink: function(status) {
            // show the exam link if the user should retry onboarding, or if they haven't submitted the exam
            var NO_SHOW_STATES = ['submitted', 'second_review_required', 'verified'];
            return !NO_SHOW_STATES.includes(status);
        },

        render: function() {
            var statusText = {};
            var releaseDate;
            var now = new Date();
            var data = this.model.toJSON();
            if (this.template) {
                if (data.expiration_date && this.isExpiringSoon(data.expiration_date)) {
                    this.status = 'expiring_soon';
                } else {
                    this.status = data.onboarding_status;
                }
                statusText = this.getExamAttemptText(this.status);
                releaseDate = new Date(data.onboarding_release_date);
                data = {
                    onboardingStatus: this.status,
                    onboardingStatusText: statusText.status,
                    onboardingMessage: statusText.message,
                    onboardingDetail: statusText.detail,
                    showOnboardingReminder: !['verified', 'other_course_approved'].includes(data.onboarding_status),
                    onboardingNotReleased: releaseDate > now,
                    showOnboardingExamLink: this.shouldShowExamLink(data.onboarding_status),
                    onboardingLink: data.onboarding_link,
                    onboardingReleaseDate: releaseDate.toLocaleDateString()
                };

                $(this.el).html(this.template(data));
            }
        },

        loadTemplateData: function() {
            var self = this;
            // only load data/render if course_id is defined
            if (self.course_id) {
                $.ajax({url: self.template_url, dataType: 'html'})
                    .done(function(templateData) {
                        self.template = _.template(templateData);
                        self.hydrate();
                    });
            }
        },

        hydrate: function() {
            var self = this;
            self.model.fetch({
                success: function() {
                    self.render();
                    self.updateCss();
                }
            });
        }
    });
    this.edx.courseware.proctored_exam.ProctoredExamInfo = edx.courseware.proctored_exam.ProctoredExamInfo;
}).call(this, Backbone, $, _, gettext);
