===================================
 Proctoring backend implementation
===================================

Proctoring services (PS) who wish to integrate with Open edX should implement a `REST API`_ and a thin `Python wrapper`_, as described below.

Proctoring services integrated with Open edX may also optionally
implement a `Javascript API`_ to hook into specific browser-level
events.

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
header and translate all human readable rules and instructions into the requested language.

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

The PS server must respond with an object containing at least the following fields::

    {
        "id": "<some opaque id for the attempt>",
    }

The PS server can block the user from taking a proctored exam if onboarding prerequistes haven't been met. Return an object with ``status`` set to one of the following:

    * ``onboarding_missing``: The user has not completed an onboarding exam.
    * ``onboarding_pending``: The user has taken an onboarding exam, but it is pending review.
    * ``onboarding_failed``: The user failed the onboarding exam requirements.
    * ``onboarding_expired``: The onboarding profile has expired, requiring the user to re-take an onboarding exam.

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

Open edX will issue a ``PATCH`` request with a ``started`` status when the learner starts the proctored exam, and a ``submitted`` status when the learner finishes the exam. A status of ``error`` may be used in case of a technical error being associated with a learner's proctoring session.

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

``DELETE``: removes attempt on PS server

When an attempt is deleted on the Open edX server, it will make a ``DELETE`` request on the PS server. On success, return::

    {
        "status": "deleted"
    }


User management endpoint
^^^^^^^^^^^^^^^^^^^^^^^^

    /api/v1/user/{user_id}/

``{user_id}`` is the id sent by the Open edX server on exam attempts.

``DELETE``: deletes all user data associated with this user id. Response::

    true or false


Exam ready callback
^^^^^^^^^^^^^^^^^^^

After the PS client software starts, the PS system should make a ``POST`` request to ``/api/v1/edx_proctoring/proctored_exam/attempt/{attempt_id}/ready`` with the following data::

    {
        "status": "ready"
    }



Exam review callback
^^^^^^^^^^^^^^^^^^^^

After the PS system has reviewed an attempt, it must issue a ``POST`` request to the Open edX server at ``/api/v1/edx_proctoring/v1/proctored_exam/attempt/{attempt_id}/reviewed``

The expected JSON request must include the following fields::

    {
        "status": "passed",
        "comments": []
    }

Status must be one of ``["passed", "violation", "suspicious", "not_reviewed"]``.

The JSON request may also include the following optional fields::

    {
        "reviewed_by": "user@example.com"
    }

``reviewed_by`` must be included whenever a specific edX user (e.g. a member of a course team) initiated the review.

There can be an arbitrary number of review comments in the ``comments`` array, formatted with at least the following fields::

    {
        "comment": "Human readable comment",
        "status": "unknown"
    }

Each comment can also optionally include the following fields::

    {
        "start": 123,
        "stop": 144
    }

Start and stop are seconds relative to the start of the recorded proctoring session.


Instructor Dashboard
--------------------

It is possible to add support for an instructor dashboard for reviewing proctored exam violations and/or configuring proctored exam options.

The ``get_instructor_url`` method of the backend will return a URL on the PS end that will redirect to the instructor dashboard.

By default, this URL will be ``base_url + u'/api/v1/instructor/{client_id}/?jwt={jwt}'``. This URL template is specified by the ``instructor_url`` property.
You may override this property to modify the URL template.

The JWT_ will be signed with the client_secret configured for the backend, and the decoded token contains the following data::

    {
        "course_id": <course id>,
        "user": <user>,
        "iss": <issuer>,
        "jti": <JWT id>,
        "exp": <expiration time>
    }

By default, ``get_instructor_url`` returns this URL:

1. /api/v1/instructor/{client_id}/?jwt={jwt}

    This URL will provide information that can be used for four different dashboards.

    1. course instructor dashboard
        This dashboard is on the course level and may show an overview of proctored exams in a particular course. Note that the ``course_id`` will be
        contained in the JWT.

    2. exam instructor dashboard
        This dashboard is on the individual exam level and may show an overview of proctored exam attempts. Note that the ``course_id``
        and ``exam_id`` will be contained in the JWT.

    3. exam attempt instructor dashboard
        This dashboard is on the exam attempt level and may show violations for a particular proctored exam attempt. Note that the ``course_id``, ``exam_id``,
        and ``attempt_id`` will be contained in the JWT.

    4. exam configuration dashboard
        This dashboard should be used for configuring proctored exam options. Note that the ``course_id``, ``exam_id``, and ``config=true`` will be contained in the JWT.

If you wish to modify the aforementioned logic, override the ``get_instructor_url`` method of the ``edx_proctoring.backends.rest.BaseRestProctoringProvider`` class.

--------

Onboarding Status API Endpoint
------------------------------

A backend can also be configured to support an onboarding status API endpoint. This endpoint should return a learner's onboarding status and expiration according to the provider.

By default, this URL for this endpoint will be ``base_url + u'/api/v1/courses/{course_id}/onboarding_statuses'``, with the following optional query parameters:

    * ``user_id``: a string for the id of a specific user.
    * ``status``: a string representing the status that should be filtered for
    * ``page``: an int for the page requested
    * ``page_size``: an int for the page size requested

If the URL is supplied with a ``user_id``, only that user's attempt info will be returned. The data for a call to
``api/v1/courses/course-v1:edX+DemoX+Demo_Course/onboarding_statuses?user_id=abc123`` will look like::

    {
        'user_id': abc123,
        'status': {status},
        'expiration_date' : {expiration_date}
    }

If no ``user_id`` is provided, a list of attempts will be returned. This list can be filtered by the optional query parameters. The data returned for a call to
``api/v1/courses/course-v1:edX+DemoX+Demo_Course/onboarding_statuses?status=approved_in_course&page=2&page_size=3`` should look like::

    {
        results: [
            {
                user_id: {user_id},
                status: approved_in_course,
                expiration_date: {expiration_date}
            },
            {
                user_id: {user_id},
                status: approved_in_course,
                expiration_date: {expiration_date}
            },
            {
                user_id: {user_id},
                status: approved_in_course,
                expiration_date: {expiration_date}
            },

        ],
        count: {count},
        num_pages: {num_pages}
        next: 3
        previous: 1
    }

This URL can be accessed through the ``get_onboarding_attempts`` method of the ``edx_proctoring.backends.rest.BaseRestProctoringProvider`` class. If either the URL or the method need to be changed,
both can be overriden.

The following status strings can be filtered for or returned in Verificient's implementation::

    * approved-in-course
    * approved-in-different-course
    * rejected
    * expired
    * pending
    * no-profile

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

Javascript API
--------------

Several browser-level events are exposed from the LMS to proctoring
services via javascript. Proctoring services may optionally provide
handlers for these events as methods on an ES2015 class, e.g.::

  class ProctoringServiceHandler {
    onStartExamAttempt() {
      return Promise.resolve();
    }
    onEndExamAttempt() {
      return Promise.resolve();
    }
    onPing() {
      return Promise.resolve();
    }
  }

Each handler method should return a Promise which resolves upon
successful communication with the desktop application.
This class should be wrapped in ``@edx/edx-proctoring``'s
``handlerWrapper``, with the result exported as the main export of your
``npm`` package::

  import { handlerWrapper } from '@edx/edx-proctoring';
  ...
  export default handlerWrapper(ProctoringServiceHandler);


