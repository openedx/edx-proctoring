"""
Helpers for the HTTP APIs
"""

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

    template = ""

    hours_present = False
    if hours == 0:
        hours_present = False
    elif hours == 1:
        template = _("{num_of_hours} Hour")
        hours_present = True
    elif hours >= 2:
        template = _("{num_of_hours} Hours")
        hours_present = True

    if minutes == 0:
        if not hours_present:
            template = _("{num_of_minutes} Minutes")
    elif minutes == 1:
        if hours_present:
            template += _(" and {num_of_minutes} Minute")
        else:
            template += _("{num_of_minutes} Minute")
    elif minutes >= 2:
        if hours_present:
            template += _(" and {num_of_minutes} Minutes")
        else:
            template += _("{num_of_minutes} Minutes")

    human_time = template.format(num_of_hours=hours, num_of_minutes=minutes)
    return human_time
