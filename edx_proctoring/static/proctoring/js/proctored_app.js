$(function() {
    var proctored_exam_view = new edx.coursware.proctored_exam.ProctoredExamView({
        el: $(".proctored_exam_status"),
        proctored_template: '#proctored-exam-status-tpl',
        model: new ProctoredExamModel()
    });
    proctored_exam_view.render();

    // show the timer bar when the window scrolls.
    $(window).scroll(function() {
        if ($(this).scrollTop() > 60){
            $(".proctored_exam_status").addClass('fixed');
            $(".wrapper-course-material").css('margin-top', '58px');
        }
        else {
            $(".proctored_exam_status").removeClass('fixed');
            $(".wrapper-course-material").css('margin-top', '0');
        }
    });
});
