# -*- coding: utf-8 -*-
"""
edx_proctoring Django application initialization.
"""

from __future__ import absolute_import

import json
import os.path
import warnings

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from stevedore.extension import ExtensionManager


def make_worker_config(backends, out=os.path.join(settings.ENV_ROOT, 'workers.json')):
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
            with open(package_file, 'rb') as package_fp:
                package_json = json.load(package_fp)
            main_file = package_json['main']
            config[package] = ['babel-polyfill', os.path.join(settings.NODE_MODULES_ROOT, package, main_file)]
        except AttributeError:
            # no npm module defined
            continue
        except IOError:
            warnings.warn('Proctoring backend %s defined an npm module,'
                          'but it is not installed at %r' % (backend.__class__, package_file))
        except KeyError:
            warnings.warn('%r does not contain a `main` entry' % package_file)
    if config:
        with open(out, 'wb') as outfp:
            json.dump(config, outfp)
        return True
    return False


class EdxProctoringConfig(AppConfig):
    """
    Configuration for the edx_proctoring Django application.
    """

    name = u'edx_proctoring'
    plugin_app = {
        u'url_config': {
            u'lms.djangoapp': {
                u'namespace': u'edx_proctoring',
                u'regex': u'^api/',
                u'relative_path': u'urls',
            }
        },
        u'settings_config': {
            u'lms.djangoapp': {
                u'common': {'relative_path': u'settings.common'},
                u'aws': {'relative_path': u'settings.aws'},
            },
            u'cms.djangoapp': {
                u'common': {'relative_path': u'settings.common'},
                u'aws': {'relative_path': u'settings.aws'},
            }

        },
    }

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
        make_worker_config(self.backends.values())
