"""
Specialized exceptions for the Notification subsystem
"""


class ProctoredExamAlreadyExists(Exception):
    """
    Raised when trying to create an Exam that already exists.
    """


class ProctoredExamNotFoundException(Exception):
    """
    Raised when a look up fails.
    """


class StudentExamAttemptAlreadyExistsException(Exception):
    """
    Raised when trying to start an exam when an Exam Attempt already exists.
    """


class StudentExamAttemptDoesNotExistsException(Exception):
    """
    Raised when trying to stop an exam attempt where the Exam Attempt doesn't exist.
    """
