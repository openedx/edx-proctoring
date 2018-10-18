# -*- coding: utf-8 -*-
"""
edx_proctoring Django application initialization.
"""

from __future__ import absolute_import

import logging

from django.apps import AppConfig
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from stevedore.extension import ExtensionManager

log = logging.getLogger(__name__)


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
        for extension in self.backends:
            yield extension.name, getattr(extension.plugin, 'verbose_name', u'Unknown')

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

    def create_oauth_credentials(self, name):
        from oauth2_provider.models import get_application_model
        from django.db.utils import IntegrityError
        Application = get_application_model()
        User = get_user_model()
        username = 'proctor_api_%s' % name
        try:
            auth_user = User.objects.create_user(username)
        except IntegrityError:
            auth_user = User.objects.get(username=username)
        app, created = Application.objects.get_or_create(
                name='Proctor %s' % name,
                user=auth_user,
                client_type='confidential',
                authorization_grant_type='client-credentials'
            )
        return app.client_id, app.client_secret, username, created

    def ready(self):
        """
        Loads the available proctoring backends
        """
        self.backends = ExtensionManager(namespace='openedx.proctoring')  # pylint: disable=W0201
        for extension in self.backends:
            if getattr(extension.plugin, 'needs_oauth', False):
                client_id, client_secret, user, created = self.create_oauth_credentials(extension.name)
                if created:
                    log.debug("Created oauth credentials for %s: %s %s", extension.name, client_id, client_secret)

