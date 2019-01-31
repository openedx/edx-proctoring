"edx-proctoring signals"
from django.db.models.signals import pre_save, post_save, pre_delete
from django.dispatch import receiver

from edx_proctoring import api
from edx_proctoring import models
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus, ReviewStatus
from edx_proctoring.utils import emit_event, locate_attempt_by_attempt_code
from edx_proctoring.backends import get_backend_provider


@receiver(pre_save, sender=models.ProctoredExam)
def check_for_category_switch(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    If the exam switches from proctored to timed, notify the backend
    """
    if instance.id:
        original = sender.objects.get(pk=instance.id)
        if original.is_proctored and instance.is_proctored != original.is_proctored:
            from edx_proctoring.serializers import ProctoredExamSerializer
            exam = ProctoredExamSerializer(instance).data
            # from the perspective of the backend, the exam is now inactive.
            exam['is_active'] = False
            backend = get_backend_provider(name=exam['backend'])
            backend.on_exam_saved(exam)


@receiver(post_save, sender=models.ProctoredExamReviewPolicy)
@receiver(post_save, sender=models.ProctoredExam)
def save_exam_on_backend(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Save the exam to the backend provider when our model changes.
    It also combines the review policy into the exam when saving to the backend
    """
    if sender == models.ProctoredExam:
        exam_obj = instance
        review_policy = models.ProctoredExamReviewPolicy.get_review_policy_for_exam(instance.id)
    else:
        exam_obj = instance.proctored_exam
        review_policy = instance
    if exam_obj.is_proctored:
        from edx_proctoring.serializers import ProctoredExamSerializer
        exam = ProctoredExamSerializer(exam_obj).data
        if review_policy:
            exam['rule_summary'] = review_policy.review_policy
        backend = get_backend_provider(exam)
        external_id = backend.on_exam_saved(exam)
        if external_id and external_id != exam_obj.external_id:
            exam_obj.external_id = external_id
            exam_obj.save()


# Hook up the pre_save signal to record creations in the ProctoredExamReviewPolicyHistory table.
@receiver(pre_save, sender=models.ProctoredExamReviewPolicy)
@receiver(pre_delete, sender=models.ProctoredExamReviewPolicy)
def on_review_policy_changed(sender, instance, signal, **kwargs):  # pylint: disable=unused-argument
    """
    Archiving all changes made to the Review Policy.
    Will only archive on update/delete, and not on new entries created.
    """
    if signal is pre_save:
        if instance.id:
            instance = sender.objects.get(id=instance.id)
        else:
            return
    models.archive_model(models.ProctoredExamReviewPolicyHistory, instance, id='original_id')


# Hook up the post_save signal to record creations in the ProctoredExamStudentAllowanceHistory table.
@receiver(pre_save, sender=models.ProctoredExamStudentAllowance)
@receiver(pre_delete, sender=models.ProctoredExamStudentAllowance)
def on_allowance_changed(sender, instance, signal, **kwargs):  # pylint: disable=unused-argument
    """
    Archiving all changes made to the Student Allowance.
    Will only archive on update/delete, and not on new entries created.
    """

    if signal is pre_save:
        if instance.id:
            instance = sender.objects.get(id=instance.id)
        else:
            return
    models.archive_model(models.ProctoredExamStudentAllowanceHistory, instance, id='allowance_id')


@receiver(pre_save, sender=models.ProctoredExamStudentAttempt)
@receiver(pre_delete, sender=models.ProctoredExamStudentAttempt)
def on_attempt_changed(sender, instance, signal, **kwargs):  # pylint: disable=unused-argument
    """
    Archive the exam attempt whenever the attempt status is about to be
    modified. Make a new entry with the previous value of the status in the
    ProctoredExamStudentAttemptHistory table.
    """

    if signal is pre_save:
        if instance.id:
            # on an update case, get the original
            # and see if the status has changed, if so, then we need
            # to archive it
            original = sender.objects.get(id=instance.id)

            if original.status != instance.status:
                instance = original
            else:
                return
        else:
            return
    models.archive_model(models.ProctoredExamStudentAttemptHistory, instance, id='attempt_id')


# Hook up the signals to record updates/deletions in the ProctoredExamStudentAllowanceHistory table.
@receiver(pre_save, sender=models.ProctoredExamSoftwareSecureReview)
@receiver(pre_delete, sender=models.ProctoredExamSoftwareSecureReview)
def on_review_changed(sender, instance, signal, **kwargs):  # pylint: disable=unused-argument
    """
    Archiving all changes made to the Review.
    Will only archive on update/delete, and not on new entries created.
    """
    if signal is pre_save:
        if instance.id:
            # only for update cases
            instance = sender.objects.get(id=instance.id)
        else:
            # don't archive on create
            return
    models.archive_model(models.ProctoredExamSoftwareSecureReviewHistory, instance, id='review_id')


@receiver(post_save, sender=models.ProctoredExamSoftwareSecureReview)
def finish_review_workflow(sender, instance, signal, **kwargs):  # pylint: disable=unused-argument
    """
    Updates the attempt status based on the review status
    """
    review = instance
    attempt_obj, is_archived = locate_attempt_by_attempt_code(review.attempt_code)
    attempt = api.ProctoredExamStudentAttemptSerializer(attempt_obj).data

    # we could have gotten a review for an archived attempt
    # this should *not* cause an update in our credit
    # eligibility table
    if review.is_passing:
        attempt_status = ProctoredExamStudentAttemptStatus.verified
    elif review.review_status == ReviewStatus.suspicious:
        attempt_status = ProctoredExamStudentAttemptStatus.second_review_required
    else:
        attempt_status = ProctoredExamStudentAttemptStatus.rejected

    if not is_archived:
        # updating attempt status will trigger workflow
        # (i.e. updating credit eligibility table)
        # archived attempts should not trigger the workflow
        api.update_attempt_status(
            attempt['proctored_exam']['id'],
            attempt['user']['id'],
            attempt_status,
            raise_if_not_found=False
        )

    # emit an event for 'review_received'
    data = {
        'review_attempt_code': review.attempt_code,
        'review_status': review.review_status,
    }
    emit_event(attempt['proctored_exam'], 'review_received', attempt=attempt, override_data=data)
