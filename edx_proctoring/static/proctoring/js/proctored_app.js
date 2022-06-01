/* globals ProctoredExamModel:false LearnerOnboardingModel:false */
$(() => {
  'use strict';

  const proctoredExamView = new edx.courseware.proctored_exam.ProctoredExamView({
    el: $('.proctored_exam_status'),
    proctored_template: '#proctored-exam-status-tpl',
    model: new ProctoredExamModel(),
  });
  const proctoredExamInfoView = new edx.courseware.proctored_exam.ProctoredExamInfo({
    el: $('.proctoring-info-panel'),
    model: new LearnerOnboardingModel(),
  });
  proctoredExamView.render();
  proctoredExamInfoView.render();
});
