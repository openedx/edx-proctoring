describe('ProctoredExamAllowanceView', function() {
    'use strict';

    var html = '';
    var expectedProctoredAllowanceJson = [{
        testuser1: [{
            created: '2015-08-10T09:15:45Z',
            id: 1,
            modified: '2015-08-10T09:15:45Z',
            key: 'Additional time (minutes)',
            value: '1',
            proctored_exam: {
                content_id: 'i4x://edX/DemoX/sequential/9f5e9b018a244ea38e5d157e0019e60c',
                course_id: 'edX/DemoX/Demo_Course',
                exam_name: 'Test Exam',
                external_id: null,
                id: 17,
                is_active: true,
                is_practice_exam: false,
                is_proctored: true,
                time_limit_mins: 1
            },
            user: {
                username: 'testuser1',
                email: 'testuser1@test.com'
            }
        }]}
    ];

    beforeEach(function() {
        // eslint-disable-next-line max-len
        html = '<span class="tip"> <%- gettext("Allowances") %>\n    <span>\n        <a id="add-allowance" href="#"  class="add blue-button">+ <%- gettext("Add Allowance") %></a>\n    </span>\n</span>\n<% var is_allowances = proctored_exam_allowances.length !== 0 %>\n<% if (is_allowances) { %>\n\n<div class="wrapper-content wrapper">\n   <section class="content exam-allowances-content">\n            <% _.each(proctored_exam_allowances, function(student){ %>\n                <div class="accordion-trigger" aria-expanded="false" style="font-size:20px;" data-key-id="<%=generateDomId(student[0].user.username)%>">\n                    <span class="fa fa-chevron-down" aria-hidden="true"></span>\n                    <%=student[0].user.username %>\n                </div>\n                <table class="allowance-table" id="<%=generateDomId(student[0].user.username)%>" style="display:none;">\n                    <tbody>\n                        <tr class="allowance-headings">\n                            <th class="exam-name"><%- gettext("Exam Name") %></th>\n                            <th class="email"><%- gettext("Email") %></th>\n                            <th class="allowance-name"><%- gettext("Allowance Type") %> </th>\n                            <th class="allowance-value"><%- gettext("Allowance Value") %></th>\n                            <th class="c_action"><%- gettext("Actions") %> </th>\n                        </tr>\n                    <% _.each(student, function(proctored_exam_allowance){ %>\n                            <% var key = proctored_exam_allowance.key; %>\n                            <% for (i = 0; i < allowance_types.length; i += 1) { %>\n                                <% if (key === allowance_types[i][0]) { %>\n                                    <% proctored_exam_allowance.key_display_name = allowance_types[i][1]; %>\n                                    <% break; %>\n                                <% }} %>\n                            <% if (!proctored_exam_allowance.key_display_name) { %>\n                                <% proctored_exam_allowance.key_display_name = key;} %>\n                        <tr class="allowance-items">\n                            <td>\n                            <%- proctored_exam_allowance.proctored_exam.exam_name %>\n                            </td>\n                            <td>\n                            <% if (proctored_exam_allowance.user){ %>\n                            <%= proctored_exam_allowance.user.email %>\n                            </td>\n                            <% }else{ %>\n                                <td>N/A</td>\n                                <td>N/A</td>\n                            <% } %>\n                            <td>\n                            <%= proctored_exam_allowance.key_display_name %>\n                            </td>\n                        <td>\n                            <%- proctored_exam_allowance.value %></td>\n                        <td>\n                        <a data-exam-id="<%= proctored_exam_allowance.proctored_exam.id %>"\n                            data-key-name="<%= proctored_exam_allowance.key %>"\n                            data-key-value="<%= proctored_exam_allowance.key_display_name %>"\n                            data-user-name="<%= proctored_exam_allowance.user.username %>"\n                            data-exam-name="<%= proctored_exam_allowance.proctored_exam.exam_name %>"\n                        class="edit_allowance" href="#">Edit</a>\n                        <a data-exam-id="<%= proctored_exam_allowance.proctored_exam.id %>"\n                            data-key-name="<%= proctored_exam_allowance.key %>"\n                            data-user-id="<%= proctored_exam_allowance.user.id %>"\n                        class="remove_allowance" href="#">Delete</a>\n                        </td>\n                        </tr>\n                    <% }); %>\n                    </tbody>\n                </table>\n            <% }); %>\n   </section>\n</div>\n<% } %>\n';
        this.server = sinon.fakeServer.create();
        this.server.autoRespond = true;
        setFixtures('<div class="special-allowance-container" data-course-id="test_course_id"></div>');

        // load the underscore template response before calling the proctored exam allowance view.
        this.server.respondWith('GET', '/static/proctoring/templates/course_grouped_allowances.underscore',
            [
                200,
                {'Content-Type': 'text/html'},
                html
            ]
        );
    });

    afterEach(function() {
        this.server.restore();
    });
    it('should render the proctored exam allowance view properly', function() {
        this.server.respondWith('GET', '/api/edx_proctoring/v1/proctored_exam/test_course_id/grouped/allowance',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(expectedProctoredAllowanceJson)
            ]
        );

        this.proctored_exam_allowance = new edx.instructor_dashboard.proctoring.ProctoredExamAllowanceView();
        this.server.respond();
        this.server.respond();
        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html())
            .toContain('testuser1@test.com');
        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html())
            .toContain('Additional time (minutes)');
        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html())
            .toContain('Test Exam');
    });

    it('should toggle the dropdown correctly', function() {
        expectedProctoredAllowanceJson[0].testuser1[0].user.username = 'testuser1@test.com';
        this.server.respondWith('GET', '/api/edx_proctoring/v1/proctored_exam/test_course_id/grouped/allowance',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(expectedProctoredAllowanceJson)
            ]
        );

        this.proctored_exam_allowance = new edx.instructor_dashboard.proctoring.ProctoredExamAllowanceView();
        this.server.respond();
        this.server.respond();
        $('.accordion-trigger').trigger('click');
        expect($('.accordion-trigger').attr('aria-expanded')).toBe('true');
    });
});
