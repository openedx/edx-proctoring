var edx = edx || {};

(function (Backbone, $, _, gettext) {
    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};
    var attemptStatusOptions = {
        rejected: gettext('Rejected'),
        verified: gettext('Verified')
    };
    edx.instructor_dashboard.proctoring.ProctoredExamAttemptStatusView = Backbone.ModalView.extend({
        name: "AttemptStatusView",
        template: null,
        template_url: '/static/proctoring/templates/student-proctored-exam-attempt-status.underscore',
        initialize: function (options) {
            this.proctored_exam_attempt_view = options.proctored_exam_attempt_view;
            this.course_id = options.course_id;
            this.ssReview = options.ssReview;
            this.attemptStatus = options.attemptStatus;
            this.attemptStatusOptions = attemptStatusOptions;
            _.bindAll(this, "render");
            this.loadTemplateData();
        },
        events: {
            "submit form": "saveProctoredExamStaffReview"
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
                attempt_status: $("select#proctored_exam_attempt_status").val(),
                //allowance_type: $("select#allowance_type").val(),
                reason: $("#reason").val()
                //user_info: $("#user_info").val()
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
        saveProctoredExamStaffReview: function (event) {
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
                // call the new post api method
                // to save the proctored Exam staff review
            }
        },

        render: function () {
            var data = {
                ssReview: this.ssReview,
                attemptStatusOptions: this.attemptStatusOptions
            };
            var html = this.template(data);
            $(this.el).html(html);

            // update the drop down with the current status selected
            this.$el.find("select#proctored_exam_attempt_status").val(this.attemptStatus);

            this.$form = {
                attempt_status: $("select#proctored_exam_attempt_status"),
                reason: $("#reason")
            };
            return this;
        }
    });
}).call(this, Backbone, $, _, gettext);
