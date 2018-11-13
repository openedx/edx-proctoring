"""
Status enums for edx-proctoring
"""
from edx_proctoring.exceptions import ProctoredExamBadReviewStatus


class ProctoredExamStudentAttemptStatus(object):
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

    @classmethod
    def is_completed_status(cls, status):
        """
        Returns a boolean if the passed in status is in a "completed" state, meaning
        that it cannot go backwards in state
        """
        return status in [
            cls.declined, cls.timed_out, cls.submitted, cls.second_review_required,
            cls.verified, cls.rejected, cls.error
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


class ReviewStatus(object):
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
        if status not in [cls.passed, cls.violation, cls.suspicious, cls.not_reviewed]:
            raise ProctoredExamBadReviewStatus(status)
        return True


class SoftwareSecureReviewStatus(object):
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
                'Received unexpected reviewStatus field value from payload. '
                'Was {review_status}.'.format(review_status=status)
            )
            raise ProctoredExamBadReviewStatus(err_msg)
        return True
