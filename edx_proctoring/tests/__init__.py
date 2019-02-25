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
    or elsewhere.

    edx-platform imports tests from edx-proctoring, which causes duplicate
    rules, so ignore the KeyError thrown by the rules package.
    """
    try:
        rules.add_perm('accounts.can_retire_user', rules.is_staff)
    except KeyError:
        pass
    try:
        rules.add_perm('edx_proctoring.can_take_proctored_exam', rules.is_authenticated)
    except KeyError:
        pass


setup_test_backends()
setup_test_perms()
