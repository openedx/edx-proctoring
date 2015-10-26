"""
Lists of constants that can be used in the edX proctoring
"""

from django.conf import settings
import datetime


DEFAULT_SOFTWARE_SECURE_REVIEW_POLICY = (
    settings.PROCTORING_SETTINGS['DEFAULT_REVIEW_POLICY'] if
    'DEFAULT_REVIEW_POLICY' in settings.PROCTORING_SETTINGS
    else getattr(settings, 'DEFAULT_REVIEW_POLICY', 'Closed Book')
)

REQUIRE_FAILURE_SECOND_REVIEWS = (
    settings.PROCTORING_SETTINGS['REQUIRE_FAILURE_SECOND_REVIEWS'] if
    'REQUIRE_FAILURE_SECOND_REVIEWS' in settings.PROCTORING_SETTINGS
    else getattr(settings, 'REQUIRE_FAILURE_SECOND_REVIEWS', True)
)

SOFTWARE_SECURE_CLIENT_TIMEOUT = (
    settings.PROCTORING_SETTINGS['SOFTWARE_SECURE_CLIENT_TIMEOUT'] if
    'SOFTWARE_SECURE_CLIENT_TIMEOUT' in settings.PROCTORING_SETTINGS
    else getattr(settings, 'SOFTWARE_SECURE_CLIENT_TIMEOUT', 30)
)

SHUT_DOWN_GRACEPERIOD = (
    settings.PROCTORING_SETTINGS['SHUT_DOWN_GRACEPERIOD'] if
    'SHUT_DOWN_GRACEPERIOD' in settings.PROCTORING_SETTINGS
    else getattr(settings, 'SHUT_DOWN_GRACEPERIOD', 10)
)

MINIMUM_TIME = datetime.datetime.fromtimestamp(0)

ALLOW_REVIEW_UPDATES = (
    settings.PROCTORING_SETTINGS['ALLOW_REVIEW_UPDATES'] if
    'ALLOW_REVIEW_UPDATES' in settings.PROCTORING_SETTINGS
    else getattr(settings, 'ALLOW_REVIEW_UPDATES', False)
)

CLIENT_TIMEOUT = (
    settings.PROCTORING_SETTINGS['CLIENT_TIMEOUT'] if
    'CLIENT_TIMEOUT' in settings.PROCTORING_SETTINGS
    else getattr(settings, 'CLIENT_TIMEOUT', 30)
)

MINIMUM_TIME = datetime.datetime.fromtimestamp(0)

ALLOW_REVIEW_UPDATES = (
    settings.PROCTORING_SETTINGS['ALLOW_REVIEW_UPDATES'] if
    'ALLOW_REVIEW_UPDATES' in settings.PROCTORING_SETTINGS
    else getattr(settings, 'ALLOW_REVIEW_UPDATES', False)
)

CLIENT_TIMEOUT = (
    settings.PROCTORING_SETTINGS['CLIENT_TIMEOUT'] if
    'CLIENT_TIMEOUT' in settings.PROCTORING_SETTINGS
    else getattr(settings, 'CLIENT_TIMEOUT', 30)
)

MINIMUM_TIME = datetime.datetime.fromtimestamp(0)
