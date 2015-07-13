"""
Various callback paths
"""

from django.template import Context, loader
from django.http import HttpResponse

from edx_proctoring.exceptions import StudentExamAttemptDoesNotExistsException

from edx_proctoring.api import (
    start_exam_attempt_by_code,
)


def start_exam_callback(request, attempt_code):  # pylint: disable=unused-argument
    """
    A callback endpoint which is called when SoftwareSecure completes
    the proctoring setup and the exam should be started.

    NOTE: This returns HTML as it will be displayed in an embedded browser

    This is an authenticated endpoint and the attempt_code is passed in
    as a query string parameter
    """

    # start the exam!
    try:
        start_exam_attempt_by_code(attempt_code)
    except StudentExamAttemptDoesNotExistsException:
        return HttpResponse(
            content='That exam code is not valid',
            status=404
        )

    template = loader.get_template('proctoring/proctoring_launch_callback.html')

    return HttpResponse(template.render(Context({})))
