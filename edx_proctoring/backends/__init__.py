"""
All supporting Proctoring backends
"""

from importlib import import_module
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


# Cached instance of backend provider
_BACKEND_PROVIDER = None


def get_backend_provider():
    """
    Returns an instance of the configured backend provider that is configured
    via the settings file
    """

    global _BACKEND_PROVIDER  # pylint: disable=global-statement

    if not _BACKEND_PROVIDER:
        config = getattr(settings, 'PROCTORING_BACKEND_PROVIDER')
        if not config:
            raise ImproperlyConfigured("Settings not configured with PROCTORING_BACKEND_PROVIDER!")

        if 'class' not in config or 'options' not in config:
            msg = (
                "Misconfigured PROCTORING_BACKEND_PROVIDER settings, "
                "must have both 'class' and 'options' keys."
            )
            raise ImproperlyConfigured(msg)

        module_path, _, name = config['class'].rpartition('.')
        class_ = getattr(import_module(module_path), name)

        _BACKEND_PROVIDER = class_(**config['options'])

    return _BACKEND_PROVIDER
