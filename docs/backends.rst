===================================
 Proctoring backend implementation
===================================

Proctoring services (PS) who wish to integrate with Open edX should implement a `REST API`_ and a thin `Python wrapper`_, as described below.

REST API
--------

Implement the following endpoints. In order to authenticate requests from the Open edX server, the PS backend should
enable Oauth 2 authentication using JWT_. The Open edX installation will be configured with a client key and a client secret provided by the PS and will authenticate each request to the PS.

To obtain a JWT_ token, the PS system must make an Oauth2 request to ``/oauth2/access_token``.

SSL is required for all (production environment) requests.

All requests and responses in this API are formatted as JSON objects.


Proctoring System configuration endpoint
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    /api/v1/config/

``GET``: returns an object of the available configuration options and metadata for the proctoring service.::

    {
        "rules": {
            "allow_multiple": "Allow multiple monitors",
            "allow_notes": "Allow paper notes",
            "allow_apps": "Allow other applications to be running",
            ...
        },
        "name": "My Proctoring Service",
        "download_url": "https://my.proctoring.com/download/software",
        "instructions": [
            "Step one, download the software",
            "Next, run the software",
            ...
        ]
    }

The keys in the rules object should be machine readable. The values are human readable. PS should respect the HTTP request ``Accept-Language``
header and translate all human readable rules into the requested language.

If a download_url is included in the response, Open edX will redirect learners to the address before the proctoring session starts. The address will include ``attempt={attempt_id}`` in the query string.

Exam endpoint
^^^^^^^^^^^^^

    /api/v1/exam/{exam_id}/

``GET``: returns an object describing the exam. If no exam exists, return 404 error.::

    {
        "rules": {
            "allow_notes": true,
            "allow_multiple": false
        }
    }

    /api/v1/exam/

``POST``: may be used to create the exam on the PS, by sending an object like this::

    {
        "rules": {
            "allow_notes": false,
            "allow_multiple": true
        },
        "rule_summary": "Human readable summary of rules.",
        "course_id": "myOrgX:Course101",
        "is_practice": false,
        "is_proctored": true,
        "id": 123,
        "name": "Course Final Exam"
    }

The rules object will match the rule keys returned from the configuration endpoint above. Any options which aren't passed in should be set to default values by the proctoring service.

The PS system should respond with an object containing at least the following fields::

    {
        "id": "<some opaque id for the exam>"
    }


Exam attempt endpoint
^^^^^^^^^^^^^^^^^^^^^

    /api/v1/exam/{exam_id}/attempt/

``{exam_id}`` is the id returned by the PS during exam creation.


``POST``: registers the exam attempt on the PS.::

    {
        "user_id": "ae0305a9427a91f6f63e55af0eaa1d9c4c02af07f672d15e4a77d99b65327822",
        "user_name": "Joe Smith"
    }

The PS system should respond with an object containing at least the following fields::

    {
        "id": "<some opaque id for the attempt>",
    }

..

    /api/v1/exam/{exam_id}/attempt/{attempt_id}/

``{exam_id}`` is the id returned by the PS at exam creation and ``{attempt_id}`` is the id returned by the PS during exam attempt creation.

``PATCH``: changes the status of the attempt::

    {
        "status": "started",
    }
    {
        "status": "submitted",
    }

Open edX will issue a ``PATCH`` request with a ``started`` status when the learner starts the proctored exam, and a ``submitted`` status when the learner finishes the exam.

``GET``: returns PS information about the attempt

For convenience, the PS should return the exam instructions and the software download url in this response::

    {
        "status": "created",
        "instructions": [
            "Download software",
            "Run software",
            ...
        ],
        "download_url": "http://my-proctoring.com/download"
    }


Exam ready callback
^^^^^^^^^^^^^^^^^^^

After the PS client software starts, the PS system should make a ``POST`` request to ``/api/v1/edx_proctoring/proctored_exam/attempt/{attempt_id}/ready`` with the following data::

    {
        "status": "ready"
    }



Exam review callback
^^^^^^^^^^^^^^^^^^^^

After the PS system has reviewed an attempt, it must issue a ``POST`` request to the Open edX server at ``/api/v1/edx_proctoring/v1/proctored_exam/attempt/{attempt_id}/reviewed``

The expected JSON request must include::

    {
        "status": "passed",
        "comments": []
    }

Status must be one of ``["passed", "violation", "suspicious", "not_reviewed"]``.

There can be an arbitrary number of review comments, formatted with at least the following fields::

    {
        "comment": "Human readable comment",
        "status": "unknown"
    }

The following fields are optional::

    {
        "start": 123,
        "stop": 144
    }

(Start and stop are seconds relative to the start of the recorded proctoring session.)

--------

Python wrapper
--------------

Easy way
^^^^^^^^

If you have followed the URL conventions listed above to implement your REST API, the rest of the integration is very simple:

 * Create a Python package which depends on ``edx_proctoring``.
 * Subclass ``edx_proctoring.backends.rest.BaseRestProctoringProvider``, overriding ``base_url`` with the root URL of your server.
 * Register the class as an entrypoint in the package's setup.py::

    entry_points={
        'openedx.proctoring': [
            'my_provider = my_package.backend:MyBackendProvider'
        ]
    }
 * Upload package to pypi_

Manual way
^^^^^^^^^^

 * Create a Python package.
 * Create a class which implements all of the methods from ``edx_proctoring.backends.backend.ProctoringBackendProvider``. You do not need to use a REST API for anything, but you do need to conform to the backend API.
 * Register the entrypoint as shown above.
 * Upload package to pypi_


.. _JWT: https://jwt.io/
.. _pypi: https://pypi.org/


