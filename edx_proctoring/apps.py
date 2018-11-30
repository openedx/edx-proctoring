# -*- coding: utf-8 -*-
"""
edx_proctoring Django application initialization.
"""

from __future__ import absolute_import

import warnings

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
        """
        Returns an iterator of available backends:
        backend_name, verbose name
        """
        for name, backend in self.backends.items():
            yield name, getattr(backend, 'verbose_name', u'Unknown')

    def get_backend(self, name=None):
        """
        Returns an instance of the proctoring backend.

        :param str name: Name of entrypoint in openedx.proctoring
        :param dict options: Keyword arguments to use when instantiating the backend
        """
        if name is None:
            try:
                name = settings.PROCTORING_BACKENDS['DEFAULT']
            except (KeyError, AttributeError):
                raise ImproperlyConfigured("No default proctoring backend set in settings.PROCTORING_BACKENDS")
        try:
            return self.backends[name]
        except KeyError:
            raise NotImplementedError("No proctoring backend configured for '{}'.  "
                                      "Available: {}".format(name, list(self.backends)))

    def ready(self):
        """
        Loads the available proctoring backends
        """
        config = settings.PROCTORING_BACKENDS

        self.backends = {}  # pylint: disable=W0201
        not_found = []
        for extension in ExtensionManager(namespace='openedx.proctoring'):
            name = extension.name
            try:
                options = config[name]
                self.backends[name] = extension.plugin(**options)
            except KeyError:
                not_found.append(name)
        if not_found:  # pragma: no branch
            warnings.warn("No proctoring backend configured for '{}'.  "
                          "Available: {}".format(not_found, list(self.backends)))
