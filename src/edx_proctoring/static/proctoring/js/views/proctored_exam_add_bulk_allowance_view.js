edx = edx || {};

(function(Backbone, $, _, gettext) {
    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};

    edx.instructor_dashboard.proctoring.AddBulkAllowanceView = Backbone.ModalView.extend({
        name: 'AddBulkAllowanceView',
        template: null,
        template_url: '/static/proctoring/templates/add-new-bulk-allowance.underscore',
        initialize: function(options) {
            this.all_exams = options.proctored_exams;
            this.proctored_exams = [];
            this.timed_exams = [];
            this.proctored_exam_allowance_view = options.proctored_exam_allowance_view;
            this.course_id = options.course_id;
            this.allowance_types = options.allowance_types;
            this.model = new edx.instructor_dashboard.proctoring.ProctoredExamBulkAllowanceModel();
            _.bindAll(this, 'render');
            this.loadTemplateData();
            // Backbone.Validation.bind( this,  {valid:this.hideError, invalid:this.showError});
        },
        events: {
            'submit form': 'addAllowance',
            'change #proctored_exam': 'selectExam',
            'change #timed_exam': 'selectExam',
            'change #allowance_type': 'selectAllowance',
            'change #exam_type': 'selectExamType'
        },
        loadTemplateData: function() {
            var self = this;
            $.ajax({url: self.template_url, dataType: 'html'})
                .done(function(templateData) {
                    self.sortExamsByExamType();
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
            $el.find('form #minutes_label').css({
                display: 'inline-block'
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
            $el.find('form select').css({
                padding: '2px 0px 2px 2px',
                'font-size': '16px',
                width: '100%'
            });
            $el.find('#selected_exams').css({
                background: '#fff',
                display: 'flex',
                'flex-wrap': 'wrap',
                'align-content': 'flex-start',
                'overflow-x': 'scroll'
            });
            $el.find('.tag').css({
                'font-size': '14px',
                height: '15px',
                'margin-right': '5px',
                padding: '5px 6px',
                border: '1px solid #ccc',
                'border-radius': '3px',
                background: '#eee',
                display: 'flex',
                'align-items': 'center',
                color: '#333',
                'box-shadow': '0 0 4px rgba(0, 0, 0, 0.2), inset 0 1px 1px #fff',
                cursor: 'default'
            });
            $el.find('.close-selected-exam').css({
                'font-size': '16px',
                margin: '5px'
            });
            $el.find('.exam_dropdown').css({
                height: '60px'
            });
        },
        getCurrentFormValues: function() {
            return {
                allowance_type: $('select#allowance_type').val(),
                allowance_value: $('#allowance_value').val(),
                user_info: $('#user_info').val()
            };
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
        addAllowance: function(event) {
            var $errorResponse, formValues, formHasErrors, examIdCollection;
            var self = this;
            event.preventDefault();
            $errorResponse = $('.error-response');
            $errorResponse.html();
            formValues = this.getCurrentFormValues();
            examIdCollection = '';

            $('.close-selected-exam').each(function() {
                examIdCollection += $(this).attr('data-item') + ',';
            });

            formHasErrors = this.checkFormErrors(formValues, examIdCollection);

            if (!formHasErrors) {
                self.model.fetch({
                    headers: {
                        'X-CSRFToken': self.proctored_exam_allowance_view.getCSRFToken()
                    },
                    type: 'PUT',
                    data: {
                        course_id: self.course_id,
                        exam_ids: examIdCollection,
                        user_ids: formValues.user_info,
                        allowance_type: formValues.allowance_type,
                        value: formValues.allowance_value
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
        selectExamAtIndex: function(examID, examName) {
            var createdTag = this.createTag(examName, examID);
            $('.exam_dropdown:visible').val('default');
            $('.exam_dropdown:visible option[value=' + examID + ']').remove();
            $('#selected_exams').append(createdTag);
            this.updateCss();
        },
        selectExam: function() {
            this.selectExamAtIndex($('.exam_dropdown:visible').val(), $('.exam_dropdown:visible :selected').text());
        },
        selectAllowance: function() {
            this.updateAllowanceLabels($('#allowance_type').val());
        },
        selectExamType: function() {
            $('.close-selected-exam').each(function() {
                $(this).trigger('click');
            });
            if ($('#proctored_exam').is(':visible')) {
                $('#proctored_exam').hide();
                $('#timed_exam').show();
                $('#allowance_type option[value="review_policy_exception"]').remove();
            } else {
                $('#proctored_exam').show();
                $('#timed_exam').hide();
                $('#allowance_type').append(new Option(gettext('Review Policy Exception'), 'review_policy_exception'));
            }
            this.updateAllowanceLabels($('#allowance_type').val());
        },
        updateAllowanceLabels: function(selectedAllowanceType) {
            if (selectedAllowanceType === 'additional_time_granted') {
                $('#allowance_value_label').text(gettext('Add Time(Minutes)'));
            } else if (selectedAllowanceType === 'time_multiplier') {
                $('#allowance_value_label').text(gettext('Add Multiplier as a Number Greater Than 1'));
            } else {
                $('#allowance_value_label').text(gettext('Add Policy Exception'));
            }
        },
        sortExamsByExamType: function() {
            var self = this;
            self.all_exams.forEach(function(exam) {
                if (exam.is_proctored) {
                    self.proctored_exams.push(exam);
                } else {
                    self.timed_exams.push(exam);
                }
            });
        },
        createTag: function(examName, examID) {
            var div = document.createElement('div');
            var span = document.createElement('span');
            var closeIcon = document.createElement('span');
            div.setAttribute('class', 'tag');
            span.innerHTML = examName;
            closeIcon.innerHTML = 'x';
            closeIcon.setAttribute('class', 'close-selected-exam');
            closeIcon.setAttribute('data-item', examID);
            closeIcon.setAttribute('data-name', examName);
            closeIcon.onclick = this.deleteTag;
            div.appendChild(span);
            div.appendChild(closeIcon);
            return div;
        },
        deleteTag: function() {
            var examID = $(this).data('item');
            var examName = $(this).data('name');
            $(this).closest('div').remove();
            $('.exam_dropdown:visible').append(new Option(examName, examID));
        },
        checkFormErrors: function(formValues, examIdCollection) {
            var formHasErrors;
            var self = this;
            $.each(formValues, function(key, value) {
                if (value === '') {
                    formHasErrors = true;
                    self.showError(self, key, gettext('Required field'));
                } else {
                    self.hideError(self, key);
                }
            });

            if (examIdCollection === '') {
                formHasErrors = true;
                self.showError(self, 'proctored_exam', gettext('Required field'));
            } else {
                self.hideError(self, 'proctored_exam');
            }
            return formHasErrors;
        },

        render: function() {
            $(this.el).html(this.template({
                proctored_exams: this.proctored_exams,
                timed_exams: this.timed_exams,
                allowance_types: this.allowance_types
            }));

            this.$form = {
                proctored_exam: this.$('select#proctored_exam'),
                timed_exam: this.$('select#timed_exam'),
                allowance_type: this.$('select#allowance_type'),
                allowance_value: this.$('#allowance_value'),
                user_info: this.$('#user_info')
            };
            return this;
        }
    });
}).call(this, Backbone, $, _, gettext);
