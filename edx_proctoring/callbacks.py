"""
Various callback paths that support callbacks from SoftwareSecure
"""

import logging
from django.template import loader
from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import reverse

from edx_proctoring.api import (
    get_exam_attempt_by_code,
    mark_exam_attempt_as_ready,
)
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus

log = logging.getLogger(__name__)


def start_exam_callback(request, attempt_code):  # pylint: disable=unused-argument
    """
    A callback endpoint which is called when SoftwareSecure completes
    the proctoring setup and the exam should be started.

    NOTE: This returns HTML as it will be displayed in an embedded browser

    This is an authenticated endpoint and the attempt_code is passed in
    as part of the URL path

    IMPORTANT: This is an unauthenticated endpoint, so be VERY CAREFUL about extending
    this endpoint
    """

    attempt = get_exam_attempt_by_code(attempt_code)
    if not attempt:
        log.warning("Attempt code %r cannot be found.", attempt_code)
        return HttpResponse(
            content='You have entered an exam code that is not valid.',
            status=404
        )

    if attempt['status'] in [ProctoredExamStudentAttemptStatus.created,
                             ProctoredExamStudentAttemptStatus.download_software_clicked]:
        mark_exam_attempt_as_ready(attempt['proctored_exam']['id'], attempt['user']['id'])

    log.info("Exam %r has been marked as ready", attempt['proctored_exam']['id'])

    course_id = attempt['proctored_exam']['course_id']
    content_id = attempt['proctored_exam']['content_id']

    exam_url = reverse('jump_to', args=[course_id, content_id])

    return HttpResponseRedirect(exam_url)
