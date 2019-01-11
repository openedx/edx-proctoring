edX Proctoring Developer Guide
==============================

.. contents::


How do I use proctoring on devstack?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
* Create a test course
    * Follow the steps here: Including Proctored Exams in Your Course
* Read the `learner guide for using proctoring <http://edx.readthedocs.io/projects/edx-guide-for-students/en/latest/completing_assignments/SFD_proctored_exams.html>`_
* Start out by trying a practice proctored exam to understand the process
* The Instructor Dashboard has a "Special Exams" tab for administering proctoring
    * can add allowances per user, e.g. additional time for an exam
    * can also reset exam attempts for individual users
* More debugging can be done in Django admin
    * "Edx_Proctoring" section
    * "Proctored exam software secure review" has log of responses from SoftwareSecure

How do I develop on edx-proctoring?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

These are the steps to install edx-proctoring into your pre-existing devstack image:

Clone edx-proctoring into the src directory next to edx-platform folder in your host filesystem::

    $ cd src
    $ git clone https://github.com/edx/edx-proctoring

Install the proctoring package into edx-platform in the container, for both LMS and Studio:

Edit or create the ``edx-platform/requirements/private.txt`` file::

    # edx-platform/requirements/private.txt
    # This file will be used in the docker image, so use file paths that work there.
    -e /edx/src/edx-proctoring

The packages we specified in ``private.txt`` will be automatically pulled down by::

    $ make lms-shell
    root@a7ff4f3f3f6b:/edx/app/edxapp/edx-platform# paver install_prereqs;exit
    $ make studio-shell
    root@a7ff4f3f3f6b:/edx/app/edxapp/edx-platform# paver install_prereqs;exit

In edx-platform/lms/envs/private.py and edx-platform/cms/envs/private.py:

.. code-block:: python

    from .production import FEATURES
     
    FEATURES['ENABLE_SPECIAL_EXAMS'] = True

    PROCTORING_SETTINGS = {
        'MUST_BE_VERIFIED_TRACK': False
    }


Using mockprock as a backend
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

`Mockprock <https://github.com/edx/mockprock>`_ is a proctoring backend that runs as an HTTP server and a python module. It allows you to simulate the entire proctoring workflow.

To install it::
    $ cd src
    $ git clone git@github.com:edx/mockprock.git

Then add it to your ``private.txt``::
    -e /edx/src/mockprock

Add it to your ``private.py``::

    PROCTORING_BACKENDS = {
        'DEFAULT': 'mockprock',
        'null': {},
        'mockprock': {
            'client_id': 'abcd',
            'client_secret': 'abcdsecret',
        }
    }

Reinstall requirements in lms and studio.

Then back in your host shell::

    cd ~/workspace/src/mockprock/
    pip install -e .[server]
    python -m mockprock.server

The command will tell you you have to supply an client_id and client_secret. It'll open your browser to the django admin page where you should create or use an existing credential. Note the client_id and client_secret and restart the server::

    python -m mockprock.server {client_id} {client_secret}


How do I run proctoring tests?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    cd /edx/src/edx-proctoring
    make test-all


How do I set up proctoring on a sandbox?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Start by following the steps here: https://github.com/edx/edx-proctoring

* Add the edX-specific configuration settings
* Restart Studio and LMS::

    sudo /edx/bin/supervisorctl restart lms cms

* Create a test course

* Enroll verified@example.com in the course
* Log in to Django admin
* Add a verified course mode for your course
* Update the verified user's mode to be "verified"
* You will need to fake verifying the user's identification, or else enable a feature to automatically verify users for testing. 
    * To fake the verification:
        * Go to ``/admin/verify_student/manualverification/`` on your sandbox
        * Create a record for the given user, with status "approved".

How do I use proctoring on stage?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Create a test user that is not staff

Note: you can create new emails by adding a suffix starting with + to your edx email
For example, andya+test@edx.org

* Enroll for the `proctoring test course <https://courses.stage.edx.org/courses/course-v1:Proctoring2+Proctoring2+Proctoring2/info>`_
* Sign up for the verified track
* When paying, use one of the `test credit cards <http://www.cybersource.com/developers/other_resources/quick_references/test_cc_numbers/>`_

Note: you can use any expiration date in the future, and any three digit CVN

How do I release edx-proctoring?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
When releasing a new version of edx-proctoring, we use a process that is very similar to edx-platform. However, since edx-proctoring is a dependent library for edx-platform, there are some differences.

Release a new version of edx-proctoring
----------------------------------------

* Update the version in ``edx_proctoring/__init__.py`` and ``package.json``
* Create a `new release on GitHub <https://github.com/edx/edx-proctoring/releases>`_ using the version number 
* Send an email to release-notifications@edx.org announcing the new version
* Update edx-platform to use the new version
    * In edx-platform, create a branch and update the requirements/edx/base.in file to reflect the new tagged branch. 
* create a PR of this branch in edx-platform onto edx-platform:master
* Once the PR onto edx-platform has been merged, the updated edx-proctoring will be live in production when the normally scheduled release completes.
