var edx = edx || {};

(function (Backbone, $, _, gettext) {
    'use strict';

    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};
    var viewHelper = {
        getDateFormat: function(date) {
            if (date) {
                return new Date(date).toString('MMM dd, yyyy h:mmtt');
            }
            else {
                return '---';
            }

        }
    };
    edx.instructor_dashboard.proctoring.ProctoredExamAttemptView = Backbone.View.extend({
        initialize: function (options) {
            this.$el = options.el;
            this.collection = options.collection;
            this.tempate_url = options.template_url;
            this.model = options.model;
            this.course_id = this.$el.data('course-id');
            this.template = null;

            this.initial_url = this.collection.url;
            this.attempt_url = this.model.url;
            this.collection.url = this.initial_url + this.course_id;
            this.inSearchMode = false;
            this.searchText = "";

            /* re-render if the model changes */
            this.listenTo(this.collection, 'change', this.collectionChanged);

            /* Load the static template for rendering. */
            this.loadTemplateData();
        },
        events: {
            "click .remove-attempt": "onRemoveAttempt",
            'click li > a.target-link': 'getPaginatedAttempts',
            'click .search-attempts > span.search': 'searchAttempts',
            'click .search-attempts > span.clear-search': 'clearSearch'
        },
        searchAttempts: function(event) {
            var searchText = $('#search_attempt_id').val();
            if (searchText !== "") {
                this.inSearchMode = true;
                this.searchText = searchText;
                this.collection.url = this.initial_url + this.course_id + "/search/" + searchText;
                this.hydrate();
                event.stopPropagation();
                event.preventDefault();
            }
        },
        clearSearch: function(event) {
            this.inSearchMode = false;
            this.searchText = "";
            this.collection.url = this.initial_url + this.course_id;
            this.hydrate();
            event.stopPropagation();
            event.preventDefault();
        },
        getPaginatedAttempts: function(event) {
            var target = $(event.currentTarget);
            this.collection.url = target.data('target-url');
            this.hydrate();
            event.stopPropagation();
            event.preventDefault();
        },
        getCSRFToken: function () {
            var cookieValue = null;
            var name = 'csrftoken';
            if (document.cookie && document.cookie != '') {
                var cookies = document.cookie.split(';');
                for (var i = 0; i < cookies.length; i++) {
                    var cookie = jQuery.trim(cookies[i]);
                    // Does this cookie string begin with the name we want?
                    if (cookie.substring(0, name.length + 1) == (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        },
        loadTemplateData: function () {
            var self = this;
            $.ajax({url: self.tempate_url, dataType: "html"})
                .error(function (jqXHR, textStatus, errorThrown) {

                })
                .done(function (template_data) {
                    self.template = _.template(template_data);
                    self.hydrate();
                });
        },
        hydrate: function () {
            /* This function will load the bound collection */

            /* add and remove a class when we do the initial loading */
            /* we might - at some point - add a visual element to the */
            /* loading, like a spinner */
            var self = this;
            self.collection.fetch({
                success: function () {
                    self.render();
                }
            });
        },
        collectionChanged: function () {
            this.hydrate();
        },
        render: function () {
            if (this.template !== null) {
                var self = this;
                var data = {
                    proctored_exam_attempts: this.collection.toJSON()[0].proctored_exam_attempts,
                    pagination_info: this.collection.toJSON()[0].pagination_info,
                    attempt_url: this.collection.toJSON()[0].attempt_url,
                    inSearchMode: this.inSearchMode,
                    searchText: this.searchText
                };
                _.extend(data, viewHelper);
                var html = this.template(data);
                this.$el.html(html);
                this.$el.show();
            }
        },
        onRemoveAttempt: function (event) {
            event.preventDefault();

            // confirm the user's intent
            if (!confirm(gettext('Are you sure you wish to remove this student\'s exam attempt?'))) {
                return;
            }
            var $target = $(event.currentTarget);
            var attemptId = $target.data("attemptId");

            var self = this;
            self.model.url = this.attempt_url + attemptId;
            self.model.fetch( {
                headers: {
                    "X-CSRFToken": this.getCSRFToken()
                },
                type: 'DELETE',
                success: function () {
                    // fetch the attempts again.
                    self.hydrate();
                }
            });
        }
    });
    this.edx.instructor_dashboard.proctoring.ProctoredExamAttemptView = edx.instructor_dashboard.proctoring.ProctoredExamAttemptView;
}).call(this, Backbone, $, _, gettext);
