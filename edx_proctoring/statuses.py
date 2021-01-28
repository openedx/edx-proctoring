"""
Status enums for edx-proctoring
"""

from edx_proctoring.exceptions import ProctoredExamBadReviewStatus


class ProctoredExamStudentAttemptStatus:
    """
    A class to enumerate the various status that an attempt can have

    IMPORTANT: Since these values are stored in a database, they are system
    constants and should not be language translated, since translations
    might change over time.
    """

    # the student is eligible to decide if he/she wants to pursue credit
    eligible = 'eligible'

    # the attempt record has been created, but the exam has not yet
    # been started
    created = 'created'

    # the student has clicked on the external
    # software download link
    download_software_clicked = 'download_software_clicked'

    # the attempt is ready to start but requires
    # user to acknowledge that he/she wants to start the exam
    ready_to_start = 'ready_to_start'

    # the student has started the exam and is
    # in the process of completing the exam
    started = 'started'

    # the student has completed the exam
    ready_to_submit = 'ready_to_submit'

    #
    # The follow statuses below are considered in a 'completed' state
    # and we will not allow transitions to status above this mark
    #

    # the student declined to take the exam as a proctored exam
    declined = 'declined'

    # the exam has timed out
    timed_out = 'timed_out'

    # the student has submitted the exam for proctoring review
    submitted = 'submitted'

    # the student has submitted the exam for proctoring review
    second_review_required = 'second_review_required'

    # the exam has been verified and approved
    verified = 'verified'

    # the exam has been rejected
    rejected = 'rejected'

    # the exam is believed to be in error
    error = 'error'

    # the course end date has passed
    expired = 'expired'

    # the learner is ready to resume their errored proctored exam
    ready_to_resume = 'ready_to_resume'

    # the exam has been resumed and new attempt has been created
    resumed = 'resumed'

    # the onboarding attempt has been reset
    onboarding_reset = 'onboarding_reset'

    # onboarding failure states
    # the user hasn't taken an onboarding exam
    onboarding_missing = 'onboarding_missing'
    # the onboarding exam is pending review
    onboarding_pending = 'onboarding_pending'
    # the user failed onboarding
    onboarding_failed = 'onboarding_failed'
    # the onboarding data expired
    onboarding_expired = 'onboarding_expired'

    onboarding_errors = (onboarding_missing, onboarding_pending, onboarding_failed, onboarding_expired)

    @classmethod
    def is_completed_status(cls, status):
        """
        Returns a boolean if the passed in status is in a "completed" state, meaning
        that it cannot go backwards in state
        """
        return status in [
            cls.declined, cls.timed_out, cls.submitted, cls.second_review_required,
            cls.verified, cls.rejected, cls.error, cls.ready_to_resume, cls.resumed,
            cls.onboarding_missing, cls.onboarding_pending, cls.onboarding_failed, cls.onboarding_expired
        ]

    @classmethod
    def is_incomplete_status(cls, status):
        """
        Returns a boolean if the passed in status is in an "incomplete" state.
        """
        return status in [
            cls.eligible, cls.created, cls.download_software_clicked, cls.ready_to_start, cls.started,
            cls.ready_to_submit
        ]

    @classmethod
    def needs_credit_status_update(cls, to_status):
        """
        Returns a boolean if the passed in to_status calls for an update to the credit requirement status.
        """
        return to_status in [
            cls.verified, cls.rejected, cls.declined, cls.submitted, cls.error
        ]

    @classmethod
    def needs_grade_override(cls, to_status):
        """
        Returns a boolean if the passed in to_status calls for an override of the learner's grade.
        """
        return to_status in [
            cls.rejected
        ]

    @classmethod
    def is_a_cascadable_failure(cls, to_status):
        """
        Returns a boolean if the passed in to_status has a failure that needs to be cascaded
        to other unattempted exams.
        """
        return to_status in [
            cls.declined
        ]

    @classmethod
    def is_valid_status(cls, status):
        """
        Makes sure that passed in status string is valid
        """
        return cls.is_completed_status(status) or cls.is_incomplete_status(status)

    @classmethod
    def is_pre_started_status(cls, status):
        """
        Returns a boolean if the status passed is prior to "started" state.
        """
        return status in [
            cls.created, cls.download_software_clicked, cls.ready_to_start
        ]

    @classmethod
    def is_in_progress_status(cls, status):
        """
        Returns a boolean if the status passed is "in progress".
        """
        return status in [
            cls.started, cls.ready_to_submit
        ]

    @classmethod
    def is_resume_status(cls, status):
        """
        Returns a boolean if the status passed is "resumed" or "ready to resume"
        """
        return status in [
            cls.ready_to_resume, cls.resumed
        ]


class ReviewStatus:
    """
    Standard review statuses
    """
    passed = u'passed'
    violation = u'violation'
    suspicious = u'suspicious'
    not_reviewed = u'not_reviewed'

    @classmethod
    def validate(cls, status):
        """
        Validate review status
        """
        if status not in (cls.passed, cls.violation, cls.suspicious, cls.not_reviewed):
            raise ProctoredExamBadReviewStatus(status)
        return True


class SoftwareSecureReviewStatus:
    """
    These are the valid review statuses from
    SoftwareSecure
    """

    clean = u'Clean'
    violation = u'Rules Violation'
    suspicious = u'Suspicious'
    not_reviewed = u'Not Reviewed'

    passing_statuses = [
        clean,
        violation]
    failing_statuses = [
        not_reviewed,
        suspicious]
    notify_support_for_status = suspicious

    from_standard_status = {
        ReviewStatus.passed: clean,
        ReviewStatus.violation: violation,
        ReviewStatus.suspicious: suspicious,
        ReviewStatus.not_reviewed: not_reviewed,
    }

    to_standard_status = {
        clean: ReviewStatus.passed,
        violation: ReviewStatus.violation,
        suspicious: ReviewStatus.suspicious,
        not_reviewed: ReviewStatus.not_reviewed,
    }

    @classmethod
    def validate(cls, status):
        """
        Validates the status, or raises ProctoredExamBadReviewStatus
        """
        if status not in cls.passing_statuses + cls.failing_statuses:
            err_msg = (
                u'Received unexpected reviewStatus field value from payload. '
                u'Was {review_status}.'.format(review_status=status)
            )
            raise ProctoredExamBadReviewStatus(err_msg)
        return True


class InstructorDashboardOnboardingAttemptStatus:
    """
    A class to enumerate the different statuses a proctored exam attempt
    in an onboarding exam can have and to map them to internal database statutes.
    These are intended to be used in externally facing applications, such
    as the Instructor Dashboard.
    """
    not_started = 'not_started'
    setup_started = 'setup_started'
    proctoring_started = 'proctoring_started'
    submitted = 'submitted'
    rejected = 'rejected'
    verified = 'verified'
    error = 'error'

    onboarding_statuses = {
        ProctoredExamStudentAttemptStatus.created: setup_started,
        ProctoredExamStudentAttemptStatus.download_software_clicked: setup_started,
        ProctoredExamStudentAttemptStatus.ready_to_start: setup_started,
        ProctoredExamStudentAttemptStatus.started: proctoring_started,
        ProctoredExamStudentAttemptStatus.ready_to_submit: proctoring_started,
        ProctoredExamStudentAttemptStatus.submitted: submitted,
        ProctoredExamStudentAttemptStatus.verified: verified,
        ProctoredExamStudentAttemptStatus.error: error,
    }

    @classmethod
    def get_onboarding_status_from_attempt_status(cls, status):
        """
        Get the externally facing proctored exam attempt onboarding status
        from an internal database proctored exam attempt status.

        Parameters:
            * status: a ProctoredExamStudentAttemptStatus status
        """
        if status:
            return cls.onboarding_statuses.get(status)
        return cls.not_started
