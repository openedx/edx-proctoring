"""
Data models for the proctoring subsystem
"""
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from model_utils.models import TimeStampedModel


class ProctoredExam(models.Model):
    """
    Information about the Proctored Exam.
    """

    course_id = models.CharField(max_length=255, db_index=True)

    # This will be the pointer to the id of the piece
    # of course_ware which is the proctored exam.
    content_id = models.CharField(max_length=255, db_index=True)

    # This will be a integration specific ID - say to SoftwareSecure.
    external_id = models.TextField(null=True, db_index=True)


class ProctoredExamStudentAttempt(models.Model):
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


class QuerySetWithUpdateSignal(models.query.QuerySet):
    """
    Custom QuerySet class to send the POST_UPDATE_SIGNAL
    every time the object is updated.
    """
    def update(self, **kwargs):
        print 'here'
        super(QuerySetWithUpdateSignal, self).update(**kwargs)
        _make_archive_copy(self.get())


class ProctoredExamStudentAllowanceManager(models.Manager):
    """
    Custom manager to override with the custom queryset
    to enable the POST_UPDATE_SIGNAL
    """
    def get_query_set(self):
        return QuerySetWithUpdateSignal(self.model, using=self._db)


class ProctoredExamStudentAllowance(TimeStampedModel):
    """
    Information about allowing a student additional time on exam.
    """

    objects = ProctoredExamStudentAllowanceManager()

    user_id = models.IntegerField()

    proctored_exam = models.ForeignKey(ProctoredExam)

    key = models.CharField(max_length=255)

    value = models.CharField(max_length=255)


class ProctoredExamStudentAllowanceHistory(TimeStampedModel):
    """
    This should be the same schema as ProctoredExamStudentAllowance
    but will record (for audit history) all entries that have been updated.
    """

    user_id = models.IntegerField()

    proctored_exam = models.ForeignKey(ProctoredExam)

    key = models.CharField(max_length=255)

    value = models.CharField(max_length=255)


# Hook up the custom POST_UPDATE_SIGNAL signal to record updations in the ProctoredExamStudentAllowanceHistory table.
@receiver(post_save, sender=ProctoredExamStudentAllowance)
def archive_allowance_updations(sender, **kwargs):  # pylint: disable=unused-argument
    """
    Archiving all changes made to the Student Allowance.
    Will only archive on update, and not on new entries created.
    """

    _make_archive_copy(kwargs['instance'])


def _make_archive_copy(updated_obj):
    """
    Make a clone and populate in the History table
    """

    archive_object = ProctoredExamStudentAllowanceHistory()
    updated_obj_dict = updated_obj.__dict__
    updated_obj_dict.pop('id')
    archive_object.__dict__.update(updated_obj_dict)
    archive_object.save()
