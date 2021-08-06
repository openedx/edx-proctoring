edx = edx || {};

(function(Backbone, $, _, gettext) {
    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};

    edx.instructor_dashboard.proctoring.EditAllowanceView = Backbone.ModalView.extend({
        name: 'EditAllowanceView',
        template: null,
        template_url: '/static/proctoring/templates/edit-allowance.underscore',
        initialize: function(options) {
            this.selected_exam_ID = options.selected_exam_ID;
            this.selected_exam_name = options.selected_exam_name;
            this.proctored_exam_allowance_view = options.proctored_exam_allowance_view;
            this.course_id = options.course_id;
            this.selected_user = options.selected_user;
            this.allowance_type = options.allowance_type;
            this.allowance_type_name = options.allowance_type_name;
            this.model = new edx.instructor_dashboard.proctoring.ProctoredExamBulkAllowanceModel();
            _.bindAll(this, 'render');
            this.loadTemplateData();
            // Backbone.Validation.bind( this,  {valid:this.hideError, invalid:this.showError});
        },
        events: {
            'submit form': 'editAllowance'
        },
        loadTemplateData: function() {
            var self = this;
            $.ajax({url: self.template_url, dataType: 'html'})
                .done(function(templateData) {
                    self.template = _.template(templateData);
                    self.render();
                    self.showModal();
                    self.updateCss();
                });
        },
        updateCss: function() {
            var $el = $(this.el);
            $el.find('.modal-header').css({
                color: '#1580b0',
                'font-size': '20px',
                'font-weight': '600',
                'line-height': 'normal',
                padding: '10px 15px',
                'border-bottom': '1px solid #ccc'
            });
            $el.find('form').css({
                padding: '15px'
            });
            $el.find('form table.compact td').css({
                'vertical-align': 'middle',
                padding: '4px 8px'
            });
            $el.find('form label').css({
                display: 'block',
                'font-size': '14px',
                margin: 0,
                cursor: 'default'
            });
            $el.find('form input[type="text"]').css({
                height: '26px',
                padding: '1px 8px 2px',
                'font-size': '14px',
                width: '100%'
            });
            $el.find('form input[type="submit"]').css({
                'margin-top': '10px',
                float: 'right'
            });
            $el.find('.error-message').css({
                color: '#ff0000',
                'line-height': 'normal',
                'font-size': '14px'
            });
            $el.find('.error-response').css({
                color: '#ff0000',
                'line-height': 'normal',
                'font-size': '14px',
                padding: '0px 10px 5px 7px'
            });
        },
        getAllowanceValue: function() {
            return $('#allowance_value').val();
        },
        hideError: function(view, attr) {
            var $element = view.$form[attr];

            $element.removeClass('error');
            $element.parent().find('.error-message').empty();
        },
        showError: function(view, attr, errorMessage) {
            var $element = view.$form[attr];
            var $errorMessage;

            $element.addClass('error');
            $errorMessage = $element.parent().find('.error-message');
            if ($errorMessage.length === 0) {
                $errorMessage = $("<div class='error-message'></div>");
                $element.parent().append($errorMessage);
            }

            $errorMessage.empty().append(errorMessage);
            this.updateCss();
        },
        editAllowance: function(event) {
            var $errorResponse, formHasErrors, allowanceValue;
            var self = this;
            event.preventDefault();
            $errorResponse = $('.error-response');
            $errorResponse.html();
            allowanceValue = this.getAllowanceValue();
            formHasErrors = false;

            if (allowanceValue === '') {
                formHasErrors = true;
                self.showError(self, 'allowance_value', gettext('Required field'));
            } else {
                self.hideError(self, 'allowance_value');
            }

            if (!formHasErrors) {
                self.model.fetch({
                    headers: {
                        'X-CSRFToken': self.proctored_exam_allowance_view.getCSRFToken()
                    },
                    type: 'PUT',
                    data: {
                        exam_ids: this.selected_exam_ID,
                        user_ids: this.selected_user,
                        allowance_type: this.allowance_type,
                        value: allowanceValue
                    },
                    success: function() {
                        // fetch the allowances again.
                        $errorResponse.html();
                        self.proctored_exam_allowance_view.collection.url =
                            self.proctored_exam_allowance_view.initial_url + self.course_id + '/allowance';
                        self.proctored_exam_allowance_view.hydrate();
                        self.hideModal();
                    },
                    error: function(unused, response) {
                        var data = $.parseJSON(response.responseText);
                        self.showError(self, data.field, data.detail);
                    }
                });
            }
        },
        render: function() {
            $(this.el).html(this.template({
                selected_user: this.selected_user,
                selected_exam_name: this.selected_exam_name,
                allowance_type: this.allowance_type,
                allowance_type_name: this.allowance_type_name
            }));

            this.$form = {
                allowance_value: this.$('#allowance_value')
            };
            return this;
        }
    });
}).call(this, Backbone, $, _, gettext);
