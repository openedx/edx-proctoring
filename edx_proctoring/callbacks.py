"""
Various callback paths that support callbacks from SoftwareSecure
"""

import logging

from django.http import HttpResponse, HttpResponseRedirect
from django.urls import NoReverseMatch, reverse

from edx_proctoring.api import get_exam_attempt_by_code, mark_exam_attempt_as_ready, update_attempt_status
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
        log.warning(
            'attempt_code=%(attempt_code)s cannot be found.',
            {
                'attempt_code': attempt_code,
            }
        )
        return HttpResponse(
            content='You have entered an exam code that is not valid.',
            status=404
        )
    attempt_status = attempt['status']
    if attempt_status in [ProctoredExamStudentAttemptStatus.created,
                          ProctoredExamStudentAttemptStatus.download_software_clicked]:
        mark_exam_attempt_as_ready(attempt['id'])

    # if a user attempts to re-enter an exam that has not yet been submitted, submit the exam
    if ProctoredExamStudentAttemptStatus.is_in_progress_status(attempt_status):
        update_attempt_status(attempt['id'], ProctoredExamStudentAttemptStatus.submitted)
    else:
        log.warning(
            'Attempted to enter proctored exam attempt_id=%(attempt_id)s when status=%(attempt_status)s',
            {
                'attempt_id': attempt['id'],
                'attempt_status': attempt_status,
            }
        )

    course_id = attempt['proctored_exam']['course_id']
    content_id = attempt['proctored_exam']['content_id']

    exam_url = ''
    try:
        exam_url = reverse('jump_to', args=[course_id, content_id])
    except NoReverseMatch:
        log.exception("BLOCKING ERROR: Can't find course info url for course_id=%s", course_id)
    response = HttpResponseRedirect(exam_url)
    response.set_signed_cookie('exam', attempt['attempt_code'])
    return response
