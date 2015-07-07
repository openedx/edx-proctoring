(function(Backbone) {
    var ProctoredExamAllowanceModel = Backbone.Model.extend({
        /* we should probably pull this from a data attribute on the HTML */
        url: '/api/edx_proctoring/v1/proctored_exam/allowance',

        defaults: {

        }
    });

    this.ProctoredExamAllowanceModel = ProctoredExamAllowanceModel;
}).call(this, Backbone);
