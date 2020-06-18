"Tests for generating webpack config json"

import json
import os
import os.path
import tempfile
import unittest

from mock import patch

from django.conf import settings

from edx_proctoring.apps import make_worker_config
from edx_proctoring.backends.tests.test_backend import TestBackendProvider


class TestWorkerConfig(unittest.TestCase):
    "Tests for generating webpack config json"

    def setUp(self):  # pylint: disable=super-method-not-called
        super(TestWorkerConfig, self).setUp()
        self.outfile = tempfile.mktemp(prefix='test-%d' % os.getpid())
        self.to_del = [self.outfile]

    def tearDown(self):  # pylint: disable=super-method-not-called
        for path in self.to_del:
            if os.path.exists(path):
                os.unlink(path)

    def _make_npm_module(self, package, main=None):
        "creates a fake 'npm module'"
        package_json = {
            'name': package
        }
        if main:
            package_json['main'] = main
            self.to_del.append(main)
        package_file = os.path.join(settings.NODE_MODULES_ROOT, package, 'package.json')
        try:
            os.makedirs(os.path.dirname(package_file))
        except OSError:
            pass
        with open(package_file, 'wb') as package_fp:
            package_fp.write(json.dumps(package_json).encode('utf-8'))
            self.to_del.append(package_file)
        return package

    def _check_outfile(self, expected):
        "checks that the outfile contains expected json"
        if expected is None:
            self.assertFalse(os.path.exists(self.outfile))
        else:
            with open(self.outfile, 'rb') as out_fp:
                data = json.loads(out_fp.read().decode('utf-8'))
                self.assertEqual(data, expected)

    def test_create_success(self):
        backend = TestBackendProvider()
        backend.npm_module = self._make_npm_module('success', 'foo/bar/baz.js')
        self.assertTrue(make_worker_config([backend], self.outfile))
        self._check_outfile(
            {'success': [
                'babel-polyfill',
                '/tmp/test-proctoring-modules/success/foo/bar/baz.js'
            ]}
        )

    def test_not_defined(self):
        backend = TestBackendProvider()
        self.assertFalse(make_worker_config([backend], self.outfile))
        self._check_outfile(None)

    def test_no_main(self):
        backend = TestBackendProvider()
        backend.npm_module = self._make_npm_module('no-main')
        self.assertFalse(make_worker_config([backend], self.outfile))
        self._check_outfile(None)

    def test_no_module(self):
        backend = TestBackendProvider()
        backend.npm_module = 'test-1234'
        self.assertFalse(make_worker_config([backend], self.outfile))
        self._check_outfile(None)

    def test_no_permission(self):
        self.outfile = '/etc/workers-test.json'
        backend = TestBackendProvider()
        backend.npm_module = self._make_npm_module('no-perm', 'foo/bar/baz.js')
        self.assertFalse(make_worker_config([backend], self.outfile))
        self._check_outfile(None)

    @patch('django.conf.settings.NODE_MODULES_ROOT', None)
    def test_no_setting(self):
        backend = TestBackendProvider()
        backend.npm_module = 'no-setting'
        self.assertFalse(make_worker_config([backend], self.outfile))
        self._check_outfile(None)
