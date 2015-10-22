"""
Helpers for the HTTP APIs
"""

import pytz
import logging
from datetime import datetime, timedelta

from django.utils.translation import ugettext as _
from rest_framework.views import APIView
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated

from edx_proctoring.models import (
    ProctoredExamStudentAttempt,
    ProctoredExamStudentAttemptHistory,
)
from edx_proctoring import constants
from edx_proctoring.runtime import get_runtime_service

log = logging.getLogger(__name__)


class AuthenticatedAPIView(APIView):
    """
    Authenticate APi View.
    """
    authentication_classes = (SessionAuthentication,)
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
        time_remaining_seconds = (expires_at - now_utc).seconds
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
        template = _("{num_of_hours} hour")
        hours_present = True
    elif hours >= 2:
        template = _("{num_of_hours} hours")
        hours_present = True
    else:
        template = "error"

    if template != "error":
        if minutes == 0:
            if not hours_present:
                template = _("{num_of_minutes} minutes")
        elif minutes == 1:
            if hours_present:
                template += _(" and {num_of_minutes} minute")
            else:
                template += _("{num_of_minutes} minute")
        else:
            if hours_present:
                template += _(" and {num_of_minutes} minutes")
            else:
                template += _("{num_of_minutes} minutes")

    human_time = template.format(num_of_hours=hours, num_of_minutes=minutes)
    return human_time


def locate_attempt_by_attempt_code(attempt_code):
    """
    Helper method to look up an attempt by attempt_code. This can be either in
    the ProctoredExamStudentAttempt *OR* ProctoredExamStudentAttemptHistory tables
    we will return a tuple of (attempt, is_archived_attempt)
    """
    attempt_obj = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_code(attempt_code)

    is_archived_attempt = False
    if not attempt_obj:
        # try archive table
        attempt_obj = ProctoredExamStudentAttemptHistory.get_exam_attempt_by_code(attempt_code)
        is_archived_attempt = True

        if not attempt_obj:
            # still can't find, error out
            err_msg = (
                'Could not locate attempt_code: {attempt_code}'.format(attempt_code=attempt_code)
            )
            log.error(err_msg)

    return (attempt_obj, is_archived_attempt)


def has_client_app_shutdown(attempt):
    """
    Returns True if the client app has shut down, False otherwise
    """

    # we never heard from the client, so it must not have started
    if not attempt['last_poll_timestamp']:
        return True

    elapsed_time = (datetime.now(pytz.UTC) - attempt['last_poll_timestamp']).total_seconds()
    return elapsed_time > constants.SOFTWARE_SECURE_SHUT_DOWN_GRACEPERIOD


def emit_event(short_name, context, data):
    """
    Helper method to emit an analytics event
    """

    name = '.'.join(['edx', 'edx-proctoring', 'exam', short_name])

    service = get_runtime_service('analytics')
    if service:
        service.emit_event(name, context, data)
    else:
        log.warn('Analytics event not configured. If this is a production environment, please resolve.')
