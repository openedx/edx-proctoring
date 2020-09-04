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
    def __init__(self, *args):
        """ Init method of exception """
        ProctoredBaseException.__init__(self, u'The exam_id does not exist.', *args)


class ProctoredExamReviewPolicyNotFoundException(ProctoredBaseException):
    """
    Raised when a look up fails.
    """


class ProctoredExamReviewPolicyAlreadyExists(ProctoredBaseException):
    """
    Raised when trying to create an ProctoredExamReviewPolicy that already exists.
    """


class ProctoredExamNotActiveException(ProctoredBaseException):
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


class StudentExamAttemptOnPastDueProctoredExam(ProctoredBaseException):
    """
    Raised when trying to create attempt instance on past due proctored exam
    """


class UserNotFoundException(ProctoredBaseException):
    """
    Raised when the user not found.
    """


class AllowanceValueNotAllowedException(ProctoredBaseException):
    """
    Raised when the allowance value is not an non-negative integer
    """


class BackendProviderCannotRegisterAttempt(ProctoredBaseException):
    """
    Raised when a back-end provider cannot register an attempt
    """

    def __init__(self, content, http_status):
        """ Init method of exception """
        super(BackendProviderCannotRegisterAttempt, self).__init__(self, content)
        self.http_status = http_status


class BackendProviderSentNoAttemptID(BackendProviderCannotRegisterAttempt):
    """
    Raised when a back-end provider returns a JSON without exam ID
    in response to new exam attempt registration
    """


class BackendProviderOnboardingException(ProctoredBaseException):
    """
    Raised when a back-end provider cannot register an attempt
    because of missing/failed onboarding requirements
    """
    def __init__(self, status):
        """ Init method of exception """
        super(BackendProviderOnboardingException, self).__init__(self, status)
        self.status = status


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


class BackendProviderCannotRetireUser(ProctoredBaseException):
    """
    Raised when a back-end provider cannot retire a user
    """
