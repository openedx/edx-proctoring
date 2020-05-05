edX Proctoring Developer Guide
==============================

.. contents::


How do I use proctoring on devstack?
------------------------------------
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
-----------------------------------

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
----------------------------

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

The command will tell you you have to supply an client_id and client_secret. It'll open your browser to the Django admin page where you should create or use an existing credential. You'll also need to add the user associated with the credential to the "mockprock_review" Django group. You can create the group at ``/admin/auth/group/``. Note the client_id and client_secret and restart the server::

    python -m mockprock.server {client_id} {client_secret}


How do I run proctoring tests?
------------------------------

    cd /edx/src/edx-proctoring
    make test-all


How do I set up proctoring on a running sandbox?
------------------------------------------------

Start by following the steps here: https://github.com/edx/edx-proctoring

* Add the edX-specific configuration settings

  * What specifically needs to be configured depends on the backends
    you'll need on your sandbox. See the next section on
    `Backend-specific Information`_
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

Backend-specific Information
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

One of the main motivations for setting up a sandbox to test
proctoring is having an externally accessible system which can be
accessed by our proctoring providers' systems. This enables more
thorough end-to-end testing.

To enable proctoring in a way that won't be overridden by ansible
plays, you can add the following to a sandbox's
``/edx/app/edx_ansible/server-vars.yml`` at the end of the
``EDXAPP_FEATURES`` array::

  EDX_APP_FEATURES:
    MILESTONES_APP: true
    ...
    ENABLE_API_DOCS: true
    ENABLE_SPECIAL_EXAMS: true

  PROCTORING_SETTINGS:
    MUST_BE_VERIFIED_TRACK: False

  COMMON_JWT_PUBLIC_SIGNING_JWK_SET: ' {"keys":[{"kty":"RSA", ... }]}'

  EDXAPP_PROCTORING_BACKENDS:
    ...

Placing these configurations here (rather than the more generic
locations mentioned in `the README`_) will allow us to leverage the
power of the ansible plays used to construct and administer
sandboxes, e.g. those run via the ``/edx/bin/update`` script.
`More on that here.`_

You will need to `generate a public JWK keypair`_.

The contents of ``EDXAPP_PROCTORING_BACKENDS`` will depend on which
backend(s) you're interested in testing. It's necessary to provide a
``DEFAULT`` backend.

Proctortrack
""""""""""""

As will be the case with all REST backends implementing `our spec`_, one
doesn't need to configure much to get Proctortrack working on a
sandbox, e.g.::
  EDXAPP_PROCTORING_BACKENDS:
    DEFAULT: 'proctortrack'
    proctortrack:
      client_id: "<you'll need to fill these in with credentials from Proctortrack>"
      client_secret: "<you'll need to fill these in with credentials from Proctortrack>"
      base_url: 'https://prestaging.verificient.com'
      integration_specific_email: "proctortrack-support@edx.org"

In addition to adding these configurations, you'll also need to set up
a user which PT can authenticate as.

* Create a user group called ``proctortrack_review`` in Django admin
* Create a user, and associate it with that group
* Create an OAuth application
  (``/admin/oauth2_provider/application/``) pointing to the user
  you've created, and share the client_id with folks on the other end
  of the integration.

.. _our spec: ./backends.rst
.. _the README: https://github.com/edx/edx-proctoring
.. _generate a public JWK keypair: https://mkjwk.org/
.. _More on that here.: https://openedx.atlassian.net/wiki/spaces/EdxOps/pages/13960183/Sandboxes#Sandboxes-Updatingcode

RPNow
"""""

Comparably more is required for our older support of PSI's RemoteProctor NOW software::

  EDXAPP_PROCTORING_BACKENDS:
    DEFAULT: "software_secure"
    software_secure:
      crypto_key: "<secret>"
      exam_register_endpoint: "https://exams.remoteproctor.io/exams/registration/"
      exam_sponsor: "edx LMS"
      organization: "edxdev"
      secret_key_id: "<secret>"
      secret_key: "<secret>"
      software_download_url: "http://edxdev.remoteproctor.com"
      send_email: true

At edX, we keep these non-production secrets stored behind `a private confluence document`_.

.. _a private confluence document: https://openedx.atlassian.net/wiki/spaces/EDUCATOR/pages/160027798/Software+Secure+debug+proctoring+configuration

How do I use proctoring on stage?
---------------------------------

* Create a test user that is not staff

Note: you can create new emails by adding a suffix starting with + to your edX email
For example, andya+test@edx.org

* Enroll for the `proctoring test course <https://courses.stage.edx.org/courses/course-v1:Proctoring2+Proctoring2+Proctoring2/info>`_
* Sign up for the verified track
* When paying, use one of the `test credit cards <https://developer.cybersource.com/hello-world/testing-guide.html>`_

Note: you can use any expiration date in the future, and any three digit CVN

How do I release edx-proctoring?
--------------------------------
When releasing a new version of edx-proctoring, we use a process that is very similar to edx-platform. However, since edx-proctoring is a dependent library for edx-platform, there are some differences.

Release a new version of edx-proctoring
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Update the version in ``edx_proctoring/__init__.py`` and ``package.json``
* Create a `new release on GitHub <https://github.com/edx/edx-proctoring/releases>`_ using the version number 
* Send an email to release-notifications@edx.org announcing the new version
* Update edx-platform to use the new version
    * In edx-platform, create a branch and update the requirements/edx/base.in file to reflect the new tagged branch. 
* create a PR of this branch in edx-platform onto edx-platform:master
* Once the PR onto edx-platform has been merged, the updated edx-proctoring will be live in production when the normally scheduled release completes.
