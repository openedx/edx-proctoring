Change Log
----------

..
   All enhancements and patches to edx-proctoring will be documented
   in this file.  It adheres to the structure of https://keepachangelog.com/ ,
   but in reStructuredText instead of Markdown (for ease of incorporation into
   Sphinx documentation and the PyPI description).

   This project adheres to Semantic Versioning (https://semver.org/).

.. There should always be an "Unreleased" section for changes pending release.

Unreleased
~~~~~~~~~~

[4.8.2] - 2021-12-21
~~~~~~~~~~~~~~~~~~~~
* Fix timeout value not getting passed to worker handler

[4.8.1] - 2021-12-07
~~~~~~~~~~~~~~~~~~~~
* Remove older exam attempt history table.

[4.8.0] - 2021-12-07
~~~~~~~~~~~~~~~~~~~~
* Remove older exam attempt history object that has been replaced.

[4.7.3] - 2021-12-06
~~~~~~~~~~~~~~~~~~~~
* Catch errors from `onStartExamAttempt` and `onEndExamAttempt`.

[4.7.2] - 2021-11-17
~~~~~~~~~~~~~~~~~~~~
* Add SimpleHistory to proctoring_proctoredexam table

[4.7.1] - 2021-11-16
~~~~~~~~~~~~~~~~~~~~
* Assign interstitial to timed exam status

[4.7.0] - 2021-11-08
~~~~~~~~~~~~~~~~~~~~
* Convert onboarding profile API waffle flag to Django setting.

[4.6.0] - 2021-11-03
~~~~~~~~~~~~~~~~~~~~
* Remove references to "ready_to_resume" and "resumed" statuses.

[4.5.0] - 2021-11-01
~~~~~~~~~~~~~~~~~~~~
* Remove references to VERIFIED_NAME_FLAG Django waffle flag.

[4.4.1] - 2021-11-01
~~~~~~~~~~~~~~~~~~~~
* Fix version number for previous release

[4.4.0] - 2021-10-29
~~~~~~~~~~~~~~~~~~~~
* Exam attempt should remain resumable after they have been marked as ready to resume. In order
  for that to be true, the resume states are no longer represented as a status, but instead that
  information is contained within the `ready_to_resume` and `resumed` fields.

[4.3.3] - 2021-10-29
~~~~~~~~~~~~~~~~~~~~
* Remove ProctoredExamSoftwareSecureReview.video_url column from database.

[4.3.2] - 2021-10-28
~~~~~~~~~~~~~~~~~~~~
* Remove video_url reference from ProctoredExamSoftwareSecureReview.

[4.3.1] - 2021-10-28
~~~~~~~~~~~~~~~~~~~~
* Set the to be retired column video_url on ProctoredExamSoftwareSecureReview to be nullable.

[4.3.0] - 2021-10-28
~~~~~~~~~~~~~~~~~~~~
* Upgrade the requirements and move edx-proctoring to be on Django 3.2 instead of Django 2.2

[4.2.0] - 2021-10-20
~~~~~~~~~~~~~~~~~~~~
* Timed exams should remain visible after the course end date has passed

[4.1.3] - 2021-10-15
~~~~~~~~~~~~~~~~~~~~
* Always allow practice attempts to trigger grade/credit/certificate updates

[4.1.2] - 2021-10-07
~~~~~~~~~~~~~~~~~~~~
* Instructor dashboard view should redirect to review url for PSI exam attempts

[4.1.1] - 2021-10-05
~~~~~~~~~~~~~~~~~~~~
* Bug fix to redact video url from raw data in exam review

[4.1.0] - 2021-09-28
~~~~~~~~~~~~~~~~~~~~
* Add GH action for migrations tests.
* Add test for `_register_proctored_exam_attempt`.
* Capture video review url in software secure review and encrypt before saving

[4.0.4] - 2021-10-05
~~~~~~~~~~~~~~~~~~~~~
* Switched from jsonfield2 to jsonfield as the earlier one has archived and merged back in the latter one.

[4.0.2] - 2021-09-28
~~~~~~~~~~~~~~~~~~~~~
* Batch of refactorings to use format strings/lazy string formatting for logging calls

[4.0.1] - 2021-09-21
~~~~~~~~~~~~~~~~~~~~~
* Bug fix for student onboarding statuses by course. If learner has multiple attempts, return non-reset attempt status if possible.

[4.0.0] - 2021-08-25
~~~~~~~~~~~~~~~~~~~~~
**BREAKING CHANGES:**

* BREAKING CHANGE: Upgraded dependency pyjwt[crypto] to 2.1.0, which introduces its own breaking changes that may affect consumers of this library. Pay careful attention to the 2.0.0 breaking changes documented in https://pyjwt.readthedocs.io/en/stable/changelog.html#v2-0-0.

[3.24.6] - 2021-09-03
~~~~~~~~~~~~~~~~~~~~~
* Upgrade edx-lint for linting
* Update code style
* Handler test refactor

[3.24.5] - 2021-09-02
~~~~~~~~~~~~~~~~~~~~~
* Add management command for updating an attempt status based on its associated review

[3.24.4] - 2021-09-02
~~~~~~~~~~~~~~~~~~~~~
* Add testing for exam attempt email failure and related logging
* Fix signal handler connection

[3.24.3] - 2021-09-02
~~~~~~~~~~~~~~~~~~~~~
* Get verified name enabled from name affirmation service.

[3.24.2] - 2021-09-01
~~~~~~~~~~~~~~~~~~~~~
* Add exception handler and logging to proctored exam attempt emails. This prevents user errors
  if the email is not able to be sent.

[3.24.1] - 2021-08-30
~~~~~~~~~~~~~~~~~~~~~
* Bug fix for exam registration

[3.24.0] - 2021-08-25
~~~~~~~~~~~~~~~~~~~~~
* Re-added code for using a verified name for a proctored exam attempt that had been reverted.
  Replaced with signal emitters, which will allow name affirmation to contain the logic for deciding
  when a verified name should be created or updated. Also restructured signal files to differentiate
  between signal senders and signal receivers.

[3.23.8] - 2021-08-25
~~~~~~~~~~~~~~~~~~~~~
* Fix the template on bulk exam allowance view where username is used for DOM id

[3.23.7] - 2021-08-24
~~~~~~~~~~~~~~~~~~~~~
* Fix error in onboarding status panel rejected filter

[3.23.6] - 2021-08-23
~~~~~~~~~~~~~~~~~~~~~
* Fix error where course staff were unable to add allowances.

[3.23.5] - 2021-08-19
~~~~~~~~~~~~~~~~~~~~~
* Fix a 500 error which would occur on stage when submitting an allowance.

[3.23.4] - 2021-08-18
~~~~~~~~~~~~~~~~~~~~~
* Change instructor onboarding API to fetch all onboarding profiles from the proctoring provider
  instead of making mulitple calls to the proctoring provider to assembke the full data set.
* Add logging statements to better evaluate performance of the endpoint.

[3.23.3] - 2021-08-16
~~~~~~~~~~~~~~~~~~~~~
* Remove the old allowance code entirely, so only the bulk allowance modal is used.

[3.23.2] - 2021-08-06
~~~~~~~~~~~~~~~~~~~~~
* Change errors on the bulk allowance modal so they appear on their associated field.

[3.23.1] - 2021-08-06
~~~~~~~~~~~~~~~~~~~~~
* Fixes bug that occurs when a proctoring vendor returns onboarding information that includes user IDs that represent
  learners that are not returned by the edX API as being enrolled in the course in a proctoring eligible mode.
* Adds logging statement to enable further investigation.

[3.23.0] - 2021-08-04
~~~~~~~~~~~~~~~~~~~~~
* Add simple history to proctored exam attempt, writing both old and new model for now. Includes admin view.
* Update documentation and makefile targets for a clear path from clone to running tests.

[3.22.1] - 2021-08-02
~~~~~~~~~~~~~~~~~~~~~
* Add edit button to grouped allowances, which allows instructors to edit the value of a single allowance.

[3.22.0] - 2021-07-26
~~~~~~~~~~~~~~~~~~~~~
* If verified name functionality is enabled through the "name_affirmation" runtime service,
  use it in proctored exam attempt creation. (see https://github.com/edx/edx-name-affirmation)
* When updating a proctored exam attempt to "verified" status, update the user's verified
  name status, if verified name functionality is enabled and they have one linked to that
  exam attempt.

[3.21.1] - 2021-07-26
~~~~~~~~~~~~~~~~~~~~~
* Removed name field in proctored exam attempt from the DB.

[3.21.0] - 2021-07-23
~~~~~~~~~~~~~~~~~~~~~
* Added feature behind the bulk allowance waffle flag that groups allowances by users.
* Updated the UI so allowances are under dropdown for each user

[3.20.6] - 2021-07-22
~~~~~~~~~~~~~~~~~~~~~
* Removed use of name field in proctored exam attempt admin.

[3.20.5] - 2021-07-21
~~~~~~~~~~~~~~~~~~~~~
* No changes, gets tag and internal version in sync

[3.20.4] - 2021-07-21
~~~~~~~~~~~~~~~~~~~~~
* Removed use of name field in proctored exam attempt.

[3.20.2] - 2021-07-21
~~~~~~~~~~~~~~~~~~~~~
* Removed IP fields in proctored exam attempt from the DB
* Made name field in proctored exam attempt nullable

[3.20.1] - 2021-07-20
~~~~~~~~~~~~~~~~~~~~~
* Removed use of IP fields in proctored exam attempt.

[3.20.0] - 2021-07-19
~~~~~~~~~~~~~~~~~~~~~
* Added Django 3.0, 3.1 & 3.2 Support

[3.19.0] - 2021-07-16
~~~~~~~~~~~~~~~~~~~~~
* Updated allowance modal to allow bulk allowances to be added.
* Added waffle flag to enable/disable bulk allowances feature.

[3.18.0] - 2021-07-15
~~~~~~~~~~~~~~~~~~~~~
* Remove old proctored exam attempt url.
* Fix onboarding link generation in proctored exam attempt view when exam attempt is in
  onboarding errors status, don't return the link to exams that are not accessible to user.
* Update onboarding link url in student onboarding status view to link
  to the learning mfe page instead of LMS.

[3.17.3] - 2021-07-14
~~~~~~~~~~~~~~~~~~~~~
* Add missing get_proctoring_config method to base backend provider class.

[3.17.2] - 2021-07-2
~~~~~~~~~~~~~~~~~~~~~
* Updated ProctoredExamAttempt view to use the content id from the query.

[3.17.1] - 2021-06-25
~~~~~~~~~~~~~~~~~~~~~
* Fix JSON parse failure when error response from course onboarding status endpoint does not
  return valid JSON.

[3.17.0] - 2021-06-23
~~~~~~~~~~~~~~~~~~~~~
* Replace internal logic for determing learners' onboarding statuses for the course onboarding API
  with provider onboarding API.

[3.16.0] - 2021-06-22
~~~~~~~~~~~~~~~~~~~~~
* Created a GET api endpoint which groups course allowances by users.

[3.15.1] - 2021-06-16
~~~~~~~~~~~~~~~~~~~~~
* Fix a bug in exam attempt API where total time allowed for the exam would not include allowance time.
* Add `test_plan` document to describe key features and test cases
* Update `developing` document with the instructions for frontend-lib-special-exam local development setup

[3.15.0] - 2021-06-15
~~~~~~~~~~~~~~~~~~~~~
* Created a POST api endpoint to add allowances for multiple students and multiple exams at the same time.

[3.14.0] - 2021-06-10
~~~~~~~~~~~~~~~~~~~~~
* When an exam attempt is finished for the first time, mark all completable children in the exam as complete
  in the Completion Service using the Instructor Service. If the Completion Service is not enabled, nothing
  will happen.

[3.13.2] - 2021-06-09
~~~~~~~~~~~~~~~~~~~~~
* Extend exam attempt API to return total time left in the attempt
  and a link to the onboarding exam in case user tries to take proctored
  exam when they haven't passed required onboarding exam.
  Modify API to check if exam has passed due date.

[3.13.1] - 2021-06-08
~~~~~~~~~~~~~~~~~~~~~
* If an attempt transitions from `ready_to_submit` back to `started`, the proctoring provider
  backend function `start_exam_attempt` will not be called.

[3.13.0] - 2021-06-07
~~~~~~~~~~~~~~~~~~~~~
* If the Django setting `PROCTORED_EXAM_VIEWABLE_PAST_DUE` is false, exam content will not be viewable past
  an exam's due date, even if a learner has acknowledged their status.
* Extend exam attempt API to return exam type and to check if
  user has satisfied prerequisites before taking proctored exam.
* Extend proctoring settings API to return additional data about proctoring
  provider.
* Add API endpoint which provides exam review policy for specific exam.
  Usage case is to provide required data for the learning app MFE.

[3.12.0] - 2021-06-04
~~~~~~~~~~~~~~~~~~~~~
* If the `is_integrity_signature_enabled` waffle flag is turned on, do not render the ID verification
  template for proctored exams.

[3.11.6] - 2021-06-03
~~~~~~~~~~~~~~~~~~~~~
* Add logging for attempt status transitions caused by a time out or reattempt

[3.11.5] - 2021-06-01
~~~~~~~~~~~~~~~~~~~~~
* Fix a bug where we are to pass to vendor javascript a value in milliseconds, instead of just seconds

[3.11.4] - 2021-05-27
~~~~~~~~~~~~~~~~~~~~~
* Use the same DEFAULT_DESKTOP_APPLICATION_PING_INTERVAL_SECONDS interval to start the exam and ping the
  proctoring desktop applicaiton

[3.11.3] - 2021-05-27
~~~~~~~~~~~~~~~~~~~~~
* Fix a bug where the Learning Sequences API does not have a schedule for a sequence, which can occur
  when a sequence is unavailable to a learner, and the learner should not know of the existence of the sequence
  (e.g. when a sequence is content gated by enrollment track and the learner is not in the requisite enrollment track).

[3.11.2] - 2021-05-25
~~~~~~~~~~~~~~~~~~~~~
* Add allow-list to prevent nonexistent backend configurations from causing errors

[3.11.1] - 2021-05-25
~~~~~~~~~~~~~~~~~~~~~
* Fix for onboarding status API endpoint. The endpoint requires an obscured user id.

[3.11.0] - 2021-05-24
~~~~~~~~~~~~~~~~~~~~~
* Add ability to get onboarding statuses from a proctoring provider API endpoint
* Extend the learner onboarding status API to determine whether the only onboarding exam or all
  onboarding exams are past due and past an "onboarding_past_due" flag in the response. modify
  the API to not return a link to the onboarding exam if the onboarding exam should not be
  accessible by the learner (i.e. it is to be released or is past due).
* Modify the display behavior of the learner onboarding panel to display "Onboarding Past Due"
  if the only onboarding or all onboarding exams are past due.

[3.10.2] - 2021-05-24
~~~~~~~~~~~~~~~~~~~~~
* Use onboarding status API endpoint for student onboarding info panel

[3.10.1] - 2021-05-21
~~~~~~~~~~~~~~~~~~~~~
* Add ability to get onboarding statuses from a proctoring provider API endpoint
* Add API endpoint which provides proctoring generic and backend specific
  instructions for the proctoring exam. Usage case is to provide required data
  for the learning app MFE.

[3.10.0] - 2021-05-19
~~~~~~~~~~~~~~~~~~~~~
* Add by-backend configurability of the link which shows on the onboarding panel

[3.9.4] - 2021-05-19
~~~~~~~~~~~~~~~~~~~~
* Fix a bug in processing onboarding exams in StudentOnboardingStatusView,
  resulting in an incorrect list of accessible onboarding exams.

[3.9.3] - 2021-05-18
~~~~~~~~~~~~~~~~~~~~
* Fix styling on allowance dropdown to prevent overflow for long exam names.

[3.9.2] - 2021-05-17
~~~~~~~~~~~~~~~~~~~~
* Remove the hide condition for onboarding exam reset by student. Roll out Proctoring Improvement Waffle Flag

[3.9.1] - 2021-05-17
~~~~~~~~~~~~~~~~~~~~
* Add the backend model field is_resumable to the ProctoredExamStudentAttempt model.
* Expose the is_resumable property to the UI so users can resume exam attempts when that property is set

[3.9.0] - 2021-05-17
~~~~~~~~~~~~~~~~~~~~
* Add API endpoint which provides sequence exam data with current active attempt.
  Usage case is to provide required data for the learning app MFE.
* Moved StudentProctoredExamAttemptCollection collecting attempt data logic
  to a separate standalone `get_exam_attempt_data` function.

[3.8.9] - 2021-05-07
~~~~~~~~~~~~~~~~~~~~
* Update language on proctored exam info panel if learner has
  a verified onboarding attempt

[3.8.8] - 2021-04-23
~~~~~~~~~~~~~~~~~~~~
* Add detailed logging of ping failures
* Expose ping timeout value to external javascript worker
* Add documentation for javascript worker development

[3.8.7] - 2021-04-16
~~~~~~~~~~~~~~~~~~~~
* Add pyjwt as explicit dependency to edx-proctoring library.
* Pin version of pyjwt to less than 2.0.0.

[3.8.6] - 2021-04-13
~~~~~~~~~~~~~~~~~~~~
* Fix JWT encoding bug introduced by version 2.0.1 of pyjwt[crypto] library.
* Add RST validator

[3.8.5] - 2021-04-07
~~~~~~~~~~~~~~~~~~~~~
* Add handling of the "onboarding_reset" attempt status to the
  StudentOnboardingStatusByCourseView view and the StudentOnboardingStatus
  panel in the Instructor Dashboard.

[3.8.4] - 2021-04-05
~~~~~~~~~~~~~~~~~~~~~
* Add the request username to the proctoring info panel, allowing course staff to masquerade as
  a specific user.

[3.8.3] - 2021-04-05
~~~~~~~~~~~~~~~~~~~~~
* Use exam due_date or course end date to evaluate the visibility of the onboarding status panel

[3.8.2] - 2021-04-02
~~~~~~~~~~~~~~~~~~~~~
* Update `DEFAULT_DESKTOP_APPLICATION_PING_INTERVAL_SECONDS` to pull from settings.

[3.8.1] - 2021-04-01
~~~~~~~~~~~~~~~~~~~~~
* Increase ping interval from 30 to 60 seconds.

[3.8.0] - 2021-03-31
~~~~~~~~~~~~~~~~~~~~~
* Remove exam resume waffle flag references and fully roll out exam resume and grouped attempt features.

[3.7.16] - 2021-03-30
~~~~~~~~~~~~~~~~~~~~~
* Reduce time for ping interval from 120 to 30 seconds.

[3.7.15] - 2021-03-24
~~~~~~~~~~~~~~~~~~~~~
* Improved learner messaging on onboarding panel and submitted interstitial.

[3.7.14] - 2021-03-19
~~~~~~~~~~~~~~~~~~~~~
* Fix issue where a course key object was being passed in to `get_proctoring_escalation_email`,
  rather than a string.

[3.7.13] - 2021-03-16
~~~~~~~~~~~~~~~~~~~~~
* Update proctored exam error message to remove statement that the user must restart their exam
  from scratch, and include a proctoring escalation email rather than a link to support if
  applicable.

[3.7.12] - 2021-03-15
~~~~~~~~~~~~~~~~~~~~~
* Update the onboarding status to take into account sections that are not accessible to the user
  or has a release date in the future. For sections with release dates in the future,
  that date will now be shown to the learner.
* Fixed accessibility bug on Special Exam Attempts panel on instructor dashboard

[3.7.9] - 2021-03-09
~~~~~~~~~~~~~~~~~~~~
* Update onboarding status logic such that 'approved in another course' will take precedence over
  a non verified state in the requested course.

[3.7.8] - 2021-03-08
~~~~~~~~~~~~~~~~~~~~
* Add enrollment mode column to onboarding status panel on instructor dashboard

[3.7.7] - 2021-03-08
~~~~~~~~~~~~~~~~~~~~
* Add loading spinner for searching to onboarding attempt and special attempts sections on the
  instructor dashboard

[3.7.6] - 2021-03-05
~~~~~~~~~~~~~~~~~~~~
* Fix bug with StudentProctoredExamAttempt put handler where course_id was being incorrectly determined,
  preventing course staff from marking learners' attempts as "ready_to_resume".

[3.7.5] - 2021-03-05
~~~~~~~~~~~~~~~~~~~~
* Add more useful attributes to log messages, in a key=value format that is easier to extract, and reduce
  duplicate exception logs.
* Update private.txt file path in developer docs

[3.7.4] - 2021-03-03
~~~~~~~~~~~~~~~~~~~~
* Show "approved in other course" status for learner who has a valid verified onboarding attempt in another course,
  on the instructor's student onboarding status panel

[3.7.3] - 2021-03-02
~~~~~~~~~~~~~~~~~~~~
* Change use of get_active_enrollments_by_course method of the LMS Enrollments service to
  get_enrollments_can_take_proctored_exams, which is more performant. This shifts the responsibility
  of checking learners' ability to access proctored exams to the LMS, allowing the LMS to construst a
  bulk query for all learners in a course with active enrollments instead of needing to execute multiple
  queries on a per learner basis.

[3.7.2] - 2021-03-02
~~~~~~~~~~~~~~~~~~~~
* Refactor the proctoring API function to get all verified onboarding attempts of a group of learners.

[3.7.1] - 2021-03-02
~~~~~~~~~~~~~~~~~~~~
* Update table on instructors dashboard to add accordian for multiple attempts

[3.7.0] - 2021-03-01
~~~~~~~~~~~~~~~~~~~~
* Update the learner onboarding status view to consider verified attempts from other courses.

[3.6.7] - 2021-02-24
~~~~~~~~~~~~~~~~~~~~
* Fix requirements file

[3.6.6] - 2021-02-24
~~~~~~~~~~~~~~~~~~~~
* Revert jsonfield PR

[3.6.5] - 2021-02-23
~~~~~~~~~~~~~~~~~~~~
* Bug fix to allow course staff to reset attempts

[3.6.4] - 2021-02-24
~~~~~~~~~~~~~~~~~~~~
* Switched from jsonfield2 to jsonfield as the earlier one has archived and merged back in the latter one.

[3.6.3] - 2021-02-23
~~~~~~~~~~~~~~~~~~~~
* Add a script to generate obscure_user_ids for proctoring vendors to use.
* Update the logic for the instructor dashboard onboarding view to match the learners' view,
  so that multiple onboarding exams for the same course can be considered.

[3.6.2] - 2021-02-22
~~~~~~~~~~~~~~~~~~~~
* Change learner onboarding status from "proctoring_started" to "onboarding_started"
  to more clearly describe the learner's onboarding status.

[3.6.1] - 2021-02-19
~~~~~~~~~~~~~~~~~~~~
* Add time_remaining_seconds field of ProctoredExamStudentAttempt model to readonly_fields in
  Django admin page so it is not required when editing the model.
* Update reference to Exception.message to use string representation of the exception, as message
  is no longer an attribute of the Exception class.

[3.6.0] - 2021-02-19
~~~~~~~~~~~~~~~~~~~~
* Do not override exam view for a learner taking a practice exam when the learner does
  not have access to proctoring. This allows the learner to see the exam content and does
  not allow the learner access to the proctoring software.

[3.5.1] - 2021-02-19
~~~~~~~~~~~~~~~~~~~~
* Add missing `rejected` status to list of onboarding attempt statuses.

[3.5.0] - 2021-02-18
~~~~~~~~~~~~~~~~~~~~
* Add new UI for instructor dashboard that groups attempts for each user and exam.
* Add endpoint that returns a list of most recent attempts for each user and exam. Each
  attempt that is returned contains additional data on the past attempts
  associated with the user/exam.

[3.4.1] - 2021-02-17
~~~~~~~~~~~~~~~~~~~~
* Restrict the resume option on the instructor dashboard to attempts that are
  in an "error" state and are not for onboarding or practice exams.

[3.4.0] - 2021-02-11
~~~~~~~~~~~~~~~~~~~~
* Add a new interstitial for exam attempts in the "ready_to_resume" state to
  indicate to learner that their exam attempt is ready to be resumed and to
  prompt the learner to resume their exam.

[3.3.0] - 2021-02-11
~~~~~~~~~~~~~~~~~~~~
* Add learner onboarding view to instructor dashboard.

[3.2.1] - 2021-02-11
~~~~~~~~~~~~~~~~~~~~
* bugfix to 500 errors from proctored exam attempt status endpoint used by the LMS to drive timer functionality

[3.2.0] - 2021-02-10
~~~~~~~~~~~~~~~~~~~~
* Update to update_attempt_status function to account for multiple attempts per exam
* Update to grade, credit, and status email updates based on multiple attempts

[3.1.0] - 2021-02-08
~~~~~~~~~~~~~~~~~~~~
* Add endpoint to return onboarding status information for users in a course.

[3.0.0] - 2021-02-05
~~~~~~~~~~~~~~~~~~~~~
* Update the secret key to the proctoring specific one so we are fixing for the learners being impacted by rotated django secret.

[2.6.7] - 2021-02-04
~~~~~~~~~~~~~~~~~~~~~
* Bug fix for onboarding info panel showing for all proctoring backends, independent of support for onboarding exams

[2.6.6] - 2021-02-01
~~~~~~~~~~~~~~~~~~~~~
* Bug fix for issue that prevented exam resets

[2.6.5] - 2021-01-28
~~~~~~~~~~~~~~~~~~~~~
* Update error interstitial to use the reset_exam_attempt flow that is used for other
  onboarding attempt reset

[2.6.4] - 2021-01-26
~~~~~~~~~~~~~~~~~~~~~
* Fix bug that was preventing exams from being reset
* Add exam removal endpoint to be used on the instructor dashboard in place of the
  current exam attempt reset endpoint as we now have multiple attempts. This new
  endpoint is only accessible to course and edX staff

[2.6.3] - 2021-01-26
~~~~~~~~~~~~~~~~~~~~~
* Update the learner onboarding status panel on "submitted" state so learner knows they need to wait
* Added npm-shrinkwrap.json to pin the graceful-fs to version 4.2.2 to solve "primordials" exception during gulp test

[2.6.2] - 2021-01-25
~~~~~~~~~~~~~~~~~~~~~
* Update endpoint that returns onboarding exam status to account for
  users enrollment mode.

[2.6.1] - 2021-01-25
~~~~~~~~~~~~~~~~~~~~~
* Add a dropdown component.
* If the "data-enable-exam-resume-proctoring-improvements" data attribute on the element of the ProctoredExamAttemptView
  Backbone is true,

  * use the dropdown menu component on the Instructor Dashboard Proctored Exam Attempt panel for proctored exam attempts in the error state, providing the following options:

    * Resume, which transitions the exam attempt into the ready_to_resume state.
    * Reset, which behaves the same as the previous reset functionality, originally exposed via the [x] link.
  * change the [x] link to Reset for exam attempts in other states.

* If the "data-enable-exam-resume-proctoring-improvements" data attribute on the element of the ProctoredExamAttemptView Backbone is
  false there is no change.

[2.6.0] - 2021-01-21
~~~~~~~~~~~~~~~~~~~~~
* Replace Travis CI with Github Actions.
* If a course has a proctoring escalation email set, emails that are sent when an
  exam attempt is verified or rejected will contain that email address rather than a
  link to support.

[2.5.13] - 2021-01-20
~~~~~~~~~~~~~~~~~~~~~
* Allow staff users to modify another user's exam attempt status via the
  the StudentProctoredExamAttempt view's PUT handler only when the action is
  "mark_ready_to_resume" and the user ID is passed in via the request data.

[2.5.12] - 2021-01-20
~~~~~~~~~~~~~~~~~~~~~
* Allow blank fields in Django admin for `external_id`, `due_date`, and `backend`
  in proctored exams.

[2.5.11] - 2021-01-19
~~~~~~~~~~~~~~~~~~~~~
* Added ProctoredExam to django admin

[2.5.10] - 2021-01-15
~~~~~~~~~~~~~~~~~~~~~
* Added management command to update `is_attempt_active` field on review models

[2.5.9] - 2021-01-13
~~~~~~~~~~~~~~~~~~~~
* Added `is_attempt_active` field to ProctoredExamSoftwareSecureReview and
  ProctoredExamSoftwareSecureReviewHistory models to note if the attempt for
  that review has been archived. When an attempt is archived and if it is associated
  with a review, this field will be set to False

[2.5.8] - 2021-01-12
~~~~~~~~~~~~~~~~~~~~
* Ignore the `ProctoredExamStudentAttemptHistory` table when viewing onboarding status.
  This fixes a bug where the status would return `verified` even after all attempts had
  been deleted.

[2.5.7] - 2021-01-08
~~~~~~~~~~~~~~~~~~~~
* Allow the creation of multiple exam attempts for a single user in a single exam, as long
  as the most recent attempt is `ready_to_resume` or `resumed`. When an exam is resumed, the
  time remaining is saved to the new attempt and is used to calculate the expiration time.

[2.5.6] - 2021-01-06
~~~~~~~~~~~~~~~~~~~~
* Updated the StudentProctoredExamAttempt view's PUT handler to allow for a
  new action "mark_ready_to_resume", which transitions exam attempts in the "error" state
  to a "ready_to_resume" state.

[2.5.5] - 2020-01-05
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* Cover `Start System Check` button on the proctoring instruction page with the
  conditions software download link is provided by the proctoring provider,
  since some providers do not has that step in the onboarding process.
* Changed handler for exam ping to remove learner from the exam on 403 error.
* Added `time_remaining_seconds` field to the exam attempt model in order to
  allow the remaining time on an exam attempt to be saved after it enters an
  error state.
* Fix bug allowing learners access to onboarding setup after exam due date.

[2.5.4] - 2020-12-17
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* Minor template fix

[2.5.3] - 2020-12-10
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* Upgrade celery to 5.0.4

[2.5.2] - 2020-12-10
~~~~~~~~~~~~~~~~~~~~

* Fixed bug for proctoring info panel

[2.5.1] - 2020-12-10
~~~~~~~~~~~~~~~~~~~~

* Add endpoint to expose the learner's onboarding status

[2.5.0] - 2020-12-09
~~~~~~~~~~~~~~~~~~~~

* Changed behavior of practice exam reset to create a new exam attempt instead
  of rolling back state of the current attempt.
* Added new proctoring info panel to expose onboarding exam status to learners
* Added option to reset a failed or pending onboarding exam.

[2.4.9] - 2020-11-17
~~~~~~~~~~~~~~~~~~~~

* Fix unbound local variable issue in api.get_attempt_status_summary
* Added new action to student exam attempt PUT allowing users
  to reset a completed practice exam.

[2.4.8] - 2020-10-19
~~~~~~~~~~~~~~~~~~~~

* Created a separate error message for inactive users. Refined the
  existing error message to only show for network error or service disruption.


[2.4.7] - 2020-10-06
~~~~~~~~~~~~~~~~~~~~

* Removed the rpnowv4_flow waffle flag to cleanup code

For details of changes prior to this release, please see
the `GitHub commit history`_.

.. _GitHub commit history: https://github.com/edx/edx-proctoring/commits/master
