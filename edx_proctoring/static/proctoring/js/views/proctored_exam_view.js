edx = edx || {};

(function(Backbone, $, _, gettext) {
    'use strict';

    edx.courseware = edx.courseware || {};
    edx.courseware.proctored_exam = edx.courseware.proctored_exam || {};

    edx.courseware.proctored_exam.ProctoredExamView = Backbone.View.extend({
        initialize: function(options) {
            var templateHtml, controlsTemplateHtml;
            _.bindAll(this, 'detectScroll');
            this.$el = options.el;
            this.timerBarTopPosition = this.$el.position().top;
            this.initialCourseNavBarMarginTop = this.timerBarTopPosition - 3;
            this.model = options.model;
            this.templateId = options.proctored_template;
            this.template = null;
            this.timerId = null;
            this.timerTick = 0;
            this.secondsLeft = 0;
            /* give an extra 5 seconds where the timer holds at 00:00 before page refreshes */
            this.grace_period_secs = 5;
            this.poll_interval = 60;
            this.first_time_rendering = true;

            // we need to keep a copy here because the model will
            // get destroyed before onbeforeunload is called
            this.taking_as_proctored = false;

            templateHtml = $(this.templateId).text();
            if (templateHtml !== null) {
                /* don't assume this backbone view is running on a page with the underscore templates */
                this.template = _.template(templateHtml);
            }

            controlsTemplateHtml = $(this.examControlsTemplateId).text();
            if (controlsTemplateHtml !== null) {
                /* don't assume this backbone view is running on a page with the underscore templates */
                this.controls_template = _.template(controlsTemplateHtml);
            }

            /* re-render if the model changes */
            this.listenTo(this.model, 'change', this.modelChanged);

            $(window).unbind('beforeunload', this.unloadMessage);

            /* make the async call to the backend REST API */
            /* after it loads, the listenTo event will file and */
            /* will call into the rendering */
            this.model.fetch();
        },
        events: {
            'click #toggle_timer': 'toggleTimerVisibility',
            'click .js-toggle-show-more': 'toggleShowText'
        },
        detectScroll: function(event) {
            var examStatusBarHeight;
            var $courseNavBar = $('.wrapper-course-material');
            if (!$courseNavBar.length) {
                $courseNavBar = $('.course-tabs');
            }
            examStatusBarHeight = this.$el.height();
            if ($(event.currentTarget).scrollTop() > this.timerBarTopPosition) {
                $('.proctored_exam_status').addClass('is-fixed');
                $courseNavBar.css('margin-top', examStatusBarHeight + 'px');
            } else {
                $('.proctored_exam_status').removeClass('is-fixed');
                $courseNavBar.css('margin-top', '0');
            }
        },
        modelChanged: function() {
            var desktopApplicationJsUrl;
            // if we are a proctored exam, then we need to alert user that he/she
            // should not be navigating around the courseware
            var takingAsProctored = this.model.get('taking_as_proctored');
            var timeLeft = this.model.get('time_remaining_seconds') > 0;
            var status = this.model.get('attempt_status');
            var inCourseware = document.location.href.indexOf(
                '/courses/' + this.model.get('course_id') + '/courseware/'
            ) > -1;
            this.secondsLeft = this.model.get('time_remaining_seconds');

            if (takingAsProctored && timeLeft && inCourseware && status !== 'started') {
                $(window).bind('beforeunload', this.unloadMessage);
            } else {
                // remove callback on unload event
                $(window).unbind('beforeunload', this.unloadMessage);
            }
            desktopApplicationJsUrl = this.model.get('desktop_application_js_url');
            if (desktopApplicationJsUrl && !edx.courseware.proctored_exam.configuredWorkerURL) {
                edx.courseware.proctored_exam.configuredWorkerURL = desktopApplicationJsUrl;
            }

            this.render();
        },
        render: function() {
            var html, self;
            if (this.template !== null) {
                if (
                    this.model.get('in_timed_exam') &&
                    this.model.get('time_remaining_seconds') > 0 &&
                    this.model.get('attempt_status') !== 'error'
                ) {
                    // add callback on scroll event
                    $(window).bind('scroll', this.detectScroll);

                    html = this.template(this.model.toJSON());
                    this.$el.html(html);
                    this.$el.show();
                    // only render the accesibility string the first time we render after
                    // page load (then we will update on time left warnings)
                    if (this.first_time_rendering) {
                        this.accessibility_time_string = this.model.get('accessibility_time_string');
                        this.$el.find('.timer-announce').html(this.accessibility_time_string);
                        if (!(window && window.matchMedia && window.matchMedia('(min-width: 992px)').matches)) {
                            this.toggleShowText();
                        }
                        this.first_time_rendering = false;
                    }
                    this.updateRemainingTime();
                    this.timerId = setInterval(this.updateRemainingTime.bind(this), 1000, this);

                    // Bind a click handler to the exam controls
                    self = this;
                    $('.exam-button-turn-in-exam').click(function() {
                        $(window).unbind('beforeunload', self.unloadMessage);

                        $.ajax({
                            url: '/api/edx_proctoring/v1/proctored_exam/attempt/' + self.model.get('attempt_id'),
                            type: 'PUT',
                            data: {
                                action: 'stop'
                            },
                            success: function() {
                                // change the location of the page to the active exam page
                                // which will reflect the new state of the attempt
                                location.href = self.model.get('exam_url_path');
                            }
                        });
                    });
                } else {
                    // remove callback on scroll event
                    $(window).unbind('scroll', this.detectScroll);
                }
            }
            return this;
        },
        reloadPage: function() {
            location.reload();
        },
        unloadMessage: function() {
            return gettext('Are you sure you want to leave this page? \n' +
                'To pass your proctored exam you must also pass the online proctoring session review.');
        },
        updateRemainingTime: function() {
            var url, queryString, newState;
            var self = this;
            var pingInterval = self.model.get('ping_interval');
            self.timerTick += 1;
            self.secondsLeft -= 1;

            // AED 2020-02-21:
            // If the learner is in a state where they've finished the exam
            // and the attempt can be submitted (i.e. they are "ready_to_submit"),
            // don't ping the proctoring app (which action could move
            // the attempt into an error state).
            if (
                self.timerTick % pingInterval === pingInterval / 2 &&
                edx.courseware.proctored_exam.configuredWorkerURL &&
                this.model.get('attempt_status') !== 'ready_to_submit'
            ) {
                edx.courseware.proctored_exam.pingApplication(pingInterval)
                    .catch(self.endExamForFailureState.bind(self));
            }
            if (self.timerTick % self.poll_interval === 0) {
                url = self.model.url + '/' + self.model.get('attempt_id');
                queryString = '?sourceid=in_exam&proctored=' + self.model.get('taking_as_proctored');
                $.ajax(url + queryString)
                    .success(function(data) {
                        if (data.status === 'error') {
                            // The proctoring session is in error state
                            // refresh the page to bring up the new Proctoring state from the backend.
                            clearInterval(self.timerId); // stop the timer once the time finishes.
                            $(window).unbind('beforeunload', self.unloadMessage);
                            self.reloadPage();
                        } else {
                            self.secondsLeft = data.time_remaining_seconds;
                            self.accessibility_time_string = data.accessibility_time_string;
                        }
                    })
                    .error(function(error) {
                        // if unauthorized refresh the page to kick user out of exam
                        if (error.status === 403) {
                            clearInterval(self.timerId);
                            $(window).unbind('beforeunload', self.unloadMessage);
                            self.reloadPage();
                        }
                    });
            }
            self.$el.find('div.exam-timer').attr('class');
            newState = self.model.getRemainingTimeState(self.secondsLeft);

            if (newState !== null && !self.$el.find('div.exam-timer').hasClass(newState)) {
                self.$el.find('div.exam-timer').removeClass('warning critical');
                self.$el.find('div.exam-timer').addClass('low-time ' + newState);
                // refresh accessibility string
                self.$el.find('.timer-announce').html(self.accessibility_time_string);
            }

            self.$el.find('h3#time_remaining_id b').html(self.model.getFormattedRemainingTime(self.secondsLeft));
            if (self.secondsLeft <= -self.grace_period_secs) {
                clearInterval(self.timerId); // stop the timer once the time finishes.
                $(window).unbind('beforeunload', this.unloadMessage);
                // refresh the page when the timer expired
                edx.courseware.proctored_exam.endExam(self.model.get('exam_started_poll_url')).then(self.reloadPage);
            }
        },
        endExamForFailureState: function() {
            var self = this;
            return $.ajax({
                data: {
                    action: 'error'
                },
                url: this.model.url + '/' + this.model.get('attempt_id'),
                type: 'PUT'
            }).done(function(result) {
                if (result.exam_attempt_id) {
                    self.reloadPage();
                }
            });
        },
        toggleTimerVisibility: function(event) {
            var $button = $(event.currentTarget);
            var icon = $button.find('i');
            var timer = this.$el.find('h3#time_remaining_id b');
            if (timer.hasClass('timer-hidden')) {
                timer.removeClass('timer-hidden');
                $button.attr('aria-pressed', 'false');
                icon.removeClass('fa-eye').addClass('fa-eye-slash');
            } else {
                timer.addClass('timer-hidden');
                $button.attr('aria-pressed', 'true');
                icon.removeClass('fa-eye-slash').addClass('fa-eye');
            }
            event.stopPropagation();
            event.preventDefault();
        },
        toggleShowText: function() {
            var $examText = this.$el.find('.js-exam-text');
            var $toggle = this.$el.find('.js-toggle-show-more');
            var $additionalText = this.$el.find('.js-exam-additional-text');
            var currentlyShowingLongText = $examText.data('showLong');
            $additionalText
                // uses both a v1 and a bootstrap utility class because
                // this banner appears across both types of pages
                .toggleClass('hidden d-none', currentlyShowingLongText)
                .attr('aria-hidden', currentlyShowingLongText);
            $toggle.html(currentlyShowingLongText ? $toggle.data('showMoreText') : $toggle.data('showLessText'));
            $examText.data('showLong', !currentlyShowingLongText);
        }
    });
    this.edx.courseware.proctored_exam.ProctoredExamView = edx.courseware.proctored_exam.ProctoredExamView;
}).call(this, Backbone, $, _, gettext);
