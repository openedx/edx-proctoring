"""
Runtime services that the LMS can register than we can callback on
"""

_RUNTIME_SERVICES = {}


def set_runtime_service(name, callback):
    """
    Adds a service provided by the runtime (aka LMS) to our directory
    """

    _RUNTIME_SERVICES[name] = callback


def get_runtime_service(name):
    """
    Returns a registered runtime service, None if no match is found
    """

    return _RUNTIME_SERVICES.get(name)
