edx = edx || {};

(function (Backbone, $, _) {
  'use strict';

  edx.instructor_dashboard = edx.instructor_dashboard || {};
  edx.instructor_dashboard.proctoring = edx.instructor_dashboard.proctoring || {};

  edx.instructor_dashboard.proctoring.ProctoredExamAllowanceView = Backbone.View.extend({
    initialize() {
      this.allowance_types = [
        ['additional_time_granted', gettext('Additional Time (minutes)')],
        ['review_policy_exception', gettext('Review Policy Exception')],
        ['time_multiplier', gettext('Time Multiplier')],
      ];

      this.collection = new edx.instructor_dashboard.proctoring.ProctoredExamAllowanceCollection();
      this.proctoredExamCollection = new edx.instructor_dashboard.proctoring.ProctoredExamCollection();
      /* unfortunately we have to make some assumptions about what is being set up in HTML */
      this.setElement($('.special-allowance-container'));
      this.course_id = this.$el.data('course-id');
      /* this should be moved to a 'data' attribute in HTML */
      this.template_url = '/static/proctoring/templates/course_grouped_allowances.underscore';
      this.template = null;
      this.initial_url = this.collection.url;
      this.allowance_url = `${this.initial_url}allowance`;
      /* re-render if the model changes */
      this.listenTo(this.collection, 'change', this.collectionChanged);

      /* Load the static template for rendering. */
      this.loadTemplateData();

      this.proctoredExamCollection.url += this.course_id;
    },
    events: {
      'click #add-allowance': 'showAddModal',
      'click .remove_allowance': 'removeAllowance',
      'click .accordion-trigger': 'toggleAllowanceAccordion',
      'click .edit_allowance': 'editAllowance',
    },
    getCSRFToken() {
      let cookieValue = null;
      const name = 'csrftoken';
      let cookies; let cookie; let
        i;
      if (document.cookie && document.cookie !== '') {
        cookies = document.cookie.split(';');
        for (i = 0; i < cookies.length; i += 1) {
          cookie = jQuery.trim(cookies[i]);
          // Does this cookie string begin with the name we want?
          if (cookie.substring(0, name.length + 1) === (`${name}=`)) {
            cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
            break;
          }
        }
      }
      return cookieValue;
    },
    removeAllowance(event) {
      const $element = $(event.currentTarget);
      const userID = $element.data('user-id');
      const examID = $element.data('exam-id');
      const key = $element.data('key-name');
      const self = this;
      self.collection.url = this.allowance_url;
      self.collection.fetch(
        {
          headers: {
            'X-CSRFToken': this.getCSRFToken(),
          },
          type: 'DELETE',
          data: {
            exam_id: examID,
            user_id: userID,
            key,
          },
          success() {
            // fetch the allowances again.
            self.hydrate();
          },
        },
      );
      event.stopPropagation();
      event.preventDefault();
    },
    /*
         This entry point is required for Instructor Dashboard
         See setup_instructor_dashboard_sections() in
         instructor_dashboard.coffee (in edx-platform)
         */
    constructor(section) {
      /* the Instructor Dashboard javascript expects this to be set up */
      $(section).data('wrapper', this);

      this.initialize({});
    },
    onClickTitle() {
      // called when this is selected in the instructor dashboard

    },
    loadTemplateData() {
      const self = this;
      $.ajax({ url: self.template_url, dataType: 'html' })
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
      self.collection.url = `${self.initial_url + self.course_id}/grouped/allowance`;
      self.collection.fetch({
        success() {
          self.render();
        },
      });
    },
    collectionChanged() {
      this.hydrate();
    },
    render() {
      const self = this;
      let html;
      if (this.template !== null) {
        html = this.template({
          proctored_exam_allowances: this.collection.toJSON()[0],
          allowance_types: self.allowance_types,
          generateDomId: self.generateDomId,
        });
        this.$el.html(html);
      }
    },
    showAddModal(event) {
      const self = this;
      self.proctoredExamCollection.fetch({
        success() {
          // eslint-disable-next-line no-new
          new edx.instructor_dashboard.proctoring.AddBulkAllowanceView({
            course_id: self.course_id,
            proctored_exams: self.proctoredExamCollection.toJSON(),
            proctored_exam_allowance_view: self,
            allowance_types: self.allowance_types,
          });
        },
      });
      event.stopPropagation();
      event.preventDefault();
    },
    editAllowance(event) {
      const $element = $(event.currentTarget);
      const userName = $element.data('user-name');
      const examID = $element.data('exam-id');
      const examName = $element.data('exam-name');
      const key = $element.data('key-name');
      const keyName = $element.data('key-value');
      const self = this;
      self.proctoredExamCollection.fetch({
        success() {
          // eslint-disable-next-line no-new
          new edx.instructor_dashboard.proctoring.EditAllowanceView({
            course_id: self.course_id,
            selected_exam_ID: examID,
            selected_exam_name: examName,
            proctored_exam_allowance_view: self,
            selected_user: userName,
            allowance_type: key,
            allowance_type_name: keyName,
          });
        },
      });
    },
    toggleAllowanceAccordion(event) {
      // based on code from openedx/features/course_experience/static/course_experience/js/CourseOutline.js
      // but modified to better fit this feature's needs
      let accordionRow; let isExpanded; let $toggleChevron; let
        $contentPanel;
      accordionRow = event.currentTarget;
      if (accordionRow.classList.contains('accordion-trigger')) {
        isExpanded = accordionRow.getAttribute('aria-expanded') === 'true';
        if (!isExpanded) {
          $toggleChevron = $(accordionRow).find('.fa-chevron-down');
          $contentPanel = $(`#${accordionRow.getAttribute('data-key-id').trim()}`);
          $contentPanel.show();
          $toggleChevron.addClass('fa-rotate-180');
          accordionRow.setAttribute('aria-expanded', 'true');
        } else {
          $toggleChevron = $(accordionRow).find('.fa-chevron-down');
          $contentPanel = $(`#${accordionRow.getAttribute('data-key-id').trim()}`);
          $contentPanel.hide();
          $toggleChevron.removeClass('fa-rotate-180');
          accordionRow.setAttribute('aria-expanded', 'false');
        }
      }
    },
    generateDomId(username) {
      return `ui-id-${username.replace(/\W/g, '')}`;
    },
  });
  this.edx.instructor_dashboard.proctoring.ProctoredExamAllowanceView = edx.instructor_dashboard.proctoring.ProctoredExamAllowanceView;
}).call(this, Backbone, $, _);
