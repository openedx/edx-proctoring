describe('ProctoredExamAddAllowanceView', function () {
    var html = '';
    var allowancesHtml = '';
    var errorAddingAllowance = {
        detail: "Cannot find user"
    };
    var expectedProctoredAllowanceJson = [
        {
            created: "2015-08-10T09:15:45Z",
            id: 1,
            modified: "2015-08-10T09:15:45Z",
            key: "additional_time_granted",
            value: "1",
            proctored_exam: {
                content_id: "i4x://edX/DemoX/sequential/9f5e9b018a244ea38e5d157e0019e60c",
                course_id: "edX/DemoX/Demo_Course",
                exam_name: "Test Exam",
                external_id: null,
                id: 6,
                is_active: true,
                is_practice_exam: false,
                is_proctored: true,
                time_limit_mins: 1
            },
            user: {
                username: 'testuser1',
                email: 'testuser1@test.com'
            }
        }
    ];

    var expectedTimedAllowanceJson = [
        {
            created: "2015-08-10T09:15:45Z",
            id: 1,
            modified: "2015-08-10T09:15:45Z",
            key: "additional_time_granted",
            value: "1",
            proctored_exam: {
                content_id: "i4x://edX/DemoX/sequential/9f5e9b018a244ea38e5d157e0019e60c",
                course_id: "edX/DemoX/Demo_Course",
                exam_name: "Test Exam",
                external_id: null,
                id: 6,
                is_active: true,
                is_practice_exam: false,
                is_proctored: false,
                time_limit_mins: 1
            },
            user: {
                username: 'testuser1',
                email: 'testuser1@test.com'
            }
        }
    ];

    var proctoredExamJson = [
        {
            exam_name: "Midterm Exam",
            is_proctored: true,
            is_practice: false,
            id: 5
        },
        {
            exam_name: "Final Exam",
            is_proctored: false,
            is_practice: false,
            id: 6
        },
        {
            exam_name: "Test Exam",
            is_proctored: true,
            is_practice: true,
            id: 7
        }
    ];

    var allowanceTypes = [
        ['additional_time_granted', gettext('Additional Time (minutes)')],
        ['review_policy_exception', gettext('Review Policy Exception')]
    ];

    beforeEach(function () {

        // We have converted the edx_proctoring/static/proctoring/templates/add-new-allowance.underscore template
        // from http://www.howtocreate.co.uk/tutorials/jsexamples/syntax/prepareInline.html

        html = '<div class=\'modal-header\'><%- gettext(\"Add a New Allowance\") %><\/div>\n<form>\n    <h3 class=\'error-response\'><h3>\n    <table class=\'compact\'>\n        <tr>\n            <td>\n                <label><%- gettext(\"Special Exam\") %><\/label>\n            <\/td>\n            <td>\n                <select id=\'proctored_exam\'>\n                    <% _.each(proctored_exams, function(proctored_exam){ %>\n                    <option value=\"<%= proctored_exam.id %>\">\n                    <%- interpolate(gettext(\' %(exam_display_name)s \'), { exam_display_name: proctored_exam.exam_name }, true) %>\n                    <\/option>\n                    <% }); %>\n                <\/select>\n            <\/td>\n        <\/tr>\n        <tr>\n            <td>\n                <label><%- gettext(\"Exam Type\") %><\/label>\n            <\/td>\n            <td>\n                <label id=\'exam_type_label\'>\n                    <%- gettext(\"Timed Exam\") %>\n                <\/label>\n            <\/td>\n        <\/tr>\n        <tr>\n            <td>\n                <label><%- gettext(\"Allowance Type\") %><\/label>\n            <\/td>\n            <td>\n                <select id=\"allowance_type\">\n                    <% _.each(allowance_types, function(allowance_type){ %>\n                    <option value=\"<%= allowance_type[0] %>\">\n                        <%= allowance_type[1] %>\n                    <\/option>\n                    <% }); %>\n                <\/select>\n\n                <label id=\'timed_exam_allowance_type\'>\n                    <%- gettext(\"Additional Time (minutes)\") %>\n                <\/label>\n            <\/td>\n        <\/tr>\n        <tr>\n            <td>\n                <label id=\'allowance_value_label\'><%- gettext(\"Value\") %><\/label>\n            <\/td>\n            <td>\n                <input type=\"text\" id=\"allowance_value\" \/>\n                <label id=\'timed_exam_mins_label\'><%- gettext(\"minutes\") %><\/label>\n            <\/td>\n        <\/tr>\n        <tr>\n            <td>\n                <label><%- gettext(\"Username or Email\") %><\/label>\n            <\/td>\n            <td>\n                <input type=\"text\" id=\"user_info\" \/>\n            <\/td>\n        <\/tr>\n        <tr>\n            <td><\/td>\n            <td>\n                <input id=\'addNewAllowance\' type=\'submit\' value=\'Save\' \/>\n            <\/td>\n        <\/tr>\n    <\/table>\n<\/form>\n';

        allowancesHtml = '<span class="tip">' +
            '<%- gettext("Allowances") %>' +
            '<span> <a id="add-allowance" href="#"  class="add blue-button">+' +
            '<%- gettext("Add Allowance") %>' +
            '</a> </span> </span>' +
            '<% var is_allowances = proctored_exam_allowances.length !== 0 %>' +
            '<% if (is_allowances) { %>'+
            '<div class="wrapper-content wrapper"> <section class="content"> <table class="allowance-table">' +
            '<thead><tr class="allowance-headings">' +
            '<th class="exam-name">Exam Name</th>' +
            '<th class="username">Username</th>' +
            '<th class="email">Email</th>' +
            '<th class="allowance-name">Allowance Type</th>' +
            '<th class="allowance-value">Allowance Value</th>' +
            '<th class="c_action">Actions </th>' +
            '</tr></thead>' +
            '<tbody>' +
            '<% _.each(proctored_exam_allowances, function(proctored_exam_allowance){ %>' +
            '<tr class="allowance-items">' +
            '<td>' +
            '<%- interpolate(gettext(" %(exam_display_name)s "), { exam_display_name: proctored_exam_allowance.proctored_exam.exam_name }, true) %>' +
            '</td>' +
            '<% if (proctored_exam_allowance.user){ %>' +
            '<td>' +
            '<%- interpolate(gettext(" %(username)s "), { username: proctored_exam_allowance.user.username }, true) %>' +
            '</td>' +
            '<td>' +
            '<%- interpolate(gettext(" %(email)s "), { email: proctored_exam_allowance.user.email }, true) %>' +
            '</td>' +
            '<% }else{ %>' +
            '<td>N/A</td><td>N/A</td>' +
            '<% } %>' +
            '<td>' +
            '<%- interpolate(gettext(" %(allowance_name)s "), { allowance_name: proctored_exam_allowance.key_display_name }, true) %>' +
            '</td>' +
            '<td>' +
            '<%= proctored_exam_allowance.value %>' +
            '</td>' +
            '<td>' +
            '<a data-exam-id="<%= proctored_exam_allowance.proctored_exam.id %>" data-key-name="<%= proctored_exam_allowance.key %>" data-user-id="<%= proctored_exam_allowance.user.id %>"class="remove_allowance" href="#">[x]</a>' +
            '</td></tr>' +
            '<% }); %>' +
            '</tbody></table></section></div>' +
            '<% } %>';
        this.server = sinon.fakeServer.create();
        this.server.autoRespond = true;

        setFixtures('<div class="special-allowance-container" data-course-id="test_course_id"></div>');
        // load the underscore template response before calling the proctored exam allowance view.
        this.server.respondWith("GET", "/static/proctoring/templates/add-new-allowance.underscore",
            [
                200,
                {"Content-Type": "text/html"},
                html
            ]
        );
        this.server.respondWith("GET", "/static/proctoring/templates/course_allowances.underscore",
            [
                200,
                {"Content-Type": "text/html"},
                allowancesHtml
            ]
        );
    });

    afterEach(function() {
        this.server.restore();
    });
    it("should render the proctored exam add allowance view properly", function () {
        this.server.respondWith('GET', '/api/edx_proctoring/v1/proctored_exam/test_course_id/allowance',
            [
                200,
                {
                    "Content-Type": "application/json"
                },
                JSON.stringify(expectedProctoredAllowanceJson)
            ]
        );

        this.proctored_exam_allowance = new edx.instructor_dashboard.proctoring.ProctoredExamAllowanceView();
        var add_allowance_view = new edx.instructor_dashboard.proctoring.AddAllowanceView({
            course_id: 'test_course_id',
            proctored_exams: proctoredExamJson,
            proctored_exam_allowance_view: this.proctored_exam_allowance,
            allowance_types: allowanceTypes
        });
        this.server.respond();
        this.server.respond();
        this.server.respond();

        expect(add_allowance_view.$el.find('#proctored_exam').html()).toContain('Midterm Exam');
        expect(add_allowance_view.$el.find('#proctored_exam').html()).toContain('Final Exam');
        expect(add_allowance_view.$el.find('#proctored_exam').html()).toContain('Test Exam');
        expect(add_allowance_view.$el.find('#exam_type_label')).toExist();
        $('#proctored_exam').val('5');
        $('#proctored_exam').trigger( "change" );
        expect(add_allowance_view.$el.find('#exam_type_label').html()).toContain('Proctored Exam');
    });


    it("should render the timed exam add allowance view properly", function () {
        this.server.respondWith('GET', '/api/edx_proctoring/v1/proctored_exam/test_course_id/allowance',
            [
                200,
                {
                    "Content-Type": "application/json"
                },
                JSON.stringify(expectedTimedAllowanceJson)
            ]
        );

        this.proctored_exam_allowance = new edx.instructor_dashboard.proctoring.ProctoredExamAllowanceView();
        var add_allowance_view = new edx.instructor_dashboard.proctoring.AddAllowanceView({
            course_id: 'test_course_id',
            proctored_exams: proctoredExamJson,
            proctored_exam_allowance_view: this.proctored_exam_allowance,
            allowance_types: allowanceTypes
        });
        this.server.respond();
        this.server.respond();
        this.server.respond();

        expect(add_allowance_view.$el.find('#proctored_exam').html()).toContain('Midterm Exam');
        expect(add_allowance_view.$el.find('#proctored_exam').html()).toContain('Final Exam');
        expect(add_allowance_view.$el.find('#proctored_exam').html()).toContain('Test Exam');
        expect(add_allowance_view.$el.find('#exam_type_label')).toExist();
        $('#proctored_exam').val('6');
        $('#proctored_exam').trigger( "change" );
        expect(add_allowance_view.$el.find('#exam_type_label').html()).toContain('Timed Exam');
    });


    it("should add the proctored exam allowance", function () {
        this.server.respondWith('GET', '/api/edx_proctoring/v1/proctored_exam/test_course_id/allowance',
            [
                200,
                {
                    "Content-Type": "application/json"
                },
                JSON.stringify([])
            ]
        );

        this.proctored_exam_allowance = new edx.instructor_dashboard.proctoring.ProctoredExamAllowanceView();
        var add_allowance_view = new edx.instructor_dashboard.proctoring.AddAllowanceView({
            course_id: 'test_course_id',
            proctored_exams: proctoredExamJson,
            proctored_exam_allowance_view: this.proctored_exam_allowance,
            allowance_types: allowanceTypes
        });

        this.server.respond();
        this.server.respond();
        this.server.respond();

        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html()).not.toContain('testuser1');
        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html()).not.toContain('testuser1@test.com');
        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html()).not.toContain('Additional Time (minutes)');
        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html()).not.toContain('Test Exam');

        // add the proctored exam allowance
        this.server.respondWith('PUT', '/api/edx_proctoring/v1/proctored_exam/allowance',
            [
                200,
                {
                    "Content-Type": "application/json"
                },
                JSON.stringify([])
            ]
        );

        // again fetch the results after the proctored exam allowance addition
        this.server.respondWith('GET', '/api/edx_proctoring/v1/proctored_exam/test_course_id/allowance',
            [
                200,
                {
                    "Content-Type": "application/json"
                },
                JSON.stringify(expectedProctoredAllowanceJson)
            ]
        );

        //select the form values

        $('#proctored_exam').val('Test Exam');
        $('#allowance_type').val('additional_time_granted');
        $('#allowance_value').val('1');
        $("#user_info").val('testuser1');

        // trigger the add allowance event.
        var spyEvent = spyOnEvent('form', 'submit');
        $('form').trigger( "submit" );

        // process the deleted allowance requests.
        this.server.respond();
        this.server.respond();

        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html()).toContain('testuser1');
        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html()).toContain('testuser1@test.com');
        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html()).toContain('Additional Time (minutes)');
        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html()).toContain('Test Exam');
    });
    it("should send error when adding proctored exam allowance", function () {
        this.server.respondWith('GET', '/api/edx_proctoring/v1/proctored_exam/test_course_id/allowance',
            [
                200,
                {
                    "Content-Type": "application/json"
                },
                JSON.stringify([])
            ]
        );

        this.proctored_exam_allowance = new edx.instructor_dashboard.proctoring.ProctoredExamAllowanceView();
        var add_allowance_view = new edx.instructor_dashboard.proctoring.AddAllowanceView({
            course_id: 'test_course_id',
            proctored_exams: proctoredExamJson,
            proctored_exam_allowance_view: this.proctored_exam_allowance,
            allowance_types: allowanceTypes
        });

        this.server.respond();
        this.server.respond();
        this.server.respond();

        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html()).not.toContain('testuser1');
        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html()).not.toContain('testuser1@test.com');
        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html()).not.toContain('Additional Time (minutes)');
        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html()).not.toContain('Test Exam');

        // add the proctored exam allowance
        this.server.respondWith('PUT', '/api/edx_proctoring/v1/proctored_exam/allowance',
            [
                400,
                {
                    "Content-Type": "application/json"
                },
                JSON.stringify(errorAddingAllowance)
            ]
        );

        // again fetch the results after the proctored exam allowance addition
        this.server.respondWith('GET', '/api/edx_proctoring/v1/proctored_exam/test_course_id/allowance',
            [
                200,
                {
                    "Content-Type": "application/json"
                },
                JSON.stringify(expectedProctoredAllowanceJson)
            ]
        );

        //select the form values
        // invalid user_info returns error
        $('#proctored_exam').val('Test Exam');
        $('#allowance_type').val('additional_time_granted');
        $('#allowance_value').val('2');
        $("#user_info").val('testuser112321');

        // trigger the add allowance event.
        var spyEvent = spyOnEvent('form', 'submit');
        $('form').trigger( "submit" );

        // process the deleted allowance requests.
        this.server.respond();
        this.server.respond();

        expect(add_allowance_view.$el.find('.error-response').html()).toContain('Cannot find user');

        //select the form values
        // empty value returns error
        $('#proctored_exam').val('Test Exam');
        $('#allowance_type').val('Additional Time (minutes)');
        $('#allowance_value').val('');
        $("#user_info").val('testuser1');

        // trigger the add allowance event.
        var spyEvent = spyOnEvent('form', 'submit');
        $('form').trigger( "submit" );

        expect(add_allowance_view.$el.find('.error-message').html()).toContain('Required field');

    });
});
