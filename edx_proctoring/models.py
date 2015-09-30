"""
Data models for the proctoring subsystem
"""
from django.db import models
from django.db.models import Q
from django.db.models.signals import pre_save, pre_delete
from django.dispatch import receiver
from model_utils.models import TimeStampedModel
from django.utils.translation import ugettext as _

from django.contrib.auth.models import User
from edx_proctoring.exceptions import UserNotFoundException
from django.db.models.base import ObjectDoesNotExist


class ProctoredExam(TimeStampedModel):
    """
    Information about the Proctored Exam.
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

    # Whether this exam actually is proctored or not.
    is_proctored = models.BooleanField()

    # Whether this exam is for practice only.
    is_practice_exam = models.BooleanField()

    # Whether this exam will be active.
    is_active = models.BooleanField()

    class Meta:
        """ Meta class for this Django model """
        unique_together = (('course_id', 'content_id'),)
        db_table = 'proctoring_proctoredexam'

    def __unicode__(self):
        """
        How to serialize myself as a string
        """

        return "{course_id}: {exam_name} ({active})".format(
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
    def get_all_exams_for_course(cls, course_id, active_only=False):
        """
        Returns all exams for a give course
        """
        result = cls.objects.filter(course_id=course_id)
        if active_only:
            result = result.filter(is_active=True)
        return result


class ProctoredExamStudentAttemptStatus(object):
    """
    A class to enumerate the various status that an attempt can have

    IMPORTANT: Since these values are stored in a database, they are system
    constants and should not be language translated, since translations
    might change over time.
    """

    # the student is eligible to decide if he/she wants to persue credit
    eligible = 'eligible'

    # the attempt record has been created, but the exam has not yet
    # been started
    created = 'created'

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

    # the exam has been verified and approved
    verified = 'verified'

    # the exam has been rejected
    rejected = 'rejected'

    # the exam was not reviewed
    not_reviewed = 'not_reviewed'

    # the exam is believed to be in error
    error = 'error'

    # status alias for sending email
    status_alias_mapping = {
        submitted: _('pending'),
        verified: _('satisfactory'),
        rejected: _('unsatisfactory')
    }

    @classmethod
    def is_completed_status(cls, status):
        """
        Returns a boolean if the passed in status is in a "completed" state, meaning
        that it cannot go backwards in state
        """
        return status in [
            cls.declined, cls.timed_out, cls.submitted, cls.verified, cls.rejected,
            cls.not_reviewed, cls.error
        ]

    @classmethod
    def is_incomplete_status(cls, status):
        """
        Returns a boolean if the passed in status is in an "incomplete" state.
        """
        return status in [
            cls.eligible, cls.created, cls.ready_to_start, cls.started, cls.ready_to_submit
        ]

    @classmethod
    def needs_credit_status_update(cls, to_status):
        """
        Returns a boolean if the passed in to_status calls for an update to the credit requirement status.
        """
        return to_status in [
            cls.verified, cls.rejected, cls.declined, cls.not_reviewed, cls.submitted,
            cls.error
        ]

    @classmethod
    def is_a_cascadable_failure(cls, to_status):
        """
        Returns a boolean if the passed in to_status has a failure that needs to be cascaded
        to other attempts.
        """
        return to_status in [
            cls.rejected, cls.declined
        ]

    @classmethod
    def needs_status_change_email(cls, to_status):
        """
        We need to send out emails for rejected, verified and submitted statuses.
        """

        return to_status in [
            cls.rejected, cls.submitted, cls.verified
        ]

    @classmethod
    def get_status_alias(cls, status):
        """
        Returns status alias used in email
        """

        return cls.status_alias_mapping.get(status, '')

    @classmethod
    def is_valid_status(cls, status):
        """
        Makes sure that passed in status string is valid
        """
        return cls.is_completed_status(status) or cls.is_incomplete_status(status)


class ProctoredExamReviewPolicy(TimeStampedModel):
    """
    This is how an instructor can set review policies for a proctored exam
    """

    # who set this ProctoredExamReviewPolicy
    set_by_user = models.ForeignKey(User)

    # for which exam?
    proctored_exam = models.ForeignKey(ProctoredExam, db_index=True)

    # policy that will be passed to reviewers
    review_policy = models.TextField()

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
    """

    # what was the original PK for the Review Policy
    original_id = models.IntegerField(db_index=True)

    # who set this ProctoredExamReviewPolicy
    set_by_user = models.ForeignKey(User)

    # for which exam?
    proctored_exam = models.ForeignKey(ProctoredExam, db_index=True)

    # policy that will be passed to reviewers
    review_policy = models.TextField()

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexamreviewpolicyhistory'
        verbose_name = 'proctored exam review policy history'

    def delete(self, *args, **kwargs):
        """
        Don't allow deletions!
        """
        raise NotImplementedError()


# Hook up the post_save signal to record creations in the ProctoredExamReviewPolicyHistory table.
@receiver(pre_save, sender=ProctoredExamReviewPolicy)
def on_review_policy_saved(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Archiving all changes made to the Student Allowance.
    Will only archive on update, and not on new entries created.
    """

    if instance.id:
        # only for update cases
        original = ProctoredExamReviewPolicy.objects.get(id=instance.id)
        _make_review_policy_archive_copy(original)


# Hook up the pre_delete signal to record creations in the ProctoredExamReviewPolicyHistory table.
@receiver(pre_delete, sender=ProctoredExamReviewPolicy)
def on_review_policy_deleted(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Archive the allowance when the item is about to be deleted
    """

    _make_review_policy_archive_copy(instance)


def _make_review_policy_archive_copy(instance):
    """
    Do the copying into the history table
    """

    archive_object = ProctoredExamReviewPolicyHistory(
        original_id=instance.id,
        set_by_user_id=instance.set_by_user_id,
        proctored_exam=instance.proctored_exam,
        review_policy=instance.review_policy,
    )
    archive_object.save()


class ProctoredExamStudentAttemptManager(models.Manager):
    """
    Custom manager
    """
    def get_exam_attempt(self, exam_id, user_id):
        """
        Returns the Student Exam Attempt object if found
        else Returns None.
        """
        try:
            exam_attempt_obj = self.get(proctored_exam_id=exam_id, user_id=user_id)
        except ObjectDoesNotExist:  # pylint: disable=no-member
            exam_attempt_obj = None
        return exam_attempt_obj

    def get_exam_attempt_by_id(self, attempt_id):
        """
        Returns the Student Exam Attempt by the attempt_id else return None
        """
        try:
            exam_attempt_obj = self.get(id=attempt_id)
        except ObjectDoesNotExist:  # pylint: disable=no-member
            exam_attempt_obj = None
        return exam_attempt_obj

    def get_exam_attempt_by_code(self, attempt_code):
        """
        Returns the Student Exam Attempt object if found
        else Returns None.
        """
        try:
            exam_attempt_obj = self.get(attempt_code=attempt_code)
        except ObjectDoesNotExist:  # pylint: disable=no-member
            exam_attempt_obj = None
        return exam_attempt_obj

    def get_all_exam_attempts(self, course_id):
        """
        Returns the Student Exam Attempts for the given course_id.
        """

        return self.filter(proctored_exam__course_id=course_id).order_by('-created')

    def get_filtered_exam_attempts(self, course_id, search_by):
        """
        Returns the Student Exam Attempts for the given course_id filtered by search_by.
        """
        filtered_query = Q(proctored_exam__course_id=course_id) & (
            Q(user__username__contains=search_by) | Q(user__email__contains=search_by)
        )

        return self.filter(filtered_query).order_by('-created')

    def get_active_student_attempts(self, user_id, course_id=None):
        """
        Returns the active student exams (user in-progress exams)
        """
        filtered_query = Q(user_id=user_id) & (Q(status=ProctoredExamStudentAttemptStatus.started) |
                                               Q(status=ProctoredExamStudentAttemptStatus.ready_to_submit))
        if course_id is not None:
            filtered_query = filtered_query & Q(proctored_exam__course_id=course_id)

        return self.filter(filtered_query).order_by('-created')


class ProctoredExamStudentAttempt(TimeStampedModel):
    """
    Information about the Student Attempt on a
    Proctored Exam.
    """
    objects = ProctoredExamStudentAttemptManager()

    user = models.ForeignKey(User, db_index=True)

    proctored_exam = models.ForeignKey(ProctoredExam, db_index=True)

    # started/completed date times
    started_at = models.DateTimeField(null=True)

    # completed_at means when the attempt was 'submitted'
    completed_at = models.DateTimeField(null=True)

    last_poll_timestamp = models.DateTimeField(null=True)
    last_poll_ipaddr = models.CharField(max_length=32, null=True)

    # this will be a unique string ID that the user
    # will have to use when starting the proctored exam
    attempt_code = models.CharField(max_length=255, null=True, db_index=True)

    # This will be a integration specific ID - say to SoftwareSecure.
    external_id = models.CharField(max_length=255, null=True, db_index=True)

    # this is the time limit allowed to the student
    allowed_time_limit_mins = models.IntegerField()

    # what is the status of this attempt
    status = models.CharField(max_length=64)

    # if the user is attempting this as a proctored exam
    # in case there is an option to opt-out
    taking_as_proctored = models.BooleanField()

    # Whether this attempt is considered a sample attempt, e.g. to try out
    # the proctoring software
    is_sample_attempt = models.BooleanField()

    student_name = models.CharField(max_length=255)

    # what review policy was this exam submitted under
    # Note that this is not a foreign key because
    # this ID might point to a record that is in the History table
    review_policy_id = models.IntegerField(null=True)

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexamstudentattempt'
        verbose_name = 'proctored exam attempt'
        unique_together = (('user', 'proctored_exam'),)

    @classmethod
    def create_exam_attempt(cls, exam_id, user_id, student_name, allowed_time_limit_mins,
                            attempt_code, taking_as_proctored, is_sample_attempt, external_id,
                            review_policy_id=None):
        """
        Create a new exam attempt entry for a given exam_id and
        user_id.
        """

        return cls.objects.create(
            proctored_exam_id=exam_id,
            user_id=user_id,
            student_name=student_name,
            allowed_time_limit_mins=allowed_time_limit_mins,
            attempt_code=attempt_code,
            taking_as_proctored=taking_as_proctored,
            is_sample_attempt=is_sample_attempt,
            external_id=external_id,
            status=ProctoredExamStudentAttemptStatus.created,
            review_policy_id=review_policy_id
        )

    def delete_exam_attempt(self):
        """
        deletes the exam attempt object and archives it to the ProctoredExamStudentAttemptHistory table.
        """
        self.delete()


class ProctoredExamStudentAttemptHistory(TimeStampedModel):
    """
    This should be the same schema as ProctoredExamStudentAttempt
    but will record (for audit history) all entries that have been updated.
    """

    user = models.ForeignKey(User, db_index=True)

    # this is the PK of the original table, note this is not a FK
    attempt_id = models.IntegerField(null=True)

    proctored_exam = models.ForeignKey(ProctoredExam, db_index=True)

    # started/completed date times
    started_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)

    # this will be a unique string ID that the user
    # will have to use when starting the proctored exam
    attempt_code = models.CharField(max_length=255, null=True, db_index=True)

    # This will be a integration specific ID - say to SoftwareSecure.
    external_id = models.CharField(max_length=255, null=True, db_index=True)

    # this is the time limit allowed to the student
    allowed_time_limit_mins = models.IntegerField()

    # what is the status of this attempt
    status = models.CharField(max_length=64)

    # if the user is attempting this as a proctored exam
    # in case there is an option to opt-out
    taking_as_proctored = models.BooleanField()

    # Whether this attampt is considered a sample attempt, e.g. to try out
    # the proctoring software
    is_sample_attempt = models.BooleanField()

    student_name = models.CharField(max_length=255)

    # what review policy was this exam submitted under
    # Note that this is not a foreign key because
    # this ID might point to a record that is in the History table
    review_policy_id = models.IntegerField(null=True)

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

        items = cls.objects.filter(attempt_code=attempt_code).order_by("-created")
        if items:
            exam_attempt_obj = items[0]

        return exam_attempt_obj

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexamstudentattempthistory'
        verbose_name = 'proctored exam attempt history'


@receiver(pre_delete, sender=ProctoredExamStudentAttempt)
def on_attempt_deleted(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Archive the exam attempt when the item is about to be deleted
    Make a clone and populate in the History table
    """

    archive_object = ProctoredExamStudentAttemptHistory(
        user=instance.user,
        attempt_id=instance.id,
        proctored_exam=instance.proctored_exam,
        started_at=instance.started_at,
        completed_at=instance.completed_at,
        attempt_code=instance.attempt_code,
        external_id=instance.external_id,
        allowed_time_limit_mins=instance.allowed_time_limit_mins,
        status=instance.status,
        taking_as_proctored=instance.taking_as_proctored,
        is_sample_attempt=instance.is_sample_attempt,
        student_name=instance.student_name,
        review_policy_id=instance.review_policy_id,
    )
    archive_object.save()


class QuerySetWithUpdateOverride(models.query.QuerySet):
    """
    Custom QuerySet class to make an archive copy
    every time the object is updated.
    """
    def update(self, **kwargs):
        super(QuerySetWithUpdateOverride, self).update(**kwargs)
        _make_archive_copy(self.get())


class ProctoredExamStudentAllowanceManager(models.Manager):
    """
    Custom manager to override with the custom queryset
    to enable archiving on Allowance updation.
    """
    def get_query_set(self):
        return QuerySetWithUpdateOverride(self.model, using=self._db)


class ProctoredExamStudentAllowance(TimeStampedModel):
    """
    Information about allowing a student additional time on exam.
    """

    # DONT EDIT THE KEYS - THE FIRST VALUE OF THE TUPLE - AS ARE THEY ARE STORED IN THE DATABASE
    # THE SECOND ELEMENT OF THE TUPLE IS A DISPLAY STRING AND CAN BE EDITED
    ADDITIONAL_TIME_GRANTED = ('additional_time_granted', _('Additional Time (minutes)'))
    REVIEW_POLICY_EXCEPTION = ('review_policy_exception', _('Review Policy Exception'))

    all_allowances = [
        ADDITIONAL_TIME_GRANTED + REVIEW_POLICY_EXCEPTION
    ]

    objects = ProctoredExamStudentAllowanceManager()

    user = models.ForeignKey(User)

    proctored_exam = models.ForeignKey(ProctoredExam)

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
        return cls.objects.filter(proctored_exam__course_id=course_id)

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
        if isinstance(key, tuple) and len(key) > 0:
            key = key[0]

        # were we passed a PK?
        if isinstance(user_info, (int, long)):
            user_id = user_info
        else:
            # we got a string, so try to resolve it
            users = User.objects.filter(username=user_info)
            if not users.exists():
                users = User.objects.filter(email=user_info)

            if not users.exists():
                err_msg = (
                    'Cannot find user against {user_info}'
                ).format(user_info=user_info)
                raise UserNotFoundException(err_msg)

            user_id = users[0].id

        try:
            student_allowance = cls.objects.get(proctored_exam_id=exam_id, user_id=user_id, key=key)
            student_allowance.value = value
            student_allowance.save()
        except cls.DoesNotExist:  # pylint: disable=no-member
            cls.objects.create(proctored_exam_id=exam_id, user_id=user_id, key=key, value=value)

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
    """

    # what was the original id of the allowance
    allowance_id = models.IntegerField()

    user = models.ForeignKey(User)

    proctored_exam = models.ForeignKey(ProctoredExam)

    key = models.CharField(max_length=255)

    value = models.CharField(max_length=255)

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexamstudentallowancehistory'
        verbose_name = 'proctored allowance history'


# Hook up the post_save signal to record creations in the ProctoredExamStudentAllowanceHistory table.
@receiver(pre_save, sender=ProctoredExamStudentAllowance)
def on_allowance_saved(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Archiving all changes made to the Student Allowance.
    Will only archive on update, and not on new entries created.
    """

    if instance.id:
        original = ProctoredExamStudentAllowance.objects.get(id=instance.id)
        _make_archive_copy(original)


@receiver(pre_delete, sender=ProctoredExamStudentAllowance)
def on_allowance_deleted(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Archive the allowance when the item is about to be deleted
    """

    _make_archive_copy(instance)


def _make_archive_copy(item):
    """
    Make a clone and populate in the History table
    """

    archive_object = ProctoredExamStudentAllowanceHistory(
        allowance_id=item.id,
        user=item.user,
        proctored_exam=item.proctored_exam,
        key=item.key,
        value=item.value
    )
    archive_object.save()


class ProctoredExamSoftwareSecureReview(TimeStampedModel):
    """
    This is where we store the proctored exam review feedback
    from the exam reviewers
    """

    # which student attempt is this feedback for?
    attempt_code = models.CharField(max_length=255, db_index=True)

    # overall status of the review
    review_status = models.CharField(max_length=255)

    # The raw payload that was received back from the
    # reviewing service
    raw_data = models.TextField()

    # URL for the exam video that had been reviewed
    video_url = models.TextField()

    # user_id of person who did the review (can be None if submitted via server-to-server API)
    reviewed_by = models.ForeignKey(User, null=True, related_name='+')

    # student username for the exam
    # this is an optimization for the Django Admin pane (so we can search)
    # this is null because it is being added after initial production ship
    student = models.ForeignKey(User, null=True, related_name='+')

    # exam_id for the review
    # this is an optimization for the Django Admin pane (so we can search)
    # this is null because it is being added after initial production ship
    exam = models.ForeignKey(ProctoredExam, null=True)

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexamsoftwaresecurereview'
        verbose_name = 'Proctored exam software secure review'

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
    """

    # which student attempt is this feedback for?
    attempt_code = models.CharField(max_length=255, db_index=True)

    # overall status of the review
    review_status = models.CharField(max_length=255)

    # The raw payload that was received back from the
    # reviewing service
    raw_data = models.TextField()

    # URL for the exam video that had been reviewed
    video_url = models.TextField()

    # user_id of person who did the review (can be None if submitted via server-to-server API)
    reviewed_by = models.ForeignKey(User, null=True, related_name='+')

    # student username for the exam
    # this is an optimization for the Django Admin pane (so we can search)
    # this is null because it is being added after initial production ship
    student = models.ForeignKey(User, null=True, related_name='+')

    # exam_id for the review
    # this is an optimization for the Django Admin pane (so we can search)
    # this is null because it is being added after initial production ship
    exam = models.ForeignKey(ProctoredExam, null=True)

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexamsoftwaresecurereviewhistory'
        verbose_name = 'Proctored exam review archive'


# Hook up the post_save signal to record creations in the ProctoredExamStudentAllowanceHistory table.
@receiver(pre_save, sender=ProctoredExamSoftwareSecureReview)
def on_review_saved(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Archiving all changes made to the Student Allowance.
    Will only archive on update, and not on new entries created.
    """

    if instance.id:
        # only for update cases
        original = ProctoredExamSoftwareSecureReview.objects.get(id=instance.id)
        _make_review_archive_copy(original)


@receiver(pre_delete, sender=ProctoredExamSoftwareSecureReview)
def on_review_deleted(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Archive the allowance when the item is about to be deleted
    """

    _make_review_archive_copy(instance)


def _make_review_archive_copy(instance):
    """
    Do the copying into the history table
    """

    archive_object = ProctoredExamSoftwareSecureReviewHistory(
        attempt_code=instance.attempt_code,
        review_status=instance.review_status,
        raw_data=instance.raw_data,
        video_url=instance.video_url,
        reviewed_by=instance.reviewed_by,
        student=instance.student,
        exam=instance.exam,
    )
    archive_object.save()


class ProctoredExamSoftwareSecureComment(TimeStampedModel):
    """
    This is where we store the proctored exam review comments
    from the exam reviewers
    """

    # which student attempt is this feedback for?
    review = models.ForeignKey(ProctoredExamSoftwareSecureReview)

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
