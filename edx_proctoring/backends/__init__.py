"""
All supporting Proctoring backends
"""
from django.apps import apps


def get_backend_provider(exam=None):
    """
    Returns an instance of the configured backend provider
    """
    backend_name = None
    if exam:
        if 'is_proctored' in exam and not exam['is_proctored']:
            # timed exams don't have a backend
            return None
        elif exam['backend']:
            backend_name = exam['backend']
    return apps.get_app_config('edx_proctoring').get_backend(name=backend_name)
