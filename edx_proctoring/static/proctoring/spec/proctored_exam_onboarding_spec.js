describe('ProctoredExamOnboardingView', function() {
    'use strict';

    var html = '';
    var expectedOnboardingDataJson = [{
        count: 4,
        previous: null,
        next: null,
        num_pages: 1,
        results: [
            {
                username: 'testuser1',
                status: 'not_started',
                modified: null
            },
            {
                username: 'testuser2',
                status: 'verified',
                modified: '2021-01-28T17:59:19.913336Z'
            },
            {
                username: 'testuser3',
                status: 'submitted',
                modified: '2021-01-28T17:46:05.316349Z'
            },
            {
                username: 'testuser4',
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
        results: []
    }];

    beforeEach(function() {
        html = '<div class="wrapper-content wrapper">' +
        '<% var isOnboardingItems = onboardingItems.length !== 0 %>' +
        '<div class="content onboarding-status-content">' +
        '<div class="top-header">' +
        '<div class="search-onboarding">' +
        '<input type="text" id="search_onboarding_id" placeholder="e.g johndoe or john.doe@gmail.com"' +
        '<% if (inSearchMode) { %>' +
        'value="<%= searchText %>"' +
        '<%} %>' +
        '/>' +
        '<span class="search"><span class="icon fa fa-search" aria-hidden="true"></span></span>' +
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
        '{ onboardingStatus: getOnboardingStatus(status) }, true) %>' +
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
        '<%- interpolate(gettext(" %(onboardingStatus)s "), ' +
        '{ onboardingStatus: getOnboardingStatus(item.status) }, true) %>' +
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
        expect(this.proctored_exam_onboarding_view.$el.find('.onboarding-items').html())
            .toContain('testuser1');
        expect(this.proctored_exam_onboarding_view.$el.find('.onboarding-items').html())
            .toContain('Not Started');
        expect(this.proctored_exam_onboarding_view.$el.find('.onboarding-items').html())
            .toContain('---');
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

        spyOnEvent('.filter-form', 'submit');
        $('.status-checkboxes > li > input#submitted').click();
        $('.status-checkboxes > li > input#verified').click();
        $('.filter-form').submit();

        expect(this.proctored_exam_onboarding_view.filters).toEqual(['submitted', 'verified']);
        expect(this.proctored_exam_onboarding_view.collection.url).toEqual(
            '/api/edx_proctoring/v1/user_onboarding/status/course_id/test_course_id?page=1&statuses=submitted,verified'
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
});
