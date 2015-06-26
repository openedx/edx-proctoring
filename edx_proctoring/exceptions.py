"""
Specialized exceptions for the Notification subsystem
"""


class ProctoredExamAlreadyExists(Exception):
    """
    Generic exception when a look up fails. Since we are abstracting away the backends
    we need to catch any native exceptions and re-throw as a generic exception
    """


class ProctoredExamNotFoundException(Exception):
    """
    Generic exception when a look up fails. Since we are abstracting away the backends
    we need to catch any native exceptions and re-throw as a generic exception
    """


class StudentExamAttemptAlreadyExistsException(Exception):
    """
    Generic exception when a look up fails. Since we are abstracting away the backends
    we need to catch any native exceptions and re-throw as a generic exception
    """
