"""
All supporting Proctoring backends
"""

from django.apps import apps


def get_backend_provider(exam=None, name=None):
    """
    Returns an instance of the configured backend provider
    Passing in an exam will return the backend for that exam
    Passing in a name will return the named backend
    """
    if exam:
        if 'is_proctored' in exam and not exam['is_proctored']:
            # timed exams don't have a backend
            return None
        if exam['backend']:
            name = exam['backend']
    return apps.get_app_config('edx_proctoring').get_backend(name=name)
