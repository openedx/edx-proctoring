"""
Monkeypatches the extension manager to add the default backends
"""
from stevedore.extension import ExtensionManager, Extension


def setup_test_backends():
    """
    Sets up the backend entrypoints required for testing.
    """
    from django.apps import apps
    config = apps.get_app_config('edx_proctoring')
    if not getattr(config, '_mock_testing', None):
        from edx_proctoring.backends.tests.test_backend import TestBackendProvider
        from edx_proctoring.backends.null import NullBackendProvider
        from edx_proctoring.backends.mock import MockProctoringBackendProvider
        from edx_proctoring.backends.software_secure import SoftwareSecureBackendProvider
        extensions = [
            Extension('test', 'openedx.proctoring', TestBackendProvider, None),
            Extension('null', 'openedx.proctoring', NullBackendProvider, None),
            Extension('mock', 'openedx.proctoring', MockProctoringBackendProvider, None),
            Extension('software_secure', 'openedx.proctoring', SoftwareSecureBackendProvider, None)
        ]

        config.backends = ExtensionManager.make_test_instance(extensions)
        config._mock_testing = True  # pylint: disable=protected-access


setup_test_backends()
