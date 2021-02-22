edx = edx || {};

(function(Backbone, $, _, gettext) {
    'use strict';

    var viewHelper, onboardingStatuses, onboardingStatusReadableFormat;
    edx.instructor_dashboard = edx.instructor_dashboard || {};
    edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};
    onboardingStatuses = [
        'not_started',
        'setup_started',
        'onboarding_started',
        'submitted',
        'verified',
        'rejected',
        'error'
    ];
    onboardingStatusReadableFormat = {
        not_started: gettext('Not Started'),
        setup_started: gettext('Setup Started'),
        onboarding_started: gettext('Onboarding Started'),
        started: gettext('Started'),
        submitted: gettext('Submitted'),
        verified: gettext('Verified'),
        rejected: gettext('Rejected'),
        error: gettext('Error')
    };
    viewHelper = {
        getDateFormat: function(date) {
            if (date) {
                return new Date(date).toString('MMM dd, yyyy h:mmtt');
            } else {
                return '---';
            }
        },
        getOnboardingStatus: function(status) {
            if (onboardingStatuses.includes(status)) {
                return onboardingStatusReadableFormat[status];
            } else {
                return status;
            }
        }
    };
    edx.instructor_dashboard.proctoring.ProctoredExamOnboardingView = Backbone.View.extend({
        initialize: function() {
            this.setElement($('.student-onboarding-status-container'));
            this.collection = new edx.instructor_dashboard.proctoring.ProctoredExamOnboardingCollection();
            this.templateUrl = '/static/proctoring/templates/student-onboarding-status.underscore';
            this.courseId = this.$el.data('course-id');
            this.template = null;

            this.initialUrl = this.collection.url;
            this.collection.url = this.initialUrl + this.courseId;
            this.inSearchMode = false;
            this.searchText = '';
            this.filters = [];
            this.currentPage = 1;

            /* re-render if the model changes */
            this.listenTo(this.collection, 'change', this.collectionChanged);

            /* Load the static template for rendering. */
            this.loadTemplateData();
        },
        events: {
            'click .search-onboarding > span.search': 'searchItems',
            'click .search-onboarding > span.clear-search': 'clearSearch',
            'submit .filter-form': 'filterItems',
            'click .clear-filters': 'clearFilters',
            'click li > a.target-link': 'getPaginatedItems'
        },
        searchItems: function(event) {
            var searchText = $('#search_onboarding_id').val();
            if (searchText !== '') {
                this.inSearchMode = true;
                this.searchText = searchText;
                this.currentPage = 1;
                this.collection.url = this.constructUrl();
                this.hydrate();
                event.stopPropagation();
                event.preventDefault();
            }
        },
        clearSearch: function(event) {
            this.inSearchMode = false;
            this.searchText = '';
            this.currentPage = 1;
            this.collection.url = this.constructUrl();
            this.hydrate();
            event.stopPropagation();
            event.preventDefault();
        },
        filterItems: function(event) {
            var $checkboxes = $('.status-checkboxes li input').get();
            var filters = [];
            $checkboxes.forEach(function(checkbox) {
                if (checkbox.checked) {
                    filters.push(checkbox.value);
                }
            });
            this.filters = filters;
            // return to the first page and rerender the view
            this.currentPage = 1;
            this.collection.url = this.constructUrl();
            this.hydrate();
            event.stopPropagation();
            event.preventDefault();
        },
        clearFilters: function(event) {
            this.filters = [];
            this.currentPage = 1;
            this.collection.url = this.constructUrl();
            this.hydrate();
            event.stopPropagation();
            event.preventDefault();
        },
        constructUrl: function(page) {
            var url;
            page = typeof page !== 'undefined' ? page : null; // eslint-disable-line no-param-reassign
            // if the page has changed, update the current page
            if (page) {
                this.currentPage = page;
            }
            url = this.initialUrl + this.courseId + '?page=' + this.currentPage;
            if (this.searchText) {
                url = url + '&text_search=' + this.searchText;
            }
            if (this.filters.length > 0) {
                url += '&statuses=';
                // creates a string of onboarding statuses separated by ','
                this.filters.forEach(function(filter, i) {
                    if (i > 0) {
                        url += ',';
                    }
                    url += filter;
                });
            }
            return url;
        },
        getPaginatedItems: function(event) {
            var $target = $(event.currentTarget);
            var page = Number($target.data('page-number'));
            this.collection.url = this.constructUrl(page);
            this.hydrate();
            event.stopPropagation();
            event.preventDefault();
        },
        loadTemplateData: function() {
            var self = this;
            $.ajax({url: self.templateUrl, dataType: 'html'})
                .done(function(templateData) {
                    self.template = _.template(templateData);
                    self.hydrate();
                });
        },
        hydrate: function() {
            /* This function will load the bound collection */

            /* add and remove a class when we do the initial loading */
            /* we might - at some point - add a visual element to the */
            /* loading, like a spinner */
            var self = this;
            self.collection.fetch({
                success: function() {
                    self.render();
                },
                error: function() {
                    // in the case that there is no onboarding data, we
                    // still want the view to render
                    self.render();
                }
            });
        },
        collectionChanged: function() {
            this.hydrate();
        },
        render: function() {
            var data, dataJson, html, startPage, endPage;
            if (this.template !== null) {
                data = {
                    previousPage: null,
                    nextPage: null,
                    currentPage: 1,
                    onboardingItems: [],
                    onboardingStatuses: onboardingStatuses,
                    inSearchMode: this.inSearchMode,
                    searchText: this.searchText,
                    filters: this.filters,
                    constructUrl: this.constructUrl,
                    startPage: 1,
                    endPage: 1
                };

                dataJson = this.collection.toJSON()[0];
                if (dataJson) {
                    // calculate which pages ranges to display
                    // show no more than 5 pages at the same time
                    if (this.currentPage > 3) {
                        startPage = this.currentPage - 2;
                    } else {
                        startPage = 1;
                    }

                    endPage = startPage + 4;

                    if (endPage > dataJson.num_pages) {
                        endPage = dataJson.num_pages;
                    }

                    data = {
                        previousPage: dataJson.previous,
                        nextPage: dataJson.next,
                        currentPage: this.currentPage,
                        onboardingItems: dataJson.results,
                        onboardingStatuses: onboardingStatuses,
                        inSearchMode: this.inSearchMode,
                        searchText: this.searchText,
                        filters: this.filters,
                        constructUrl: this.constructUrl,
                        startPage: startPage,
                        endPage: endPage
                    };
                }

                _.extend(data, viewHelper);
                html = this.template(data);
                this.$el.html(html);
            }
        }
    });
    this.edx.instructor_dashboard.proctoring.ProctoredExamOnboardingView =
      edx.instructor_dashboard.proctoring.ProctoredExamOnboardingView;
}).call(this, Backbone, $, _, gettext);
