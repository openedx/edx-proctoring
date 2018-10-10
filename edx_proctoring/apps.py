# -*- coding: utf-8 -*-
"""
edx_proctoring Django application initialization.
"""

from __future__ import absolute_import

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from stevedore.extension import ExtensionManager


class EdxProctoringConfig(AppConfig):
    """
    Configuration for the edx_proctoring Django application.
    """

    name = 'edx_proctoring'

    def get_backend_choices(self):
        for extension in self.backends:
            yield extension.name, getattr(extension.plugin, 'human_readable_name', u'Unknown')

    def get_backend(self, name=None, options=None):
        """
        Returns an instance of the proctoring backend.

        :param str name: Name of entrypoint in openedx.proctoring
        :param dict options: Keyword arguments to use when instantiating the backend
        """
        config = getattr(settings, 'PROCTORING_BACKENDS', None)  # pylint: disable=literal-used-as-attribute
        if not config:
            raise ImproperlyConfigured("Settings not configured with PROCTORING_BACKENDS!")
        if name is None:
            try:
                name = config['DEFAULT']
            except KeyError:
                raise ImproperlyConfigured("No default proctoring backend set in settings.PROCTORING_BACKENDS")
        try:
            options = options or config[name]
            return self.backends[name].plugin(**options)
        except KeyError:
            raise NotImplementedError("No proctoring backend configured for '{}'.  "
                                      "Available: {} {}".format(name, self.backends.names(), config))

    def ready(self):
        """
        Loads the available proctoring backends
        """
        self.backends = ExtensionManager(namespace='openedx.proctoring')  # pylint: disable=W0201
