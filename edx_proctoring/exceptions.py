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


class ProctoredExamSoftwareSecureReviewNotFoundException(ProctoredBaseException):
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


class BackendProvideCannotRegisterAttempt(ProctoredBaseException):
    """
    Raised when a back-end provider cannot register an attempt
    """


class ProctoredExamPermissionDenied(ProctoredBaseException):
    """
    Raised when the calling user does not have access to the requested object.
    """


class ProctoredExamSuspiciousLookup(ProctoredBaseException):
    """
    Raised when a lookup on the student attempt table does not fully match
    all expected security keys
    """


class ProctoredExamReviewAlreadyExists(ProctoredBaseException):
    """
    Raised when a lookup on the student attempt table does not fully match
    all expected security keys
    """


class ProctoredExamBadReviewStatus(ProctoredBaseException):
    """
    Raised if we get an unexpected status back from the Proctoring attempt review status
    """


class ProctoredExamIllegalStatusTransition(ProctoredBaseException):
    """
    Raised if a state transition is not allowed, e.g. going from submitted to started
    """
