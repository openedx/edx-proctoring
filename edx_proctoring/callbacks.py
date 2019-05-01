"""
Various callback paths that support callbacks from SoftwareSecure
"""

import logging
from waffle import switch_is_active
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
from django.urls import reverse, NoReverseMatch

from edx_proctoring.api import (
    get_exam_attempt_by_code,
    mark_exam_attempt_as_ready,
)
from edx_proctoring.constants import RPNOWV4_WAFFLE_NAME
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus

log = logging.getLogger(__name__)


def start_exam_callback(request, attempt_code):  # pylint: disable=unused-argument
    """
    A callback endpoint which is called when SoftwareSecure completes
    the proctoring setup and the exam should be started.

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
    else:
        log.warning("Attempted to enter proctored exam attempt {attempt_id} when status was {attempt_status}"
                    .format(
                        attempt_id=attempt['id'],
                        attempt_status=attempt['status'],
                    ))

    log.info("Exam %r has been marked as ready", attempt['proctored_exam']['id'])
    if switch_is_active(RPNOWV4_WAFFLE_NAME):
        course_id = attempt['proctored_exam']['course_id']
        content_id = attempt['proctored_exam']['content_id']

        exam_url = ''
        try:
            exam_url = reverse('jump_to', args=[course_id, content_id])
        except NoReverseMatch:
            log.exception("BLOCKING ERROR: Can't find course info url for course %s", course_id)
        response = HttpResponseRedirect(exam_url)
        response.set_signed_cookie('exam', attempt['attempt_code'])
        return response

    template = loader.get_template('proctored_exam/proctoring_launch_callback.html')

    return HttpResponse(
        template.render({
            'platform_name': settings.PLATFORM_NAME,
            'link_urls': settings.PROCTORING_SETTINGS.get('LINK_URLS', {})
        })
    )
