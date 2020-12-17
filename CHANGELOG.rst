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
