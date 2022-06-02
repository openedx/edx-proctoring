edx = edx || {};

(function (Backbone, $, _, gettext) {
  'use strict';

  edx.instructor_dashboard = edx.instructor_dashboard || {};
  edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};
  const onboardingStatuses = [
    'not_started',
    'setup_started',
    'onboarding_started',
    'other_course_approved',
    'submitted',
    'verified',
    'rejected',
    'error',
  ];
  const onboardingProfileAPIStatuses = [
    'not_started',
    'other_course_approved',
    'submitted',
    'verified',
    'rejected',
    'expired',
  ];
  const statusAndModeReadableFormat = {
    // Onboarding statuses
    not_started: gettext('Not Started'),
    setup_started: gettext('Setup Started'),
    onboarding_started: gettext('Onboarding Started'),
    other_course_approved: gettext('Approved in Another Course'),
    started: gettext('Started'),
    submitted: gettext('Submitted'),
    verified: gettext('Verified'),
    rejected: gettext('Rejected'),
    error: gettext('Error'),
    expired: gettext('Expired'),
    // TODO: remove as part of MST-745
    onboarding_reset_past_due: gettext('Onboarding Reset Failed Due to Past Due Exam'),
    // Enrollment modes (Note: 'verified' is both a status and enrollment mode)
    audit: gettext('Audit'),
    honor: gettext('Honor'),
    professional: gettext('Professional'),
    'no-id-professional': gettext('No ID Professional'),
    credit: gettext('Credit'),
    masters: gettext('Master\'s'),
    'executive-education': gettext('Executive Education'),
  };
  const viewHelper = {
    getDateFormat(date) {
      if (date) {
        return new Date(date).toString('MMM dd, yyyy h:mmtt');
      }
      return '---';
    },
    getReadableString(str) {
      if (str in statusAndModeReadableFormat) {
        return statusAndModeReadableFormat[str];
      }
      return str;
    },
  };
  edx.instructor_dashboard.proctoring.ProctoredExamOnboardingView = Backbone.View.extend({
    initialize() {
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
      'click li > a.target-link': 'getPaginatedItems',
    },
    searchItems(event) {
      const searchText = $('#search_onboarding_id').val();
      if (searchText !== '') {
        this.inSearchMode = true;
        this.searchText = searchText;
        this.currentPage = 1;
        this.collection.url = this.constructUrl();
        const $searchIcon = $(document.getElementById('onboarding-search-indicator'));
        $searchIcon.addClass('hidden');
        const $spinner = $(document.getElementById('onboarding-loading-indicator'));
        $spinner.removeClass('hidden');
        this.hydrate();
        event.stopPropagation();
        event.preventDefault();
      }
    },
    clearSearch(event) {
      this.inSearchMode = false;
      this.searchText = '';
      this.currentPage = 1;
      this.collection.url = this.constructUrl();
      this.hydrate();
      event.stopPropagation();
      event.preventDefault();
    },
    filterItems(event) {
      const $checkboxes = $('.status-checkboxes li input').get();
      const filters = [];
      $checkboxes.forEach((checkbox) => {
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
    clearFilters(event) {
      this.filters = [];
      this.currentPage = 1;
      this.collection.url = this.constructUrl();
      this.hydrate();
      event.stopPropagation();
      event.preventDefault();
    },
    constructUrl(page) {
      let url;
      page = typeof page !== 'undefined' ? page : null; // eslint-disable-line no-param-reassign
      // if the page has changed, update the current page
      if (page) {
        this.currentPage = page;
      }
      url = `${this.initialUrl + this.courseId}?page=${this.currentPage}`;
      if (this.searchText) {
        url = `${url}&text_search=${this.searchText}`;
      }
      if (this.filters.length > 0) {
        url += '&statuses=';
        // creates a string of onboarding statuses separated by ','
        this.filters.forEach((filter, i) => {
          if (i > 0) {
            url += ',';
          }
          url += filter;
        });
      }
      return url;
    },
    getPaginatedItems(event) {
      const $target = $(event.currentTarget);
      const page = Number($target.data('page-number'));
      this.collection.url = this.constructUrl(page);
      this.hydrate();
      event.stopPropagation();
      event.preventDefault();
    },
    loadTemplateData() {
      const self = this;
      $.ajax({ url: self.templateUrl, dataType: 'html' })
        .done((templateData) => {
          self.template = _.template(templateData);
          self.hydrate();
        });
    },
    hydrate() {
      /* This function will load the bound collection */

      /* add and remove a class when we do the initial loading */
      /* we might - at some point - add a visual element to the */
      /* loading, like a spinner */
      const self = this;
      self.collection.fetch({
        success() {
          self.render();
          const $spinner = $(document.getElementById('onboarding-loading-indicator'));
          $spinner.addClass('hidden');
          const $searchIcon = $(document.getElementById('onboarding-search-indicator'));
          $searchIcon.removeClass('hidden');
        },
        error(unused, response) {
          let data; let $errorResponse; let $onboardingPanel;

          // in the case that there is no onboarding data, we
          // still want the view to render
          self.render();

          try {
            data = $.parseJSON(response.responseText);
          } catch (error) {
            data = {
              detail: 'An unexpected error occured. Please try again later.',
            };
          }

          if (data.detail) {
            $errorResponse = $('#error-response');
            $errorResponse.html(data.detail);
            $onboardingPanel = $('.onboarding-status-content');
            $onboardingPanel.hide();
          }

          const $spinner = $(document.getElementById('onboarding-loading-indicator'));
          $spinner.addClass('hidden');
          const $searchIcon = $(document.getElementById('onboarding-search-indicator'));
          $searchIcon.removeClass('hidden');
        },
      });
    },
    collectionChanged() {
      this.hydrate();
    },
    render() {
      let data; let dataJson; let html; let startPage; let endPage; let
        statuses;

      if (this.template !== null) {
        data = {
          previousPage: null,
          nextPage: null,
          currentPage: 1,
          onboardingItems: [],
          onboardingStatuses,
          inSearchMode: this.inSearchMode,
          searchText: this.searchText,
          filters: this.filters,
          constructUrl: this.constructUrl,
          startPage: 1,
          endPage: 1,
        };

        [dataJson] = this.collection.toJSON();
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

          statuses = dataJson.use_onboarding_profile_api ? onboardingProfileAPIStatuses : onboardingStatuses;
          data = {
            previousPage: dataJson.previous,
            nextPage: dataJson.next,
            currentPage: this.currentPage,
            onboardingItems: dataJson.results,
            onboardingStatuses: statuses,
            inSearchMode: this.inSearchMode,
            searchText: this.searchText,
            filters: this.filters,
            constructUrl: this.constructUrl,
            startPage,
            endPage,
          };
        }

        _.extend(data, viewHelper);
        html = this.template(data);
        this.$el.html(html);
      }
    },
  });
  const proctoredExamOnboardingView = edx.instructor_dashboard.proctoring.ProctoredExamOnboardingView;
  this.edx.instructor_dashboard.proctoring.ProctoredExamOnboardingView = proctoredExamOnboardingView;
}).call(this, Backbone, $, _, gettext);
