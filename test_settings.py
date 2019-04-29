"""
These settings are here to use during tests, because Django requires them.

In a real-world use case, apps in this project are installed into other
Django applications, so these settings will not be used.
"""

from __future__ import absolute_import, unicode_literals

import sys


# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
BASE_DIR = os.path.dirname(__file__)

ENV_ROOT = os.path.dirname(BASE_DIR)

DEBUG=True
TEST_MODE=True
TEST_ROOT = "tests"
TRANSACTIONS_MANAGED = {}
USE_TZ = True
TIME_ZONE = 'UTC'
SECRET_KEY='SHHHHHH'
PLATFORM_NAME='Open edX'
FEATURES = {}
HTTPS = 'off'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'edx_proctoring.db'),
    },
}

SITE_ID = 1
SITE_NAME = 'localhost:8000'

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'edx_proctoring',
    'edx_when',
    'rules.apps.AutodiscoverRulesConfig',
    'waffle',
)

AUTHENTICATION_BACKENDS = [
    'rules.permissions.ObjectPermissionBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.6/howto/static-files/

STATIC_URL = '/static/'

REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.UserRateThrottle',
    ),
}

if not TEST_MODE:
    # we don't want to throttle unit tests
    REST_FRAMEWORK.update({
        'DEFAULT_THROTTLE_RATES': {
            'user': '10/sec',
        }
    })

MIDDLEWARE = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
)

ROOT_URLCONF = 'test_urls'

COURSE_ID_REGEX = r'[^/+]+(/|\+)[^/+]+(/|\+)[^/]+'
COURSE_ID_PATTERN = r'(?P<course_id>%s)' % COURSE_ID_REGEX

PROCTORING_BACKENDS = {
    'test': {},
    'null': {},
    'DEFAULT': 'test',
    'software_secure': {
        "secret_key_id": "foo",
        "secret_key": "4B230FA45A6EC5AE8FDE2AFFACFABAA16D8A3D0B",
        "crypto_key": "123456789123456712345678",
        "exam_register_endpoint": "http://test",
        "organization": "edx",
        "exam_sponsor": "edX LMS",
        "software_download_url": "http://example.com",
        "send_email": True
    },
}

PROCTORING_SETTINGS = {
    'MUST_COMPLETE_ICRV': True,
    'LINK_URLS': {
        'online_proctoring_rules': '',
        'faq': '',
        'contact_us': '',
        'tech_requirements': '',
    },
    'ALLOW_CALLBACK_SIMULATION': False
}

WEBPACK_LOADER={
    'WORKERS': {
        'BUNDLE_DIR_NAME': 'bundles/',
        'STATS_FILE': 'webpack-worker-stats.json'
    }
}

DEFAULT_FROM_EMAIL = 'no-reply@example.com'
CONTACT_EMAIL = 'info@edx.org'
TECH_SUPPORT_EMAIL = 'technical@example.com'

########## TEMPLATE CONFIGURATION
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'APP_DIRS': True,
}]
########## END TEMPLATE CONFIGURATION

NODE_MODULES_ROOT = '/tmp/test-proctoring-modules'
