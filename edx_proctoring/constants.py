"""
Lists of constants that can be used in the edX proctoring
"""

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
