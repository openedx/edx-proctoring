"""
All supporting Proctoring backends
"""

from importlib import import_module
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from opaque_keys.edx.keys import CourseKey

# Cached instance of backend provider
_BACKEND_PROVIDER = None

def get_provider_name_by_course_id(course_id):
    """
    Returns string name of proctoring_service
    """
    # for normal work tests
    from courseware.courses import get_course
    course_key = CourseKey.from_string(course_id)
    course = get_course(course_key)
    return course.proctoring_service


def _get_proctoring_config(provider_name):
    """
    Returns an dictionary of the configured backend provider that is configured
    via the settings file
    """

    proctors_config = getattr(settings, 'PROCTORING_BACKEND_PROVIDERS')
    if not proctors_config:
        raise ImproperlyConfigured("Settings not configured with PROCTORING_BACKEND_PROVIDERS!")
    if provider_name not in proctors_config:
        msg = (
            "Misconfigured PROCTORING_BACKEND_PROVIDERS settings, "
            "there is not '%s' provider specified" % provider_name
        )
        raise ImproperlyConfigured(msg)

    return proctors_config[provider_name]


def get_backend_provider(provider_name, emphemeral=True):
    """
    Returns an instance of the configured backend provider that is configured
    via the settings file
    """

    global _BACKEND_PROVIDER  # pylint: disable=global-statement

    provider = _BACKEND_PROVIDER
    if not _BACKEND_PROVIDER or emphemeral:
        config = _get_proctoring_config(provider_name)

        if 'class' not in config or 'options' not in config:
            msg = (
                "Misconfigured PROCTORING_BACKEND_PROVIDERS settings, "
                "must have both 'class' and 'options' keys."
            )
            raise ImproperlyConfigured(msg)

        module_path, _, name = config['class'].rpartition('.')
        class_ = getattr(import_module(module_path), name)

        provider = class_(**config['options'])

        if not emphemeral:
            _BACKEND_PROVIDER = provider

    return provider


def get_proctoring_settings(provider_name):
    config = _get_proctoring_config(provider_name)

    if 'settings' not in config:
        msg = ("Miscongfigured PROCTORING_BACKEND_PROVIDES settings,"
               "%s must contain 'settings' option" % provider_name
               )
        raise ImproperlyConfigured(msg)
    return config['settings']


def get_proctor_settings_param(proctor_settings, param, default=False):
    predefault = {
        'SITE_NAME': settings.SITE_NAME,
        'PLATFORM_NAME': settings.PLATFORM_NAME,
        'STATUS_EMAIL_FROM_ADDRESS': settings.DEFAULT_FROM_EMAIL,
        'CONTACT_EMAIL': getattr(settings, 'CONTACT_EMAIL'),
        'ALLOW_REVIEW_UPDATES': getattr(settings, 'ALLOW_REVIEW_UPDATES', True),
    }
    if param in predefault and not default:
        default = predefault[param]
    return proctor_settings.get(param, default)
