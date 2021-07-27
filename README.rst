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

Developing
-------------

See the `developer guide`_ for configuration, devstack and sandbox setup, and other developer concerns.

.. _developer guide: ./docs/developing.rst

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
