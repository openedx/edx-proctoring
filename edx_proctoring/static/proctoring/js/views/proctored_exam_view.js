var edx = edx || {};

(function (Backbone, $, _, gettext) {
    'use strict';

    edx.coursware = edx.coursware || {};
    edx.coursware.proctored_exam = edx.coursware.proctored_exam || {};

    edx.coursware.proctored_exam.ProctoredExamView = Backbone.View.extend({
        initialize: function (options) {
            this.$el = options.el;
            this.model = options.model;
            this.templateId = options.proctored_template;
            this.template = null;
            this.timerId = null;
            /* give an extra 5 seconds where the timer holds at 00:00 before page refreshes */
            this.grace_period_secs = 5;

            // we need to keep a copy here because the model will
            // get destroyed before onbeforeunload is called
            this.taking_as_proctored = false;

            var template_html = $(this.templateId).text();
            if (template_html !== null) {
                /* don't assume this backbone view is running on a page with the underscore templates */
                this.template = _.template(template_html);
            }
            /* re-render if the model changes */
            this.listenTo(this.model, 'change', this.modelChanged);

            $(window).unbind('beforeunload', this.unloadMessage);

            /* make the async call to the backend REST API */
            /* after it loads, the listenTo event will file and */
            /* will call into the rendering */
            this.model.fetch();
        },
        modelChanged: function () {
            // if we are a proctored exam, then we need to alert user that he/she
            // should not be navigating around the courseware
            var taking_as_proctored = this.model.get('taking_as_proctored');
            var time_left = this.model.get('time_remaining_seconds') > 0;
            var in_courseware = document.location.href.indexOf('/courses/' + this.model.get('course_id') + '/courseware/') > -1;

            if ( taking_as_proctored && time_left && in_courseware){
                $(window).bind('beforeunload', this.unloadMessage);
            } else {
                // remove callback on unload event
                $(window).unbind('beforeunload', this.unloadMessage);
            }

            this.render();
        },
        render: function () {
            if (this.template !== null) {
                if (this.model.get('in_timed_exam') && this.model.get('time_remaining_seconds') > 0) {
                    var html = this.template(this.model.toJSON());
                    this.$el.html(html);
                    this.$el.show();
                    this.updateRemainingTime(this);
                    this.timerId = setInterval(this.updateRemainingTime, 1000, this);
                }
            }
            return this;
        },
        unloadMessage: function  () {
            return gettext("As you are currently taking a proctored exam,\n" +
                "you should not be navigation away from the exam.\n" +
                "This may be considered as a violation of the \n" +
                "proctored exam and you may be disqualified for \n" +
                "credit eligibility in this course.\n");
        },
        updateRemainingTime: function (self) {
            self.$el.find('div.exam-timer').removeClass("low-time warning critical");
            self.$el.find('div.exam-timer').addClass(self.model.getRemainingTimeState());
            self.$el.find('span#time_remaining_id b').html(self.model.getFormattedRemainingTime());
            if (self.model.getRemainingSeconds() <= -self.grace_period_secs) {
                clearInterval(self.timerId); // stop the timer once the time finishes.
                $(window).unbind('beforeunload', this.unloadMessage);
                // refresh the page when the timer expired
                location.reload();
            }
        }
    });
    this.edx.coursware.proctored_exam.ProctoredExamView = edx.coursware.proctored_exam.ProctoredExamView;
}).call(this, Backbone, $, _, gettext);
