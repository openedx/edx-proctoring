$(function() {
    var proctored_exam_view = new edx.coursware.proctored_exam.ProctoredExamView({
        el: $(".proctored_exam_status"),
        proctored_template: '#proctored-exam-status-tpl',
        controls_template: '#proctored-exam-controls-tpl',
        model: new ProctoredExamModel()
    });
    proctored_exam_view.render();
    var proctored_exam_attempt_view = new edx.instructor_dashboard.proctoring.ProctoredExamAttemptView({
        el: $('.student-proctored-exam-container'),
        template_url: '/static/proctoring/templates/student-proctored-exam-attempts.underscore',
        collection: new edx.instructor_dashboard.proctoring.ProctoredExamAttemptCollection(),
        model: new edx.instructor_dashboard.proctoring.ProctoredExamAttemptModel()
    });
});
