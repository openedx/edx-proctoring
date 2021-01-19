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
* Replace Travis CI with Github Actions

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
