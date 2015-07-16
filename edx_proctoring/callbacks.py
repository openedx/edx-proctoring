"""
Various callback paths
"""

from django.template import Context, loader
from django.http import HttpResponse

from edx_proctoring.api import (
    get_exam_attempt_by_code,
    mark_exam_attempt_as_ready,
)


def start_exam_callback(request, attempt_code):  # pylint: disable=unused-argument
    """
    A callback endpoint which is called when SoftwareSecure completes
    the proctoring setup and the exam should be started.

    NOTE: This returns HTML as it will be displayed in an embedded browser

    This is an authenticated endpoint and the attempt_code is passed in
    as a query string parameter
    """

    attempt = get_exam_attempt_by_code(attempt_code)
    if not attempt:
        return HttpResponse(
            content='That exam code is not valid',
            status=404
        )

    mark_exam_attempt_as_ready(attempt['proctored_exam']['id'], attempt['user']['id'])

    template = loader.get_template('proctoring/proctoring_launch_callback.html')

    return HttpResponse(template.render(Context({})))
