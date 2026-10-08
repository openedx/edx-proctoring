/* global LearnerOnboardingModel:false */
describe('ProctoredExamInfo', function() {
    'use strict';

    var html = '';

    var errorGettingOnboardingProfile = {
        detail: 'There is no onboarding exam related to this course id.'
    };

    function expectedProctoredExamInfoJson(status, examReleaseDate) {
        var releaseDate = examReleaseDate;
        if (!examReleaseDate) { // default to released a week ago
            releaseDate = new Date();
            releaseDate.setDate(new Date().getDate() - 7);
        }
        return (
            {
                onboarding_status: status,
                onboarding_link: 'onboarding_link',
                onboarding_release_date: releaseDate,
                expiration_date: null,
                onboarding_past_due: false
            }
        );
    }

    function expectedOtherCourseApprovedJson(expirationDate) {
        return (
            {
                onboarding_status: 'other_course_approved',
                onboarding_link: 'onboarding_link',
                expiration_date: expirationDate
            }
        );
    }

    beforeEach(function() {
        html = '<div class="proctoring-info">' +
            '<h3 class="message-title"> <%= gettext("This course contains proctored exams") %></h3>' +
            '<% if (onboardingStatusText) { %>' +
            '<div class="onboarding-status">' +
            '<span class="onboarding-status"><%= gettext("Current Onboarding Status:") %> ' +
            '<%= onboardingStatusText %></span>' +
            '</div>' +
            '<div class="onboarding-status-message">' +
            '<span class="onboarding-status-message"><%= onboardingMessage %></span>' +
            '</div>' +
            '<% if (onboardingDetail) { %>' +
            '<div class="onboarding-status-detail">' +
            '<span class="onboarding-status-detail"><%= onboardingDetail %></span>' +
            '</div>' +
            '<%} %>' +
            '<%} %>' +
            '<div class="onboarding-reminder">' +
            '<% if (showOnboardingReminder) { %>' +
            '<h4 class="message-title">' +
            '<% if (showOnboardingExamLink) { %>' +
            '<%= gettext("You must complete the onboarding process prior to taking any proctored exam.") %>' +
            '<% } else { %>' +
            '<%= gettext("Your submitted profile is in review.") %>' +
            '<% } %>' +
            '</h4>' +
            '<p class="message-copy">' +
            '<%= gettext("Onboarding profile review, including identity verification, can take 2+ business days.") %>' +
            '</p>' +
            '<%} %>' +
            '</div>' +
            '<% if (showOnboardingExamLink) { %>' +
            '<% if (onboardingPastDue) { %>' +
            '<a class="action action-onboarding action-disabled"><%= gettext("Onboarding Past Due") %></a>' +
            '<% } else if (onboardingNotReleased) { %>' +
            '<a class="action action-onboarding action-disabled">' +
            '<%= gettext("Onboarding Opens") %> <%= onboardingReleaseDate %></a>' +
            '<%} else { %>' +
            '<a href="<%= onboardingLink %>" class="action action-onboarding">' +
            '<%= gettext("Complete Onboarding") %></a>' +
            '<%} %>' +
            '<%} %>' +
            '<a href="https://support.edx.org/hc/en-us/articles/207249428-How-do-proctored-exams-work" ' +
            'class="action action-info-link">' +
            '<%= gettext("Review instructions and system requirements for proctored exams") %></a>' +
            '</div>';
        this.server = sinon.fakeServer.create();
        this.server.autoRespond = true;
        setFixtures('<div class="proctoring-info-panel" data-course-id="test_course_id"></div>');

        // load the underscore template response before calling the proctored exam allowance view.
        this.server.respondWith('GET', '/static/proctoring/templates/proctored-exam-info.underscore',
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

    it('should not render proctoring info panel when template is not defined', function() {
        this.proctored_exam_info = new edx.courseware.proctored_exam.ProctoredExamInfo({
            el: $('.proctoring-info-panel'),
            model: new LearnerOnboardingModel()
        });
        this.proctored_exam_info.render();
        expect(this.proctored_exam_info.$el.find('.proctoring-info-panel').html())
            .toHaveLength(0);
    });

    it('should not render proctoring info panel if no course id is provided', function() {
        setFixtures('<div class="proctoring-info-panel" data-course-id=""></div>');
        this.server.respondWith('GET', '/api/edx_proctoring/v1/user_onboarding/status?course_id=',
            [
                400,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(errorGettingOnboardingProfile)
            ]
        );

        this.proctored_exam_info = new edx.courseware.proctored_exam.ProctoredExamInfo({
            el: $('.proctoring-info-panel'),
            model: new LearnerOnboardingModel()
        });
        this.server.respond();
        this.server.respond();
        expect(this.proctored_exam_info.$el.find('.proctoring-info-panel').html())
            .toHaveLength(0);
    });

    it('should render if username is provided', function() {
        setFixtures(
            '<div class="proctoring-info-panel" data-course-id="test_course_id" ' +
            'data-username="test_username"></div>'
        );
        this.server.respondWith(
            'GET',
            '/api/edx_proctoring/v1/user_onboarding/status?course_id=test_course_id&username=test_username',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(expectedProctoredExamInfoJson('verified'))
            ]
        );

        this.proctored_exam_info = new edx.courseware.proctored_exam.ProctoredExamInfo({
            el: $('.proctoring-info-panel'),
            model: new LearnerOnboardingModel()
        });
        this.server.respond();
        this.server.respond();
        expect(this.proctored_exam_info.$el.find('.onboarding-status').html())
            .toContain('Verified');
    });

    it('should not render proctoring info panel for exam with 404 response', function() {
        this.server.respondWith('GET', '/api/edx_proctoring/v1/user_onboarding/status?course_id=test_course_id',
            [
                404,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(errorGettingOnboardingProfile)
            ]
        );

        this.proctored_exam_info = new edx.courseware.proctored_exam.ProctoredExamInfo({
            el: $('.proctoring-info-panel'),
            model: new LearnerOnboardingModel()
        });
        this.server.respond();
        this.server.respond();
        expect(this.proctored_exam_info.$el.find('.proctoring-info-panel').html())
            .toHaveLength(0);
    });

    it('should render proctoring info panel correctly for exam with other status', function() {
        this.server.respondWith('GET', '/api/edx_proctoring/v1/user_onboarding/status?course_id=test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(expectedProctoredExamInfoJson('other'))
            ]
        );

        this.proctored_exam_info = new edx.courseware.proctored_exam.ProctoredExamInfo({
            el: $('.proctoring-info-panel'),
            model: new LearnerOnboardingModel()
        });
        this.server.respond();
        this.server.respond();
        expect(this.proctored_exam_info.$el.find('.proctoring-info').css('border-top'))
            .toEqual('5px solid rgb(178, 6, 16)');
        expect(this.proctored_exam_info.$el.find('.onboarding-status').html())
            .toContain('other');
        expect(this.proctored_exam_info.$el.find('.onboarding-status-message').text())
            .toHaveLength(0);
        expect(this.proctored_exam_info.$el.find('.onboarding-reminder').html())
            .toContain('You must complete the onboarding process');
        expect(this.proctored_exam_info.$el.find('.action-onboarding').html())
            .toContain('Complete Onboarding');
    });

    it('should render proctoring info panel correctly for exam with empty string status', function() {
        this.server.respondWith('GET', '/api/edx_proctoring/v1/user_onboarding/status?course_id=test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(expectedProctoredExamInfoJson(''))
            ]
        );

        this.proctored_exam_info = new edx.courseware.proctored_exam.ProctoredExamInfo({
            el: $('.proctoring-info-panel'),
            model: new LearnerOnboardingModel()
        });
        this.server.respond();
        this.server.respond();
        expect(this.proctored_exam_info.$el.find('.proctoring-info').css('border-top'))
            .toEqual('5px solid rgb(178, 6, 16)');
        expect(this.proctored_exam_info.$el.find('.onboarding-status').html())
            .toContain('Not Started');
        expect(this.proctored_exam_info.$el.find('.onboarding-status-message').text())
            .toHaveLength(0);
        expect(this.proctored_exam_info.$el.find('.onboarding-reminder').html())
            .toContain('You must complete the onboarding process');
        expect(this.proctored_exam_info.$el.find('.action-onboarding').html())
            .toContain('Complete Onboarding');
    });

    it('should render proctoring info panel correctly for exam that has yet to be released', function() {
        var tomorrow = new Date();
        tomorrow.setDate(new Date().getDate() + 1);
        this.server.respondWith('GET', '/api/edx_proctoring/v1/user_onboarding/status?course_id=test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(expectedProctoredExamInfoJson('', tomorrow))
            ]
        );

        this.proctored_exam_info = new edx.courseware.proctored_exam.ProctoredExamInfo({
            el: $('.proctoring-info-panel'),
            model: new LearnerOnboardingModel()
        });
        this.server.respond();
        this.server.respond();
        expect(this.proctored_exam_info.$el.find('.proctoring-info').css('border-top'))
            .toEqual('5px solid rgb(178, 6, 16)');
        expect(this.proctored_exam_info.$el.find('.onboarding-status').html())
            .toContain('Not Started');
        expect(this.proctored_exam_info.$el.find('.onboarding-status-message').text())
            .toHaveLength(0);
        expect(this.proctored_exam_info.$el.find('.onboarding-reminder').html())
            .toContain('You must complete the onboarding process');
        expect(this.proctored_exam_info.$el.find('.action-onboarding').html())
            .toContain('Onboarding Opens ' + tomorrow.toLocaleDateString());
    });

    it('should render proctoring info panel correctly for past due exam', function() {
        var twoDaysAgo = new Date();
        var data = {
            onboarding_status: status,
            onboarding_link: null,
            onboarding_release_date: twoDaysAgo,
            expiration_date: null,
            onboarding_past_due: true
        };
        this.server.respondWith('GET', '/api/edx_proctoring/v1/user_onboarding/status?course_id=test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(data)
            ]
        );

        this.proctored_exam_info = new edx.courseware.proctored_exam.ProctoredExamInfo({
            el: $('.proctoring-info-panel'),
            model: new LearnerOnboardingModel()
        });
        this.server.respond();
        this.server.respond();
        expect(this.proctored_exam_info.$el.find('.proctoring-info').css('border-top'))
            .toEqual('5px solid rgb(178, 6, 16)');
        expect(this.proctored_exam_info.$el.find('.onboarding-status').html())
            .toContain('Not Started');
        expect(this.proctored_exam_info.$el.find('.onboarding-status-message').text())
            .toHaveLength(0);
        expect(this.proctored_exam_info.$el.find('.onboarding-reminder').html())
            .toContain('You must complete the onboarding process');
        expect(this.proctored_exam_info.$el.find('.action-onboarding').html())
            .toContain('Onboarding Past Due');
    });

    it('should render proctoring info panel correctly for created exam', function() {
        this.server.respondWith('GET', '/api/edx_proctoring/v1/user_onboarding/status?course_id=test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(expectedProctoredExamInfoJson('created'))
            ]
        );

        this.proctored_exam_info = new edx.courseware.proctored_exam.ProctoredExamInfo({
            el: $('.proctoring-info-panel'),
            model: new LearnerOnboardingModel()
        });
        this.server.respond();
        this.server.respond();
        expect(this.proctored_exam_info.$el.find('.proctoring-info').css('border-top'))
            .toEqual('5px solid rgb(178, 6, 16)');
        expect(this.proctored_exam_info.$el.find('.onboarding-status').html())
            .toContain('Not Started');
        expect(this.proctored_exam_info.$el.find('.onboarding-reminder').html())
            .toContain('You must complete the onboarding process');
        expect(this.proctored_exam_info.$el.find('.action-onboarding').html())
            .toContain('Complete Onboarding');
    });

    it('should render proctoring info panel correctly for started exam', function() {
        this.server.respondWith('GET', '/api/edx_proctoring/v1/user_onboarding/status?course_id=test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(expectedProctoredExamInfoJson('started'))
            ]
        );

        this.proctored_exam_info = new edx.courseware.proctored_exam.ProctoredExamInfo({
            el: $('.proctoring-info-panel'),
            model: new LearnerOnboardingModel()
        });
        this.server.respond();
        this.server.respond();
        expect(this.proctored_exam_info.$el.find('.proctoring-info').css('border-top'))
            .toEqual('5px solid rgb(178, 6, 16)');
        expect(this.proctored_exam_info.$el.find('.onboarding-status').html())
            .toContain('Started');
        expect(this.proctored_exam_info.$el.find('.onboarding-reminder').html())
            .toContain('You must complete the onboarding process');
        expect(this.proctored_exam_info.$el.find('.action-onboarding').html())
            .toContain('Complete Onboarding');
    });

    it('should render proctoring info panel correctly for submitted onboarding exam', function() {
        this.server.respondWith('GET', '/api/edx_proctoring/v1/user_onboarding/status?course_id=test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(expectedProctoredExamInfoJson('submitted'))
            ]
        );
        this.proctored_exam_info = new edx.courseware.proctored_exam.ProctoredExamInfo({
            el: $('.proctoring-info-panel'),
            model: new LearnerOnboardingModel()
        });
        this.server.respond();
        this.server.respond();
        expect(this.proctored_exam_info.$el.find('.proctoring-info').css('border-top'))
            .toEqual('5px solid rgb(13, 78, 108)');
        expect(this.proctored_exam_info.$el.find('.onboarding-status').html())
            .toContain('Submitted');
        expect(this.proctored_exam_info.$el.find('.onboarding-reminder').html())
            .toContain('Your submitted profile is in review.');
        expect(this.proctored_exam_info.$el.find('.action-onboarding').html())
            .not.toContain('Complete Onboarding');
    });

    it('should render proctoring info panel correctly for second_review_required exam', function() {
        this.server.respondWith('GET', '/api/edx_proctoring/v1/user_onboarding/status?course_id=test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(expectedProctoredExamInfoJson('second_review_required'))
            ]
        );
        this.proctored_exam_info = new edx.courseware.proctored_exam.ProctoredExamInfo({
            el: $('.proctoring-info-panel'),
            model: new LearnerOnboardingModel()
        });
        this.server.respond();
        this.server.respond();
        expect(this.proctored_exam_info.$el.find('.proctoring-info').css('border-top'))
            .toEqual('5px solid rgb(13, 78, 108)');
        expect(this.proctored_exam_info.$el.find('.onboarding-status').html())
            .toContain('Submitted');
        expect(this.proctored_exam_info.$el.find('.onboarding-reminder').html())
            .toContain('Your submitted profile is in review.');
        expect(this.proctored_exam_info.$el.find('.action-onboarding').html())
            .not.toContain('Complete Onboarding');
    });

    it('should render proctoring info panel correctly for verified exam', function() {
        this.server.respondWith('GET', '/api/edx_proctoring/v1/user_onboarding/status?course_id=test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(expectedProctoredExamInfoJson('verified'))
            ]
        );
        this.proctored_exam_info = new edx.courseware.proctored_exam.ProctoredExamInfo({
            el: $('.proctoring-info-panel'),
            model: new LearnerOnboardingModel()
        });
        this.server.respond();
        this.server.respond();
        expect(this.proctored_exam_info.$el.find('.proctoring-info').css('border-top'))
            .toEqual('5px solid rgb(0, 129, 0)');
        expect(this.proctored_exam_info.$el.find('.onboarding-status').html())
            .toContain('Verified');
        expect(this.proctored_exam_info.$el.find('.onboarding-reminder').html())
            .not.toContain('You must complete the onboarding process');
        expect(this.proctored_exam_info.$el.find('.action-onboarding').html())
            .not.toContain('Complete Onboarding');
    });

    it('should render proctoring info panel correctly for rejected exam', function() {
        this.server.respondWith('GET', '/api/edx_proctoring/v1/user_onboarding/status?course_id=test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(expectedProctoredExamInfoJson('rejected'))
            ]
        );
        this.proctored_exam_info = new edx.courseware.proctored_exam.ProctoredExamInfo({
            el: $('.proctoring-info-panel'),
            model: new LearnerOnboardingModel()
        });
        this.server.respond();
        this.server.respond();
        expect(this.proctored_exam_info.$el.find('.proctoring-info').css('border-top'))
            .toEqual('5px solid rgb(178, 6, 16)');
        expect(this.proctored_exam_info.$el.find('.onboarding-status').html())
            .toContain('Rejected');
        expect(this.proctored_exam_info.$el.find('.onboarding-reminder').html())
            .toContain('You must complete the onboarding process');
        expect(this.proctored_exam_info.$el.find('.action-onboarding').html())
            .toContain('Complete Onboarding');
    });

    it('should render proctoring info panel correctly for other course approved', function() {
        var expirationDate = new Date();
        // Set the expiration date 50 days in the future
        expirationDate.setTime(expirationDate.getTime() + 3456900000);
        this.server.respondWith('GET', '/api/edx_proctoring/v1/user_onboarding/status?course_id=test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(expectedOtherCourseApprovedJson(expirationDate.toString()))
            ]
        );
        this.proctored_exam_info = new edx.courseware.proctored_exam.ProctoredExamInfo({
            el: $('.proctoring-info-panel'),
            model: new LearnerOnboardingModel()
        });
        this.server.respond();
        this.server.respond();
        expect(this.proctored_exam_info.$el.find('.onboarding-status').html())
            .toContain('Approved in Another Course');
        expect(this.proctored_exam_info.$el.find('.onboarding-status-message').html())
            .toContain('Your onboarding exam has been approved in another course');
        expect(this.proctored_exam_info.$el.find('.onboarding-status-detail').html())
            .toContain('we recommend that you complete');
        expect(this.proctored_exam_info.$el.find('.action-onboarding').html())
            .toContain('Complete Onboarding');
    });

    it('should render proctoring info panel when expiring soon', function() {
        var expirationDate = new Date();
        // This message will render if the expiration date is within 28 days
        // Set the expiration date 10 days in future
        expirationDate.setTime(expirationDate.getTime() + 864800000);
        this.server.respondWith('GET', '/api/edx_proctoring/v1/user_onboarding/status?course_id=test_course_id',
            [
                200,
                {
                    'Content-Type': 'application/json'
                },
                JSON.stringify(expectedOtherCourseApprovedJson(expirationDate.toString()))
            ]
        );
        this.proctored_exam_info = new edx.courseware.proctored_exam.ProctoredExamInfo({
            el: $('.proctoring-info-panel'),
            model: new LearnerOnboardingModel()
        });
        this.server.respond();
        this.server.respond();
        expect(this.proctored_exam_info.$el.find('.onboarding-status').html())
            .toContain('Expiring Soon');
        expect(this.proctored_exam_info.$el.find('.onboarding-status-message').html())
            .toContain('However, your onboarding status is expiring soon.');
        expect(this.proctored_exam_info.$el.find('.action-onboarding').html())
            .toContain('Complete Onboarding');
    });
});
