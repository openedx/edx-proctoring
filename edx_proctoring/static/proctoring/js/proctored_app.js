$(function() {
    var proctored_exam_view = new edx.coursware.proctored_exam.ProctoredExamView({
        el: $(".proctored_exam_status"),
        proctored_template: '#proctored-exam-status-tpl',
        model: new ProctoredExamModel()
    });
    proctored_exam_view.render();

    var proctored_exam_allowance_view = new edx.instructor_dashboard.proctoring.ProctoredExamAllowanceView({
        el: $(".special-allowance-container"),
        allowance_template_url: '/static/proctoring/templates/add-allowance.underscore',
        model: new ProctoredExamAllowanceModel()
    });
});
