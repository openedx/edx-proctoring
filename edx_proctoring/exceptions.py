"""
Specialized exceptions for the Notification subsystem
"""


class ProctoredBaseException(Exception):
    """
    A common base class for all exceptions
    """


class ProctoredExamAlreadyExists(ProctoredBaseException):
    """
    Raised when trying to create an Exam that already exists.
    """


class ProctoredExamNotFoundException(ProctoredBaseException):
    """
    Raised when a look up fails.
    """


class StudentExamAttemptAlreadyExistsException(ProctoredBaseException):
    """
    Raised when trying to start an exam when an Exam Attempt already exists.
    """


class StudentExamAttemptDoesNotExistsException(ProctoredBaseException):
    """
    Raised when trying to stop an exam attempt where the Exam Attempt doesn't exist.
    """


class StudentExamAttemptedAlreadyStarted(ProctoredBaseException):
    """
    Raised when the same exam attempt is being started twice
    """


class UserNotFoundException(ProctoredBaseException):
    """
    Raised when the user not found.
    """
