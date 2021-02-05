"""
Helpers for the HTTP APIs
"""

import hashlib
import hmac
import logging
from datetime import datetime, timedelta

import pytz
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from edx_when import api as when_api
from eventtracking import tracker
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from django.conf import settings
from django.utils.translation import ugettext as _

from edx_proctoring.models import ProctoredExamStudentAttempt, ProctoredExamStudentAttemptHistory
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus

log = logging.getLogger(__name__)


class AuthenticatedAPIView(APIView):
    """
    Authenticate APi View.
    """
    authentication_classes = (SessionAuthentication, JwtAuthentication)
    permission_classes = (IsAuthenticated,)


def get_time_remaining_for_attempt(attempt):
    """
    Returns the remaining time (in seconds) on an attempt
    """

    # returns 0 if the attempt has not been started yet.
    if attempt['started_at'] is None:
        return 0

    # need to adjust for allowances
    expires_at = attempt['started_at'] + timedelta(minutes=attempt['allowed_time_limit_mins'])

    now_utc = datetime.now(pytz.UTC)

    if expires_at > now_utc:
        time_remaining_seconds = (expires_at - now_utc).total_seconds()
    else:
        time_remaining_seconds = 0

    return time_remaining_seconds


def humanized_time(time_in_minutes):
    """
    Converts the given value in minutes to a more human readable format
    1 -> 1 Minute
    2 -> 2 Minutes
    60 -> 1 hour
    90 -> 1 hour and 30 Minutes
    120 -> 2 hours
    """
    hours = int(time_in_minutes / 60)
    minutes = time_in_minutes % 60

    hours_present = False
    if hours == 0:
        hours_present = False
        template = ""
    elif hours == 1:
        template = _(u"{num_of_hours} hour")
        hours_present = True
    elif hours >= 2:
        template = _(u"{num_of_hours} hours")
        hours_present = True
    else:
        template = "error"

    if template != "error":
        if minutes == 0:
            if not hours_present:
                template = _(u"{num_of_minutes} minutes")
        elif minutes == 1:
            if hours_present:
                template += _(u" and {num_of_minutes} minute")
            else:
                template += _(u"{num_of_minutes} minute")
        else:
            if hours_present:
                template += _(u" and {num_of_minutes} minutes")
            else:
                template += _(u"{num_of_minutes} minutes")

    human_time = template.format(num_of_hours=hours, num_of_minutes=minutes)
    return human_time


def locate_attempt_by_attempt_code(attempt_code):
    """
    Helper method to look up an attempt by attempt_code. This can be either in
    the ProctoredExamStudentAttempt *OR* ProctoredExamStudentAttemptHistory tables
    we will return a tuple of (attempt, is_archived_attempt)
    """
    attempt_obj = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_code(attempt_code)

    if not attempt_obj:
        # try archive table
        attempt_obj = ProctoredExamStudentAttemptHistory.get_exam_attempt_by_code(attempt_code)

        if not attempt_obj:
            # still can't find, error out
            err_msg = (
                u'Could not locate attempt_code: {attempt_code}'.format(attempt_code=attempt_code)
            )
            log.error(err_msg)
            is_archived = None
        else:
            is_archived = True
    else:
        is_archived = False
    return attempt_obj, is_archived


def emit_event(exam, event_short_name, attempt=None, override_data=None):
    """
    Helper method to emit an analytics event
    """

    exam_type = (
        'timed' if not exam['is_proctored'] else
        ('practice' if exam['is_practice_exam'] else 'proctored')
    )

    # establish baseline schema for event 'context'
    context = {
        'course_id': exam['course_id']
    }

    # establish baseline schema for event 'data'
    data = {
        'exam_id': exam['id'],
        'exam_content_id': exam['content_id'],
        'exam_name': exam['exam_name'],
        'exam_default_time_limit_mins': exam['time_limit_mins'],
        'exam_is_proctored': exam['is_proctored'],
        'exam_is_practice_exam': exam['is_practice_exam'],
        'exam_is_active': exam['is_active']
    }

    if attempt:
        # if an attempt is passed in then use that to add additional baseline
        # schema elements

        # let's compute the relative time we're firing the event
        # compared to the start time, if the attempt has already started.
        # This can be used to determine how far into an attempt a given
        # event occured (e.g. "time to complete exam")
        attempt_event_elapsed_time_secs = (
            (datetime.now(pytz.UTC) - attempt['started_at']).total_seconds() if attempt['started_at'] else
            None
        )

        attempt_data = {
            'attempt_id': attempt['id'],
            'attempt_user_id': attempt['user']['id'],
            'attempt_started_at': attempt['started_at'],
            'attempt_completed_at': attempt['completed_at'],
            'attempt_code': attempt['attempt_code'],
            'attempt_allowed_time_limit_mins': attempt['allowed_time_limit_mins'],
            'attempt_status': attempt['status'],
            'attempt_event_elapsed_time_secs': attempt_event_elapsed_time_secs
        }
        data.update(attempt_data)
        name = '.'.join(['edx', 'special_exam', exam_type, 'attempt', event_short_name])
    else:
        name = '.'.join(['edx', 'special_exam', exam_type, event_short_name])

    # allow caller to override event data
    if override_data:
        data.update(override_data)

    _emit_event(name, context, data)


def _emit_event(name, context, data):
    """
    Do the actual integration into the event-tracker
    """

    try:
        if context:
            # try to parse out the org_id from the course_id
            if 'course_id' in context:
                try:
                    course_key = CourseKey.from_string(context['course_id'])
                    context['org_id'] = course_key.org
                except InvalidKeyError:
                    # leave org_id blank
                    pass

            with tracker.get_tracker().context(name, context):
                tracker.emit(name, data)
        else:
            # if None is passed in then we don't construct the 'with' context stack
            tracker.emit(name, data)
    except KeyError:
        # This happens when a default tracker has not been registered by the host application
        # aka LMS. This is normal when running unit tests in isolation.
        log.warning(
            u'Analytics tracker not properly configured. '
            u'If this message appears in a production environment, please investigate'
        )


def obscured_user_id(user_id, *extra):
    """
    Obscures the user id, returning a sha1 hash
    Any extra information can be added to the hash
    """
    obs_hash = hmac.new(settings.PROCTORING_USER_OBFUSCATION_KEY.encode('ascii'), digestmod=hashlib.sha1)
    obs_hash.update(str(user_id).encode('utf-8'))
    obs_hash.update(b''.join(str(ext).encode('utf-8') for ext in extra))
    return obs_hash.hexdigest()


def has_due_date_passed(due_datetime):
    """
    Return True if due date is lesser than current datetime, otherwise False
    and if due_datetime is None then we don't have to consider the due date for return False
    """

    if due_datetime:
        return due_datetime <= datetime.now(pytz.UTC)
    return False


def get_exam_due_date(exam, user=None):
    """
    Return the due date for the exam.
    Uses edx_when to lookup the date for the subsection.
    """
    due_date = when_api.get_date_for_block(exam['course_id'], exam['content_id'], 'due', user=user)
    return due_date or exam['due_date']


def verify_and_add_wait_deadline(context, exam, user_id):
    """
    Verify if the wait deadline should be added to template context.

    If the grace period is present and is valid after the exam
    has passed due date, for the given user, add the wait deadline to context. If the due
    date is not present, which happens for self-paced courses, no context
    update will take place.
    """
    exam_due_date = get_exam_due_date(exam, user_id)
    if not (context.get('grace_period', False) and exam_due_date):
        return False
    wait_deadline = exam_due_date + context['grace_period']
    if not has_due_date_passed(wait_deadline):
        context.update(
            {'wait_deadline': wait_deadline.isoformat()}
        )
        return True
    return False


def is_reattempting_exam(from_status, to_status):
    """
    Returns a boolean representing whether or not a user is trying to reattempt an exam.

    Given user's exam is in progress, and he is kicked out due to low bandwidth or
    closes the secure browser. Its expected that the user should not be able to restart
    the exam workflow.
    This behavior is being implemented due to edX's integrity constraints.
    """
    return (
        ProctoredExamStudentAttemptStatus.is_in_progress_status(from_status) and
        ProctoredExamStudentAttemptStatus.is_pre_started_status(to_status)
    )
