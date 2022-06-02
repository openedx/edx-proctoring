(Backbone => {
  'use strict';

  this.LearnerOnboardingModel = Backbone.Model.extend({
    url: '/api/edx_proctoring/v1/user_onboarding/status',
  });
}).call(this, Backbone);
