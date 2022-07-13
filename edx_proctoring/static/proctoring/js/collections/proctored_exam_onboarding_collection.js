edx = edx || {};
(Backbone => {
  'use strict';

  edx.instructor_dashboard = edx.instructor_dashboard || {};
  edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};

  edx.instructor_dashboard.proctoring.ProctoredExamOnboardingCollection = Backbone.Collection.extend({
    url: '/api/edx_proctoring/v1/user_onboarding/status/course_id/',
  });
  const proctoredExamOnboardingCollection = edx.instructor_dashboard.proctoring.ProctoredExamOnboardingCollection;
  this.edx.instructor_dashboard.proctoring.ProctoredExamOnboardingCollection = proctoredExamOnboardingCollection;
}).call(this, Backbone);
