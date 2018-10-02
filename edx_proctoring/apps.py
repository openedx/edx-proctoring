# -*- coding: utf-8 -*-
"""
edx_proctoring Django application initialization.
"""

from __future__ import absolute_import

from collections import OrderedDict
from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from stevedore.extension import ExtensionManager


class EdxProctoringConfig(AppConfig):
    """
    Configuration for the edx_proctoring Django application.
    """

    name = 'edx_proctoring'

    def get_backend(self, name=None, options=None):
        """
        Returns an instance of the proctoring backend.

        :param str name: Name of entrypoint in openedx.proctoring
        :param dict options: Keyword arguments to use when instantiating the backend
        """
        config = getattr(settings, 'PROCTORING_BACKEND_PROVIDERS', None)  # pylint: disable=literal-used-as-attribute
        if not config:
            raise ImproperlyConfigured("Settings not configured with PROCTORING_BACKEND_PROVIDERS!")
        if name is None:
            try:
                name = config['DEFAULT']
            except KeyError:
                raise ImproperlyConfigured("No default proctoring backend set in settings.PROCTORING_BACKEND_PROVIDERS")
        try:
            options = options or config[name]
            return self.backends[name].plugin(**options)
        except KeyError:
            raise NotImplementedError("No proctoring backend configured for '{}'.  "\
                "Available: {} {}".format(name, self.backends.names(), config))

    def ready(self):
        """
        Loads the available proctoring backends
        """
        self.backends = ExtensionManager(namespace='openedx.proctoring')
