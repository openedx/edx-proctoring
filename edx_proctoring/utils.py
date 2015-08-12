"""
Helpers for the HTTP APIs
"""

import pytz
from datetime import datetime, timedelta

from django.utils.translation import ugettext as _
from rest_framework.views import APIView
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated


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
