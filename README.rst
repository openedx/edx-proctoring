edx-proctoring
==============

.. image:: https://img.shields.io/pypi/v/edx-proctoring.svg
    :target: https://pypi.python.org/pypi/edx-proctoring/
    :alt: PyPI

.. image:: https://github.com/edx/edx-proctoring/workflows/Python%20CI/badge.svg
    :target: https://github.com/edx/edx-proctoring/actions?query=workflow%3A%22Python+CI%22
    :alt: Python CI

.. image:: https://codecov.io/gh/edx/edx-proctoring/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/edx/edx-proctoring
    :alt: Codecov

.. image:: https://img.shields.io/pypi/pyversions/edx-proctoring.svg
    :target: https://pypi.python.org/pypi/edx-proctoring/
    :alt: Supported Python versions

.. image:: https://img.shields.io/github/license/edx/django-component-views.svg
    :target: https://github.com/edx/edx-proctoring/blob/master/LICENSE.txt
    :alt: License

This is the exam proctoring subsystem for the Open edX platform.

Overview
--------

Proctored exams are exams with time limits that learners complete while online
proctoring software monitors their computers and behavior for activity that
might be evidence of cheating. This Python library provides the proctoring
implementation used by Open edX.

Documentation
-------------

For authoring documentation, see `Including Proctored Exams In Your Course`_.

Installation
------------

To install edx-proctoring:

    mkvirtualenv edx-proctoring
    make install

To run the tests:

    make test-all

For a full list of Make targets:

    make help

Configuration
-------------

In order to use edx-proctoring, you must obtain an account (and secret
configuration - see below) with SoftwareSecure, which provides the proctoring
review services that edx-proctoring integrates with.

You will need to turn on the ENABLE_SPECIAL_EXAMS in lms.env.json and
cms.env.json FEATURES dictionary::

    "FEATURES": {
        :
        "ENABLE_SPECIAL_EXAMS": true,
        :
    }

Also in your lms.env.json and cms.env.json file please add the following::


    "PROCTORING_SETTINGS": {
        "LINK_URLS": {
            "contact_us": "{add link here}",
            "faq": "{add link here}",
            "online_proctoring_rules": "{add link here}",
            "tech_requirements": "{add link here}"
        }
    },

In your lms.auth.json file, please add the following *secure* information::

    "PROCTORING_BACKENDS": {
        "software_secure": {
            "crypto_key": "{add SoftwareSecure crypto key here}",
            "exam_register_endpoint": "{add endpoint to SoftwareSecure}",
            "exam_sponsor": "{add SoftwareSecure sponsor}",
            "organization": "{add SoftwareSecure organization}",
            "secret_key": "{add SoftwareSecure secret key}",
            "secret_key_id": "{add SoftwareSecure secret key id}",
            "software_download_url": "{add SoftwareSecure download url}"
        },
        'DEFAULT': 'software_secure'
    },

You will need to restart services after these configuration changes for them to
take effect.

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

License
-------

The code in this repository is licensed under the AGPL 3.0 unless
otherwise noted.

Please see ``LICENSE.txt`` for details.

How To Contribute
-----------------

Contributions are very welcome.

Please read `How To Contribute <https://github.com/edx/edx-platform/blob/master/CONTRIBUTING.rst>`_ for details.

Even though they were written with ``edx-platform`` in mind, the guidelines
should be followed for Open edX code in general.

Reporting Security Issues
-------------------------

Please do not report security issues in public. Please email security@edx.org.

Getting Help
------------

Have a question about this repository, or about Open edX in general?  Please
refer to this `list of resources`_ if you need any assistance.

.. _list of resources: https://open.edx.org/getting-help
.. _Including Proctored Exams In Your Course: https://edx.readthedocs.io/projects/edx-partner-course-staff/en/latest/proctored_exams/index.html
