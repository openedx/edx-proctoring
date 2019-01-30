"""
Monkeypatches the default backends
"""
from __future__ import absolute_import

import rules


def setup_test_backends():
    """
    Sets up the backend entrypoints required for testing.
    """
    from django.apps import apps
    config = apps.get_app_config('edx_proctoring')
    from edx_proctoring.backends.tests.test_backend import TestBackendProvider
    from edx_proctoring.backends.null import NullBackendProvider
    from edx_proctoring.backends.mock import MockProctoringBackendProvider
    config.backends['test'] = TestBackendProvider()
    config.backends['null'] = NullBackendProvider()
    config.backends['mock'] = MockProctoringBackendProvider()


def setup_test_perms():
    """
    Create missing permissions that would be defined in edx-platform,
    or elsewhere
    """
    rules.add_perm('accounts.can_retire_user', rules.is_staff)


setup_test_backends()
setup_test_perms()
