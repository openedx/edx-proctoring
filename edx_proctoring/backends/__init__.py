"""
All supporting Proctoring backends
"""
from django.apps import apps


def get_backend_provider(exam=None):
    """
    Returns an instance of the configured backend provider
    """
    backend_name = None
    options = {}
    if exam and exam['backend']:
        backend_name = exam['backend']
    return apps.get_app_config('edx_proctoring').get_backend(name=backend_name, options=options)
