describe('ProctoredExamAttemptView', function() {
    'use strict';

    var html = '';
    var deletedProctoredExamAttemptJson = [{
        attempt_url: '/api/edx_proctoring/v1/proctored_exam/attempt/course_id/edX/DemoX/Demo_Course',
        proctored_exam_attempts: [],
        pagination_info: {
            current_page: 1,
            has_next: false,
            has_previous: false,
            total_pages: 1
        }

    }];
    function getExpectedProctoredExamAttemptWithAttemptStatusJson(status, isPracticeExam) {
        // eslint-disable-next-line no-param-reassign
        isPracticeExam = typeof isPracticeExam !== 'undefined' ? isPracticeExam : false;
        return (
            [{
                attempt_url: '/api/edx_proctoring/v1/proctored_exam/attempt/course_id/edX/DemoX/Demo_Course',
                pagination_info: {
                    current_page: 1,
                    has_next: false,
                    has_previous: false,
                    total_pages: 1
                },
                proctored_exam_attempts: [{
                    allowed_time_limit_mins: 1,
                    attempt_code: '20C32387-372E-48BD-BCAC-A2BE9DC91E09',
                    completed_at: null,
                    created: '2015-08-10T09:15:45Z',
                    external_id: '40eceb15-bcc3-4791-b43f-4e843afb7ae8',
                    id: 43,
                    is_sample_attempt: false,
                    modified: '2015-08-10T09:15:45Z',
                    started_at: '2015-08-10T09:15:45Z',
                    status: status,
                    is_resumable: false,
                    taking_as_proctored: true,
                    proctored_exam: {
                        content_id: 'i4x://edX/DemoX/sequential/9f5e9b018a244ea38e5d157e0019e60c',
                        course_id: 'edX/DemoX/Demo_Course',
                        exam_name: 'Normal Exam',
                        external_id: null,
                        id: 17,
                        is_active: true,
                        is_practice_exam: isPracticeExam,
                        is_proctored: true,
                        time_limit_mins: 1
                    },
                    user: {
                        id: 1,
                        username: 'testuser1',
                        email: 'testuser1@test.com'
                    },
                    all_attempts: [{
                        allowed_time_limit_mins: 1,
                        attempt_code: '20C32387-372E-48BD-BCAC-A2BE9DC91E09',
                        completed_at: null,
                        created: '2015-08-10T09:15:45Z',
                        external_id: '40eceb15-bcc3-4791-b43f-4e843afb7ae8',
                        id: 43,
                        is_sample_attempt: false,
                        modified: '2015-08-10T09:15:45Z',
                        started_at: '2015-08-10T09:15:45Z',
                        status: status,
                        taking_as_proctored: true,
                        proctored_exam: {
                            content_id: 'i4x://edX/DemoX/sequential/9f5e9b018a244ea38e5d157e0019e60c',
                            course_id: 'edX/DemoX/Demo_Course',
                            exam_name: 'Normal Exam',
                            external_id: null,
                            id: 17,
                            is_active: true,
                            is_practice_exam: isPracticeExam,
                            is_proctored: true,
                            time_limit_mins: 1
                        },
                        user: {
                            id: 1,
                            username: 'testuser1',
                            email: 'testuser1@test.com'
                        }
                    }]
                }]
            }]
        );
    }

    function getExpectedGroupedProctoredExamAttemptWithAttemptStatusJson(
        status, isPracticeExam, isResumable, readyToResume, resumed
    ) {
        // eslint-disable-next-line no-param-reassign
        isPracticeExam = typeof isPracticeExam !== 'undefined' ? isPracticeExam : false;
        // eslint-disable-next-line no-param-reassign
        isResumable = typeof isResumable !== 'undefined' ? isResumable : false;
        return (
            [{
                attempt_url: '/api/edx_proctoring/v1/proctored_exam/attempt/course_id/edX/DemoX/Demo_Course',
                pagination_info: {
                    current_page: 1,
                    has_next: false,
                    has_previous: false,
                    total_pages: 1
                },
                proctored_exam_attempts: [{
                    allowed_time_limit_mins: 1,
                    attempt_code: '20C32387-372E-48BD-BCAC-A2BE9DC91E09',
                    completed_at: null,
                    created: '2015-08-10T09:15:45Z',
                    external_id: '40eceb15-bcc3-4791-b43f-4e843afb7ae8',
                    id: 43,
                    is_sample_attempt: false,
                    modified: '2015-08-10T09:15:45Z',
                    started_at: '2015-08-10T09:15:45Z',
                    status: status,
                    is_resumable: isResumable,
                    ready_to_resume: readyToResume,
                    resumed: resumed,
                    taking_as_proctored: true,
                    proctored_exam: {
                        content_id: 'i4x://edX/DemoX/sequential/9f5e9b018a244ea38e5d157e0019e60c',
                        course_id: 'edX/DemoX/Demo_Course',
                        exam_name: 'Normal Exam',
                        external_id: null,
                        id: 17,
                        is_active: true,
                        is_practice_exam: isPracticeExam,
                        is_proctored: true,
                        time_limit_mins: 1
                    },
                    user: {
                        username: 'testuser1',
                        email: 'testuser1@test.com',
                        id: 1
                    },
                    all_attempts: [
                        {
                            allowed_time_limit_mins: 1,
                            attempt_code: '20C32387-372E-48BD-BCAC-A2BE9DC91E09',
                            completed_at: null,
                            created: '2015-08-10T09:15:45Z',
                            external_id: '40eceb15-bcc3-4791-b43f-4e843afb7ae8',
                            id: 43,
                            is_sample_attempt: false,
                            modified: '2015-08-10T09:15:45Z',
                            started_at: '2015-08-10T09:15:45Z',
                            status: status,
                            is_resumable: isResumable,
                            ready_to_resume: readyToResume,
                            resumed: resumed,
                            taking_as_proctored: true,
                            proctored_exam: {
                                content_id: 'i4x://edX/DemoX/sequential/9f5e9b018a244ea38e5d157e0019e60c',
                                course_id: 'edX/DemoX/Demo_Course',
                                exam_name: 'Normal Exam',
                                external_id: null,
                                id: 17,
                                is_active: true,
                                is_practice_exam: isPracticeExam,
                                is_proctored: true,
                                time_limit_mins: 1
                            },
                            user: {
                                username: 'testuser1',
                                email: 'testuser1@test.com',
                                id: 1
                            }
                        },
                        {
                            allowed_time_limit_mins: 1,
                            attempt_code: '20C32387-372E-48BD-BCAC-A2BE9DC91E10',
                            completed_at: null,
                            created: '2015-08-10T09:15:45Z',
                            external_id: '40eceb15-bcc3-4791-b43f-4e843afb7ae9',
                            id: 44,
                            is_sample_attempt: false,
                            modified: '2015-08-10T09:15:45Z',
                            started_at: '2015-08-10T09:15:45Z',
                            status: 'resumed',
                            is_resumable: false,
                            ready_to_resume: true,
                            resumed: true,
                            taking_as_proctored: true,
                            proctored_exam: {
                                content_id: 'i4x://edX/DemoX/sequential/9f5e9b018a244ea38e5d157e0019e60c',
                                course_id: 'edX/DemoX/Demo_Course',
                                exam_name: 'Normal Exam',
                                external_id: null,
                                id: 17,
                                is_active: true,
                                is_practice_exam: isPracticeExam,
                                is_proctored: true,
                                time_limit_mins: 1
                            },
                            user: {
                                username: 'testuser1',
                                email: 'testuser1@test.com',
                                id: 1
                            }
                        }
                    ]
                }]
            }]
        );
    }

    beforeEach(function() {
        html = '<div class="wrapper-content wrapper">' +
        '<% var is_proctored_attempts = proctored_exam_attempts.length !== 0 %>' +
        '<div class="content exam-attempts-content">' +
        '<div class="top-header">' +
        '<div class="search-attempts">' +
        '<input type="text" id="search_attempt_id" placeholder="e.g johndoe or john.doe@gmail.com"' +
        '<% if (inSearchMode) { %> value="<%= searchText %>" <%} %> /> ' +
        '<span class="search">' +
        '<span class="icon fa fa-search" id="attempt-search-indicator" aria-hidden="true"></span>' +
        '<div aria-live="polite" aria-relevant="all">' +
        '<div id="attempt-loading-indicator" class="hidden">' +
        '<span class="icon fa fa-spinner fa-pulse" aria-hidden="true"></span>' +
        '<span class="sr"><%- gettext("Loading") %></span>' +
        '</div>' +
        '</div>' +
        '</span>' +
        '<span class="clear-search"><span class="icon fa fa-remove" aria-hidden="true"></span></span>' +
        '</div>' +
        '<ul class="pagination">' +
        '<% if (!pagination_info.has_previous){ %>' +
        '<li class="disabled"> <a aria-label="Previous"> <span aria-hidden="true">&laquo;</span> </a> </li>' +
        '<% } else { %>' +
        '<li>' +
        '<a class="target-link " data-target-url="' +
        '<%- interpolate("%(attempt_url)s?page=%(count)s ",' +
        '{attempt_url: attempt_url, count: pagination_info.current_page - 1}, true) %>' +
        '"' +
        'href="#" aria-label="Previous">' +
        '<span aria-hidden="true">&laquo;</span> </a> </li> <% }%>' +
        '<% for(var n = 1; n <= pagination_info.total_pages; n++) { %>' +
        '<li> <a class="target-link <% if (pagination_info.current_page == n){ %> active <% } %>" data-target-url=" ' +
        '<%- interpolate("%(attempt_url)s?page=%(count)s ", {attempt_url: attempt_url, count: n}, true) %>' +
        '"href="#"><%= n %> </a></li> <% } %>' +
        '<% if (!pagination_info.has_next){ %>' +
        '<li class="disabled"> <a aria-label="Next"> <span aria-hidden="true">&raquo;</span> </a></li>' +
        '<% } else { %> <li> <a class="target-link" href="#" aria-label="Next" data-target-url="' +
        '<%- interpolate("%(attempt_url)s?page=%(count)s ",' +
        '{attempt_url: attempt_url, count: pagination_info.current_page + 1}, true) %>' +
        '" > <span aria-hidden="true">&raquo;</span></a> </li> <% }%> </ul><div class="clearfix"></div></div>' +
        '<table class="exam-attempts-table"> <thead><tr class="exam-attempt-headings">' +
        '<th class="more"></th>' +
        '<th class="username">Username</th>' +
        '<th class="exam-name">Exam Name</th>' +
        '<th class="attempt-allowed-time">Allowed Time (Minutes)</th>' +
        '<th class="attempt-started-at">Started At</th>' +
        '<th class="attempt-completed-at">Completed At</th>' +
        '<th class="attempt-status">Status</th>' +
        '<th class="attempt-ready-to-resume"><%- gettext("Ready to Resume") %> </th>' +
        '<th class="c_action">Actions</th>' +
        '</tr></thead>' +
        '<% if (is_proctored_attempts) { %>\n' +
        '<% _.each(proctored_exam_attempts, function(proctored_exam_attempt, dashboard_index){ %>' +
        '<tbody class="<%= proctored_exam_attempt.row_class %><% if (proctored_exam_attempt.all_attempts.length > 1)' +
        ' { %> accordion-trigger <% } %>"' +
        'aria-expanded="false"' +
        'id="<%= proctored_exam_attempt.id %>"' +
        'aria-controls="<%= proctored_exam_attempt.id %>_contents"' +
        '<% if (proctored_exam_attempt.all_attempts.length > 1) { %>' +
        'tabindex=0 <% } %>' +
        '>' +
        '<tr class="allowance-items">' +
        '<td>' +
        '<% if (proctored_exam_attempt.all_attempts.length > 1) { %>' +
        '<span class="fa fa-chevron-right" aria-hidden="true"></span>' +
        '<% } %> </td>' +
        '<td>' +
        '<%- interpolate(gettext(\' %(username)s \'), { username: proctored_exam_attempt.user.username }, true) %>' +
        '</td>' +
        '<td>' +
        '<%- interpolate(gettext(\' %(exam_display_name)s \'), ' +
        '{ exam_display_name: proctored_exam_attempt.proctored_exam.exam_name }, true) %>' +
        '</td>' +
        '<td> <%= proctored_exam_attempt.allowed_time_limit_mins %></td>' +
        '<td> <%= proctored_exam_attempt.exam_attempt_type %></td>' +
        '<% if (proctored_exam_attempt.all_attempts.length <= 1){ %>' +
        '<td> <%= getDateFormat(proctored_exam_attempt.started_at) %></td>' +
        '<td> <%= getDateFormat(proctored_exam_attempt.completed_at) %></td>' +
        '<td>' +
        '<% if (proctored_exam_attempt.status){ %>' +
        '<%= getExamAttemptStatus(proctored_exam_attempt.status) %>' +
        '<% } else { %> N/A <% } %>' +
        '</td>' +
        '<% if (' +
        'proctored_exam_attempt.ready_to_resume && !proctored_exam_attempt.resumed' +
        ') { %>' +
        '<td>' +
        '<span class="fa fa-check-circle" aria-hidden="true"></span>' +
        '</td>' +
        '<% } else { %>' +
        '<td></td>' +
        '<% } %>' +
        '<% } else { %>' +
        '<td></td>' +
        '<td></td>' +
        '<td></td>' +
        '<td></td>' +
        '<% } %>' +
        '<td>' +
        '<% if (proctored_exam_attempt.status){ %>' +
        '<% if (' +
        'proctored_exam_attempt.is_resumable &&' +
        '!proctored_exam_attempt.proctored_exam.is_practice_exam' +
        ') { %>' +
        '<div class="wrapper-action-more">' +
        '<button class="action action-more" type="button" ' +
        'id="actions-dropdown-link-<%= dashboard_index %>" aria-haspopup="true" aria-expanded="false" ' +
        'aria-controls="actions-dropdown-<%= dashboard_index %>" data-dashboard-index="<%= dashboard_index %>">' +
        '<span class="fa fa-cog" aria-hidden="true"></span>' +
        '</button>' +
        '<div class="actions-dropdown" id="actions-dropdown-<%= dashboard_index %>" tabindex="-1">' +
        '<ul class="actions-dropdown-list" id="actions-dropdown-list-<%= dashboard_index %>" ' +
        'aria-label="<%- gettext("Available Actions") %>" role="menu">' +
        '<li class="actions-item" role="menuitem">' +
        '<a href="#" class="action resume-attempt" data-attempt-id="<%= proctored_exam_attempt.id %>" ' +
        'data-user-id="<%= proctored_exam_attempt.user.id %>" >' +
        '<%- gettext("Resume") %>' +
        '</a>' +
        '</li>' +
        '<li class="actions-item" role="menuitem">' +
        '<a href="#" class="action remove-attempt" data-attempt-id="<%= proctored_exam_attempt.id %>" ' +
        'data-user-id="<%= proctored_exam_attempt.user.id %>" ' +
        'data-exam-id="<%= proctored_exam_attempt.proctored_exam.id %>" >' +
        '<%- gettext("Reset") %>' +
        '</a>' +
        '</li>' +
        '</ul>' +
        '</div>' +
        '</div>' +
        '<% } else { %>' +
        '<a href="#" class="action remove-attempt" data-attempt-id="<%= proctored_exam_attempt.id %>" ' +
        'data-user-id="<%= proctored_exam_attempt.user.id %>" ' +
        'data-exam-id="<%= proctored_exam_attempt.proctored_exam.id %>" >' +
        '<%- gettext("Reset") %>' +
        '</a>' +
        '<% } %>' +
        '<% } else { %>' +
        'N/A' +
        '<% } %>' +
        '</td>' +
        '</tr>' +
        '</tbody>' +
        '<% if (proctored_exam_attempt.all_attempts.length > 1) { %>' +
        '<tbody class="accordion-panel is-hidden" id="<%= proctored_exam_attempt.id %>_contents">' +
        '<% _.each(proctored_exam_attempt.all_attempts, function(proctored_exam_attempt) { %>' +
        '<tr class="allowance-items">' +
        '<td></td> <td></td> <td></td> <td></td> <td></td>' +
        '<td> <%= getDateFormat(proctored_exam_attempt.started_at) %></td>' +
        '<td> <%= getDateFormat(proctored_exam_attempt.completed_at) %></td>' +
        '<td>' +
        '<% if (proctored_exam_attempt.status) { %>' +
        '<%= getExamAttemptStatus(proctored_exam_attempt.status) %>' +
        '<% } else { %> N/A <% } %> </td>' +
        '<% if (' +
        'proctored_exam_attempt.ready_to_resume && !proctored_exam_attempt.resumed' +
        ') { %>' +
        '<td>' +
        '<span class="fa fa-check-circle" aria-hidden="true"></span>' +
        '</td>' +
        '<% } else { %>' +
        '<td></td>' +
        '<% } %>' +
        '<td></td> ' +
        '</tr> <% }); %>' +
        '</tbody> <% }%> <% }); %> <% } %>' +
        '</table>' +
        '<% if (!is_proctored_attempts) { %>' +
        '<p> No exam results found. </p>' +
        '<% } %>' +
        '</div>' +
        '</div>';
        this.server = sinon.fakeServer.create();
        this.server.autoRespond = true;
        setFixtures('<div class="student-proctored-exam-container" data-course-id="test_course_id"></div>');

        // load the underscore template response before calling the proctored exam attempt view.
        this.server.respondWith(
            'GET',
            '/static/proctoring/templates/student-proctored-exam-attempts-grouped.underscore',
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
    it('should render the proctored exam attempt view properly', function() {
        this.server.respondWith('GET', '/api/edx_proctoring/v1/proctored_exam/attempt/grouped/course_id/test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(getExpectedProctoredExamAttemptWithAttemptStatusJson('started'))
            ]
        );
        this.proctored_exam_attempt_view = new edx.instructor_dashboard.proctoring.ProctoredExamAttemptView();

        this.server.respond();
        this.server.respond();

        expect(this.proctored_exam_attempt_view.$el.find('tr.allowance-items')).toContainHtml('<td> testuser1 </td>');
        expect(this.proctored_exam_attempt_view.$el.find('tr.allowance-items').html()).toContain('Normal Exam');
    });

    it('should search for the proctored exam attempt', function() {
        var searchText = 'testuser1';
        this.server.respondWith('GET', '/api/edx_proctoring/v1/proctored_exam/attempt/grouped/course_id/test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(getExpectedProctoredExamAttemptWithAttemptStatusJson('started'))
            ]
        );

        this.proctored_exam_attempt_view = new edx.instructor_dashboard.proctoring.ProctoredExamAttemptView();

        // Process all requests so far
        this.server.respond();
        this.server.respond();

        expect(this.proctored_exam_attempt_view.$el.find('tr.allowance-items')).toContainHtml('<td> testuser1 </td>');
        expect(this.proctored_exam_attempt_view.$el.find('tr.allowance-items').html()).toContain('Normal Exam');
        expect(this.proctored_exam_attempt_view.$el.find('#attempt-search-indicator').hasClass('hidden'))
            .toEqual(false);
        expect(this.proctored_exam_attempt_view.$el.find('#attempt-loading-indicator').hasClass('hidden'))
            .toEqual(true);

        $('#search_attempt_id').val(searchText);

        // search for the proctored exam attempt
        this.server.respondWith(
            'GET',
            '/api/edx_proctoring/v1/proctored_exam/attempt/grouped/course_id/test_course_id/search/' + searchText,
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(getExpectedProctoredExamAttemptWithAttemptStatusJson('started'))
            ]
        );

        // trigger the search attempt event.
        spyOnEvent('.search-attempts > span.search', 'click');
        $('.search-attempts > span.search').trigger('click');

        // check that spinner is visible
        expect(this.proctored_exam_attempt_view.$el.find('#attempt-search-indicator').hasClass('hidden'))
            .toEqual(true);
        expect(this.proctored_exam_attempt_view.$el.find('#attempt-loading-indicator').hasClass('hidden'))
            .toEqual(false);

        // process the search attempt requests.
        this.server.respond();

        // search matches the existing attempts
        expect(this.proctored_exam_attempt_view.$el.find('tr.allowance-items').html()).toContain('testuser1');
        expect(this.proctored_exam_attempt_view.$el.find('tr.allowance-items').html()).toContain('Normal Exam');
        // check that spinner is hidden again
        expect(this.proctored_exam_attempt_view.$el.find('#attempt-search-indicator').hasClass('hidden'))
            .toEqual(false);
        expect(this.proctored_exam_attempt_view.$el.find('#attempt-loading-indicator').hasClass('hidden'))
            .toEqual(true);
    });

    it('should clear the search for the proctored exam attempt', function() {
        var searchText = 'invalid_search_text';
        this.server.respondWith('GET', '/api/edx_proctoring/v1/proctored_exam/attempt/grouped/course_id/test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(getExpectedProctoredExamAttemptWithAttemptStatusJson('started'))
            ]
        );
        this.proctored_exam_attempt_view = new edx.instructor_dashboard.proctoring.ProctoredExamAttemptView();

        // Process all requests so far
        this.server.respond();
        this.server.respond();

        expect(this.proctored_exam_attempt_view.$el.find('tr.allowance-items')).toContainHtml('<td> testuser1 </td>');
        expect(this.proctored_exam_attempt_view.$el.find('tr.allowance-items').html()).toContain('Normal Exam');

        $('#search_attempt_id').val(searchText);

        // search the proctored exam attempt
        this.server.respondWith(
            'GET',
            '/api/edx_proctoring/v1/proctored_exam/attempt/grouped/course_id/test_course_id/search/' + searchText,
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(deletedProctoredExamAttemptJson)
            ]
        );

        // trigger the search attempt event.
        spyOnEvent('.search-attempts > span.search', 'click');
        $('.search-attempts > span.search').trigger('click');

        // process the search attempt request.
        this.server.respond();

        // search doesn't matches the existing attempts
        expect(this.proctored_exam_attempt_view.$el.find('tr.allowance-items').html()).not.toContain('testuser1');
        expect(this.proctored_exam_attempt_view.$el.find('tr.allowance-items').html()).not.toContain('Normal Exam');


        this.server.respondWith('GET', '/api/edx_proctoring/v1/proctored_exam/attempt/grouped/course_id/test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(getExpectedProctoredExamAttemptWithAttemptStatusJson('started'))
            ]
        );

        // trigger the clear search event.
        spyOnEvent('.search-attempts > span.clear-search', 'click');
        $('.search-attempts > span.clear-search').trigger('click');

        // process the reset attempt request.
        this.server.respond();

        // after resetting the attempts, selector matches the existing attempts
        expect(this.proctored_exam_attempt_view.$el.find('tr.allowance-items').html()).toContain('testuser1');
        expect(this.proctored_exam_attempt_view.$el.find('tr.allowance-items').html()).toContain('Normal Exam');
    });

    it('should display check when exam attempt is ready to resume', function() {
        var rows;

        this.server.respondWith('GET', '/api/edx_proctoring/v1/proctored_exam/attempt/grouped/course_id/test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(getExpectedGroupedProctoredExamAttemptWithAttemptStatusJson(
                    'error', false, true, true, false)
                )
            ]
        );
        this.proctored_exam_attempt_view = new edx.instructor_dashboard.proctoring.ProctoredExamAttemptView();

        // Process all requests so far
        this.server.respond();
        this.server.respond();

        rows = this.proctored_exam_attempt_view.$el.find('tbody').children();
        expect(rows.length).toEqual(3);

        // check that ready to resume check does not appear in outer level
        expect(rows[0].outerHTML).not.toContain('fa-check-circle');

        // check that status is present in other two rows
        expect(rows[1].outerHTML).toContain('fa-check-circle');
        expect(rows[2].outerHTML).not.toContain('fa-check-circle');
    });

    it('should not display check when exam attempt has status ready to resume but has been resumed', function() {
        var rows;

        this.server.respondWith('GET', '/api/edx_proctoring/v1/proctored_exam/attempt/grouped/course_id/test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(getExpectedGroupedProctoredExamAttemptWithAttemptStatusJson(
                    'error', false, false, false, true)
                )
            ]
        );
        this.proctored_exam_attempt_view = new edx.instructor_dashboard.proctoring.ProctoredExamAttemptView();

        // Process all requests so far
        this.server.respond();
        this.server.respond();

        rows = this.proctored_exam_attempt_view.$el.find('tbody').children();
        expect(rows.length).toEqual(3);

        // check that ready to resume check does not appear in outer level
        expect(rows[0].outerHTML).not.toContain('fa-check-circle');

        // check that status is present in other two rows
        expect(rows[1].outerHTML).not.toContain('fa-check-circle');
        expect(rows[2].outerHTML).not.toContain('fa-check-circle');
    });

    it('should mark exam attempt "ready_to_resume" on resume', function() {
        this.server.respondWith('GET', '/api/edx_proctoring/v1/proctored_exam/attempt/grouped/course_id/test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(getExpectedGroupedProctoredExamAttemptWithAttemptStatusJson('error', false, true))
            ]
        );
        this.proctored_exam_attempt_view = new edx.instructor_dashboard.proctoring.ProctoredExamAttemptView();

        // Process all requests so far
        this.server.respond();
        this.server.respond();

        expect(this.proctored_exam_attempt_view.$el.find('tbody').html()).toContain('testuser1');
        expect(this.proctored_exam_attempt_view.$el.find('tbody').html()).toContain('Normal Exam');
        expect(this.proctored_exam_attempt_view.$el.find('tbody.accordion-panel').html()).toContain('Error');

        expect(this.proctored_exam_attempt_view.$el.find('button.action').html()).not.toHaveLength(0);
        expect(this.proctored_exam_attempt_view.$el.find('.actions-dropdown').hasClass('is-visible')).toEqual(false);

        this.server.respondWith('PUT', '/api/edx_proctoring/v1/proctored_exam/attempt/43',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify([])
            ]
        );

        // again fetch the results after the proctored exam attempt is marked ready_to_resume
        this.server.respondWith('GET', '/api/edx_proctoring/v1/proctored_exam/attempt/grouped/course_id/test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(getExpectedGroupedProctoredExamAttemptWithAttemptStatusJson(
                    'error', false, false, true, false
                ))
            ]
        );

        spyOn(window, 'confirm').and.callFake(function() {
            return true;
        });

        // click the gear button to open the action dropdown
        spyOnEvent('.action-more', 'click');
        $('.action-more').trigger('click');

        expect(this.proctored_exam_attempt_view.$el.find('.actions-dropdown').hasClass('is-visible')).toEqual(true);
        expect(this.proctored_exam_attempt_view.$el.find(
            '.actions-dropdown .actions-dropdown-list .actions-item .action'
        )[0].text).toContain('Resume');
        expect(this.proctored_exam_attempt_view.$el.find('.actions-dropdown .actions-dropdown-list '
        + '.actions-item .action')[1].text).toContain('Reset');
        expect(this.proctored_exam_attempt_view.$el.find('.accordion-panel').hasClass('is-hidden')).toEqual(true);

        // trigger the resume attempt event.
        spyOnEvent('.resume-attempt', 'click');
        $('.resume-attempt').trigger('click');

        expect(window.confirm.calls.argsFor(0)[0]).toEqual(
            'Are you sure you want to resume this student\'s exam attempt?'
        );

        // process the resume attempt requests.
        this.server.respond();
        this.server.respond();

        expect(this.proctored_exam_attempt_view.$el.find('tbody').html()).toContain('testuser1');
        expect(this.proctored_exam_attempt_view.$el.find('tbody').html()).toContain('Normal Exam');
        expect(this.proctored_exam_attempt_view.$el.find('tbody.accordion-panel').html()).toContain('fa-check-circle');
        expect(this.proctored_exam_attempt_view.$el.find('.actions-dropdown').hasClass('is-visible')).toEqual(false);
    });

    it('should not display actions dropdown for practice exam attempts', function() {
        this.server.respondWith('GET', '/api/edx_proctoring/v1/proctored_exam/attempt/grouped/course_id/test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(getExpectedGroupedProctoredExamAttemptWithAttemptStatusJson('error', true, true))
            ]
        );
        this.proctored_exam_attempt_view = new edx.instructor_dashboard.proctoring.ProctoredExamAttemptView();

        // Process all requests so far
        this.server.respond();
        this.server.respond();

        expect(this.proctored_exam_attempt_view.$el.find('tbody').html()).toContain('testuser1');
        expect(this.proctored_exam_attempt_view.$el.find('tbody').html()).toContain('Normal Exam');
        expect(this.proctored_exam_attempt_view.$el.find('tbody.accordion-panel').html()).toContain('Error');

        expect(this.proctored_exam_attempt_view.$el.find('button.action').html()).toHaveLength(0);
        expect(this.proctored_exam_attempt_view.$el.find('.actions-dropdown').html()).toHaveLength(0);
    });

    it('should not display actions dropdown for exam attempts not resumable', function() {
        this.server.respondWith('GET', '/api/edx_proctoring/v1/proctored_exam/attempt/grouped/course_id/test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(getExpectedGroupedProctoredExamAttemptWithAttemptStatusJson('error', true, false))
            ]
        );
        this.proctored_exam_attempt_view = new edx.instructor_dashboard.proctoring.ProctoredExamAttemptView();

        // Process all requests so far
        this.server.respond();
        this.server.respond();

        expect(this.proctored_exam_attempt_view.$el.find('tbody').html()).toContain('testuser1');
        expect(this.proctored_exam_attempt_view.$el.find('tbody').html()).toContain('Normal Exam');
        expect(this.proctored_exam_attempt_view.$el.find('tbody.accordion-panel').html()).toContain('Error');

        expect(this.proctored_exam_attempt_view.$el.find('button.action').html()).toHaveLength(0);
        expect(this.proctored_exam_attempt_view.$el.find('.actions-dropdown').html()).toHaveLength(0);
    });

    it('should display grouped attempts', function() {
        var rows;

        this.server.respondWith('GET', '/api/edx_proctoring/v1/proctored_exam/attempt/grouped/course_id/test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(getExpectedGroupedProctoredExamAttemptWithAttemptStatusJson('error', false, true))
            ]
        );
        this.proctored_exam_attempt_view = new edx.instructor_dashboard.proctoring.ProctoredExamAttemptView();

        // Process all requests so far
        this.server.respond();
        this.server.respond();

        rows = this.proctored_exam_attempt_view.$el.find('tbody').children();

        expect(rows.length).toEqual(3);

        // check that status does not appear in first row of group
        expect(rows[0].outerHTML).not.toContain('Error');
        expect(rows[0].outerHTML).not.toContain('Resumed');
        expect(rows[0].outerHTML).toContain('action-more');

        // check that status is present in other two rows
        expect(rows[1].outerHTML).toContain('Error');
        expect(rows[1].outerHTML).not.toContain('action-more');
        expect(rows[2].outerHTML).toContain('resumed');
        expect(rows[2].outerHTML).not.toContain('action-more');
    });

    it('deletes attempts', function() {
        this.server.respondWith('GET', '/api/edx_proctoring/v1/proctored_exam/attempt/grouped/course_id/test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(getExpectedGroupedProctoredExamAttemptWithAttemptStatusJson('error', false, true))
            ]
        );
        this.proctored_exam_attempt_view = new edx.instructor_dashboard.proctoring.ProctoredExamAttemptView();

        // Process all requests so far
        this.server.respond();
        this.server.respond();

        // delete the proctored exam attempts
        this.server.respondWith(
            'DELETE',
            '/api/edx_proctoring/v1/proctored_exam/exam_id/17/user_id/1/reset_attempts',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify([])
            ]
        );

        // again fetch the results after the proctored exam attempt deletion
        this.server.respondWith(
            'GET',
            '/api/edx_proctoring/v1/proctored_exam/attempt/grouped/course_id/test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(deletedProctoredExamAttemptJson)
            ]
        );

        spyOn(window, 'confirm').and.callFake(function() {
            return true;
        });

        // click the gear button to open the action dropdown
        spyOnEvent('.action-more', 'click');
        $('.action-more').trigger('click');

        expect(this.proctored_exam_attempt_view.$el.find('.actions-dropdown').hasClass('is-visible')).toEqual(true);
        expect(this.proctored_exam_attempt_view.$el.find(
            '.actions-dropdown .actions-dropdown-list .actions-item .action'
        )[0].text).toContain('Resume');
        expect(this.proctored_exam_attempt_view.$el.find('.actions-dropdown .actions-dropdown-list '
        + '.actions-item .action')[1].text).toContain('Reset');

        // trigger the remove attempt event.
        spyOnEvent('.remove-attempt', 'click');
        $('.remove-attempt').trigger('click');

        // process the deleted attempt requests.
        this.server.respond();
        this.server.respond();

        expect(this.proctored_exam_attempt_view.$el.find('tbody').html()).not.toContain('testuser1');
        expect(this.proctored_exam_attempt_view.$el.find('tbody').html()).not.toContain('Normal Exam');
    });

    it('shows and hides accordion when toggled', function() {
        this.server.respondWith('GET', '/api/edx_proctoring/v1/proctored_exam/attempt/grouped/course_id/test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(getExpectedGroupedProctoredExamAttemptWithAttemptStatusJson('submitted', false))
            ]
        );
        this.proctored_exam_attempt_view = new edx.instructor_dashboard.proctoring.ProctoredExamAttemptView();

        // Process all requests so far
        this.server.respond();
        this.server.respond();

        // check that accordion is hidden
        expect(this.proctored_exam_attempt_view.$el.find('.accordion-panel').hasClass('is-hidden')).toEqual(true);

        // click to expand section
        spyOnEvent('.accordion-trigger', 'click');
        $('.accordion-trigger').trigger('click');

        // check that accordion is no longer hidden
        expect(this.proctored_exam_attempt_view.$el.find('.accordion-panel').hasClass('is-hidden')).toEqual(false);
    });

    it('searches and shows spinner for grouped attempts', function() {
        var searchText = 'testuser1';

        this.server.respondWith('GET', '/api/edx_proctoring/v1/proctored_exam/attempt/grouped/course_id/test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(getExpectedGroupedProctoredExamAttemptWithAttemptStatusJson('submitted', false))
            ]
        );
        this.proctored_exam_attempt_view = new edx.instructor_dashboard.proctoring.ProctoredExamAttemptView();

        // Process all requests so far
        this.server.respond();
        this.server.respond();

        expect(this.proctored_exam_attempt_view.$el.find('#attempt-search-indicator').hasClass('hidden'))
            .toEqual(false);
        expect(this.proctored_exam_attempt_view.$el.find('#attempt-loading-indicator').hasClass('hidden'))
            .toEqual(true);

        $('#search_attempt_id').val(searchText);

        // search for the proctored exam attempt
        this.server.respondWith(
            'GET',
            '/api/edx_proctoring/v1/proctored_exam/attempt/grouped/course_id/test_course_id/search/' + searchText,
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(getExpectedGroupedProctoredExamAttemptWithAttemptStatusJson('started'))
            ]
        );

        // trigger the search attempt event.
        spyOnEvent('.search-attempts > span.search', 'click');
        $('.search-attempts > span.search').trigger('click');

        // check that spinner is visible
        expect(this.proctored_exam_attempt_view.$el.find('#attempt-search-indicator').hasClass('hidden'))
            .toEqual(true);
        expect(this.proctored_exam_attempt_view.$el.find('#attempt-loading-indicator').hasClass('hidden'))
            .toEqual(false);

        // process the search attempt requests.
        this.server.respond();

        // check that spinner is hidden again
        expect(this.proctored_exam_attempt_view.$el.find('#attempt-search-indicator').hasClass('hidden'))
            .toEqual(false);
        expect(this.proctored_exam_attempt_view.$el.find('#attempt-loading-indicator').hasClass('hidden'))
            .toEqual(true);
    });
});
