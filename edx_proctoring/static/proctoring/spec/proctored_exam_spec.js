describe('ProctoredExamView', function () {
    beforeEach(function () {
        this.server = sinon.fakeServer.create();
        jasmine.clock().install();
        setFixtures(
            '<div class="proctored_exam_status">' +
            '<script type="text/template" id="proctored-exam-status-tpl">' +
            '<div class="exam-timer">' +
            'You are taking "' +
            '<a href="<%= exam_url_path %>"> <%= exam_display_name %> </a>' +
            '" as a proctored exam. The timer on the right shows the time remaining in the exam' +
            '<span class="exam-timer-clock"> <span id="time_remaining_id">' +
            '<b> </b> <button role="button" id="toggle_timer" aria-label="Hide Timer" aria-pressed="false">' +
            '<i class="fa fa-eye-slash" aria-hidden="true"></i></button>' +
            '</span> </span>' +
            '</div>' +
            '</script>'+
            '</div>'
        );
        this.model = new ProctoredExamModel({
            in_timed_exam: true,
            is_proctored: true,
            exam_display_name: 'Midterm',
            taking_as_proctored: true,
            exam_url_path: '/test_url',
            time_remaining_seconds: 45, //2 * 60 + 15,
            low_threshold_sec: 30,
            attempt_id: 2,
            critically_low_threshold_sec: 15,
            lastFetched: new Date()
        });

        this.proctored_exam_view = new edx.courseware.proctored_exam.ProctoredExamView(
            {
                model: this.model,
                el: $(".proctored_exam_status"),
                proctored_template: '#proctored-exam-status-tpl'
            }
        );
        this.proctored_exam_view.render();
    });

    afterEach(function() {
        this.server.restore();
        jasmine.clock().uninstall();
    });

    it('renders items correctly', function () {
        expect(this.proctored_exam_view.$el.find('a')).toHaveAttr('href',  this.model.get("exam_url_path"));
        expect(this.proctored_exam_view.$el.find('a')).toContainHtml(this.model.get('exam_display_name'));
    });
    it('changes behavior when clock time decreases low threshold', function () {
        this.proctored_exam_view.secondsLeft = 25;
        this.proctored_exam_view.render();
        expect(this.proctored_exam_view.$el.find('div.exam-timer')).toHaveClass('low-time warning');
    });
    it('changes behavior when clock time decreases critically low threshold', function () {
        this.proctored_exam_view.secondsLeft = 5;
        this.proctored_exam_view.render();
        expect(this.proctored_exam_view.$el.find('div.exam-timer')).toHaveClass('low-time critical');
    });
    it('toggles timer visibility correctly', function() {
        var button = this.proctored_exam_view.$el.find('#toggle_timer');
        var timer = this.proctored_exam_view.$el.find('span#time_remaining_id b');
        expect(timer).not.toHaveClass('timer-hidden');
        button.click();
        expect(timer).toHaveClass('timer-hidden');
        button.click();
        expect(timer).not.toHaveClass('timer-hidden');
    });
    it("reload the page when the exam time finishes", function(){
        this.proctored_exam_view.secondsLeft = -10;
        var reloadPage = spyOn(this.proctored_exam_view, 'reloadPage');
        this.proctored_exam_view.updateRemainingTime(this.proctored_exam_view);
        expect(reloadPage).toHaveBeenCalled();
    });
    it("resets the remaining exam time after the ajax response", function(){
        this.server.respondWith(
            "GET",
            "/api/edx_proctoring/v1/proctored_exam/attempt/" +
            this.proctored_exam_view.model.get('attempt_id') +
            '?sourceid=in_exam&proctored=true',
            [
                200,
                {"Content-Type": "application/json"},
                JSON.stringify({
                    time_remaining_seconds: -10
                })
            ]
        );
        this.proctored_exam_view.timerTick = this.proctored_exam_view.poll_interval-1; // to make the ajax call.
        var reloadPage = spyOn(this.proctored_exam_view, 'reloadPage');
        this.proctored_exam_view.updateRemainingTime(this.proctored_exam_view);
        this.server.respond();
        this.proctored_exam_view.updateRemainingTime(this.proctored_exam_view);
        expect(reloadPage).toHaveBeenCalled();
    });
    it("calls external js global function on off-beat", function() {
      this.proctored_exam_view.model.set('ping_interval', 60);
        edx.courseware.proctored_exam.pingApplication = jasmine.createSpy().and.returnValue(Promise.resolve());
        edx.courseware.proctored_exam.configuredWorkerURL = 'nonempty/string.html';
        this.proctored_exam_view.timerTick = this.proctored_exam_view.model.get('ping_interval') / 2 - 1;
        this.proctored_exam_view.updateRemainingTime(this.proctored_exam_view);
        expect(edx.courseware.proctored_exam.pingApplication).toHaveBeenCalled();
        delete edx.courseware.proctored_exam.pingApplication;
        delete edx.courseware.proctored_exam.configuredWorkerURL;
    });
    it("reloads the page after failure-state ajax call", function(done) {
        this.server.respondWith(
            function(request) {
                request.respond(200,
                                {"Content-Type": "application/json"},
                                '{"exam_attempt_id": "abcde"}'
                );
            }
        );
        var reloadPage = spyOn(this.proctored_exam_view, 'reloadPage');
        this.proctored_exam_view.endExamForFailureState().done(function() {
            expect(reloadPage).toHaveBeenCalled();
            done();
        });
        this.server.respond();
    });
    it("does not reload the page after failure-state ajax call when server responds with no attempt id", function(done) {
        // this case mimics current behavior of the server when the
        // proctoring backend is configured to not block the user for a
        // failed ping.
        this.server.respondWith(
            function(request) {
                request.respond(200,
                                {"Content-Type": "application/json"},
                                '{"exam_attempt_id": false}'
                );
            }
        );
        var reloadPage = spyOn(this.proctored_exam_view, 'reloadPage');
        this.proctored_exam_view.endExamForFailureState().done(function() {
            expect(reloadPage).not.toHaveBeenCalled();
            done();
        });
        this.server.respond();
    });

    it("sets global variable when unset", function() {
        expect(window.edx.courseware.proctored_exam.configuredWorkerURL).toBeUndefined();
        this.proctored_exam_view.model.set("desktop_application_js_url", "nonempty string");
        expect(window.edx.courseware.proctored_exam.configuredWorkerURL).not.toBeUndefined();
        this.proctored_exam_view.model.set("desktop_application_js_url", "another nonempty string");
        expect(window.edx.courseware.proctored_exam.configuredWorkerURL).toEqual("nonempty string");
        delete window.edx.courseware.proctored_exam.configuredWorkerURL;
    });
});
