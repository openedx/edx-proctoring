edx = edx || {};

(function(Backbone, $, _, gettext) {
    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};

    edx.instructor_dashboard.proctoring.AddAllowanceView = Backbone.ModalView.extend({
        name: 'AddAllowanceView',
        template: null,
        template_url: '/static/proctoring/templates/add-new-allowance.underscore',
        initialize: function(options) {
            this.all_exams = options.proctored_exams;
            this.proctored_exams = [];
            this.timed_exams = [];
            this.proctored_exam_allowance_view = options.proctored_exam_allowance_view;
            this.course_id = options.course_id;
            this.allowance_types = options.allowance_types;
            this.model = new edx.instructor_dashboard.proctoring.ProctoredExamAllowanceModel();
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
                    self.sortExams();
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
                'font-size': '14px'
            });
            $el.find('form input[type="submit"]').css({
                'margin-top': '10px',
                padding: '2px 32px'
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
                'font-size': '16px'
            });
            $el.find('#selected_exams').css({
                'border-radius': '3px',
                'background': '#fff',
                display: 'flex',
                'flex-wrap': 'wrap',
                'align-content': 'flex-start',
                padding: '6px',
                'overflow-x': 'scroll'
            });
            $el.find('.tag').css({
                'font-size': '14px',
                height: '15px',
                'margin': '5px',
                padding: '5px 6px',
                'border': '1px solid #ccc',
                'border-radius': '3px',
                'background': '#eee',
                display: 'flex',
                'align-items': 'center',
                color: '#333',
                'box-shadow': '0 0 4px rgba(0, 0, 0, 0.2), inset 0 1px 1px #fff',
                'cursor': 'default'
            });
            $el.find('.close').css({
                'font-size': '16px',
                'margin': '5px'
            });

        },
        getCurrentFormValues: function() {
            return {
                proctored_exam: this.selectedExams,
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
            var $errorResponse, values, formHasErrors, exams;
            var self = this;
            event.preventDefault();
            $errorResponse = $('.error-response');
            $errorResponse.html();
            values = this.getCurrentFormValues();
            formHasErrors = false;
            exams = '';

            $('.close').each(function() {
                exams += $(this).attr('data-item') + ',';
            });

            $.each(values, function(key, value) {
                if (value === '') {
                    formHasErrors = true;
                    console.log(key);
                    self.showError(self, key, gettext('Required field'));
                } else {
                    self.hideError(self, key);
                }
            });

            if (exams === '') {
                formHasErrors = true;
                self.showError(self, 'proctored_exam', gettext('Required field'));
            } else {
                self.hideError(self, 'proctored_exam');
            }

            if (!formHasErrors) {
                self.model.fetch({
                    headers: {
                        'X-CSRFToken': self.proctored_exam_allowance_view.getCSRFToken()
                    },
                    type: 'PUT',
                    data: {
                        exam_ids: exams,
                        user_ids: values.user_info,
                        allowance_type: values.allowance_type,
                        value: values.allowance_value
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
                        $errorResponse.html(gettext(data.detail));
                    }
                });
            }
        },
        selectExamAtIndex: function(examID, examName) {
            console.log(examID);
            console.log(examName);
            $('.exam_dropdown:visible').val("default");
            $('.exam_dropdown:visible option[value=' + examID + ']').remove();
            var createdTag = this.createTag(examName, examID);
            console.log(createdTag);
            $('#selected_exams').append(createdTag);
            this.updateCss();
        },
        selectExam: function() {
            this.selectExamAtIndex($('.exam_dropdown:visible').val(), $('.exam_dropdown:visible :selected').text());
        },
        selectAllowance: function() {
            this.updateAllowanceLabels($('#allowance_type').val());
        },
        selectExamType: function () {
            $('.close').each(function() {
                $(this).trigger('click');
            });
            if($('#proctored_exam').is(":visible")){
                $('#proctored_exam').hide();
                $('#timed_exam').show();
                $('#allowance_type option[value="review_policy_exception"]').remove();
            } else {
                $('#proctored_exam').show();
                $('#timed_exam').hide();
                $('#allowance_type').append(new Option(gettext('Review Policy Exception'), 'review_policy_exception'));              
            }

        },
        updateAllowanceLabels: function(selectedAllowanceType) {
            if (selectedAllowanceType === 'additional_time_granted') {
                $('#minutes_label').show();
                $('#allowance_value_label').text(gettext('Additional Time'));
            } else {
                $('#minutes_label').hide();
                $('#allowance_value_label').text(gettext('Value'));
            }
        },
        sortExams: function() {
            this.all_exams.forEach(exam => {
                if (exam.is_proctored) {
                    this.proctored_exams.push(exam);
                } else {
                    this.timed_exams.push(exam);
                }
            });
        },
        createTag(examName, examID) {
            const div = document.createElement('div');
            div.setAttribute('class', 'tag');
            const span = document.createElement('span');
            span.innerHTML = examName;
            const closeIcon = document.createElement('span');
            closeIcon.innerHTML = 'x';
            closeIcon.setAttribute('class', 'close');
            closeIcon.setAttribute('data-item', examID);
            closeIcon.setAttribute('data-name', examName);
            closeIcon.onclick = this.deleteTag;
            div.appendChild(span);
            div.appendChild(closeIcon);
            return div;
        },
        deleteTag() {
            console.log($(this));
            var examID = $(this).data('item');
            var examName = $(this).data('name');
            $(this).closest("div").remove();
            $('.exam_dropdown:visible').append(new Option(examName, examID));
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