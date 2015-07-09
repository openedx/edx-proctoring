var edx = edx || {};

(function(Backbone, $, _) {
    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};

    edx.instructor_dashboard.proctoring.AddAllowanceView = Backbone.ModalView.extend(
	{
		name: "AddAllowanceView",
		template: null,
        model: edx.instructor_dashboard.proctoring.ProctoredExamAllowanceModel,
        tempate_url: '/static/proctoring/templates/add-new-allowance.underscore',
		initialize: function(options) {
			this.proctored_exams = options.proctored_exams;
            _.bindAll( this, "render");
            this.loadTemplateData();
            //Backbone.Validation.bind( this,  {valid:this.hideError, invalid:this.showError});
        },
		events: {
            "submit form": "addAllowance"
	    },
        loadTemplateData: function(){
            var self = this;
            $.ajax({url: self.tempate_url, dataType: "html"})
            .error(function(jqXHR, textStatus, errorThrown){

            })
            .done(function(template_data) {
                self.template  = _.template(template_data);
                self.render();
                self.showModal();
            });
        },

		getCurrentFormValues: function() {
            return {
                proctored_exam: $("select#proctored_exam").val(),
                allowance_type: $("select#allowance_type").val(),
                value: $("#allowance_value").val(),
				user_info: $("#user_info").val()
            };
        },
		hideError:
			function(  view, attr, selector)
			{
				var $element = view.$form[attr];

				$element.removeClass( "error");
				$element.parent().find( ".error-message").empty();
			},
		showError:
			function( view, attr, errorMessage, selector)
			{
				var $element = view.$form[attr];

				$element.addClass( "error");
				var $errorMessage = $element.parent().find(".error-message");
				if( $errorMessage.length == 0)
				{
					$errorMessage = $("<div class='error-message'></div>");
					$element.parent().append( $errorMessage);
				}

				$errorMessage.empty().append( errorMessage);
			},
		addAllowance:
			function( event)
			{
				event.preventDefault();
				var values = this.getCurrentFormValues();

//				if( this.model.set( this.getCurrentFormValues()))
//				{
					this.hideModal();
//				}
			},

		render:
			function()
			{
                var exams_data = [{'exam_name':'exam12'},{'exam_name':'exam22'},{'exam_name':'exam32'}];
                var allowance_types = ['Additional time (minutes)'];

				$(this.el).html( this.template({
                    proctored_exams: this.proctored_exams,
                    allowance_types: allowance_types
                }));

				this.$form = {
					name: this.$("#name"),
					email: this.$("#email"),
					phone: this.$("#phone")
				};
				return this;
			}
	});
}).call(this, Backbone, $, _);
