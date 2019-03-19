/* globals ProctoredExamModel:false */
$(function() {
    'use strict';

    var proctoredExamView = new edx.courseware.proctored_exam.ProctoredExamView({
        el: $('.proctored_exam_status'),
        proctored_template: '#proctored-exam-status-tpl',
        model: new ProctoredExamModel()
    });
    proctoredExamView.render();
});
