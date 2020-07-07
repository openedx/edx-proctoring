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
            with open(package_file, 'r') as package_fp:
                package_json = json.load(package_fp)
            main_file = package_json['main']
            config[package] = ['babel-polyfill', os.path.join(settings.NODE_MODULES_ROOT, package, main_file)]
        except AttributeError:
            # no npm module defined
            continue
        except IOError:
            warnings.warn(u'Proctoring backend %s defined an npm module,'
                          u'but it is not installed at %r' % (backend.__class__, package_file))
        except KeyError:
            warnings.warn(u'%r does not contain a `main` entry' % package_file)
    if config:
        try:
            with open(out, 'wb+') as outfp:
                outfp.write(json.dumps(config).encode('utf-8'))
        except IOError:
            warnings.warn(u"Could not write worker config to %s" % out)
        else:
            # make sure that this file is group writable, because it may be written by different users
            os.chmod(out, 0o664)
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
            },
            u'cms.djangoapp': {
                u'namespace': u'edx_proctoring',
                u'regex': u'^api/',
                u'relative_path': u'instructor_dashboard_exam_urls',
            },
        },
        u'settings_config': {
            u'lms.djangoapp': {
                u'common': {'relative_path': u'settings.common'},
                u'production': {'relative_path': u'settings.production'},
            },
            u'cms.djangoapp': {
                u'common': {'relative_path': u'settings.common'},
                u'production': {'relative_path': u'settings.production'},
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
                raise ImproperlyConfigured(u"No default proctoring backend set in settings.PROCTORING_BACKENDS")
        try:
            return self.backends[name]
        except KeyError:
            raise NotImplementedError(u"No proctoring backend configured for '{}'.  "
                                      u"Available: {}".format(name, list(self.backends)))

    def ready(self):
        """
        Loads the available proctoring backends
        """
        # pylint: disable=unused-import
        # pylint: disable=import-outside-toplevel
        from edx_proctoring import signals
        config = settings.PROCTORING_BACKENDS

        self.backends = {}  # pylint: disable=W0201
        for extension in ExtensionManager(namespace='openedx.proctoring'):
            name = extension.name
            try:
                options = config[name]
                self.backends[name] = extension.plugin(**options)
            except KeyError:
                pass
        make_worker_config(list(self.backends.values()), out=os.path.join(settings.ENV_ROOT, 'workers.json'))
