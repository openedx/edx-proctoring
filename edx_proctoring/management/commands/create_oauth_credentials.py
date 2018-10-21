"""
Django management command that creates Oauth credentials for installed REST backends
"""
import logging

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.utils import IntegrityError

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django Management command to create Oauth credentials for installed backends
    """

    def handle(self, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Management command entrypoint
        """
        config = apps.get_app_config('edx_proctoring')
        for extension in config.backends:
            if getattr(extension.plugin, 'needs_oauth', False):
                client_id, client_secret, user, created = self.create_oauth_credentials(extension.name)
                if created:
                    log.info("Created oauth credentials for %s: %s %s %s",
                             user, extension.name, client_id, client_secret)

    def create_oauth_credentials(self, name):
        """
        Automatically create oauth credentials for REST backends
        """
        username = 'proctor_api_%s' % name
        try:
            auth_user = get_user_model().objects.create_user(username)
        except IntegrityError:
            auth_user = get_user_model().objects.get(username=username)
        app, created = apps.get_model('oauth2_provider.Application').objects.get_or_create(
            name='Proctor %s' % name,
            user=auth_user,
            client_type='confidential',
            authorization_grant_type='client-credentials'
            )
        return app.client_id, app.client_secret, username, created
