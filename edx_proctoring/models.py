# pylint: disable=too-many-lines
"""
Data models for the proctoring subsystem
"""

# pylint: disable=model-missing-unicode


from model_utils.models import TimeStampedModel

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Q
from django.db.models.base import ObjectDoesNotExist
from django.utils.translation import ugettext_noop

from edx_proctoring.backends import get_backend_provider
from edx_proctoring.exceptions import (
    AllowanceValueNotAllowedException,
    ProctoredExamNotActiveException,
    UserNotFoundException
)
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus, SoftwareSecureReviewStatus

USER_MODEL = get_user_model()


class ProctoredExam(TimeStampedModel):
    """
    Information about the Proctored Exam.

    .. no_pii:
    """

    course_id = models.CharField(max_length=255, db_index=True)

    # This will be the pointer to the id of the piece
    # of course_ware which is the proctored exam.
    content_id = models.CharField(max_length=255, db_index=True)

    # This will be a integration specific ID - say to SoftwareSecure.
    external_id = models.CharField(max_length=255, null=True, db_index=True)

    # This is the display name of the Exam (Midterm etc).
    exam_name = models.TextField()

    # Time limit (in minutes) that a student can finish this exam.
    time_limit_mins = models.IntegerField()

    # Due date is a deadline to finish the exam
    due_date = models.DateTimeField(null=True)

    # Whether this exam actually is proctored or not.
    is_proctored = models.BooleanField(default=False)

    # Whether this exam is for practice only.
    is_practice_exam = models.BooleanField(default=False)

    # Whether this exam will be active.
    is_active = models.BooleanField(default=False)

    # Whether to hide this exam after the due date
    hide_after_due = models.BooleanField(default=False)

    # override the platform default backend choice
    backend = models.CharField(max_length=255, null=True, default=None)

    class Meta:
        """ Meta class for this Django model """
        unique_together = (('course_id', 'content_id'),)
        db_table = 'proctoring_proctoredexam'

    def __str__(self):
        """ String representation """
        # pragma: no cover
        return u"{course_id}: {exam_name} ({active})".format(
            course_id=self.course_id,
            exam_name=self.exam_name,
            active='active' if self.is_active else 'inactive',
        )

    @classmethod
    def get_exam_by_content_id(cls, course_id, content_id):
        """
        Returns the Proctored Exam if found else returns None,
        Given course_id and content_id
        """
        try:
            proctored_exam = cls.objects.get(course_id=course_id, content_id=content_id)
        except cls.DoesNotExist:  # pylint: disable=no-member
            proctored_exam = None
        return proctored_exam

    @classmethod
    def get_exam_by_id(cls, exam_id):
        """
        Returns the Proctored Exam if found else returns None,
        Given exam_id (PK)
        """
        try:
            proctored_exam = cls.objects.get(id=exam_id)
        except cls.DoesNotExist:  # pylint: disable=no-member
            proctored_exam = None
        return proctored_exam

    @classmethod
    def get_all_exams_for_course(cls, course_id, active_only=False, proctored_exams_only=False):
        """
        Returns all exams for a give course
        """
        filtered_query = Q(course_id=course_id)

        if active_only:
            filtered_query = filtered_query & Q(is_active=True)
        if proctored_exams_only:
            filtered_query = filtered_query & Q(is_proctored=True) & Q(is_practice_exam=False)

        return cls.objects.filter(filtered_query)


class ProctoredExamReviewPolicy(TimeStampedModel):
    """
    This is how an instructor can set review policies for a proctored exam

    .. no_pii:
    """

    # who set this ProctoredExamReviewPolicy
    set_by_user = models.ForeignKey(USER_MODEL, on_delete=models.CASCADE)

    # for which exam?
    proctored_exam = models.ForeignKey(ProctoredExam, db_index=True, on_delete=models.CASCADE)

    # policy that will be passed to reviewers
    review_policy = models.TextField(default=u'')

    def __str__(self):
        """ String representation """
        # pragma: no cover
        return u"ProctoredExamReviewPolicy: {set_by_user} ({proctored_exam})".format(
            set_by_user=self.set_by_user,
            proctored_exam=self.proctored_exam,
        )

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexamreviewpolicy'
        verbose_name = 'Proctored exam review policy'
        verbose_name_plural = "Proctored exam review policies"

    @classmethod
    def get_review_policy_for_exam(cls, exam_id):
        """
        Returns the current exam review policy for the specified
        exam_id or None if none exists
        """

        try:
            return cls.objects.get(proctored_exam_id=exam_id)
        except cls.DoesNotExist:  # pylint: disable=no-member
            return None


class ProctoredExamReviewPolicyHistory(TimeStampedModel):
    """
    Archive table to record all policies that were deleted or updated

    .. no_pii:
    """

    # what was the original PK for the Review Policy
    original_id = models.IntegerField(db_index=True)

    # who set this ProctoredExamReviewPolicy
    set_by_user = models.ForeignKey(USER_MODEL, on_delete=models.CASCADE)

    # for which exam?
    proctored_exam = models.ForeignKey(ProctoredExam, db_index=True, on_delete=models.CASCADE)

    # policy that will be passed to reviewers
    review_policy = models.TextField()

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexamreviewpolicyhistory'
        verbose_name = 'proctored exam review policy history'

    def delete(self, *args, **kwargs):  # pylint: disable=signature-differs
        """
        Don't allow deletions!
        """
        raise NotImplementedError()


class ProctoredExamStudentAttemptManager(models.Manager):
    """
    Custom manager
    """
    def get_current_exam_attempt(self, exam_id, user_id):
        """
        Returns the most recent Student Exam Attempt object if found
        else Returns None.
        """
        try:
            exam_attempt_obj = self.filter(
                proctored_exam_id=exam_id, user_id=user_id
            ).latest('created')  # pylint: disable=no-member
        except ObjectDoesNotExist:  # pylint: disable=no-member
            exam_attempt_obj = None
        return exam_attempt_obj

    def get_exam_attempt_by_id(self, attempt_id):
        """
        Returns the Student Exam Attempt by the attempt_id else return None
        """
        try:
            exam_attempt_obj = self.get(id=attempt_id)  # pylint: disable=no-member
        except ObjectDoesNotExist:  # pylint: disable=no-member
            exam_attempt_obj = None
        return exam_attempt_obj

    def get_exam_attempt_by_code(self, attempt_code):
        """
        Returns the Student Exam Attempt object if found
        else Returns None.
        """
        try:
            exam_attempt_obj = self.get(attempt_code=attempt_code)  # pylint: disable=no-member
        except ObjectDoesNotExist:  # pylint: disable=no-member
            exam_attempt_obj = None
        return exam_attempt_obj

    def get_exam_attempt_by_external_id(self, external_id):
        """
        Returns the Student Exam Attempt object if found
        else Returns None.
        """
        try:
            exam_attempt_obj = self.get(external_id=external_id)  # pylint: disable=no-member
        except ObjectDoesNotExist:  # pylint: disable=no-member
            exam_attempt_obj = None
        return exam_attempt_obj

    def get_all_exam_attempts(self, course_id):
        """
        Returns the Student Exam Attempts for the given course_id.
        """
        filtered_query = Q(proctored_exam__course_id=course_id)
        return self.filter(filtered_query).order_by('-created')  # pylint: disable=no-member

    def get_filtered_exam_attempts(self, course_id, search_by):
        """
        Returns the Student Exam Attempts for the given course_id filtered by search_by.
        """
        filtered_query = Q(proctored_exam__course_id=course_id) & (
            Q(user__username__contains=search_by) | Q(user__email__contains=search_by)
        )
        return self.filter(filtered_query).order_by('-created')  # pylint: disable=no-member

    def get_proctored_exam_attempts(self, course_id, username):
        """
        Returns the Student's Proctored Exam Attempts for the given course_id.
        """
        # pylint: disable=no-member
        return self.filter(
            proctored_exam__course_id=course_id,
            user__username=username,
            taking_as_proctored=True,
            is_sample_attempt=False,
        ).order_by('-completed_at')

    def get_active_student_attempts(self, user_id, course_id=None):
        """
        Returns the active student exams (user in-progress exams)
        """
        filtered_query = Q(user_id=user_id) & (Q(status=ProctoredExamStudentAttemptStatus.started) |
                                               Q(status=ProctoredExamStudentAttemptStatus.ready_to_submit))
        if course_id is not None:
            filtered_query = filtered_query & Q(proctored_exam__course_id=course_id)

        return self.filter(filtered_query).order_by('-created')  # pylint: disable=no-member

    def clear_onboarding_errors(self, user_id):
        """
        Removes any attempts in the onboarding error states.
        (They will automatically be saved to the attempt history table)
        """
        # pylint: disable=no-member
        self.filter(user_id=user_id,
                    status__in=ProctoredExamStudentAttemptStatus.onboarding_errors).delete()


class ProctoredExamStudentAttempt(TimeStampedModel):
    """
    Information about the Student Attempt on a
    Proctored Exam.

    .. pii: new attempts log the student's name and IP
    .. pii_types: name, ip
    .. pii_retirement: local_api
    """
    objects = ProctoredExamStudentAttemptManager()

    user = models.ForeignKey(USER_MODEL, db_index=True, on_delete=models.CASCADE)

    proctored_exam = models.ForeignKey(ProctoredExam, db_index=True, on_delete=models.CASCADE)

    # started/completed date times
    started_at = models.DateTimeField(null=True)

    # completed_at means when the attempt was 'submitted'
    completed_at = models.DateTimeField(null=True)

    # These two fields have been deprecated.
    # They were used in client polling that no longer exists.
    last_poll_timestamp = models.DateTimeField(null=True)
    last_poll_ipaddr = models.CharField(max_length=32, null=True)

    # this will be a unique string ID that the user
    # will have to use when starting the proctored exam
    attempt_code = models.CharField(max_length=255, null=True, db_index=True)

    # This will be a integration specific ID - say to SoftwareSecure.
    external_id = models.CharField(max_length=255, null=True, db_index=True)

    # this is the time limit allowed to the student
    allowed_time_limit_mins = models.IntegerField(null=True)

    # what is the status of this attempt
    status = models.CharField(max_length=64)

    # if the user is attempting this as a proctored exam
    # in case there is an option to opt-out
    taking_as_proctored = models.BooleanField(default=False, verbose_name=ugettext_noop("Taking as Proctored"))

    # Whether this attempt is considered a sample attempt, e.g. to try out
    # the proctoring software
    is_sample_attempt = models.BooleanField(default=False, verbose_name=ugettext_noop("Is Sample Attempt"))

    # Note - this is currently unset
    student_name = models.CharField(max_length=255)

    # what review policy was this exam submitted under
    # Note that this is not a foreign key because
    # this ID might point to a record that is in the History table
    review_policy_id = models.IntegerField(null=True)

    # if student has press the button to explore the exam then true
    # else always false
    is_status_acknowledged = models.BooleanField(default=False)

    # if the attempt enters an error state, the remaining time should
    # be saved in order to allow the learner to resume
    time_remaining_seconds = models.IntegerField(null=True)

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexamstudentattempt'
        verbose_name = 'proctored exam attempt'

    @classmethod
    def create_exam_attempt(cls, exam_id, user_id, student_name, attempt_code,
                            taking_as_proctored, is_sample_attempt, external_id,
                            review_policy_id=None, status=None, time_remaining_seconds=None):
        """
        Create a new exam attempt entry for a given exam_id and
        user_id.
        """
        status = status or ProctoredExamStudentAttemptStatus.created
        return cls.objects.create(
            proctored_exam_id=exam_id,
            user_id=user_id,
            student_name=student_name,
            attempt_code=attempt_code,
            taking_as_proctored=taking_as_proctored,
            is_sample_attempt=is_sample_attempt,
            external_id=external_id,
            status=status,
            review_policy_id=review_policy_id,
            time_remaining_seconds=time_remaining_seconds
        )  # pylint: disable=no-member

    def delete_exam_attempt(self):
        """
        Deletes the exam attempt object and archives it to the ProctoredExamStudentAttemptHistory table.
        """
        self.delete()


class ProctoredExamStudentAttemptHistory(TimeStampedModel):
    """
    This should be the same schema as ProctoredExamStudentAttempt
    but will record (for audit history) all entries that have been updated.

    .. pii: new attempts log the student's name and IP
    .. pii_types: name, ip
    .. pii_retirement: local_api
    """

    user = models.ForeignKey(USER_MODEL, db_index=True, on_delete=models.CASCADE)

    # this is the PK of the original table, note this is not a FK
    attempt_id = models.IntegerField(null=True)

    proctored_exam = models.ForeignKey(ProctoredExam, db_index=True, on_delete=models.CASCADE)

    # started/completed date times
    started_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)

    # this will be a unique string ID that the user
    # will have to use when starting the proctored exam
    attempt_code = models.CharField(max_length=255, null=True, db_index=True)

    # This will be a integration specific ID - say to SoftwareSecure.
    external_id = models.CharField(max_length=255, null=True, db_index=True)

    # this is the time limit allowed to the student
    allowed_time_limit_mins = models.IntegerField(null=True)

    # what is the status of this attempt
    status = models.CharField(max_length=64)

    # if the user is attempting this as a proctored exam
    # in case there is an option to opt-out
    taking_as_proctored = models.BooleanField(default=False)

    # Whether this attampt is considered a sample attempt, e.g. to try out
    # the proctoring software
    is_sample_attempt = models.BooleanField(default=False)

    # Note - this is currently unset
    student_name = models.CharField(max_length=255)

    # what review policy was this exam submitted under
    # Note that this is not a foreign key because
    # this ID might point to a record that is in the History table
    review_policy_id = models.IntegerField(null=True)

    # These two fields have been deprecated.
    # They were used in client polling that no longer exists.
    last_poll_timestamp = models.DateTimeField(null=True)
    last_poll_ipaddr = models.CharField(max_length=32, null=True)

    @classmethod
    def get_exam_attempt_by_code(cls, attempt_code):
        """
        Returns the Student Exam Attempt object if found
        else Returns None.
        """
        # NOTE: compared to the ProctoredExamAttempt table
        # we can have multiple rows with the same attempt_code
        # So, just return the first one (most recent) if
        # there are any
        exam_attempt_obj = None

        try:
            exam_attempt_obj = cls.objects.filter(attempt_code=attempt_code).latest("created")
        except cls.DoesNotExist:  # pylint: disable=no-member
            pass

        return exam_attempt_obj

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexamstudentattempthistory'
        verbose_name = 'proctored exam attempt history'


def archive_model(model, instance, **mapping):
    """
    Archives the instance to the given history model
    optionally maps field names from the instance model to the history model
    """
    archive = model()
    # timestampedmodels automatically create these
    mapping['created'] = mapping['modified'] = None
    for field in instance._meta.get_fields():
        to_name = mapping.get(field.name, field.name)
        if to_name is not None:
            setattr(archive, to_name, getattr(instance, field.name, None))
    archive.save()
    return archive


class QuerySetWithUpdateOverride(models.QuerySet):
    """
    Custom QuerySet class to make an archive copy
    every time the object is updated.
    """
    def update(self, **kwargs):
        """ Create a copy after update """
        super().update(**kwargs)
        archive_model(ProctoredExamStudentAllowanceHistory, self.get(), id='allowance_id')


class ProctoredExamStudentAllowanceManager(models.Manager):
    """
    Custom manager to override with the custom queryset
    to enable archiving on Allowance updation.
    """
    def get_queryset(self):
        """
        Return a specialized queryset
        """
        return QuerySetWithUpdateOverride(self.model, using=self._db)


class ProctoredExamStudentAllowance(TimeStampedModel):
    """
    Information about allowing a student additional time on exam.

    .. pii: allowances have a free-form text field which may be identifiable
    .. pii_types: other
    .. pii_retirement: local_api
    """

    # DONT EDIT THE KEYS - THE FIRST VALUE OF THE TUPLE - AS ARE THEY ARE STORED IN THE DATABASE
    # THE SECOND ELEMENT OF THE TUPLE IS A DISPLAY STRING AND CAN BE EDITED
    ADDITIONAL_TIME_GRANTED = ('additional_time_granted', ugettext_noop('Additional Time (minutes)'))
    REVIEW_POLICY_EXCEPTION = ('review_policy_exception', ugettext_noop('Review Policy Exception'))

    all_allowances = [
        ADDITIONAL_TIME_GRANTED + REVIEW_POLICY_EXCEPTION
    ]

    objects = ProctoredExamStudentAllowanceManager()

    user = models.ForeignKey(USER_MODEL, on_delete=models.CASCADE)

    proctored_exam = models.ForeignKey(ProctoredExam, on_delete=models.CASCADE)

    key = models.CharField(max_length=255)

    value = models.CharField(max_length=255)

    class Meta:
        """ Meta class for this Django model """
        unique_together = (('user', 'proctored_exam', 'key'),)
        db_table = 'proctoring_proctoredexamstudentallowance'
        verbose_name = 'proctored allowance'

    @classmethod
    def get_allowances_for_course(cls, course_id):
        """
        Returns all the allowances for a course.
        """
        filtered_query = Q(proctored_exam__course_id=course_id)
        return cls.objects.filter(filtered_query)

    @classmethod
    def get_allowance_for_user(cls, exam_id, user_id, key):
        """
        Returns an allowance for a user within a given exam
        """
        try:
            student_allowance = cls.objects.get(proctored_exam_id=exam_id, user_id=user_id, key=key)
        except cls.DoesNotExist:  # pylint: disable=no-member
            student_allowance = None
        return student_allowance

    @classmethod
    def get_allowances_for_user(cls, exam_id, user_id):
        """
        Returns an allowances for a user within a given exam
        """
        return cls.objects.filter(proctored_exam_id=exam_id, user_id=user_id)

    @classmethod
    def add_allowance_for_user(cls, exam_id, user_info, key, value):
        """
        Add or (Update) an allowance for a user within a given exam
        """
        user_id = None

        # see if key is a tuple, if it is, then the first element is the key
        if isinstance(key, tuple) and len(key) > 0:  # pylint: disable=len-as-condition
            key = key[0]

        if not cls.is_allowance_value_valid(key, value):
            err_msg = (
                u'allowance_value "{value}" should be non-negative integer value.'
            ).format(value=value)
            raise AllowanceValueNotAllowedException(err_msg)
        # were we passed a PK?
        if isinstance(user_info, int):
            user_id = user_info
        else:
            # we got a string, so try to resolve it
            users = USER_MODEL.objects.filter(username=user_info)
            if not users.exists():
                users = USER_MODEL.objects.filter(email=user_info)

            if not users.exists():
                err_msg = (
                    u'Cannot find user against {user_info}'
                ).format(user_info=user_info)
                raise UserNotFoundException(err_msg)

            user_id = users[0].id

        exam = ProctoredExam.get_exam_by_id(exam_id)
        if exam and not exam.is_active:
            raise ProctoredExamNotActiveException

        try:
            student_allowance = cls.objects.get(proctored_exam_id=exam_id, user_id=user_id, key=key)
            student_allowance.value = value
            student_allowance.save()
            action = "updated"
        except cls.DoesNotExist:  # pylint: disable=no-member
            student_allowance = cls.objects.create(proctored_exam_id=exam_id, user_id=user_id, key=key, value=value)
            action = "created"
        return student_allowance, action

    @classmethod
    def is_allowance_value_valid(cls, allowance_type, allowance_value):
        """
        Method that validates the allowance value against the allowance type
        """
        # validates the allowance value only when the allowance type is "ADDITIONAL_TIME_GRANTED"
        if allowance_type in cls.ADDITIONAL_TIME_GRANTED:
            if not allowance_value.isdigit():
                return False

        return True

    @classmethod
    def get_additional_time_granted(cls, exam_id, user_id):
        """
        Helper method to get the additional time granted
        """
        allowance = cls.get_allowance_for_user(exam_id, user_id, cls.ADDITIONAL_TIME_GRANTED[0])
        if allowance:
            return int(allowance.value)

        return None

    @classmethod
    def get_review_policy_exception(cls, exam_id, user_id):
        """
        Helper method to get the policy exception that reviewers should
        follow
        """
        allowance = cls.get_allowance_for_user(exam_id, user_id, cls.REVIEW_POLICY_EXCEPTION[0])
        return allowance.value if allowance else None


class ProctoredExamStudentAllowanceHistory(TimeStampedModel):
    """
    This should be the same schema as ProctoredExamStudentAllowance
    but will record (for audit history) all entries that have been updated.

    .. pii: allowances have a free-form text field which may be identifiable
    .. pii_types: other
    .. pii_retirement: local_api
    """

    # what was the original id of the allowance
    allowance_id = models.IntegerField()

    user = models.ForeignKey(USER_MODEL, on_delete=models.CASCADE)

    proctored_exam = models.ForeignKey(ProctoredExam, on_delete=models.CASCADE)

    key = models.CharField(max_length=255)

    value = models.CharField(max_length=255)

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexamstudentallowancehistory'
        verbose_name = 'proctored allowance history'


class ProctoredExamSoftwareSecureReview(TimeStampedModel):
    """
    This is where we store the proctored exam review feedback
    from the exam reviewers

    .. pii: reviews contain video of the exam
            retirement to be implemented in https://openedx.atlassian.net/browse/EDUCATOR-4776
    .. pii_types: video
    .. pii_retirement: to_be_implemented
    """

    # which student attempt is this feedback for?
    attempt_code = models.CharField(max_length=255, db_index=True, unique=True)

    # is this attempt active?
    is_attempt_active = models.BooleanField(default=True)

    # overall status of the review
    review_status = models.CharField(max_length=255)

    # The raw payload that was received back from the
    # reviewing service
    raw_data = models.TextField()

    # URL for the exam video that had been reviewed
    # NOTE: To be deleted in future release, once the code that depends on it
    # has been removed
    video_url = models.TextField()

    # user_id of person who did the review (can be None if submitted via server-to-server API)
    reviewed_by = models.ForeignKey(USER_MODEL, null=True, related_name='+', on_delete=models.CASCADE)

    # student username for the exam
    # this is an optimization for the Django Admin pane (so we can search)
    # this is null because it is being added after initial production ship
    student = models.ForeignKey(USER_MODEL, null=True, related_name='+', on_delete=models.CASCADE)

    # exam_id for the review
    # this is an optimization for the Django Admin pane (so we can search)
    # this is null because it is being added after initial production ship
    exam = models.ForeignKey(ProctoredExam, null=True, on_delete=models.CASCADE)

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexamsoftwaresecurereview'
        verbose_name = 'Proctored exam software secure review'

    @property
    def is_passing(self):
        """
        Returns whether the review should be considered "passing"
        """
        backend = get_backend_provider(name=self.exam.backend)
        # if the backend defines `passing_statuses`, use that
        statuses = getattr(backend, 'passing_statuses', []) or SoftwareSecureReviewStatus.passing_statuses
        return self.review_status in statuses

    @property
    def should_notify(self):
        """
        Returns whether to notify support/course teams
        """
        return self.review_status in SoftwareSecureReviewStatus.notify_support_for_status and not self.reviewed_by

    @classmethod
    def get_review_by_attempt_code(cls, attempt_code):
        """
        Does a lookup by attempt_code
        """
        try:
            review = cls.objects.get(attempt_code=attempt_code)
            return review
        except cls.DoesNotExist:  # pylint: disable=no-member
            return None


class ProctoredExamSoftwareSecureReviewHistory(TimeStampedModel):
    """
    When records get updated, we will archive them here

    .. pii: reviews contain video of the exam
            retirement to be implemented in https://openedx.atlassian.net/browse/EDUCATOR-4776
    .. pii_types: video
    .. pii_retirement: to_be_implemented
    """

    # which student attempt is this feedback for?
    attempt_code = models.CharField(max_length=255, db_index=True)

    # is this attempt active?
    is_attempt_active = models.BooleanField(default=True)

    # overall status of the review
    review_status = models.CharField(max_length=255)

    # The raw payload that was received back from the
    # reviewing service
    raw_data = models.TextField()

    # URL for the exam video that had been reviewed
    video_url = models.TextField()

    # user_id of person who did the review (can be None if submitted via server-to-server API)
    reviewed_by = models.ForeignKey(USER_MODEL, null=True, related_name='+', on_delete=models.CASCADE)

    # student username for the exam
    # this is an optimization for the Django Admin pane (so we can search)
    # this is null because it is being added after initial production ship
    student = models.ForeignKey(USER_MODEL, null=True, related_name='+', on_delete=models.CASCADE)

    # exam_id for the review
    # this is an optimization for the Django Admin pane (so we can search)
    # this is null because it is being added after initial production ship
    exam = models.ForeignKey(ProctoredExam, null=True, on_delete=models.CASCADE)

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexamsoftwaresecurereviewhistory'
        verbose_name = 'Proctored exam review archive'


class ProctoredExamSoftwareSecureComment(TimeStampedModel):
    """
    This is where we store the proctored exam review comments
    from the exam reviewers

    .. pii: comment contains free-form text which could be personally-identifying
            retirement to be implemented in https://openedx.atlassian.net/browse/EDUCATOR-4776
    .. pii_types: other
    .. pii_retirement: to_be_implemented
    """

    # which student attempt is this feedback for?
    review = models.ForeignKey(ProctoredExamSoftwareSecureReview, on_delete=models.CASCADE)

    # start time in the video, in seconds, regarding the comment
    start_time = models.IntegerField()

    # stop time in the video, in seconds, regarding the comment
    stop_time = models.IntegerField()

    # length of time, in seconds, regarding the comment
    duration = models.IntegerField()

    # the text that the reviewer typed in
    comment = models.TextField()

    # reviewers opinion regarding exam validitity based on the comment
    status = models.CharField(max_length=255)

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexamstudentattemptcomment'
        verbose_name = 'proctored exam software secure comment'
