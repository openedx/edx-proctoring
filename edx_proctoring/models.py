"""
Data models for the proctoring subsystem
"""
import pytz
from datetime import datetime
from django.db import models
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from model_utils.models import TimeStampedModel


class ProctoredExam(TimeStampedModel):
    """
    Information about the Proctored Exam.
    """

    course_id = models.CharField(max_length=255, db_index=True)

    # This will be the pointer to the id of the piece
    # of course_ware which is the proctored exam.
    content_id = models.CharField(max_length=255, db_index=True)

    # This will be a integration specific ID - say to SoftwareSecure.
    external_id = models.TextField(null=True, db_index=True)

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

    @classmethod
    def get_exam_by_content_id(cls, course_id, content_id):
        """
        Returns the Proctored Exam if found else returns None,
        Given course_id and content_id
        """
        try:
            proctored_exam = cls.objects.get(course_id=course_id, content_id=content_id)
        except cls.DoesNotExist:
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
        except cls.DoesNotExist:
            proctored_exam = None
        return proctored_exam


class ProctoredExamStudentAttempt(TimeStampedModel):
    """
    Information about the Student Attempt on a
    Proctored Exam.
    """
    user_id = models.IntegerField(db_index=True)

    proctored_exam = models.ForeignKey(ProctoredExam, db_index=True)

    # started/completed date times
    started_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)

    # This will be a integration specific ID - say to SoftwareSecure.
    external_id = models.TextField(null=True, db_index=True)

    # what is the status of this attempt
    status = models.CharField(max_length=64)

    @property
    def is_active(self):
        """ returns boolean if this attempt is considered active """
        return self.started_at and not self.completed_at

    @classmethod
    def start_exam_attempt(cls, exam_id, user_id, external_id):
        """
        create and return an exam attempt entry for a given
        exam_id. If one already exists, then returns None.
        """
        if cls.get_student_exam_attempt(exam_id, user_id) is None:
            return cls.objects.create(
                proctored_exam_id=exam_id,
                user_id=user_id,
                external_id=external_id,
                started_at=datetime.now(pytz.UTC)
            )
        else:
            return None

    @classmethod
    def get_student_exam_attempt(cls, exam_id, user_id):
        """
        Returns the Student Exam Attempt object if found
        else Returns None.
        """
        try:
            exam_attempt_obj = cls.objects.get(proctored_exam_id=exam_id, user_id=user_id)
        except cls.DoesNotExist:
            exam_attempt_obj = None
        return exam_attempt_obj


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

    user_id = models.IntegerField()

    proctored_exam = models.ForeignKey(ProctoredExam)

    key = models.CharField(max_length=255)

    value = models.CharField(max_length=255)

    class Meta:
        """ Meta class for this Django model """
        unique_together = (('user_id', 'proctored_exam', 'key'),)

    @classmethod
    def get_allowance_for_user(cls, exam_id, user_id, key):
        """
        Returns an allowance for a user within a given exam
        """
        try:
            student_allowance = cls.objects.get(proctored_exam_id=exam_id, user_id=user_id, key=key)
        except cls.DoesNotExist:
            student_allowance = None
        return student_allowance

    @classmethod
    def add_allowance_for_user(cls, exam_id, user_id, key, value):
        """
        Add or (Update) an allowance for a user within a given exam
        """
        try:
            student_allowance = cls.objects.get(proctored_exam_id=exam_id, user_id=user_id, key=key)
            student_allowance.value = value
            student_allowance.save()
        except cls.DoesNotExist:
            cls.objects.create(proctored_exam_id=exam_id, user_id=user_id, key=key, value=value)


class ProctoredExamStudentAllowanceHistory(TimeStampedModel):
    """
    This should be the same schema as ProctoredExamStudentAllowance
    but will record (for audit history) all entries that have been updated.
    """

    # what was the original id of the allowance
    allowance_id = models.IntegerField()

    user_id = models.IntegerField()

    proctored_exam = models.ForeignKey(ProctoredExam)

    key = models.CharField(max_length=255)

    value = models.CharField(max_length=255)


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
        user_id=item.user_id,
        proctored_exam=item.proctored_exam,
        key=item.key,
        value=item.value
    )
    archive_object.save()
