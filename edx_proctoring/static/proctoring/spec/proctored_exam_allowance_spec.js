describe('ProctoredExamAllowanceView', function () {
    var html = '';
    var expectedProctoredAllowanceJson = [
        {
            created: "2015-08-10T09:15:45Z",
            id: 1,
            modified: "2015-08-10T09:15:45Z",
            key: "Additional time (minutes)",
            value: "1",
            proctored_exam: {
                content_id: "i4x://edX/DemoX/sequential/9f5e9b018a244ea38e5d157e0019e60c",
                course_id: "edX/DemoX/Demo_Course",
                exam_name: "Test Exam",
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
        }
    ];

    beforeEach(function () {
        html = '<span class="tip">' +
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
        this.server.respondWith("GET", "/static/proctoring/templates/course_allowances.underscore",
            [
                200,
                {"Content-Type": "text/html"},
                html
            ]
        );
    });

    afterEach(function() {
        this.server.restore();
    });
    it("should render the proctored exam allowance view properly", function () {
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
        this.server.respond();
        this.server.respond();
        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html()).toContain('testuser1');
        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html()).toContain('testuser1@test.com');
        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html()).toContain('Additional time (minutes)');
        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html()).toContain('Test Exam');
    });
    //
    it("should remove the proctored exam allowance", function () {
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

        this.server.respond();
        this.server.respond();

        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html()).toContain('testuser1');
        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html()).toContain('testuser1@test.com');
        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html()).toContain('Additional time (minutes)');
        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html()).toContain('Test Exam');

        // delete the proctored exam allowance one by one
        this.server.respondWith('DELETE', '/api/edx_proctoring/v1/proctored_exam/allowance',
            [
                200,
                {
                    "Content-Type": "application/json"
                },
                JSON.stringify([])
            ]
        );

        // again fetch the results after the proctored exam allowance deletion
        this.server.respondWith('GET', '/api/edx_proctoring/v1/proctored_exam/test_course_id/allowance',
            [
                200,
                {
                    "Content-Type": "application/json"
                },
                JSON.stringify([])
            ]
        );

        // trigger the remove allowance event.
        var spyEvent = spyOnEvent('.remove_allowance', 'click');
        $('.remove_allowance').trigger( "click" );

        // process the deleted allowance requests.
        this.server.respond();
        this.server.respond();

        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html()).not.toContain('testuser1');
        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html()).not.toContain('testuser1@test.com');
        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html()).not.toContain('Additional time (minutes)');
        expect(this.proctored_exam_allowance.$el.find('tr.allowance-items').html()).not.toContain('Test Exam');
    });
});
