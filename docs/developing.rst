edX Proctoring Developer Guide
==============================

.. contents::


How do I use proctoring on devstack?
------------------------------------
* Create a test course
    * Follow the steps here: `Including Proctored Exams in Your Course <https://docs.openedx.org/en/latest/educators/how-tos/proctored_exams/enable_proctored_exams.html>`_
        * Note that the UI may be different on devstack with Enable Proctored Exams in Advanced Settings
* Read the `learner guide for using proctoring <https://docs.openedx.org/en/latest/learners/completing_assignments/proctored_exams.html>`_
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
    $ git clone https://github.com/openedx/edx-proctoring

Install the proctoring package into edx-platform in the container, for both LMS and Studio:

Edit or create the ``edx-platform/requirements/edx/private.txt`` file::

    # edx-platform/requirements/private.txt
    # This file will be used in the docker image, so use file paths that work there.
    -e /edx/src/edx-proctoring

The packages we specified in ``private.txt`` will be automatically pulled down by::

    $ make lms-shell
    root@a7ff4f3f3f6b:/edx/app/edxapp/edx-platform# paver install_prereqs;exit
    $ make studio-shell
    root@a7ff4f3f3f6b:/edx/app/edxapp/edx-platform# paver install_prereqs;exit

In ``edx-platform/lms/envs/private.py`` and ``edx-platform/cms/envs/private.py``:

.. code-block:: python

    from .production import FEATURES

    FEATURES['ENABLE_SPECIAL_EXAMS'] = True

    PROCTORING_SETTINGS = {
        'MUST_BE_VERIFIED_TRACK': False
    }


How do I setup `mfe-special-exam-lib` for local development?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

`MFE special exam lib <https://github.com/edx/frontend-lib-special-exams/>`_ is a react library to support
special exams in the Learning MFE.

Make sure that `frontend-app-learning` is setup and running on your devstack.

The special exam lib is installed as a dependency of Learning MFE.
And for the local development module export flow should be overridden following the instructions at
in `local-module-development <https://github.com/openedx/frontend-app-learning#local-module-development>`_



* Example `module.config.js` file in `frontend-app-learning` assuming this library is located at
  `$YOUR_WORKSPACE/src/frontend-lib-special-exams/`. Please note your project folders may be different:

.. code-block::

  // module.config.js
  module.exports = {
    localModules: [
      { moduleName: '@edx/frontend-lib-special-exams', dir: '../src/frontend-lib-special-exams', dist: 'src' },
    ],
  };

* restart devstack::

    $ make dev.stop
    $ make dev.up.lms+frontend-app-learning


How does the proctoring system work?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

See `System Overview`_ for a description of the proctoring system and it's components.


Email Templates
---------------

edx-proctoring provides generic base email templates that are rendered and sent to learners based
on changes to the status of a proctored exam attempt. They have been designed such that you may leverage Django template
inheritance to customize their content to the proctoring backend. Because proctoring backend plugins are installed in edx-platform,
you must create an overriding template in the edx-platform repository. The template path should be ``emails/proctoring/{backend}/{template_name}``.
Note that your template can either completely override the base template in edx-proctoring, or it can extend the base template in order to leverage
the existing content of the blocks within the base template, particularly if you only need to change a portion of the template.

Debugging
------------

To debug with PDB, run ``pytest`` with the ``-n0`` flag. This restricts the number
of processes in a way that is compatible with ``pytest``

    pytest -n0 [file-path]


Using mockprock as a backend
----------------------------

`Mockprock <https://github.com/openedx/mockprock>`_ is a proctoring backend that runs as an HTTP server and a python module. It allows you to simulate the entire proctoring workflow.

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

Rebuild static assets to make sure mockprock ui scripts are available. In devstack::

   make dev.static.lms

Then back in your host shell, install and run the server. It is recommended to run this in a virtual environment.::

    cd ~/workspace/src/mockprock/
    pip install -e .[server]
    python -m mockprock.server

If you use Z shell (zsh), the command ``pip install -e .[server]`` will fail with ``zsh: no matches found: .[server]``. This is because `zsh uses square brackets for globbing/pattern matching <https://stackoverflow.com/questions/30539798/zsh-no-matches-found-requestssecurity>`_. You should instead run the following command.::

   pip install -e ".[server]"

The command will tell you you have to supply an client_id and client_secret. It'll open your browser to the Django admin page where you should create or use an existing credential. You'll also need to add the user associated with the credential to the "mockprock_review" Django group. You can create the group at ``/admin/auth/group/``. Note the client_id and client_secret and restart the server::

    python -m mockprock.server {client_id} {client_secret}

Note that mockprock does not run in a Docker container; it runs on the host machine. If you are running Docker devstack, the LMS, which includes the ``edx-proctoring`` subsystem, runs in a Docker container.
In a few spots, the ``edx-proctoring`` code, running in the LMS Docker container, needs to redirect the user to pages on the host.
The URL that the user is sent to is defined in the mockprock backend as ``base_url``, which is ``http://host.docker.internal:11136``.
``host.docker.internal`` is a special DNS name that is used by Docker to resolve to the host IP, since the host IP is not static; you can view Docker documentation on this feature `here <https://docs.docker.com/desktop/mac/networking/>`_.
Docker `claims <https://github.com/docker/for-mac/issues/2965>`_ that this should resolve correctly to the host's internal IP address as of Docker desktop version ``3.4.0``. However, if it does not resolve correctly, you can add the following entry to your host's ``/etc/hosts`` file.::

    127.0.0.1	host.docker.internal

If you need to run local changes to the `mockprock Javascript worker`_ or the `worker interface`_ in this library::

   make lms-shell

   (cd /edx/src/mockprock; npm link)
   npm link @edx/mockprock

   cd /edx/src/mockprock
   (cd /edx/src/edx-proctoring; npm link)
   npm link @edx/edx-proctoring

.. _mockprock Javascript worker: https://github.com/openedx/mockprock/tree/master/static
.. _worker interface: https://github.com/openedx/edx-proctoring/blob/master/edx_proctoring/static/index.js

How do I run proctoring tests?
------------------------------

    cd /edx/src/edx-proctoring
    make test-all


How do I set up proctoring on a running sandbox?
------------------------------------------------

Start by following the steps here: https://github.com/openedx/edx-proctoring

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
locations mentioned in this document) will allow us to leverage the
power of the ansible plays used to construct and administer
sandboxes, e.g. those run via the ``/edx/bin/update`` script.
`More on that here.`_
You will need to `generate a public JWK keypair <https://mkjwk.org/>`_.

The contents of ``EDXAPP_PROCTORING_BACKENDS`` will depend on which
backend(s) you're interested in testing. It's necessary to provide a
``DEFAULT`` backend.

.. _our spec: ./backends.rst
.. _System Overview: ./system-overview.rst

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
* Describe your changes in `CHANGELOG.rst`
* Create a `new release on GitHub <https://github.com/openedx/edx-proctoring/releases>`_ using the version number
* Update edx-platform to use the new version
    * In edx-platform, create a branch and update the requirements/edx/base.txt, development.txt, and testing.txt files to reflect the new tagged branch.
* create a PR of this branch in edx-platform onto edx-platform:master
* Once the PR onto edx-platform has been merged, the updated edx-proctoring will be live in production when the normally scheduled release completes.

How do I validate my changes in stage or production?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* See `test plan`_ for manual tests and data setup

.. _test plan: ./testing/test_plan.md
