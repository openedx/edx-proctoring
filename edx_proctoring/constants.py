"""
Lists of constants that can be used in the edX proctoring
"""

from __future__ import absolute_import

import datetime

from django.conf import settings

SITE_NAME = (
    settings.PROCTORING_SETTINGS['SITE_NAME'] if
    'SITE_NAME' in settings.PROCTORING_SETTINGS else settings.SITE_NAME
)

PLATFORM_NAME = (
    settings.PROCTORING_SETTINGS['PLATFORM_NAME'] if
    'PLATFORM_NAME' in settings.PROCTORING_SETTINGS else settings.PLATFORM_NAME
)

FROM_EMAIL = (
    settings.PROCTORING_SETTINGS['STATUS_EMAIL_FROM_ADDRESS'] if
    'STATUS_EMAIL_FROM_ADDRESS' in settings.PROCTORING_SETTINGS else settings.DEFAULT_FROM_EMAIL
)

# Note that CONTACT_EMAIL is not defined in Studio runtimes
CONTACT_EMAIL = (
    settings.PROCTORING_SETTINGS['CONTACT_EMAIL'] if
    'CONTACT_EMAIL' in settings.PROCTORING_SETTINGS else getattr(settings, 'CONTACT_EMAIL', FROM_EMAIL)
)

ALLOW_REVIEW_UPDATES = (
    settings.PROCTORING_SETTINGS['ALLOW_REVIEW_UPDATES'] if
    'ALLOW_REVIEW_UPDATES' in settings.PROCTORING_SETTINGS else getattr(settings, 'ALLOW_REVIEW_UPDATES', True)
)

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

SOFTWARE_SECURE_SHUT_DOWN_GRACEPERIOD = (
    settings.PROCTORING_SETTINGS['SOFTWARE_SECURE_SHUT_DOWN_GRACEPERIOD'] if
    'SOFTWARE_SECURE_SHUT_DOWN_GRACEPERIOD' in settings.PROCTORING_SETTINGS
    else getattr(settings, 'SOFTWARE_SECURE_SHUT_DOWN_GRACEPERIOD', 10)
)

MINIMUM_TIME = datetime.datetime.fromtimestamp(0)

DEFAULT_DESKTOP_APPLICATION_PING_INTERVAL_SECONDS = 60

PING_FAILURE_PASSTHROUGH_TEMPLATE = 'edx_proctoring.{}_ping_failure_passthrough'
