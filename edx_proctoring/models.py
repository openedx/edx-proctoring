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
    user_id = models.IntegerField()

    proctored_exam = models.ForeignKey(ProctoredExam)

    # started/completed date times
    started_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)


class ProctoredExamStudentAllowance(TimeStampedModel):
    """
    Information about allowing a student additional time on exam.
    """

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


# Hook up Django signals to record changes in the ProctoredExamStudentAllowanceHistory table.
@receiver(post_save, sender=ProctoredExamStudentAllowance)
def archive_deleted_user_notification(sender, instance, *args, **kwargs):  # pylint: disable=unused-argument
    """
    Archiving the deleted user notifications.
    """
    archive_object = ProctoredExamStudentAllowanceHistory()
    archive_object.__dict__.update(instance.__dict__)
    archive_object.save()
