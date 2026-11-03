describe('ProctoredExamOnboardingView', function() {
    'use strict';

    var html = '';
    var expectedOnboardingDataJson = [{
        count: 4,
        previous: null,
        next: null,
        num_pages: 1,
        use_onboarding_profile_api: false,
        results: [
            {
                username: 'testuser1',
                enrollment_mode: 'verified',
                status: 'not_started',
                modified: null
            },
            {
                username: 'testuser2',
                enrollment_mode: 'verified',
                status: 'verified',
                modified: '2021-01-28T17:59:19.913336Z'
            },
            {
                username: 'testuser3',
                enrollment_mode: 'masters',
                status: 'submitted',
                modified: '2021-01-28T17:46:05.316349Z'
            },
            {
                username: 'testuser4',
                enrollment_mode: 'executive-education',
                status: 'other_course_approved',
                modified: '2021-01-27T17:46:05.316349Z'
            }
        ]
    }];

    var noDataJson = [{
        count: 0,
        previous: null,
        next: null,
        num_pages: 1,
        results: [],
        use_onboarding_profile_api: false
    }];

    beforeEach(function() {
        html = '<div class="wrapper-content wrapper">' +
        '<h3 class="error-response" id="error-response"></h3>' +
        '<% var isOnboardingItems = onboardingItems.length !== 0 %>' +
        '<div class="content onboarding-status-content">' +
        '<div class="top-header">' +
        '<div class="search-onboarding">' +
        '<input type="text" id="search_onboarding_id" placeholder="e.g johndoe or john.doe@gmail.com"' +
        '<% if (inSearchMode) { %>' +
        'value="<%= searchText %>"' +
        '<%} %>' +
        '/>' +
        '<span class="search">' +
        '<span class="icon fa fa-search" id="onboarding-search-indicator" aria-hidden="true"></span>' +
        '<div aria-live="polite" aria-relevant="all">' +
        '<div id="onboarding-loading-indicator" class="hidden">' +
        '<span class="icon fa fa-spinner fa-pulse" aria-hidden="true"></span>' +
        '<span class="sr"><%- gettext("Loading") %></span>' +
        '</div>' +
        '</div>' +
        '</span>' +
        '<span class="clear-search"><span class="icon fa fa-remove" aria-hidden="true"></span></span>' +
        '</div>' +
        '<ul class="pagination">' +
        '<% if (!previousPage){ %>' +
        '<li class="disabled">' +
        '<a aria-label="Previous">' +
        '<span aria-hidden="true">&laquo;</span>' +
        '</a>' +
        '</li>' +
        '<% } else { %>' +
        '<li>' +
        '<a class="target-link " data-page-number="<%= currentPage - 1 %>"' +
        'href="#" aria-label="Previous">' +
        '<span aria-hidden="true">&laquo;</span>' +
        '</a>' +
        '</li>' +
        '<% }%>' +
        '<% for(var n = startPage; n <= endPage; n++) { %>' +
        '<li>' +
        '<a class="target-link <% if (currentPage == n){ %> active <% } %>" data-page-number="<%= n %>" href="#">' +
        '<%= n %>' +
        '</a>' +
        '</li>' +
        '<% } %>' +
        '<% if (!nextPage){ %>' +
        '<li class="disabled">' +
        '<a aria-label="Next">' +
        '<span aria-hidden="true">&raquo;</span>' +
        '</a>' +
        '</li>' +
        '<% } else { %>' +
        '<li>' +
        '<a class="target-link" href="#" aria-label="Next" data-page-number="<%= currentPage + 1 %>"' +
        '>' +
        '<span aria-hidden="true">&raquo;</span>' +
        '</a>' +
        '</li>' +
        '<% }%>' +
        '</ul>' +
        '<div class="clearfix"></div>' +
        '</div>' +
        '<form class="filter-form">' +
        '<ul class="status-checkboxes">' +
        '<% _.each(onboardingStatuses, function(status){ %>' +
        '<li>' +
        '<input type="checkbox" id="<%= status %>" value="<%= status %>" ' +
        '<% if (filters.includes(status)) { %>checked="true"<% } %>>' +
        '<label for="<%= status %>">' +
        '<%- interpolate(gettext(" %(onboardingStatus)s "), ' +
        '{ onboardingStatus: getReadableString(status) }, true) %>' +
        '</label>' +
        '</li>' +
        '<% }); %>' +
        '</ul>' +
        '<button type="submit">Apply Filters</button>' +
        '<button type="button" class="clear-filters" aria-hidden="true">' +
        '<span class="icon fa fa-remove"></span>' +
        '</button>' +
        '</form>' +
        '<table class="onboarding-status-table">' +
        '<thead>' +
        '<tr class="onboarding-status-headings">' +
        '<th class="username-heading"><%- gettext("Username") %></th>' +
        '<th class="enrollment-mode-heading"><%- gettext("Enrollment Mode") %></th>' +
        '<th class="onboarding-status-heading"><%- gettext("Onboarding Status") %></th>' +
        '<th class="last-updated-heading"><%- gettext("Last Modified") %> </th>' +
        '</tr>' +
        '</thead>' +
        '<% if (isOnboardingItems) { %>' +
        '<tbody>' +
        '<% _.each(onboardingItems, function(item){ %>' +
        '<tr class="onboarding-items">' +
        '<td>' +
        '<%- interpolate(gettext(" %(username)s "), { username: item.username }, true) %>' +
        '</td>' +
        '<td>' +
        '<%- interpolate(gettext(" %(enrollmentMode)s "), ' +
        '{ enrollmentMode: getReadableString(item.enrollment_mode) }, true) %>' +
        '</td>' +
        '<td>' +
        '<%- interpolate(gettext(" %(onboardingStatus)s "), ' +
        '{ onboardingStatus: getReadableString(item.status) }, true) %>' +
        '</td>' +
        '<td><%= getDateFormat(item.modified) %></td>' +
        '</tr>' +
        '<% }); %>' +
        '</tbody>' +
        '<% } %>' +
        '</table>' +
        '<% if (!isOnboardingItems) { %>' +
        '<p class="no-onboarding-data">' +
        'There are no learners <% if (filters.length > 0 || searchText) { %>' +
        'who fit this criteria.' +
        '<%} else {%>' +
        'in this course who require onboarding exams.' +
        '<%} %>' +
        '</p>' +
        '<% } %>' +
        '</div>' +
        '</div>';
        this.server = sinon.fakeServer.create();
        this.server.autoRespond = true;
        setFixtures('<div class="student-onboarding-status-container" data-course-id="test_course_id"></div>');

        // load the underscore template response before calling the onboarding status view.
        this.server.respondWith('GET', '/static/proctoring/templates/student-onboarding-status.underscore',
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

    it('should render the proctored exam onboarding view properly', function() {
        this.server.respondWith('GET', '/api/edx_proctoring/v1/user_onboarding/status/course_id/test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(expectedOnboardingDataJson)
            ]
        );

        this.proctored_exam_onboarding_view = new edx.instructor_dashboard.proctoring.ProctoredExamOnboardingView();

        this.server.respond();
        this.server.respond();

        expect(this.proctored_exam_onboarding_view.$el.find('.onboarding-items').length)
            .toEqual(4);
        expect(this.proctored_exam_onboarding_view.$el.find('.onboarding-items').first().html())
            .toContain('testuser1');
        expect(this.proctored_exam_onboarding_view.$el.find('.onboarding-items').first().html())
            .toContain('Verified');
        expect(this.proctored_exam_onboarding_view.$el.find('.onboarding-items').first().html())
            .toContain('Not Started');
        expect(this.proctored_exam_onboarding_view.$el.find('.onboarding-items').first().html())
            .toContain('---');
        expect(this.proctored_exam_onboarding_view.$el.find('.onboarding-items').last().html())
            .toContain('testuser4');
        expect(this.proctored_exam_onboarding_view.$el.find('.onboarding-items').last().html())
            .toContain('Executive Education');
    });

    it('renders correctly with no data', function() {
        this.server.respondWith('GET', '/api/edx_proctoring/v1/user_onboarding/status/course_id/test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(noDataJson)
            ]
        );

        this.proctored_exam_onboarding_view = new edx.instructor_dashboard.proctoring.ProctoredExamOnboardingView();

        this.server.respond();
        this.server.respond();

        expect(this.proctored_exam_onboarding_view.$el.find('.no-onboarding-data').html())
            .toContain('There are no learners');
    });

    it('filters onboarding statuses', function() {
        this.server.respondWith('GET', '/api/edx_proctoring/v1/user_onboarding/status/course_id/test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(expectedOnboardingDataJson)
            ]
        );
        this.proctored_exam_onboarding_view = new edx.instructor_dashboard.proctoring.ProctoredExamOnboardingView();

        this.server.respond();
        this.server.respond();

        this.server.respondWith('GET',
            '/api/edx_proctoring/v1/user_onboarding/status/course_id/test_course_id?page=1&statuses=submitted,verified',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(expectedOnboardingDataJson)
            ]
        );

        spyOnEvent('.filter-form', 'submit');
        $('.status-checkboxes > li > input#submitted').click();
        $('.status-checkboxes > li > input#verified').click();
        $('.filter-form').submit();

        this.server.respond();

        expect(this.proctored_exam_onboarding_view.filters).toEqual(['submitted', 'verified']);
        expect(this.proctored_exam_onboarding_view.collection.url).toEqual(
            '/api/edx_proctoring/v1/user_onboarding/status/course_id/test_course_id?page=1&statuses=submitted,verified'
        );

        this.server.respondWith('GET', '/api/edx_proctoring/v1/user_onboarding/status/course_id/test_course_id?page=1',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(expectedOnboardingDataJson)
            ]
        );

        spyOnEvent('.clear-filters', 'click');
        $('.clear-filters').click();

        expect(this.proctored_exam_onboarding_view.filters).toEqual([]);
        expect(this.proctored_exam_onboarding_view.collection.url).toEqual(
            '/api/edx_proctoring/v1/user_onboarding/status/course_id/test_course_id?page=1'
        );
    });

    it('Renders approved in another course correctly', function() {
        this.server.respondWith('GET', '/api/edx_proctoring/v1/user_onboarding/status/course_id/test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(expectedOnboardingDataJson)
            ]
        );

        this.proctored_exam_onboarding_view = new edx.instructor_dashboard.proctoring.ProctoredExamOnboardingView();

        this.server.respond();
        this.server.respond();

        expect(this.proctored_exam_onboarding_view.$el.find('.onboarding-items').length)
            .toEqual(4);
        expect(this.proctored_exam_onboarding_view.$el.find('.onboarding-items').last().html())
            .toContain('testuser4');
        expect(this.proctored_exam_onboarding_view.$el.find('.onboarding-items').last().html())
            .toContain('Approved in Another Course');
    });

    it('should search for onboarding attempts', function() {
        var searchText = 'badSearch';
        this.server.respondWith('GET', '/api/edx_proctoring/v1/user_onboarding/status/course_id/test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(expectedOnboardingDataJson)
            ]
        );
        this.proctored_exam_onboarding_view = new edx.instructor_dashboard.proctoring.ProctoredExamOnboardingView();

        // Process all requests so far
        this.server.respond();
        this.server.respond();

        expect(this.proctored_exam_onboarding_view.$el.find('.onboarding-items').html())
            .toContain('testuser1');
        expect(this.proctored_exam_onboarding_view.$el.find('.onboarding-items').html())
            .toContain('Not Started');
        expect(this.proctored_exam_onboarding_view.$el.find('.onboarding-items').html())
            .toContain('---');
        expect(this.proctored_exam_onboarding_view.$el.find('#onboarding-search-indicator').hasClass('hidden'))
            .toEqual(false);
        expect(this.proctored_exam_onboarding_view.$el.find('#onboarding-loading-indicator').hasClass('hidden'))
            .toEqual(true);

        $('#search_onboarding_id').val(searchText);

        // search for the proctored exam attempt
        this.server.respondWith(
            'GET',
            '/api/edx_proctoring/v1/user_onboarding/status/course_id/test_course_id?page=1&text_search=' + searchText,
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(noDataJson)
            ]
        );


        // trigger the search attempt event.
        spyOnEvent('.search-onboarding > span.search', 'click');
        $('.search-onboarding > span.search').trigger('click');

        // check that spinner is visible
        expect(this.proctored_exam_onboarding_view.$el.find('#onboarding-search-indicator').hasClass('hidden'))
            .toEqual(true);
        expect(this.proctored_exam_onboarding_view.$el.find('#onboarding-loading-indicator').hasClass('hidden'))
            .toEqual(false);

        // process the search attempt requests.
        this.server.respond();

        // check that spinner is hidden again
        expect(this.proctored_exam_onboarding_view.$el.find('#onboarding-search-indicator').hasClass('hidden'))
            .toEqual(false);
        expect(this.proctored_exam_onboarding_view.$el.find('#onboarding-loading-indicator').hasClass('hidden'))
            .toEqual(true);
    });

    it('Renders correct filters for onboarding API', function() {
        var onboardingData;

        setFixtures(
            '<div class="student-onboarding-status-container"' +
            'data-course-id="test_course_id">' +
            '</div>'
        );

        onboardingData = JSON.parse(JSON.stringify(expectedOnboardingDataJson));
        onboardingData[0].use_onboarding_profile_api = true;

        this.server.respondWith('GET', '/api/edx_proctoring/v1/user_onboarding/status/course_id/test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(onboardingData)
            ]
        );

        this.proctored_exam_onboarding_view = new edx.instructor_dashboard.proctoring.ProctoredExamOnboardingView();

        this.server.respond();
        this.server.respond();

        expect(this.proctored_exam_onboarding_view.$el.find('.status-checkboxes').html())
            .toContain('Not Started');
        expect(this.proctored_exam_onboarding_view.$el.find('.status-checkboxes').html())
            .toContain('Submitted');
        expect(this.proctored_exam_onboarding_view.$el.find('.status-checkboxes').html())
            .toContain('Verified');
        expect(this.proctored_exam_onboarding_view.$el.find('.status-checkboxes').html())
            .toContain('Approved in Another Course');
        expect(this.proctored_exam_onboarding_view.$el.find('.status-checkboxes').html())
            .toContain('Rejected');
        expect(this.proctored_exam_onboarding_view.$el.find('.status-checkboxes').html())
            .not.toContain('Setup Started');
    });

    it('renders correctly with 503 response', function() {
        var errorMessage;

        this.server.respondWith('GET', '/api/edx_proctoring/v1/user_onboarding/status/course_id/test_course_id',
            [
                503,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify({detail: 'Error message.'})
            ]
        );

        this.proctored_exam_onboarding_view = new edx.instructor_dashboard.proctoring.ProctoredExamOnboardingView();

        this.server.respond();
        this.server.respond();

        errorMessage = this.proctored_exam_onboarding_view.$el.find('.error-response');
        expect(errorMessage.html()).toContain('Error message.');
        expect(errorMessage).toBeVisible();
        expect(this.proctored_exam_onboarding_view.$el.find('.onboarding-status-content')).not.toBeVisible();
    });

    it('renders correctly with non-JSON parseable error message response', function() {
        var errorMessage;

        this.server.respondWith('GET', '/api/edx_proctoring/v1/user_onboarding/status/course_id/test_course_id',
            [
                500,
                {
                    'Content-Type': 'application/json'
                },
                ''
            ]
        );

        this.proctored_exam_onboarding_view = new edx.instructor_dashboard.proctoring.ProctoredExamOnboardingView();

        this.server.respond();
        this.server.respond();

        errorMessage = this.proctored_exam_onboarding_view.$el.find('.error-response');
        expect(errorMessage.html()).toContain('An unexpected error occured. Please try again later.');
        expect(errorMessage).toBeVisible();
        expect(this.proctored_exam_onboarding_view.$el.find('.onboarding-status-content')).not.toBeVisible();
    });
});
