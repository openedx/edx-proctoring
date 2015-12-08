var edx = edx || {};

(function (Backbone, $, _, gettext) {
    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};

    edx.instructor_dashboard.proctoring.AddAllowanceView = Backbone.ModalView.extend({
        name: "AddAllowanceView",
        template: null,
        template_url: '/static/proctoring/templates/add-new-allowance.underscore',
        initialize: function (options) {
            this.proctored_exams = options.proctored_exams;
            this.proctored_exam_allowance_view = options.proctored_exam_allowance_view;
            this.course_id = options.course_id;
            this.allowance_types = options.allowance_types;
            this.model = new edx.instructor_dashboard.proctoring.ProctoredExamAllowanceModel();
            _.bindAll(this, "render");
            this.loadTemplateData();
            //Backbone.Validation.bind( this,  {valid:this.hideError, invalid:this.showError});
        },
        events: {
            "submit form": "addAllowance"
        },
        loadTemplateData: function () {
            var self = this;
            $.ajax({url: self.template_url, dataType: "html"})
                .error(function (jqXHR, textStatus, errorThrown) {

                })
                .done(function (template_data) {
                    self.template = _.template(template_data);
                    self.render();
                    self.showModal();
                    self.updateCss();
                });
        },
        updateCss: function() {
            var $el = $(this.el);
            $el.find('.modal-header').css({
                "color": "#1580b0",
                "font-size": "20px",
                "font-weight": "600",
                "line-height": "normal",
                "padding": "10px 15px",
                "border-bottom": "1px solid #ccc"
            });
            $el.find('form').css({
                "padding": "15px"
            });
            $el.find('form table.compact td').css({
                "vertical-align": "middle",
                "padding": "4px 8px"
            });
            $el.find('form label').css({
                "display": "block",
                "font-size": "14px",
                "margin": 0
            });
            $el.find('form input[type="text"]').css({
                "height": "26px",
                "padding": "1px 8px 2px",
                "font-size": "14px"
            });
            $el.find('form input[type="submit"]').css({
                "margin-top": "10px",
                "padding": "2px 32px"
            });
            $el.find('.error-message').css({
                "color": "#ff0000",
                "line-height": "normal",
                "font-size": "14px"
            });
            $el.find('.error-response').css({
                "color": "#ff0000",
                "line-height": "normal",
                "font-size": "14px",
                "padding": "0px 10px 5px 7px"
            });
             $el.find('form select').css({
                "padding": "2px 0px 2px 2px",
                "font-size": "16px"
            });
        },
        getCurrentFormValues: function () {
            return {
                proctored_exam: $("select#proctored_exam").val(),
                allowance_type: $("select#allowance_type").val(),
                allowance_value: $("#allowance_value").val(),
                user_info: $("#user_info").val()
            };
        },
        hideError: function (view, attr, selector) {
            var $element = view.$form[attr];

            $element.removeClass("error");
            $element.parent().find(".error-message").empty();
        },
        showError: function (view, attr, errorMessage, selector) {
            var $element = view.$form[attr];

            $element.addClass("error");
            var $errorMessage = $element.parent().find(".error-message");
            if ($errorMessage.length == 0) {
                $errorMessage = $("<div class='error-message'></div>");
                $element.parent().append($errorMessage);
            }

            $errorMessage.empty().append(errorMessage);
            this.updateCss();
        },
        addAllowance: function (event) {
            event.preventDefault();
            var error_response = $('.error-response');
            error_response.html();
            var values = this.getCurrentFormValues();
            var formHasErrors = false;


            var self = this;
            $.each(values, function(key, value) {
                if (value==="") {
                    formHasErrors = true;
                    self.showError(self, key, gettext("Required field"));
                }
                else {
                    self.hideError(self, key);
                }
            });

            if (!formHasErrors) {
                self.model.fetch({
                    headers: {
                        "X-CSRFToken": self.proctored_exam_allowance_view.getCSRFToken()
                    },
                    type: 'PUT',
                    data: {
                        'exam_id': values.proctored_exam,
                        'user_info': values.user_info,
                        'key': values.allowance_type,
                        'value': values.allowance_value
                    },
                    success: function () {
                        // fetch the allowances again.
                        error_response.html();
                        self.proctored_exam_allowance_view.collection.url = self.proctored_exam_allowance_view.initial_url + self.course_id + '/allowance';
                        self.proctored_exam_allowance_view.hydrate();
                        self.hideModal();
                    },
                    error: function(self, response, options) {
                        var data = $.parseJSON(response.responseText);
                        error_response.html(gettext(data.detail));
                    }
                });
            }
        },

        render: function () {
            $(this.el).html(this.template({
                proctored_exams: this.proctored_exams,
                allowance_types: this.allowance_types
            }));

            this.$form = {
                proctored_exam: this.$("select#proctored_exam"),
                allowance_type: this.$("select#allowance_type"),
                allowance_value: this.$("#allowance_value"),
                user_info: this.$("#user_info")
            };
            return this;
        }
    });
}).call(this, Backbone, $, _, gettext);
