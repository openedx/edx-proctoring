(function(Backbone) {
    var ProctoredExamModel = Backbone.Model.extend({
        /* we should probably pull this from a data attribute on the HTML */
        url: '/api/edx_proctoring/v1/proctored_exam/attempt',

        defaults: {
            in_timed_exam: false,
            attempt_id: 0,
            attempt_status: 'started',
            taking_as_proctored: false,
            exam_display_name: '',
            exam_url_path: '',
            time_remaining_seconds: 0,
            low_threshold_sec: 0,
            critically_low_threshold_sec: 0,
            course_id: null,
            accessibility_time_string: '',
            lastFetched: new Date()
        },
        getFormattedRemainingTime: function (secondsLeft) {
            /* since we can have a small grace period, we can end in the negative numbers */
            if (secondsLeft < 0)
                secondsLeft = 0;

            var hours = parseInt(secondsLeft / 3600);
            var minutes = parseInt(secondsLeft / 60) % 60;
            var seconds = Math.floor(secondsLeft % 60);

            return hours + ":" + (minutes < 10 ? "0" + minutes : minutes)
                + ":" + (seconds < 10 ? "0" + seconds : seconds);

        },
        getRemainingTimeState: function (secondsLeft) {
            if (secondsLeft > this.get('low_threshold_sec')) {
                return null;
            }
            else if (secondsLeft <= this.get('low_threshold_sec') && secondsLeft > this.get('critically_low_threshold_sec')) {
                // returns the class name that has some css properties
                // and it displays the user with the waring message if
                // total seconds is less than the low_threshold value.
                return "warning";
            }
            else {
                // returns the class name that has some css properties
                // and it displays the user with the critical message if
                // total seconds is less than the critically_low_threshold_sec value.
                return "critical";
            }
        }
    });

    this.ProctoredExamModel = ProctoredExamModel;
}).call(this, Backbone);
