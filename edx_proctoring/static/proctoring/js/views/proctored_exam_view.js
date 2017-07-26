var edx = edx || {};

(function (Backbone, $, _, gettext) {
    'use strict';

    edx.coursware = edx.coursware || {};
    edx.coursware.proctored_exam = edx.coursware.proctored_exam || {};

    edx.coursware.proctored_exam.ProctoredExamView = Backbone.View.extend({
        initialize: function (options) {
            _.bindAll(this, "detectScroll");
            this.$el = options.el;
            this.timerBarTopPosition = this.$el.position().top;
            this.courseNavBarMarginTop = this.timerBarTopPosition - 3;
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

            var template_html = $(this.templateId).text();
            if (template_html !== null) {
                /* don't assume this backbone view is running on a page with the underscore templates */
                this.template = _.template(template_html);
            }

            var controls_template_html = $(this.examControlsTemplateId).text();
            if (controls_template_html !== null) {
                /* don't assume this backbone view is running on a page with the underscore templates */
                this.controls_template = _.template(controls_template_html);
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
            'click #toggle_timer': 'toggleTimerVisibility'
        },
        detectScroll: function(event) {
            if ($(event.currentTarget).scrollTop() > this.timerBarTopPosition) {
                $(".proctored_exam_status").addClass('is-fixed');
                $(".wrapper-course-material").css('margin-top', this.courseNavBarMarginTop + 'px');
            }
            else {
                $(".proctored_exam_status").removeClass('is-fixed');
                $(".wrapper-course-material").css('margin-top', '0');
            }

        },
        modelChanged: function () {
            // if we are a proctored exam, then we need to alert user that he/she
            // should not be navigating around the courseware
            var taking_as_proctored = this.model.get('taking_as_proctored');
            var time_left = this.model.get('time_remaining_seconds') > 0;
            this.secondsLeft = this.model.get('time_remaining_seconds');
            var status = this.model.get('attempt_status');
            var in_courseware = document.location.href.indexOf('/courses/' + this.model.get('course_id') + '/courseware/') > -1;

            if ( taking_as_proctored && time_left && in_courseware && status !== 'started'){
                $(window).bind('beforeunload', this.unloadMessage);
            } else {
                // remove callback on unload event
                $(window).unbind('beforeunload', this.unloadMessage);
            }

            this.render();
        },
        render: function () {
            if (this.template !== null) {
                if (
                    this.model.get('in_timed_exam') &&
                    this.model.get('time_remaining_seconds') > 0 &&
                    this.model.get('attempt_status') !== 'error'
                ) {
                    // add callback on scroll event
                    $(window).bind('scroll', this.detectScroll);

                    var html = this.template(this.model.toJSON());
                    this.$el.html(html);
                    this.$el.show();
                    // only render the accesibility string the first time we render after
                    // page load (then we will update on time left warnings)
                    if (this.first_time_rendering) {
                        this.accessibility_time_string = this.model.get('accessibility_time_string');
                        this.$el.find('.timer-announce').html(this.accessibility_time_string);
                        this.first_time_rendering = false;
                    }
                    this.updateRemainingTime(this);
                    this.timerId = setInterval(this.updateRemainingTime, 1000, this);

                    // Bind a click handler to the exam controls
                    var self = this;
                    $('.exam-button-turn-in-exam').click(function(){
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
                }
                else {
                    // remove callback on scroll event
                    $(window).unbind('scroll', this.detectScroll);
                }
            }
            return this;
        },
        reloadPage: function () {
          location.reload();
        },
        unloadMessage: function  () {
            return gettext("Are you sure you want to leave this page? \n" +
                "To pass your proctored exam you must also pass the online proctoring session review.");
        },
        updateRemainingTime: function (self) {
            self.timerTick ++;
            self.secondsLeft --;
            if (self.timerTick % self.poll_interval === 0) {
                var url = self.model.url + '/' + self.model.get('attempt_id');
                var queryString = '?sourceid=in_exam&proctored=' + self.model.get('taking_as_proctored');
                $.ajax(url + queryString).success(function(data) {
                    if (data.status === 'error') {
                        // The proctoring session is in error state
                        // refresh the page to bring up the new Proctoring state from the backend.
                        clearInterval(self.timerId); // stop the timer once the time finishes.
                        $(window).unbind('beforeunload', self.unloadMessage);
                        location.reload();
                    }
                    else {
                        self.secondsLeft = data.time_remaining_seconds;
                        self.accessibility_time_string = data.accessibility_time_string;
                    }
                });
            }
            var oldState = self.$el.find('div.exam-timer').attr('class');
            var newState = self.model.getRemainingTimeState(self.secondsLeft);

            if (newState !== null && !self.$el.find('div.exam-timer').hasClass(newState)) {
                self.$el.find('div.exam-timer').removeClass("warning critical");
                self.$el.find('div.exam-timer').addClass("low-time " + newState);
                // refresh accessibility string
                self.$el.find('.timer-announce').html(self.accessibility_time_string);
            }

            self.$el.find('span#time_remaining_id b').html(self.model.getFormattedRemainingTime(self.secondsLeft));
            if (self.secondsLeft <= -self.grace_period_secs) {
                clearInterval(self.timerId); // stop the timer once the time finishes.
                $(window).unbind('beforeunload', this.unloadMessage);
                // refresh the page when the timer expired
                self.reloadPage();
            }
        },
        toggleTimerVisibility: function (event) {
            var button = $(event.currentTarget);
            var icon = button.find('i');
            var timer = this.$el.find('span#time_remaining_id b');
            if (timer.hasClass('timer-hidden')) {
                timer.removeClass('timer-hidden');
                button.attr('aria-pressed', 'false');
                icon.removeClass('fa-eye').addClass('fa-eye-slash');
            } else {
                timer.addClass('timer-hidden');
                button.attr('aria-pressed', 'true');
                icon.removeClass('fa-eye-slash').addClass('fa-eye');
            }
            event.stopPropagation();
            event.preventDefault();
        }
    });
    this.edx.coursware.proctored_exam.ProctoredExamView = edx.coursware.proctored_exam.ProctoredExamView;
}).call(this, Backbone, $, _, gettext);
