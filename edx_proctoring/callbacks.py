"""
Various callback paths
"""

import logging
from django.template import Context, loader
from django.http import HttpResponse

from rest_framework.views import APIView
from rest_framework.response import Response

from edx_proctoring.api import (
    get_exam_attempt_by_code,
    mark_exam_attempt_as_ready,
)

from edx_proctoring.backends import get_backend_provider

log = logging.getLogger(__name__)


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
            content='You have entered an exam code that is not valid.',
            status=404
        )

    mark_exam_attempt_as_ready(attempt['proctored_exam']['id'], attempt['user']['id'])

    template = loader.get_template('proctoring/proctoring_launch_callback.html')

    return HttpResponse(template.render(Context({})))


class ExamReviewCallback(APIView):
    """
    This endpoint is called by a 3rd party proctoring review service when
    there are results available for us to record
    """

    def post(self, request):
        """
        Post callback handler
        """
        provider = get_backend_provider()

        # call down into the underlying provider code
        provider.on_review_callback(request.DATA)

        return Response(
            data='OK',
            status=200
        )
