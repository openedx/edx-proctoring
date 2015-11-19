"""
Django settings file for local development purposes
"""
import sys


# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
BASE_DIR = os.path.dirname(__file__)

DEBUG=True
TEST_MODE=True
TEST_RUNNER = 'django_nose.NoseTestSuiteRunner'
TEST_ROOT = "tests"
TRANSACTIONS_MANAGED = {}
USE_TZ = True
TIME_ZONE = {}
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
    'django_nose',
)

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

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
)

ROOT_URLCONF = 'edx_proctoring.urls'

COURSE_ID_REGEX = r'[^/+]+(/|\+)[^/+]+(/|\+)[^/]+'
COURSE_ID_PATTERN = r'(?P<course_id>%s)' % COURSE_ID_REGEX

PROCTORING_BACKEND_PROVIDER = {
    "class": "edx_proctoring.backends.tests.test_backend.TestBackendProvider",
    "options": {}
}

PROCTORING_SETTINGS = {
    'MUST_BE_VERIFIED_TRACK': True,
    'MUST_COMPLETE_ICRV': True,
    'LINK_URLS': {
        'online_proctoring_rules': '',
        'faq': '',
        'contact_us': '',
        'tech_requirements': '',
    },
    'ALLOW_CALLBACK_SIMULATION': False
}

DEFAULT_FROM_EMAIL = 'no-reply@example.com'
CONTACT_EMAIL = 'info@edx.org'
