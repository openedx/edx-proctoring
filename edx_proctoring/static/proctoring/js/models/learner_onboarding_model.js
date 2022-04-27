(function (Backbone) {
  'use strict';

  const LearnerOnboardingModel = Backbone.Model.extend({
    url: '/api/edx_proctoring/v1/user_onboarding/status',
  });

  this.LearnerOnboardingModel = LearnerOnboardingModel;
}).call(this, Backbone);
