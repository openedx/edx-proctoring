var edx = edx || {};

(function(Backbone, $, _) {
    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};

    edx.instructor_dashboard.proctoring.AddAllowanceView = Backbone.ModalView.extend(
	{
		name: "AddAllowanceView",
		template: null,
        template_url: '/static/proctoring/templates/add-new-allowance.underscore',
		initialize: function(options) {
			this.proctored_exams = options.proctored_exams;
			this.proctored_exam_allowance_view = options.proctored_exam_allowance_view;
			this.course_id = options.course_id;
			this.model = new edx.instructor_dashboard.proctoring.ProctoredExamAllowanceModel();
            _.bindAll( this, "render");
            this.loadTemplateData();
            //Backbone.Validation.bind( this,  {valid:this.hideError, invalid:this.showError});
        },
		events: {
            "submit form": "addAllowance"
	    },
        loadTemplateData: function(){
            var self = this;
            $.ajax({url: self.template_url, dataType: "html"})
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
                allowance_value: $("#allowance_value").val(),
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
				var self = this;
				self.model.fetch(
                {
                    headers: {
                        "X-CSRFToken": self.proctored_exam_allowance_view.getCSRFToken()
                    },
                    type: 'PUT',
                    data: {
                        'exam_id': values.proctored_exam,
						'user_id': values.user_info,
                        'key': values.allowance_type,
                        'value': values.allowance_value
                    },
                    success: function () {
                        // fetch the allowances again.
						self.proctored_exam_allowance_view.collection.url = self.proctored_exam_allowance_view.initial_url + self.course_id + '/allowance';
                        self.proctored_exam_allowance_view.hydrate();

						self.hideModal();
                    }
                });

//				if( this.model.set( this.getCurrentFormValues()))
//				{

//				}
			},

		render: function() {
			var allowance_types = ['Additional time (minutes)'];

			$(this.el).html( this.template({
				proctored_exams: this.proctored_exams,
				allowance_types: allowance_types
			}));

			this.$form = {
				proctored_exam: this.$("select#proctored_exam"),
				allowance_type: this.$("select#allowance_type"),
				allowance_value: this.$("#allowance_value"),
				user_info: this.$("#user_info").val()
			};
			return this;
		}
	});
}).call(this, Backbone, $, _);
