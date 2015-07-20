"""
Data models for the proctoring subsystem
"""
import pytz
from datetime import datetime
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from model_utils.models import TimeStampedModel

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

    # Whether this exam will be active.
    is_active = models.BooleanField()

    class Meta:
        """ Meta class for this Django model """
        unique_together = (('course_id', 'content_id'),)
        db_table = 'proctoring_proctoredexam'

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
    def get_all_exams_for_course(cls, course_id):
        """
        Returns all exams for a give course
        """
        return cls.objects.filter(course_id=course_id)


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

        return self.filter(proctored_exam__course_id=course_id)

    def get_filtered_exam_attempts(self, course_id, search_by):
        """
        Returns the Student Exam Attempts for the given course_id filtered by search_by.
        """
        filtered_query = Q(proctored_exam__course_id=course_id) & (
            Q(user__username__contains=search_by) | Q(user__email__contains=search_by)
        )

        return self.filter(filtered_query)

    def get_active_student_attempts(self, user_id, course_id=None):
        """
        Returns the active student exams (user in-progress exams)
        """
        filtered_query = Q(user_id=user_id) & Q(started_at__isnull=False) & Q(completed_at__isnull=True)
        if course_id is not None:
            filtered_query = filtered_query & Q(proctored_exam__course_id=course_id)

        return self.filter(filtered_query)


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

    # the exam has timed out
    timed_out = 'timed_out'

    # the student has completed the exam
    completed = 'completed'

    # the student has submitted the exam for proctoring review
    submitted = 'submitted'

    # the exam has been verified and approved
    verified = 'verified'

    # the exam has been rejected
    rejected = 'rejected'

    # the exam is believed to be in error
    error = 'error'


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

    class Meta:
        """ Meta class for this Django model """
        db_table = 'proctoring_proctoredexamstudentattempt'
        verbose_name = 'proctored exam attempt'
        unique_together = (('user', 'proctored_exam'),)

    @property
    def is_active(self):
        """ returns boolean if this attempt is considered active """
        return self.started_at and not self.completed_at

    @classmethod
    def create_exam_attempt(cls, exam_id, user_id, student_name, allowed_time_limit_mins,
                            attempt_code, taking_as_proctored, is_sample_attempt, external_id):
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
        )

    def start_exam_attempt(self):
        """
        sets the model's state when an exam attempt has started
        """
        self.started_at = datetime.now(pytz.UTC)
        self.status = ProctoredExamStudentAttemptStatus.started
        self.save()

    def delete_exam_attempt(self):
        """
        deletes the exam attempt object.
        """
        self.delete()


class ProctoredExamStudentAttemptHistory(TimeStampedModel):
    """
    This should be the same schema as ProctoredExamStudentAttempt
    but will record (for audit history) all entries that have been updated.
    """

    user = models.ForeignKey(User, db_index=True)

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


@receiver(pre_delete, sender=ProctoredExamStudentAttempt)
def on_attempt_deleted(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Archive the exam attempt when the item is about to be deleted
    Make a clone and populate in the History table
    """

    archive_object = ProctoredExamStudentAttemptHistory(
        user=instance.user,
        proctored_exam=instance.proctored_exam,
        started_at=instance.started_at,
        completed_at=instance.completed_at,
        attempt_code=instance.attempt_code,
        external_id=instance.external_id,
        allowed_time_limit_mins=instance.allowed_time_limit_mins,
        status=instance.status,
        taking_as_proctored=instance.taking_as_proctored,
        is_sample_attempt=instance.is_sample_attempt,
        student_name=instance.student_name
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
        users = User.objects.filter(username=user_info)
        if not users.exists():
            users = User.objects.filter(email=user_info)

        if not users.exists():
            err_msg = (
                'Cannot find user against {user_info}'
            ).format(user_info=user_info)
            raise UserNotFoundException(err_msg)

        try:
            student_allowance = cls.objects.get(proctored_exam_id=exam_id, user_id=users[0].id, key=key)
            student_allowance.value = value
            student_allowance.save()
        except cls.DoesNotExist:  # pylint: disable=no-member
            cls.objects.create(proctored_exam_id=exam_id, user_id=users[0].id, key=key, value=value)


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
@receiver(post_save, sender=ProctoredExamStudentAllowance)
def on_allowance_saved(sender, instance, created, **kwargs):  # pylint: disable=unused-argument
    """
    Archiving all changes made to the Student Allowance.
    Will only archive on update, and not on new entries created.
    """

    if not created:
        _make_archive_copy(instance)


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
