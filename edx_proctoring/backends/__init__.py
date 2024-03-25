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
    if name == 'lti_external':
        # `get_backend_provider()` is called in many places in edx-proctoring, so this filter for
        # LTI providers needs to be in this function. Not sure if this is the exact right place
        # Also not sure what I should return here
        return None
    return apps.get_app_config('edx_proctoring').get_backend(name=name)
    