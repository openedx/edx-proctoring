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
            '<span id="time_remaining_id" class="pull-right"> <b> </b> </span> </div>' +
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

        this.proctored_exam_view = new edx.coursware.proctored_exam.ProctoredExamView(
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
    it("reload the page when the exam time finishes", function(){
        this.proctored_exam_view.secondsLeft = -10;
        var reloadPage = spyOn(this.proctored_exam_view, 'reloadPage');
        this.proctored_exam_view.updateRemainingTime(this.proctored_exam_view);
        expect(reloadPage).toHaveBeenCalled();
    });
    it("resets the remainig exam time after the ajax response", function(){
        this.server.respondWith("GET", "/api/edx_proctoring/v1/proctored_exam/attempt/" + this.proctored_exam_view.model.get('attempt_id'),
            [
                200,
                {"Content-Type": "application/json"},
                JSON.stringify({
                    time_remaining_seconds: -10
                })
            ]
        );
        this.proctored_exam_view.timerTick = 4; // to make the ajax call.
        var reloadPage = spyOn(this.proctored_exam_view, 'reloadPage');
        this.proctored_exam_view.updateRemainingTime(this.proctored_exam_view);
        this.server.respond();
        this.proctored_exam_view.updateRemainingTime(this.proctored_exam_view);
        expect(reloadPage).toHaveBeenCalled();
    });
});
