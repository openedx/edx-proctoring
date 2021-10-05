# -*- coding: utf-8 -*-
"""
edx_proctoring Django application initialization.
"""

import json
import os
import os.path
import warnings

from stevedore.extension import ExtensionManager

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

BACKEND_CONFIGURATION_ALLOW_LIST = [
    'base_url',
    'client_id',
    'client_secret',
    'crypto_key',
    'default_rules',
    'exam_register_endpoint',
    'exam_sponsor',
    'has_dashboard',
    'help_center_article_url',
    'integration_specific_email',
    'learner_notification_from_email',
    'needs_oauth',
    'organization',
    'passing_statuses',
    'ping_interval',
    'secret_key',
    'secret_key_id',
    'send_email',
    'software_download_url',
    'supports_onboarding',
    'tech_support_email',
    'tech_support_phone',
    'token_expiration_time',
    'verbose_name',
    'video_review_aes_key',
]


def make_worker_config(backends, out='/tmp/workers.json'):
    """
    Generates a config json file used for edx-platform's webpack.common.config.js
    """
    if not getattr(settings, 'NODE_MODULES_ROOT', None):
        return False
    config = {}
    for backend in backends:
        try:
            package = backend.npm_module
            package_file = os.path.join(settings.NODE_MODULES_ROOT, package, 'package.json')
            with open(package_file, 'r', encoding='utf-8') as package_fp:
                package_json = json.load(package_fp)
            main_file = package_json['main']
            config[package] = ['babel-polyfill', os.path.join(settings.NODE_MODULES_ROOT, package, main_file)]
        except AttributeError:
            # no npm module defined
            continue
        except IOError:
            warnings.warn(f'Proctoring backend {backend.__class__} defined an npm module,'
                          f'but it is not installed at {package_file!r}')
        except KeyError:
            warnings.warn(f'{package_file!r} does not contain a `main` entry')
    if config:
        try:
            with open(out, 'wb+') as outfp:
                outfp.write(json.dumps(config).encode('utf-8'))
        except IOError:
            warnings.warn(f"Could not write worker config to {out}")
        else:
            # make sure that this file is group writable, because it may be written by different users
            os.chmod(out, 0o664)
            return True
    return False


class EdxProctoringConfig(AppConfig):
    """
    Configuration for the edx_proctoring Django application.
    """

    name = 'edx_proctoring'
    plugin_app = {
        'url_config': {
            'lms.djangoapp': {
                'namespace': 'edx_proctoring',
                'regex': '^api/',
                'relative_path': 'urls',
            },
            'cms.djangoapp': {
                'namespace': 'edx_proctoring',
                'regex': '^api/',
                'relative_path': 'instructor_dashboard_exam_urls',
            },
        },
        'settings_config': {
            'lms.djangoapp': {
                'common': {'relative_path': 'settings.common'},
                'production': {'relative_path': 'settings.production'},
            },
            'cms.djangoapp': {
                'common': {'relative_path': 'settings.common'},
                'production': {'relative_path': 'settings.production'},
            }

        },
    }

    def get_backend_choices(self):
        """
        Returns an iterator of available backends:
        backend_name, verbose name
        """
        for name, backend in self.backends.items():
            yield name, getattr(backend, 'verbose_name', 'Unknown')

    def get_backend(self, name=None):
        """
        Returns an instance of the proctoring backend.

        :param str name: Name of entrypoint in openedx.proctoring
        :param dict options: Keyword arguments to use when instantiating the backend
        """
        if name is None:
            try:
                name = settings.PROCTORING_BACKENDS['DEFAULT']
            except (KeyError, AttributeError) as exc:
                raise ImproperlyConfigured("No default proctoring backend set in settings.PROCTORING_BACKENDS") \
                    from exc
        try:
            return self.backends[name]
        except KeyError as error:
            raise NotImplementedError(f"No proctoring backend configured for '{name}'.  "
                                      f"Available: {list(self.backends)}") from error

    def ready(self):
        """
        Loads the available proctoring backends
        """
        # pylint: disable=unused-import
        # pylint: disable=import-outside-toplevel
        from edx_proctoring import handlers, signals
        config = settings.PROCTORING_BACKENDS

        self.backends = {}  # pylint: disable=W0201
        for extension in ExtensionManager(namespace='openedx.proctoring'):
            name = extension.name
            try:
                options = {
                    key: val for (key, val) in config[name].items()
                    if key in BACKEND_CONFIGURATION_ALLOW_LIST
                }
                self.backends[name] = extension.plugin(**options)
            except KeyError:
                pass
        make_worker_config(list(self.backends.values()), out=os.path.join(settings.ENV_ROOT, 'workers.json'))
