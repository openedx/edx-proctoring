===================================
 Proctoring backend implementation
===================================

Proctoring providers (PS) who wish to integrate with OpenEdx should implement a `REST API`_ and a thin `Python wrapper`_, as described below.

REST API
--------

Implement the following endpoints. In order to authenticate requests from the OpenEdx server, the PS backend should
enable Basic Authentication. The OpenEdx installation will be configured with a client key and a client secret provided by the PS and will authenticate each request to the PS.

SSL is required for all (production environment) requests.

All requests and responses in this API are formatted as JSON objects.

In the following URLs, ``{exam_id}`` and ``{attempt_id}`` are opaque values created by OpenEdx.

Proctoring System configuration endpoint
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    /v1/config/

``GET``: returns an object of the available configuration options and metadata for the proctoring service.::

    {
        "config": {
            "allow_multiple": "Allow multiple monitors",
            "allow_notes": "Allow paper notes",
            "allow_apps": "Allow other applications to be running",
            ...
        },
        "name": "My Proctoring Provider",
        "download_url": "https://my.provider.com/download/software"
    }

The keys in the config object should be machine readable. The values are human readable. PS should respect the HTTP request ``Accept-Language``
header and translate all human readable configuration options into the requested language, if possible. 

If a download_url is included in the response, OpenEdx will redirect learners to the the address before the proctoring session starts. The address will include ``attempt={attempt_id}`` in the query string.

Exam endpoint
^^^^^^^^^^^^^

    /v1/exam/{exam_id}/

``GET``: returns an object about the exam. If no exam exists, return 404 error.::

    {
        "config": {
            "allow_notes": true,
            "allow_multiple": false
        }
    }

``POST``: may be used to create the exam on the PS, by sending an object like this::

    {
        "config": {
            "allow_notes": false,
            "allow_multiple": true
        }
    }

The config object will match the config keys returned from the configuration endpoint above. Any options which aren't passed in should be set to default values by the proctoring provider.


Exam attempt endpoint
^^^^^^^^^^^^^^^^^^^^^

    /v1/exam/{exam_id}/attempt/{attempt_id}/

``POST``: registers the exam attempt on the PS.::

    {
        "callback_url": "https://edx.org/.....",
        "user_id": "ae0305a9427a91f6f63e55af0eaa1d9c4c02af07f672d15e4a77d99b65327822",
        "callback_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdHRlbXB0X2lkIjoxfQ._VPnr2XS1Pf0FYU0qMW1LVzYcDOkBYuzFDeczX1QVrk"
    }

The PS system should respond with an object containing at least the following fields::

    {
        "id": "<some opaque id for the attempt>",
    }

``PATCH``: changes the status of the attempt::

    {
        "status": "start",
        "callback_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdHRlbXB0X2lkIjoxfQ._VPnr2XS1Pf0FYU0qMW1LVzYcDOkBYuzFDeczX1QVrk",
    }
    {
        "status": "stop",
        "callback_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdHRlbXB0X2lkIjoxfQ._VPnr2XS1Pf0FYU0qMW1LVzYcDOkBYuzFDeczX1QVrk",
    }

OpenEdx will issue a ``PATCH`` request with a ``start`` status when the learner starts the proctored exam, and a ``stop`` status when the learner finishes the exam.

The callback_token field in each JSON request is a JWT_ token, valid for a preconfigured amount of time. The token's payload contains the same attempt_id passed in the URL and thus is valid only for callback requests for a single attempt.

The PS system should save the token received in each request, updating it if it changes. 


Exam review callback
^^^^^^^^^^^^^^^^^^^^

After the PS system has reviewed an attempt, it must issue a POST request to the OpenEdx server at the callback_url passed in the attempt registration request.

The expected JSON request must include::

    {
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdHRlbXB0X2lkIjoxfQ._VPnr2XS1Pf0FYU0qMW1LVzYcDOkBYuzFDeczX1QVrk",
        "status": "verified",
        "comments": []
    }

Token must match the last callback_token sent by OpenEdx for this attempt. Status must be one of ``["verified", "suspicious"]``.

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


