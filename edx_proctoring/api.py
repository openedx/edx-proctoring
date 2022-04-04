# pylint: disable=too-many-branches, too-many-lines, too-many-statements

"""
In-Proc API (aka Library) for the edx_proctoring subsystem. This is not to be confused with a HTTP REST
API which is in the views.py file, per edX coding standards
"""

import logging
import uuid
from datetime import datetime, timedelta

import pytz
from opaque_keys import InvalidKeyError

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail.message import EmailMessage
from django.template import loader
from django.urls import NoReverseMatch, reverse
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop

from edx_proctoring import constants
from edx_proctoring.backends import get_backend_provider
from edx_proctoring.exceptions import (
    AllowanceValueNotAllowedException,
    BackendProviderCannotRegisterAttempt,
    BackendProviderNotConfigured,
    BackendProviderOnboardingException,
    BackendProviderSentNoAttemptID,
    ProctoredBaseException,
    ProctoredExamAlreadyExists,
    ProctoredExamIllegalResumeUpdate,
    ProctoredExamIllegalStatusTransition,
    ProctoredExamNotActiveException,
    ProctoredExamNotFoundException,
    ProctoredExamPermissionDenied,
    ProctoredExamReviewPolicyAlreadyExists,
    ProctoredExamReviewPolicyNotFoundException,
    StudentExamAttemptAlreadyExistsException,
    StudentExamAttemptDoesNotExistsException,
    StudentExamAttemptedAlreadyStarted,
    StudentExamAttemptOnPastDueProctoredExam
)
from edx_proctoring.models import (
    ProctoredExam,
    ProctoredExamReviewPolicy,
    ProctoredExamSoftwareSecureReview,
    ProctoredExamStudentAllowance,
    ProctoredExamStudentAttempt
)
from edx_proctoring.runtime import get_runtime_service
from edx_proctoring.serializers import (
    ProctoredExamReviewPolicySerializer,
    ProctoredExamSerializer,
    ProctoredExamStudentAllowanceSerializer,
    ProctoredExamStudentAttemptSerializer
)
from edx_proctoring.signals import exam_attempt_status_signal
from edx_proctoring.statuses import InstructorDashboardOnboardingAttemptStatus, ProctoredExamStudentAttemptStatus
from edx_proctoring.utils import (
    categorize_inaccessible_exams_by_date,
    emit_event,
    get_exam_due_date,
    get_exam_type,
    get_exam_url,
    get_time_remaining_for_attempt,
    get_user_course_outline_details,
    has_due_date_passed,
    has_end_date_passed,
    humanized_time,
    is_reattempting_exam,
    obscured_user_id,
    verify_and_add_wait_deadline
)

log = logging.getLogger(__name__)

SHOW_EXPIRY_MESSAGE_DURATION = 1 * 60  # duration within which expiry message is shown for a timed-out exam

APPROVED_STATUS = 'approved'

REJECTED_GRADE_OVERRIDE_EARNED = 0.0

USER_MODEL = get_user_model()


def get_onboarding_exam_link(course_id, user, is_learning_mfe):
    """
    Get link to the onboarding exam available to the user for given course.

    Parameters:
    * course_id: id of a course where search for the onboarding exam is performed
    * user: user for whom the link is built
    * is_learning_mfe: Boolean, indicates if the url should be built for the learning mfe application.

    Returns: url pointing to the available exam, if there is no onboarding exam available
    to the user returns empty string.
    """
    onboarding_exams = list(ProctoredExam.get_practice_proctored_exams_for_course(course_id).order_by('-created'))
    if not onboarding_exams or not get_backend_provider(name=onboarding_exams[0].backend).supports_onboarding:
        onboarding_link = ''
    else:
        details = get_user_course_outline_details(user, course_id)
        categorized_exams = categorize_inaccessible_exams_by_date(onboarding_exams, details)
        non_date_inaccessible_exams = categorized_exams[0]

        # remove onboarding exams not accessible to learners
        for onboarding_exam in non_date_inaccessible_exams:
            onboarding_exams.remove(onboarding_exam)

        if onboarding_exams:
            onboarding_exam = onboarding_exams[0]
            onboarding_link = get_exam_url(course_id, onboarding_exam.content_id, is_learning_mfe)
        else:
            onboarding_link = ''
    return onboarding_link


def get_total_allowed_time_for_exam(exam, user_id):
    """
    Returns total allowed time in humanized form for exam including allowance time.
    """
    total_allowed_time = _calculate_allowed_mins(exam, user_id)
    return humanized_time(total_allowed_time)


def get_proctoring_settings_by_exam_id(exam_id):
    """
    Return proctoring settings and exam proctoring backend for proctored exam by exam_id.

    Raises an exception if exam_id not found.
    Raises BackendProviderNotConfigured exception if proctoring backend is not configured.
    """
    exam = get_exam_by_id(exam_id)
    proctoring_settings = getattr(settings, 'PROCTORING_SETTINGS', {})
    proctoring_settings_data = {
        'platform_name': settings.PLATFORM_NAME,
        'contact_us': settings.CONTACT_EMAIL,
        'link_urls': proctoring_settings.get('LINK_URLS'),
        'exam_proctoring_backend': {},
    }
    if exam.get('is_proctored'):
        try:
            provider = get_backend_provider(exam)
        except NotImplementedError as error:
            log.exception(str(error))
            raise BackendProviderNotConfigured(str(error)) from error
        proctoring_settings_data.update({
            'exam_proctoring_backend': provider.get_proctoring_config(),
            'provider_tech_support_email': provider.tech_support_email,
            'provider_tech_support_phone': provider.tech_support_phone,
            'provider_name': provider.verbose_name,
            'learner_notification_from_email': provider.learner_notification_from_email,
            'integration_specific_email': get_integration_specific_email(provider),
            'proctoring_escalation_email': _get_proctoring_escalation_email(exam['course_id']),
        })
    return proctoring_settings_data


def create_exam(course_id, content_id, exam_name, time_limit_mins, due_date=None,
                is_proctored=True, is_practice_exam=False, external_id=None, is_active=True, hide_after_due=False,
                backend=None):
    """
    Creates a new ProctoredExam entity, if the course_id/content_id pair do not already exist.
    If that pair already exists, then raise exception.

    Returns: id (PK)
    """

    if ProctoredExam.get_exam_by_content_id(course_id, content_id) is not None:
        err_msg = (
            f'Attempted to create proctored exam with course_id={course_id} and content_id={content_id}, '
            'but this exam already exists.'
        )
        raise ProctoredExamAlreadyExists(err_msg)

    proctored_exam = ProctoredExam.objects.create(
        course_id=course_id,
        content_id=content_id,
        external_id=external_id,
        exam_name=exam_name,
        time_limit_mins=time_limit_mins,
        due_date=due_date,
        is_proctored=is_proctored,
        is_practice_exam=is_practice_exam,
        is_active=is_active,
        hide_after_due=hide_after_due,
        backend=backend or settings.PROCTORING_BACKENDS.get('DEFAULT', None),
    )

    log.info(
        ('Created exam (exam_id=%(exam_id)s) with parameters: course_id=%(course_id)s, '
         'content_id=%(content_id)s, exam_name=%(exam_name)s, time_limit_mins=%(time_limit_mins)s, '
         'is_proctored=%(is_proctored)s, is_practice_exam=%(is_practice_exam)s, '
         'external_id=%(external_id)s, is_active=%(is_active)s, hide_after_due=%(hide_after_due)s'),
        {
            'exam_id': proctored_exam.id,
            'course_id': course_id,
            'content_id': content_id,
            'exam_name': exam_name,
            'time_limit_mins': time_limit_mins,
            'is_proctored': is_proctored,
            'is_practice_exam': is_practice_exam,
            'external_id': external_id,
            'hide_after_due': hide_after_due,
        }
    )

    # read back exam so we can emit an event on it
    exam = get_exam_by_id(proctored_exam.id)
    emit_event(exam, 'created')
    return proctored_exam.id


def create_exam_review_policy(exam_id, set_by_user_id, review_policy):
    """
    Creates a new exam_review_policy entity, if the review_policy
    for exam_id does not already exist. If it exists, then raise exception.

    Arguments:
        exam_id: the ID of the exam with which the review policy is to be associated
        set_by_user_id: the ID of the user setting this review policy
        review_policy: the review policy for the exam

    Returns: id (PK)
    """
    exam_review_policy = ProctoredExamReviewPolicy.get_review_policy_for_exam(exam_id)
    if exam_review_policy is not None:
        err_msg = (
            f'user_id={set_by_user_id} attempted to create an exam review policy for '
            f'exam_id={exam_id}, but a review policy for this exam already exists.'
        )
        raise ProctoredExamReviewPolicyAlreadyExists(err_msg)

    exam_review_policy = ProctoredExamReviewPolicy.objects.create(
        proctored_exam_id=exam_id,
        set_by_user_id=set_by_user_id,
        review_policy=review_policy,
    )

    log.info(
        ('Created ProctoredExamReviewPolicy (review_policy=%(review_policy)s) '
         'with parameters: exam_id=%(exam_id)s, set_by_user_id=%(set_by_user_id)s'),
        {
            'exam_id': exam_id,
            'review_policy': review_policy,
            'set_by_user_id': set_by_user_id,
        }
    )

    return exam_review_policy.id


def update_review_policy(exam_id, set_by_user_id, review_policy):
    """
    Given a exam id, update/remove the existing record, otherwise raise exception if not found.

    Arguments:
        exam_id: the ID of the exam whose review policy is being updated
        set_by_user_id: the ID of the user updating this review policy
        review_policy: the review policy for the exam

    Returns: review_policy_id
    """
    log.info(
        ('Updating exam review policy with exam_id=%(exam_id)s '
         'set_by_user_id=%(set_by_user_id)s, review_policy=%(review_policy)s '),
        {
            'exam_id': exam_id,
            'set_by_user_id': set_by_user_id,
            'review_policy': review_policy,
        }
    )
    exam_review_policy = ProctoredExamReviewPolicy.get_review_policy_for_exam(exam_id)
    if exam_review_policy is None:
        err_msg = (
            f'user_id={set_by_user_id} attempted to update exam review policy for '
            f'exam_id={exam_id}, but this exam does not have a review policy.'
        )
        raise ProctoredExamReviewPolicyNotFoundException(err_msg)

    if review_policy:
        exam_review_policy.set_by_user_id = set_by_user_id
        exam_review_policy.review_policy = review_policy
        exam_review_policy.save()
        log.info(
            'Updated exam review policy for exam_id=%(exam_id)s, set_by_user_id=%(set_by_user_id)s',
            {
                'set_by_user_id': set_by_user_id,
                'exam_id': exam_id,
            }
        )
    else:
        exam_review_policy.delete()
        log.info(
            'Removed exam review policy for exam_id=%(exam_id)s, set_by_user_id=%(set_by_user_id)s',
            {
                'set_by_user_id': set_by_user_id,
                'exam_id': exam_id,
            }
        )


def remove_review_policy(exam_id):
    """
    Given a exam id, remove the existing record, otherwise raise exception if not found.
    """

    log.info(
        'Removing exam review policy for exam_id=%(exam_id)s',
        {
            'exam_id': exam_id,
        }
    )
    exam_review_policy = ProctoredExamReviewPolicy.get_review_policy_for_exam(exam_id)
    if exam_review_policy is None:
        err_msg = (
            f'Attempted to remove exam remove policy for exam_id={exam_id}, but this '
            'exam does not have a review policy.'
        )
        raise ProctoredExamReviewPolicyNotFoundException(err_msg)

    exam_review_policy.delete()


def get_review_policy_by_exam_id(exam_id):
    """
    Looks up exam by the Primary Key. Raises exception if not found.

    Returns dictionary version of the Django ORM object
    e.g.
    {
        "id": 1
        "proctored_exam": "{object}",
        "set_by_user": "{object}",
        "exam_review_rules": "review rules value"
        "created": "datetime",
        "modified": "datetime"
    }
    """
    exam_review_policy = ProctoredExamReviewPolicy.get_review_policy_for_exam(exam_id)
    if exam_review_policy is None:
        err_msg = (
            f'Attempted to get exam review policy for exam_id={exam_id}, but this review '
            'policy does not exist.'
        )
        raise ProctoredExamReviewPolicyNotFoundException(err_msg)

    return ProctoredExamReviewPolicySerializer(exam_review_policy).data


def _get_review_policy_by_exam_id(exam_id):
    """
    Looks up exam by the primary key. Returns None if not found

    Returns review_policy field of the Django ORM object
    """
    try:
        exam_review_policy = get_review_policy_by_exam_id(exam_id)
        return ProctoredExamReviewPolicySerializer(exam_review_policy).data['review_policy']
    except ProctoredExamReviewPolicyNotFoundException:
        return None


def update_exam(exam_id, exam_name=None, time_limit_mins=None, due_date=constants.MINIMUM_TIME,
                is_proctored=None, is_practice_exam=None, external_id=None, is_active=None,
                hide_after_due=None, backend=None):
    """
    Given a Django ORM id, update the existing record, otherwise raise exception if not found.
    If an argument is not passed in, then do not change it's current value.

    Returns: id
    """

    log.info(
        ('Updating exam_id=%(exam_id)s with parameters '
         'exam_name=%(exam_name)s, time_limit_mins=%(time_limit_mins)s, due_date=%(due_date)s'
         'is_proctored=%(is_proctored)s, is_practice_exam=%(is_practice_exam)s, '
         'external_id=%(external_id)s, is_active=%(is_active)s, hide_after_due=%(hide_after_due)s, '
         'backend=%(backend)s'),
        {
            'exam_id': exam_id,
            'exam_name': exam_name,
            'time_limit_mins': time_limit_mins,
            'due_date': due_date,
            'is_proctored': is_proctored,
            'is_practice_exam': is_practice_exam,
            'external_id': external_id,
            'is_active': is_active,
            'hide_after_due': hide_after_due,
            'backend': backend,
        }
    )

    proctored_exam = ProctoredExam.get_exam_by_id(exam_id)
    if proctored_exam is None:
        err_msg = (
            f'Attempted to update exam_id={exam_id}, but this exam does not exist.'
        )
        raise ProctoredExamNotFoundException(err_msg)

    if exam_name is not None:
        proctored_exam.exam_name = exam_name
    if time_limit_mins is not None:
        proctored_exam.time_limit_mins = time_limit_mins
    if due_date is not constants.MINIMUM_TIME:
        proctored_exam.due_date = due_date
    if is_proctored is not None:
        proctored_exam.is_proctored = is_proctored
    if is_practice_exam is not None:
        proctored_exam.is_practice_exam = is_practice_exam
    if external_id is not None:
        proctored_exam.external_id = external_id
    if is_active is not None:
        proctored_exam.is_active = is_active
    if hide_after_due is not None:
        proctored_exam.hide_after_due = hide_after_due
    if backend is not None:
        proctored_exam.backend = backend
    proctored_exam.save()

    # read back exam so we can emit an event on it
    exam = get_exam_by_id(proctored_exam.id)
    emit_event(exam, 'updated')

    return proctored_exam.id


def get_exam_by_id(exam_id):
    """
    Looks up exam by the Primary Key. Raises exception if not found.

    Returns dictionary version of the Django ORM object
    e.g.
    {
        "course_id": "edX/DemoX/Demo_Course",
        "content_id": "123",
        "external_id": "",
        "exam_name": "Midterm",
        "time_limit_mins": 90,
        "is_proctored": true,
        "is_active": true
    }
    """
    proctored_exam = ProctoredExam.get_exam_by_id(exam_id)
    if proctored_exam is None:
        err_msg = (
            f'Attempted to get exam_id={exam_id}, but this exam does not exist.'
        )
        raise ProctoredExamNotFoundException(err_msg)

    serialized_exam_object = ProctoredExamSerializer(proctored_exam)
    return serialized_exam_object.data


def get_exam_by_content_id(course_id, content_id):
    """
    Looks up exam by the course_id/content_id pair. Raises exception if not found.

    Returns dictionary version of the Django ORM object
    e.g.
    {
        "course_id": "edX/DemoX/Demo_Course",
        "content_id": "123",
        "external_id": "",
        "exam_name": "Midterm",
        "time_limit_mins": 90,
        "is_proctored": true,
        "is_active": true
    }
    """
    proctored_exam = ProctoredExam.get_exam_by_content_id(course_id, content_id)
    if proctored_exam is None:
        err_msg = (
            f'Cannot find proctored exam in course_id={course_id} with content_id={content_id}'
        )
        raise ProctoredExamNotFoundException(err_msg)

    serialized_exam_object = ProctoredExamSerializer(proctored_exam)
    return serialized_exam_object.data


def add_allowance_for_user(exam_id, user_info, key, value):
    """
    Adds (or updates) an allowance for a user within a given exam
    """

    log.info(
        ('Adding allowance key=%(key)s with value=%(value)s for exam_id=%(exam_id)s '
         'for user=%(user_info)s '),
        {
            'key': key,
            'value': value,
            'exam_id': exam_id,
            'user_info': user_info,
        }
    )

    try:
        student_allowance, action = ProctoredExamStudentAllowance.add_allowance_for_user(exam_id, user_info, key, value)
    except ProctoredExamNotActiveException as error:
        # let this exception raised so that we get 400 in case of inactive exam
        raise ProctoredExamNotActiveException from error

    if student_allowance is not None:
        # emit an event for 'allowance.created|updated'
        data = {
            'allowance_user_id': student_allowance.user.id,
            'allowance_key': student_allowance.key,
            'allowance_value': student_allowance.value
        }

        exam = get_exam_by_id(exam_id)
        emit_event(exam, f'allowance.{action}', override_data=data)


def get_allowances_for_course(course_id):
    """
    Get all the allowances for the course.
    """
    student_allowances = ProctoredExamStudentAllowance.get_allowances_for_course(
        course_id
    )
    return [ProctoredExamStudentAllowanceSerializer(allowance).data for allowance in student_allowances]


def remove_allowance_for_user(exam_id, user_id, key):
    """
    Deletes an allowance for a user within a given exam.
    """
    log.info(
        'Removing allowance key=%(key)s for exam_id=%(exam_id)s for user_id=%(user_id)s',
        {
            'key': key,
            'exam_id': exam_id,
            'user_id': user_id,
        }
    )

    student_allowance = ProctoredExamStudentAllowance.get_allowance_for_user(exam_id, user_id, key)
    if student_allowance is not None:
        student_allowance.delete()

        # emit an event for 'allowance.deleted'
        data = {
            'allowance_user_id': student_allowance.user.id,
            'allowance_key': student_allowance.key,
            'allowance_value': student_allowance.value
        }

        exam = get_exam_by_id(exam_id)
        emit_event(exam, 'allowance.deleted', override_data=data)


def add_bulk_allowances(exam_ids, user_ids, allowance_type, value):
    """
    Adds (or updates) an allowance for multiple users and exams
    """

    # Input pasrsing
    exam_ids = set(exam_ids)
    user_ids = set(user_ids)

    # Input validation logic to verify input is acceptable
    log.info(
        ('Adding allowances of type allowance_type=%(allowance_type)s with value=%(value)s '
         'for exams exam_ids=%(exam_ids)s and users user_ids=%(user_ids)s'),
        {
            'allowance_type': allowance_type,
            'value': value,
            'exam_ids': exam_ids,
            'user_ids': user_ids,
        }
    )

    multiplier = 0
    if allowance_type == constants.TIME_MULTIPLIER:
        err_msg = (
            f'allowance_value "{value}" should be a float value greater than 1.'
        )
        try:
            multiplier = float(value) - 1
        except ValueError as error:
            raise AllowanceValueNotAllowedException(err_msg) from error
        if multiplier < 0:
            raise AllowanceValueNotAllowedException(err_msg)

    if (allowance_type in ProctoredExamStudentAllowance.ADDITIONAL_TIME_GRANTED
            and not value.isdigit()):
        err_msg = (
            f'allowance_value "{value}" should be a non-negative integer value'
        )
        raise AllowanceValueNotAllowedException(err_msg)

    # Data processing logic to add allowances to the database
    successes = 0
    failures = 0
    data = []
    for exam_id in exam_ids:
        try:
            target_exam = get_exam_by_id(exam_id)
        except ProctoredExamNotFoundException:
            log.error(
                'Attempted to get exam_id=%(exam_id)s, but this exam does not exist.',
                {
                    'exam_id': exam_id,
                }
            )
            for user_id in user_ids:
                failures += 1
                data.append({

                    'exam_id': exam_id,
                    'user_id': user_id,
                })
            continue
        if allowance_type == constants.TIME_MULTIPLIER:
            exam_time = target_exam["time_limit_mins"]
            added_time = round(exam_time * multiplier)
            time_allowed = str(added_time)
            for user_id in user_ids:
                try:
                    add_allowance_for_user(exam_id, user_id,
                                           ProctoredExamStudentAllowance.ADDITIONAL_TIME_GRANTED,
                                           time_allowed)
                    successes += 1
                    data.append({

                        'exam_id': exam_id,
                        'user_id': user_id,
                    })

                except ProctoredBaseException:
                    log.error(
                        ('Failed to add allowance for user_id=%(user_id)s '
                         'for exam_id=%(exam_id)s'),
                        {
                            'user_id': user_id,
                            'exam_id': exam_id,
                        }
                    )
                    failures += 1
                    data.append({

                        'exam_id': exam_id,
                        'user_id': user_id,
                    })
        else:
            for user_id in user_ids:
                try:
                    add_allowance_for_user(exam_id, user_id,
                                           allowance_type,
                                           value)
                    successes += 1
                    data.append({

                        'exam_id': exam_id,
                        'user_id': user_id,
                    })
                except ProctoredBaseException:
                    log.error(
                        ('Failed to add allowance for user_id=%(user_id)s '
                         'for exam_id=%(exam_id)s'),
                        {
                            'user_id': user_id,
                            'exam_id': exam_id,
                        }
                    )
                    failures += 1
                    data.append({

                        'exam_id': exam_id,
                        'user_id': user_id,
                    })
    return data, successes, failures


def _check_for_attempt_timeout(attempt):
    """
    Helper method to see if the status of an
    exam needs to be updated, e.g. timeout
    """

    if not attempt:
        return attempt

    # right now the only adjustment to
    # status is transitioning to timeout
    has_started_exam = (
        attempt and
        attempt.get('started_at') and
        ProctoredExamStudentAttemptStatus.is_incomplete_status(attempt.get('status'))
    )
    if has_started_exam:
        now_utc = datetime.now(pytz.UTC)
        expires_at = attempt['started_at'] + timedelta(minutes=attempt['allowed_time_limit_mins'])
        has_time_expired = now_utc > expires_at

        if has_time_expired:
            update_attempt_status(
                attempt['id'],
                ProctoredExamStudentAttemptStatus.timed_out,
                timeout_timestamp=expires_at
            )
            attempt = get_exam_attempt_by_id(attempt['id'])

    return attempt


def _get_exam_attempt(exam_attempt_obj):
    """
    Helper method to commonalize all query patterns
    """

    if not exam_attempt_obj:
        return None

    serialized_attempt_obj = ProctoredExamStudentAttemptSerializer(exam_attempt_obj)
    attempt = serialized_attempt_obj.data
    attempt = _check_for_attempt_timeout(attempt)

    return attempt


def get_current_exam_attempt(exam_id, user_id):
    """
    Args:
        int: exam id
        int: user_id
    Returns:
        dict: our exam attempt
    """
    exam_attempt_obj = ProctoredExamStudentAttempt.objects.get_current_exam_attempt(exam_id, user_id)
    return _get_exam_attempt(exam_attempt_obj)


def get_exam_attempt_by_id(attempt_id):
    """
    Args:
        int: exam attempt id
    Returns:
        dict: our exam attempt
    """
    exam_attempt_obj = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_id(attempt_id)
    return _get_exam_attempt(exam_attempt_obj)


def get_exam_attempt_by_external_id(external_id):
    """
    Args:
        str: exam attempt external_id
    Returns:
        dict: our exam attempt
    """
    exam_attempt_obj = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_external_id(external_id)
    return _get_exam_attempt(exam_attempt_obj)


def get_exam_attempt_by_code(attempt_code):
    """
    Args:
        str: exam attempt attempt_code
    Returns:
        dict: our exam attempt
    """
    exam_attempt_obj = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_code(attempt_code)
    return _get_exam_attempt(exam_attempt_obj)


def get_exam_attempt_data(exam_id, attempt_id, is_learning_mfe=False):
    """
    Args:
        int: exam id
        int: exam attempt id
        bool: indicates if exam_url_path should be built for the MFE
    Returns:
        dict: our exam attempt
    """

    exam = get_exam_by_id(exam_id)
    attempt = get_exam_attempt_by_id(attempt_id)
    provider = get_backend_provider(exam)

    time_remaining_seconds = get_time_remaining_for_attempt(attempt)

    proctoring_settings = getattr(settings, 'PROCTORING_SETTINGS', {})
    low_threshold_pct = proctoring_settings.get('low_threshold_pct', .2)
    critically_low_threshold_pct = proctoring_settings.get('critically_low_threshold_pct', .05)

    allowed_time_limit_mins = attempt.get('allowed_time_limit_mins') or 0

    low_threshold = int(low_threshold_pct * float(allowed_time_limit_mins) * 60)
    critically_low_threshold = int(
        critically_low_threshold_pct * float(allowed_time_limit_mins) * 60
    )

    if not allowed_time_limit_mins or (attempt and is_attempt_ready_to_resume(attempt)):
        allowed_time_limit_mins = _calculate_allowed_mins(exam, attempt['user']['id'])

    total_time = humanized_time(allowed_time_limit_mins)

    # resolve the LMS url, note we can't assume we're running in
    # a same process as the LMS
    exam_url_path = get_exam_url(exam['course_id'], exam['content_id'], is_learning_mfe)

    attempt_data = {
        'in_timed_exam': True,
        'taking_as_proctored': attempt['taking_as_proctored'],
        'exam_type': get_exam_type(exam, provider)['humanized_type'],
        'exam_display_name': exam['exam_name'],
        'exam_url_path': exam_url_path,
        'time_remaining_seconds': time_remaining_seconds,
        'total_time': total_time,
        'low_threshold_sec': low_threshold,
        'critically_low_threshold_sec': critically_low_threshold,
        'course_id': exam['course_id'],
        'attempt_id': attempt['id'],
        'accessibility_time_string': _('you have {remaining_time} remaining').format(
            remaining_time=humanized_time(int(round(time_remaining_seconds / 60.0, 0)))
        ),
        'attempt_status': attempt['status'],
        'exam_started_poll_url': reverse(
            'edx_proctoring:proctored_exam.attempt',
            args=[attempt['id']]
        ),
        'attempt_ready_to_resume': is_attempt_ready_to_resume(attempt),
    }

    if provider:
        attempt_data.update({
            'desktop_application_js_url': provider.get_javascript(),
            'ping_interval': provider.ping_interval,
            'attempt_code': attempt['attempt_code']
        })
        if attempt['status'] in (
                ProctoredExamStudentAttemptStatus.created,
                ProctoredExamStudentAttemptStatus.download_software_clicked
        ):
            provider_attempt = provider.get_attempt(attempt)
            download_url = provider_attempt.get('download_url', None) or provider.get_software_download_url()
            attempt_data['software_download_url'] = download_url
    else:
        attempt_data['desktop_application_js_url'] = ''

    return attempt_data


def update_exam_attempt(attempt_id, **kwargs):
    """
    Update exam_attempt
    """
    exam_attempt_obj = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_id(attempt_id)
    if not exam_attempt_obj:
        err_msg = (
            f'Attempted to update exam attempt with attempt_id={attempt_id} but '
            'this attempt does not exist.'
        )
        raise StudentExamAttemptDoesNotExistsException(err_msg)

    for key, value in kwargs.items():
        # only allow a limit set of fields to update
        # namely because status transitions can trigger workflow
        if key not in [
                'is_status_acknowledged',
                'time_remaining_seconds',
        ]:
            err_msg = (
                'You cannot call into update_exam_attempt to change '
                f'field={key}. (attempt_id={attempt_id})'
            )
            raise ProctoredExamPermissionDenied(err_msg)
        setattr(exam_attempt_obj, key, value)
    exam_attempt_obj.save()


def is_exam_passed_due(exam, user=None):
    """
    Return whether the due date has passed.
    Uses edx_when to lookup the date for the subsection.
    """
    return (
        has_due_date_passed(get_exam_due_date(exam, user=user))
        # if the exam is timed and passed the course end date, it should also be considered passed due
        or (
            not exam['is_proctored'] and not exam['is_practice_exam'] and has_end_date_passed(exam['course_id'])
        )
    )


def _was_review_status_acknowledged(is_status_acknowledged, exam):
    """
    Return True if review status has been acknowledged and due date has been passed
    """
    return is_status_acknowledged and is_exam_passed_due(exam)


def _create_and_decline_attempt(exam_id, user_id):
    """
    It will create the exam attempt and change the attempt's status to decline.
    it will auto-decline further exams too
    """

    attempt_id = create_exam_attempt(exam_id, user_id)
    update_attempt_status(
        attempt_id,
        ProctoredExamStudentAttemptStatus.declined,
        raise_if_not_found=False
    )


def _register_proctored_exam_attempt(user_id, exam_id, exam, attempt_code, review_policy, verified_name=None):
    """
    Call the proctoring backend to register the exam attempt. If there are exceptions
    the external_id returned might be None. If the backend have onboarding status errors,
    it will be returned with force_status
    """
    scheme = 'https' if getattr(settings, 'HTTPS', 'on') == 'on' else 'http'
    lms_host = f'{scheme}://{settings.SITE_NAME}'

    obs_user_id = obscured_user_id(user_id, exam['backend'])
    allowed_time_limit_mins = _calculate_allowed_mins(exam, user_id)
    review_policy_exception = ProctoredExamStudentAllowance.get_review_policy_exception(exam_id, user_id)

    # get the name of the user, if the service is available
    email = None
    external_id = None
    force_status = None
    full_name = verified_name or ''
    profile_name = ''

    credit_service = get_runtime_service('credit')
    if credit_service:
        credit_state = credit_service.get_credit_state(user_id, exam['course_id'])
        if credit_state:
            profile_name = credit_state['profile_fullname']
            if not verified_name:
                full_name = profile_name
            email = credit_state['student_email']

    context = {
        'lms_host': lms_host,
        'time_limit_mins': allowed_time_limit_mins,
        'attempt_code': attempt_code,
        'is_sample_attempt': exam['is_practice_exam'],
        'user_id': obs_user_id,
        'full_name': full_name,
        'email': email
    }

    # see if there is an exam review policy for this exam
    # if so, then pass it into the provider
    if review_policy:
        context.update({
            'review_policy': review_policy.review_policy
        })

    # see if there is a review policy exception for this *user*
    # exceptions are granted on a individual basis as an
    # allowance
    if review_policy_exception:
        context.update({
            'review_policy_exception': review_policy_exception
        })

    # now call into the backend provider to register exam attempt
    try:
        external_id = get_backend_provider(exam).register_exam_attempt(
            exam,
            context=context,
        )
    except BackendProviderSentNoAttemptID as ex:
        log.error(
            ('Failed to get the attempt ID for user_id=%(user_id)s '
             'for exam_id=%(exam_id)s in course_id=%(course_id)s from the '
             'backend because the backend did not provide the id in API '
             'response, even when the HTTP response status is %(status)s, '
             'Response: %(response)s'),
            {
                'user_id': user_id,
                'exam_id': exam_id,
                'course_id': exam['course_id'],
                'response': str(ex),
                'status': ex.http_status,
            }
        )
        raise ex
    except BackendProviderCannotRegisterAttempt as ex:
        log.error(
            ('Failed to create attempt for user_id=%(user_id)s '
             'for exam_id=%(exam_id)s in course_id=%(course_id)s '
             'because backend was unable to register the attempt. '
             'Status: %(status)s, Response: %(response)s'),
            {
                'user_id': user_id,
                'exam_id': exam_id,
                'course_id': exam['course_id'],
                'response': str(ex),
                'status': ex.http_status,
            }
        )
        raise ex
    except BackendProviderOnboardingException as ex:
        force_status = ex.status
        log.error(
            ('Failed to create attempt for user_id=%(user_id)s '
             'for exam_id=%(exam_id)s in course_id=%(course_id)s '
             'because of onboarding failure: %(force_status)s'),
            {
                'user_id': user_id,
                'exam_id': exam_id,
                'course_id': exam['course_id'],
                'force_status': force_status,
            }
        )

    return external_id, force_status, full_name, profile_name


def _get_verified_name(user_id, name_affirmation_service):
    """
    Get the user's verified name if one exists. This will ignore verified names
    which have a "denied" status.

    Returns a verified name object (or None)
    """
    verified_name = None

    user = USER_MODEL.objects.get(id=user_id)

    # Only use verified name if it is approved or pending approval
    verified_name_obj = name_affirmation_service.get_verified_name(
        user, is_verified=False, statuses_to_exclude=['denied']
    )

    if verified_name_obj:
        verified_name = verified_name_obj.verified_name

    return verified_name


def create_exam_attempt(exam_id, user_id, taking_as_proctored=False):
    """
    Creates an exam attempt for user_id against exam_id. There should only
    be one exam_attempt per user per exam, with one exception described below.
    Multiple attempts by user will be archived in a separate table.

    If the attempt enters an error state, it must be marked as ready to resume,
    and another attempt must be made in order to resume the exam. This is the
    only case where multiple attempts for the same exam should exist.
    """
    # for now the student is allowed the exam default

    exam = get_exam_by_id(exam_id)

    log.info(
        ('Creating exam attempt for exam_id=%(exam_id)s for user_id=%(user_id)s '
         'in course_id=%(course_id)s with taking_as_proctored=%(taking_as_proctored)s'),
        {
            'exam_id': exam_id,
            'user_id': user_id,
            'course_id': exam['course_id'],
            'taking_as_proctored': taking_as_proctored,
        }
    )

    existing_attempt = ProctoredExamStudentAttempt.objects.get_current_exam_attempt(exam_id, user_id)
    time_remaining_seconds = None
    # only practice exams and exams with resume states may have multiple attempts
    if existing_attempt:
        if is_attempt_in_resume_process(existing_attempt):
            # save remaining time and mark the most recent attempt as resumed, if it isn't already
            time_remaining_seconds = existing_attempt.time_remaining_seconds
            mark_exam_attempt_as_resumed(existing_attempt.id)
        elif not existing_attempt.is_sample_attempt:
            err_msg = (
                f'Cannot create new exam attempt for exam_id={exam_id} and '
                f"user_id={user_id} in course_id={exam['course_id']} because it already exists!"
            )

            raise StudentExamAttemptAlreadyExistsException(err_msg)

    attempt_code = str(uuid.uuid4()).upper()

    review_policy = ProctoredExamReviewPolicy.get_review_policy_for_exam(exam_id)
    external_id = None
    force_status = None

    if is_exam_passed_due(exam, user=user_id) and taking_as_proctored:
        err_msg = (
            f'user_id={user_id} trying to create exam attempt for past due proctored '
            f"exam_id={exam_id} in course_id={exam['course_id']}. Do not register an exam attempt!"
        )
        raise StudentExamAttemptOnPastDueProctoredExam(err_msg)

    name_affirmation_service = get_runtime_service('name_affirmation')
    full_name = ''
    profile_name = ''

    if taking_as_proctored:
        verified_name = None
        if name_affirmation_service:
            verified_name = _get_verified_name(user_id, name_affirmation_service)
        external_id, force_status, full_name, profile_name = _register_proctored_exam_attempt(
            user_id, exam_id, exam, attempt_code, review_policy, verified_name,
        )

    attempt = ProctoredExamStudentAttempt.create_exam_attempt(
        exam_id,
        user_id,
        attempt_code,
        taking_as_proctored,
        exam['is_practice_exam'],
        external_id,
        review_policy_id=review_policy.id if review_policy else None,
        status=force_status,
        time_remaining_seconds=time_remaining_seconds,
    )

    exam = get_exam_by_id(exam_id)
    backend = get_backend_provider(exam)
    supports_onboarding = backend.supports_onboarding if backend else None

    # Emit signal for attempt creation
    exam_attempt_status_signal.send(
        sender='edx_proctoring',
        attempt_id=attempt.id,
        user_id=user_id,
        status=attempt.status,
        full_name=full_name,
        profile_name=profile_name,
        is_practice_exam=exam['is_practice_exam'],
        is_proctored=taking_as_proctored,
        backend_supports_onboarding=supports_onboarding
    )

    # Emit event when exam attempt created
    emit_event(exam, attempt.status, attempt=_get_exam_attempt(attempt))

    log.info(
        ('Created exam attempt_id=%(attempt_id)s for exam_id=%(exam_id)s for '
         'user_id=%(user_id)s with taking as proctored=%(taking_as_proctored)s. '
         'attempt_code=%(attempt_code)s was generated which has an '
         'external_id=%(external_id)s'),
        {
            'attempt_id': attempt.id,
            'exam_id': exam_id,
            'user_id': user_id,
            'taking_as_proctored': taking_as_proctored,
            'attempt_code': attempt_code,
            'external_id': external_id,
        }
    )

    return attempt.id


def start_exam_attempt(exam_id, user_id):
    """
    Signals the beginning of an exam attempt for a given
    exam_id. If one already exists, then an exception should be thrown.

    Returns: exam_attempt_id (PK)
    """

    existing_attempt = ProctoredExamStudentAttempt.objects.get_current_exam_attempt(exam_id, user_id)

    if not existing_attempt:
        err_msg = (
            f'Cannot start exam attempt for exam_id={exam_id} '
            f'and user_id={user_id} because it does not exist!'
        )

        raise StudentExamAttemptDoesNotExistsException(err_msg)

    return _start_exam_attempt(existing_attempt)


def start_exam_attempt_by_code(attempt_code):
    """
    Signals the beginning of an exam attempt when we only have
    an attempt code
    """

    existing_attempt = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_code(attempt_code)

    if not existing_attempt:
        err_msg = (
            f'Cannot start exam attempt for attempt_code={attempt_code} '
            'because it does not exist!'
        )

        raise StudentExamAttemptDoesNotExistsException(err_msg)

    return _start_exam_attempt(existing_attempt)


def _start_exam_attempt(existing_attempt):
    """
    Helper method
    """

    if existing_attempt.started_at and existing_attempt.status == ProctoredExamStudentAttemptStatus.started:
        # cannot restart an attempt
        err_msg = (
            f'Cannot start exam attempt for exam_id={existing_attempt.proctored_exam.id} '
            f'and user_id={existing_attempt.user_id} because it has already started!'
        )

        raise StudentExamAttemptedAlreadyStarted(err_msg)

    update_attempt_status(
        existing_attempt.id,
        ProctoredExamStudentAttemptStatus.started
    )

    return existing_attempt.id


def stop_exam_attempt(attempt_id):
    """
    Marks the exam attempt as completed (sets the completed_at field and updates the record)
    """
    return update_attempt_status(attempt_id, ProctoredExamStudentAttemptStatus.ready_to_submit)


def mark_exam_attempt_timeout(attempt_id):
    """
    Marks the exam attempt as timed_out
    """
    return update_attempt_status(attempt_id, ProctoredExamStudentAttemptStatus.timed_out)


def mark_exam_attempt_as_ready(attempt_id):
    """
    Marks the exam attempt as ready to start
    """
    return update_attempt_status(attempt_id, ProctoredExamStudentAttemptStatus.ready_to_start)


def mark_exam_attempt_as_resumed(attempt_id):
    """
    Marks the current exam attempt as resumed
    """
    exam_attempt_obj = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_id(attempt_id)
    ready_to_resume = is_attempt_in_resume_process(exam_attempt_obj)
    if ready_to_resume:
        exam_attempt_obj.resumed = True
        exam_attempt_obj.is_resumable = False
        exam_attempt_obj.save()
        return exam_attempt_obj.id

    raise ProctoredExamIllegalResumeUpdate(
        f'Attempted to mark attempt_id={attempt_id} as resumed, but '
        f'attempt was never marked as ready_to_resume. This is not allowed.'
    )


def mark_exam_attempt_as_ready_to_resume(attempt_id):
    """
    Marks the current exam attempt as ready to resume
    """
    exam_attempt_obj = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_id(attempt_id)
    is_resumable = exam_attempt_obj.is_resumable
    if is_resumable:
        exam_attempt_obj.ready_to_resume = True
        exam_attempt_obj.is_resumable = False
        exam_attempt_obj.save()
        return exam_attempt_obj.id

    raise ProctoredExamIllegalResumeUpdate(
        f'Attempted to mark attempt_id={attempt_id} as ready_to_resume, but '
        f'attempt is not resumable. This is not allowed.'
    )


def is_attempt_ready_to_resume(attempt):
    """
    Determine if an exam attempt is ready to resume

    Arguments:
        attempt: serialized attempt obj
    """

    # if the attempt has been marked as ready to resume, check to see that it has not been resumed yet
    return attempt['ready_to_resume'] and not attempt['resumed']


def is_attempt_in_resume_process(attempt_obj):
    """
    Determine if an exam attempt is in the resume process. This should check if either of the resume
    related fields are set to true.

    Arguments:
        attempt_obj: attempt object
    """
    return attempt_obj.ready_to_resume or attempt_obj.resumed


def is_state_transition_legal(from_status, to_status):
    """
    Determine and return as a boolean whether a proctored exam attempt state transition
    from from_status to to_status is an allowed state transition.

    Arguments:
        from_status: original status of a proctored exam attempt
        to_status: future status of a proctored exam attempt
    """
    in_completed_status = ProctoredExamStudentAttemptStatus.is_completed_status(from_status)
    to_incompleted_status = ProctoredExamStudentAttemptStatus.is_incomplete_status(to_status)

    # don't allow state transitions from a completed state to an incomplete state
    # if a re-attempt is desired then the current attempt must be deleted
    if in_completed_status and to_incompleted_status:
        return False
    return True


def can_update_credit_grades_and_email(attempts, to_status, exam):
    """
    Determine and return as a boolean whether an attempt should trigger an update to credit and grades

    Arguments:
        attempts: a list of all currently active attempts for a given user_id and exam_id
        to_status: future status of a proctored exam attempt
        exam: dict representation of exam object
    """
    # if the exam is a practice exam, always allow updates
    if exam['is_practice_exam']:
        return True

    statuses = [attempt['status'] for attempt in attempts]
    if len(statuses) == 1:
        # if there is only one attempt for a user in an exam, it can be responsible for updates to credits and grades
        return True
    if to_status in [ProctoredExamStudentAttemptStatus.declined, ProctoredExamStudentAttemptStatus.error]:
        # can only decline/error the most recent attempt, so return true
        # these should not send emails but will update credits and grades
        return True
    if to_status == ProctoredExamStudentAttemptStatus.submitted:
        # we only want to update a submitted status if there are no rejected past attempts
        for status in statuses:
            if status == ProctoredExamStudentAttemptStatus.rejected:
                return False
        return True
    if to_status == ProctoredExamStudentAttemptStatus.verified:
        # if we are updating an attempt to verified, we can only return true if all other attempts are verified
        for status in statuses:
            if status != ProctoredExamStudentAttemptStatus.verified:
                return False
        return True
    if to_status == ProctoredExamStudentAttemptStatus.rejected:
        if (
            statuses.count(ProctoredExamStudentAttemptStatus.rejected) > 1 or
            ProctoredExamStudentAttemptStatus.declined in statuses
        ):
            # if there is more than one rejection, do not update grades/certificate/email again
            # or if there is a declined status, do not update grades/certificate/email again
            return False
        return True

    return False


def _is_attempt_resumable(attempt_obj, to_status):
    """
    Based on the attempt object and the status it's transitioning to,
    return whether the attempt should be resumable, or not
    """
    if to_status == ProctoredExamStudentAttemptStatus.submitted or is_attempt_in_resume_process(attempt_obj):
        # Make sure we have resumable to be false in conditions where the
        # attempt is either in the resume process, or it's successfully submitted
        return False
    if to_status == ProctoredExamStudentAttemptStatus.error:
        # Only when the transition to status is "Error", the attempt is resumable
        return True

    # Otherwise, maintain resumability on the attempt
    return attempt_obj.is_resumable


# pylint: disable=inconsistent-return-statements
def update_attempt_status(attempt_id, to_status,
                          raise_if_not_found=True, cascade_effects=True, timeout_timestamp=None,
                          update_attributable_to=None):
    """
    Internal helper to handle state transitions of attempt status
    """
    exam_attempt_obj = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_id(attempt_id)

    if exam_attempt_obj is None:
        if raise_if_not_found:
            raise StudentExamAttemptDoesNotExistsException(
                f'Tried to look up exam by attempt_id={attempt_id}, '
                'but this attempt does not exist.'
            )
        return

    exam_id = exam_attempt_obj.proctored_exam.id
    user_id = exam_attempt_obj.user.id

    from_status = exam_attempt_obj.status

    log.info(
        ('Updating attempt status for exam_id=%(exam_id)s '
         'for user_id=%(user_id)s from status "%(from_status)s" to "%(to_status)s"'),
        {
            'exam_id': exam_id,
            'user_id': user_id,
            'from_status': from_status,
            'to_status': to_status,
        }
    )
    # In some configuration we may treat timeouts the same
    # as the user saying he/she wishes to submit the exam
    allow_timeout_state = settings.PROCTORING_SETTINGS.get('ALLOW_TIMED_OUT_STATE', False)
    treat_timeout_as_submitted = to_status == ProctoredExamStudentAttemptStatus.timed_out and not allow_timeout_state

    user_trying_to_reattempt = is_reattempting_exam(from_status, to_status)
    if treat_timeout_as_submitted or user_trying_to_reattempt:
        detail = 'the attempt was timed out' if treat_timeout_as_submitted else 'the user reattempted the exam'
        log.info(
            ('Attempt status for exam_id=%(exam_id)s for user_id=%(user_id)s will not be updated to '
             '"%(to_status)s" because %(submitted_message)s. Instead the attempt '
             'status will be updated to "submitted"'),
            {
                'exam_id': exam_id,
                'user_id': user_id,
                'to_status': to_status,
                'submitted_message': detail,
            }
        )
        to_status = ProctoredExamStudentAttemptStatus.submitted

    exam = get_exam_by_id(exam_id)
    backend = get_backend_provider(exam)

    if not is_state_transition_legal(from_status, to_status):
        illegal_status_transition_msg = (
            f'A status transition from "{from_status}" to "{to_status}" was attempted '
            f'on exam_id={exam_id} for user_id={user_id}. This is not '
            f"allowed! (course_id={exam['course_id']})"
        )

        raise ProctoredExamIllegalStatusTransition(illegal_status_transition_msg)

    # OK, state transition is fine, we can proceed
    exam_attempt_obj.status = to_status

    # if we have transitioned to started and haven't set our
    # started_at timestamp and calculate allowed minutes, do so now
    add_start_time = (
        to_status == ProctoredExamStudentAttemptStatus.started and
        not exam_attempt_obj.started_at
    )
    if add_start_time:
        exam_attempt_obj.started_at = datetime.now(pytz.UTC)
        exam_attempt_obj.allowed_time_limit_mins = _calculate_allowed_mins(exam, exam_attempt_obj.user_id)

    elif treat_timeout_as_submitted:
        exam_attempt_obj.completed_at = timeout_timestamp
    elif to_status == ProctoredExamStudentAttemptStatus.submitted:
        # likewise, when we transition to submitted mark
        # when the exam has been completed
        exam_attempt_obj.completed_at = datetime.now(pytz.UTC)

    # Update the is_resumable flag of the attempt based on the status transition
    exam_attempt_obj.is_resumable = _is_attempt_resumable(exam_attempt_obj, to_status)

    exam_attempt_obj.save()

    all_attempts = get_user_attempts_by_exam_id(user_id, exam_id)

    if can_update_credit_grades_and_email(all_attempts, to_status, exam):

        # see if the status transition this changes credit requirement status
        if ProctoredExamStudentAttemptStatus.needs_credit_status_update(to_status):

            # trigger credit workflow, as needed
            credit_service = get_runtime_service('credit')

            if to_status == ProctoredExamStudentAttemptStatus.verified:
                credit_requirement_status = 'satisfied'
            elif to_status == ProctoredExamStudentAttemptStatus.submitted:
                credit_requirement_status = 'submitted'
            elif to_status == ProctoredExamStudentAttemptStatus.declined:
                credit_requirement_status = 'declined'
            else:
                credit_requirement_status = 'failed'

            log.info(
                ('Calling set_credit_requirement_status for '
                 'user_id=%(user_id)s on course_id=%(course_id)s for '
                 'content_id=%(content_id)s. status=%(status)s'),
                {
                    'user_id': exam_attempt_obj.user_id,
                    'course_id': exam['course_id'],
                    'content_id': exam_attempt_obj.proctored_exam.content_id,
                    'status': credit_requirement_status,
                }
            )

            credit_service.set_credit_requirement_status(
                user_id=exam_attempt_obj.user_id,
                course_key_or_id=exam['course_id'],
                req_namespace='proctored_exam',
                req_name=exam_attempt_obj.proctored_exam.content_id,
                status=credit_requirement_status
            )

        if cascade_effects and ProctoredExamStudentAttemptStatus.is_a_cascadable_failure(to_status):
            # if user declines attempt, make sure we clear out the external_id and
            # taking_as_proctored fields
            exam_attempt_obj.taking_as_proctored = False
            exam_attempt_obj.external_id = None
            exam_attempt_obj.save()

            # some state transitions (namely to a rejected or declined status)
            # will mark other exams as declined because once we fail or decline
            # one exam all other (un-completed) proctored exams will be likewise
            # updated to reflect a declined status
            # get all other unattempted exams and mark also as declined
            all_other_exams = ProctoredExam.get_all_exams_for_course(
                exam_attempt_obj.proctored_exam.course_id,
                active_only=True
            )

            # we just want other exams which are proctored and are not practice
            other_exams = [
                other_exam
                for other_exam in all_other_exams
                if (
                    other_exam.content_id != exam_attempt_obj.proctored_exam.content_id and
                    other_exam.is_proctored and not other_exam.is_practice_exam
                )
            ]

            for other_exam in other_exams:
                # see if there was an attempt on those other exams already
                attempt = get_current_exam_attempt(other_exam.id, user_id)
                if attempt and ProctoredExamStudentAttemptStatus.is_completed_status(attempt['status']):
                    # don't touch any completed statuses
                    # we won't revoke those
                    continue

                if not attempt:
                    current_attempt_id = create_exam_attempt(other_exam.id, user_id, taking_as_proctored=False)
                else:
                    current_attempt_id = attempt['id']

                # update any new or existing status to declined
                update_attempt_status(
                    current_attempt_id,
                    ProctoredExamStudentAttemptStatus.declined,
                    cascade_effects=False
                )

        if ProctoredExamStudentAttemptStatus.needs_grade_override(to_status):
            grades_service = get_runtime_service('grades')

            if grades_service.should_override_grade_on_rejected_exam(exam['course_id']):
                log.info(
                    ('Overriding exam subsection grade for '
                     'user_id=%(user_id)s on course_id=%(course_id)s for '
                     'content_id=%(content_id)s. Override '
                     'earned_all=%(earned_all)s, '
                     'earned_graded=%(earned_graded)s.'),
                    {
                        'user_id': exam_attempt_obj.user_id,
                        'course_id': exam['course_id'],
                        'content_id': exam_attempt_obj.proctored_exam.content_id,
                        'earned_all': REJECTED_GRADE_OVERRIDE_EARNED,
                        'earned_graded': REJECTED_GRADE_OVERRIDE_EARNED,
                    }
                )

                grades_service.override_subsection_grade(
                    user_id=exam_attempt_obj.user_id,
                    course_key_or_id=exam['course_id'],
                    usage_key_or_id=exam_attempt_obj.proctored_exam.content_id,
                    earned_all=REJECTED_GRADE_OVERRIDE_EARNED,
                    earned_graded=REJECTED_GRADE_OVERRIDE_EARNED,
                    overrider=update_attributable_to,
                    comment=(f'Failed {backend.verbose_name} proctoring'
                             if backend
                             else 'Failed Proctoring')
                )

                certificates_service = get_runtime_service('certificates')

                log.info(
                    ('Invalidating certificate for user_id=%(user_id)s in course_id=%(course_id)s whose '
                     'grade dropped below passing threshold due to suspicious proctored exam'),
                    {
                        'user_id': exam_attempt_obj.user_id,
                        'course_id': exam['course_id'],
                    }
                )

                # invalidate certificate after overriding subsection grade
                certificates_service.invalidate_certificate(
                    user_id=exam_attempt_obj.user_id,
                    course_key_or_id=exam['course_id']
                )

        if (to_status == ProctoredExamStudentAttemptStatus.verified and
                ProctoredExamStudentAttemptStatus.needs_grade_override(from_status)):
            grades_service = get_runtime_service('grades')

            if grades_service.should_override_grade_on_rejected_exam(exam['course_id']):
                log.info(
                    ('Deleting override of exam subsection grade for '
                     'user_id=%(user_id)s on course_id=%(course_id)s for '
                     'content_id=%(content_id)s. Override '
                     'earned_all=%(earned_all)s, '
                     'earned_graded=%(earned_graded)s.'),
                    {
                        'user_id': exam_attempt_obj.user_id,
                        'course_id': exam['course_id'],
                        'content_id': exam_attempt_obj.proctored_exam.content_id,
                        'earned_all': REJECTED_GRADE_OVERRIDE_EARNED,
                        'earned_graded': REJECTED_GRADE_OVERRIDE_EARNED,
                    }
                )

                grades_service.undo_override_subsection_grade(
                    user_id=exam_attempt_obj.user_id,
                    course_key_or_id=exam['course_id'],
                    usage_key_or_id=exam_attempt_obj.proctored_exam.content_id,
                )

        # call service to get course name.
        credit_service = get_runtime_service('credit')
        credit_state = credit_service.get_credit_state(
            exam_attempt_obj.user_id,
            exam_attempt_obj.proctored_exam.course_id,
            return_course_info=True
        )

        default_name = _('your course')
        if credit_state:
            course_name = credit_state.get('course_name', default_name)
        else:
            course_name = default_name
            log.info(
                ('While updating attempt status, could not find credit_state for '
                 'user_id=%(user_id)s in course_id=%(course_id)s'),
                {
                    'user_id': exam_attempt_obj.user_id,
                    'course_id': exam_attempt_obj.proctored_exam.course_id,
                }
            )
        email = create_proctoring_attempt_status_email(
            user_id,
            exam_attempt_obj,
            course_name,
            exam['course_id']
        )
        if email:
            try:
                email.send()
            except Exception as err:  # pylint: disable=broad-except
                log.exception(
                    ('Exception occurred while trying to send proctoring attempt '
                     'status email for user_id=%(user_id)s in course_id=%(course_id)s -- %(err)s'),
                    {
                        'user_id': exam_attempt_obj.user_id,
                        'course_id': exam_attempt_obj.proctored_exam.course_id,
                        'err': err,
                    }
                )

    # emit an anlytics event based on the state transition
    # we re-read this from the database in case fields got updated
    # via workflow
    attempt = get_exam_attempt_by_id(attempt_id)

    # call back to the backend to register the end of the exam, if necessary
    if backend:
        # When onboarding exams change state to a completed status,
        # look up any exams in the onboarding error states, and delete them.
        # This will allow learners to return to the proctored exam and continue
        # through the workflow.
        if exam['is_practice_exam'] and backend.supports_onboarding and \
                ProctoredExamStudentAttemptStatus.is_completed_status(to_status):
            # find and delete any pending attempts
            ProctoredExamStudentAttempt.objects.clear_onboarding_errors(user_id)

        # only proctored/practice exams have a backend
        # timed exams have no backend
        backend_method = None

        # add_start_time will only have a value of true if this is the first time an
        # attempt is transitioning to started. We only want to notify the backend
        # for the first time an attempt is transitioned to a started status (MST-862).
        if to_status == ProctoredExamStudentAttemptStatus.started and add_start_time:
            backend_method = backend.start_exam_attempt
        elif to_status == ProctoredExamStudentAttemptStatus.submitted:
            backend_method = backend.stop_exam_attempt
        elif to_status == ProctoredExamStudentAttemptStatus.error:
            backend_method = backend.mark_erroneous_exam_attempt
        if backend_method:
            backend_method(exam['external_id'], attempt['external_id'])
    # we use the 'status' field as the name of the event 'verb'
    emit_event(exam, attempt['status'], attempt=attempt)

    exam_attempt_status_signal.send(
        sender='edx_proctoring',
        attempt_id=attempt['id'],
        user_id=user_id,
        status=attempt['status'],
        full_name=None,
        profile_name=None,
        is_practice_exam=exam['is_practice_exam'],
        is_proctored=attempt['taking_as_proctored'],
        backend_supports_onboarding=backend.supports_onboarding if backend else False
    )

    return attempt['id']


def create_proctoring_attempt_status_email(user_id, exam_attempt_obj, course_name, course_id):
    """
    Creates an email about change in proctoring attempt status.
    """
    # Don't send an email unless this is a non-practice proctored exam
    if not exam_attempt_obj.taking_as_proctored or exam_attempt_obj.is_sample_attempt:
        return None

    user = USER_MODEL.objects.get(id=user_id)
    course_info_url = ''
    email_subject = (
        _('Proctoring Results For {course_name} {exam_name}').format(
            course_name=course_name,
            exam_name=exam_attempt_obj.proctored_exam.exam_name
        )
    )
    status = exam_attempt_obj.status
    if status == ProctoredExamStudentAttemptStatus.submitted:
        template_name = 'proctoring_attempt_submitted_email.html'
        email_subject = (
            _('Proctoring Review In Progress For {course_name} {exam_name}').format(
                course_name=course_name,
                exam_name=exam_attempt_obj.proctored_exam.exam_name
            )
        )
    elif status == ProctoredExamStudentAttemptStatus.verified:
        template_name = 'proctoring_attempt_satisfactory_email.html'
    elif status == ProctoredExamStudentAttemptStatus.rejected:
        template_name = 'proctoring_attempt_unsatisfactory_email.html'
    else:
        # Don't send an email for any other attempt status codes
        return None

    backend = exam_attempt_obj.proctored_exam.backend
    email_template = loader.select_template(_get_email_template_paths(template_name, backend))
    try:
        course_info_url = reverse('info', args=[exam_attempt_obj.proctored_exam.course_id])
    except NoReverseMatch:
        log.exception(
            ('Attempted to create proctoring status email for user_id=%(user_id)s in exam_id=%(exam_id)s, '
             'but could not find course info url for course_id=%(course_id)s'),
            {
                'user_id': user_id,
                'exam_id': exam_attempt_obj.proctored_exam.id,
                'course_id': course_id,
            }
        )

    scheme = 'https' if getattr(settings, 'HTTPS', 'on') == 'on' else 'http'
    course_url = f'{scheme}://{constants.SITE_NAME}{course_info_url}'
    exam_name = exam_attempt_obj.proctored_exam.exam_name
    support_email_subject = _('Proctored exam {exam_name} in {course_name} for user {username}').format(
        exam_name=exam_name,
        course_name=course_name,
        username=user.username,
    )

    default_contact_url = f'{scheme}://{constants.SITE_NAME}/support/contact_us'

    # If the course has a proctoring escalation email set, use that rather than edX Support.
    # Currently only courses using Proctortrack will have this set.
    proctoring_escalation_email = _get_proctoring_escalation_email(course_id)
    if proctoring_escalation_email:
        contact_url = f'mailto:{proctoring_escalation_email}'
        contact_url_text = proctoring_escalation_email
    else:
        contact_url = getattr(settings, 'PROCTORING_BACKENDS', {}).get(backend, {}).get(
            'LINK_URLS', {}).get('contact', default_contact_url)
        contact_url_text = contact_url

    body = email_template.render({
        'username': user.username,
        'course_url': course_url,
        'course_name': course_name,
        'exam_name': exam_name,
        'status': status,
        'platform': constants.PLATFORM_NAME,
        'support_email_subject': support_email_subject,
        'contact_url': contact_url,
        'contact_url_text': contact_url_text,
    })

    email = EmailMessage(
        body=body,
        from_email=constants.FROM_EMAIL,
        to=[exam_attempt_obj.user.email],
        subject=email_subject,
    )
    email.content_subtype = 'html'
    return email


def _get_email_template_paths(template_name, backend):
    """
    Get a list of email template paths to search for, depending on the name of the desired template and the
    exam attempt's exam's backend.

    Arguments:
        template_name: the filename of the template
        backend: the name of the backend being used for the exam
    """
    base_template = f'emails/{template_name}'

    if backend:
        return [
            f'emails/proctoring/{backend}/{template_name}',
            base_template,
        ]
    return [base_template]


def _get_proctoring_escalation_email(course_id):
    """
    Returns the proctoring escalation email for a course as a string, if it exists,
    otherwise returns None.
    """
    proctoring_escalation_email = None
    instructor_service = get_runtime_service('instructor')
    if instructor_service:
        try:
            proctoring_escalation_email = instructor_service.get_proctoring_escalation_email(course_id)
        except (InvalidKeyError, ObjectDoesNotExist):
            log.warning(
                ('Could not retrieve proctoring escalation email for course_id=%(course_id)s. '
                 'Using default support contact URL instead.'),
                {
                    'course_id': course_id,
                }
            )
    return proctoring_escalation_email


def reset_practice_exam(exam_id, user_id, requesting_user):
    """
    Resets a completed practice exam attempt back to the created state.
    """
    log.info(
        'Resetting practice exam_id=%(exam_id)s for user_id=%(user_id)s',
        {
            'exam_id': exam_id,
            'user_id': user_id,
        }
    )

    exam_attempt_obj = ProctoredExamStudentAttempt.objects.get_current_exam_attempt(exam_id, user_id)
    if exam_attempt_obj is None:
        err_msg = (
            f'Tried to reset attempt in exam_id={exam_id} for user_id={user_id}, '
            'but this attempt does not exist.'
        )
        raise StudentExamAttemptDoesNotExistsException(err_msg)

    exam = get_exam_by_id(exam_id)
    if not exam['is_practice_exam']:
        err_msg = (
            f'Failed to reset attempt status on exam_id={exam_id} for user_id={user_id}. '
            f"Only practice exams may be reset! (course_id={exam['course_id']})"
        )
        raise ProctoredExamIllegalStatusTransition(err_msg)

    # prevent a reset if the exam is currently in progress or has already been verified
    attempt_in_progress = ProctoredExamStudentAttemptStatus.is_incomplete_status(exam_attempt_obj.status)
    if attempt_in_progress or exam_attempt_obj.status == ProctoredExamStudentAttemptStatus.verified:
        err_msg = (
            f'Failed to reset attempt status on exam_id={exam_id} for user_id={user_id}. '
            f"Attempt with status={exam_attempt_obj.status} cannot be reset! (course_id={exam['course_id']})"
        )
        raise ProctoredExamIllegalStatusTransition(err_msg)

    # resetting a submitted attempt that has not been reviewed will entirely remove that submission.
    if exam_attempt_obj.status == ProctoredExamStudentAttemptStatus.submitted:
        remove_exam_attempt(exam_attempt_obj.id, requesting_user)
    else:
        exam_attempt_obj.status = ProctoredExamStudentAttemptStatus.onboarding_reset
        exam_attempt_obj.save()

    emit_event(exam, 'reset_practice_exam', attempt=_get_exam_attempt(exam_attempt_obj))

    return create_exam_attempt(exam_id, user_id, taking_as_proctored=exam_attempt_obj.taking_as_proctored)


def remove_exam_attempt(attempt_id, requesting_user):
    """
    Removes an exam attempt given the attempt id. requesting_user is passed through to the instructor_service.
    """

    log.info(
        'Removing exam attempt_id=%(attempt_id)s',
        {
            'attempt_id': attempt_id,
        }
    )

    existing_attempt = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_id(attempt_id)
    if not existing_attempt:
        err_msg = (
            f'Cannot remove attempt for attempt_id={attempt_id} because it does not exist!'
        )

        raise StudentExamAttemptDoesNotExistsException(err_msg)

    username = existing_attempt.user.username
    user_id = existing_attempt.user.id
    course_id = existing_attempt.proctored_exam.course_id
    content_id = existing_attempt.proctored_exam.content_id
    to_status = existing_attempt.status

    existing_attempt.delete_exam_attempt()
    instructor_service = get_runtime_service('instructor')
    grades_service = get_runtime_service('grades')

    if instructor_service:
        instructor_service.delete_student_attempt(username, course_id, content_id, requesting_user=requesting_user)
    if grades_service:
        # EDUCATOR-2141: Also remove any grade overrides that may exist
        grades_service.undo_override_subsection_grade(
            user_id=user_id,
            course_key_or_id=course_id,
            usage_key_or_id=content_id,
        )

    # see if the status transition this changes credit requirement status
    if ProctoredExamStudentAttemptStatus.needs_credit_status_update(to_status):
        # trigger credit workflow, as needed
        credit_service = get_runtime_service('credit')
        credit_service.remove_credit_requirement_status(
            user_id=user_id,
            course_key_or_id=course_id,
            req_namespace='proctored_exam',
            req_name=content_id
        )

    # emit an event for 'deleted'
    exam = get_exam_by_content_id(course_id, content_id)
    serialized_attempt_obj = ProctoredExamStudentAttemptSerializer(existing_attempt)
    attempt = serialized_attempt_obj.data
    emit_event(exam, 'deleted', attempt=attempt)


def get_all_exams_for_course(course_id, active_only=False):
    """
    This method will return all exams for a course. This will return a list
    of dictionaries, whose schema is the same as what is returned in
    get_exam_by_id
    Returns a list containing dictionary version of the Django ORM object
    e.g.
    [{
        "course_id": "edX/DemoX/Demo_Course",
        "content_id": "123",
        "external_id": "",
        "exam_name": "Midterm",
        "time_limit_mins": 90,
        "is_proctored": true,
        "is_active": true
    },
    {
        ...: ...,
        ...: ...

    },
    ..
    ]
    """
    exams = ProctoredExam.get_all_exams_for_course(
        course_id,
        active_only=active_only
    )

    return [ProctoredExamSerializer(proctored_exam).data for proctored_exam in exams]


def get_all_exam_attempts(course_id):
    """
    Returns all the exam attempts for the course id.
    """
    exam_attempts = ProctoredExamStudentAttempt.objects.get_all_exam_attempts(course_id)
    return [ProctoredExamStudentAttemptSerializer(active_exam).data for active_exam in exam_attempts]


def get_filtered_exam_attempts(course_id, search_by):
    """
    Returns all exam attempts for a course id filtered by the search_by string in user names and emails.
    """
    exam_attempts = ProctoredExamStudentAttempt.objects.get_filtered_exam_attempts(course_id, search_by)
    return [ProctoredExamStudentAttemptSerializer(active_exam).data for active_exam in exam_attempts]


def get_user_attempts_by_exam_id(user_id, exam_id):
    """
    Returns all exam attempts for a given user and exam
    """
    exam_attempts = ProctoredExamStudentAttempt.objects.get_user_attempts_by_exam_id(user_id, exam_id)
    return [ProctoredExamStudentAttemptSerializer(active_attempt).data for active_attempt in exam_attempts]


def get_last_exam_completion_date(course_id, username):
    """
    Return the completion date of last proctoring exam for the given course and username if
    all the proctored exams are attempted and completed otherwise None
    """
    exam_attempts = ProctoredExamStudentAttempt.objects.get_proctored_exam_attempts(course_id, username)
    proctored_exams_count = ProctoredExam.get_all_exams_for_course(course_id, proctored_exams_only=True).count()
    are_all_exams_attempted = len(exam_attempts) == proctored_exams_count
    if are_all_exams_attempted:
        for attempt in exam_attempts:
            if not attempt.completed_at:
                return None

    # Last proctored exam will be at first index, because attempts are sorted descending on completed_at
    return exam_attempts[0].completed_at if exam_attempts and are_all_exams_attempted else None


def get_active_exams_for_user(user_id, course_id=None):
    """
    This method will return a list of active exams for the user,
    i.e. started_at != None and completed_at == None. Theoretically there
    could be more than one, but in practice it will be one active exam.

    If course_id is set, then attempts only for an exam in that course_id
    should be returned.

    The return set should be a list of dictionary objects which are nested


    [{
        'exam': <exam fields as dict>,
        'attempt': <student attempt fields as dict>,
        'allowances': <student allowances as dict of key/value pairs
    }, {}, ...]

    """
    result = []

    student_active_exams = ProctoredExamStudentAttempt.objects.get_active_student_attempts(user_id, course_id)
    for active_exam in student_active_exams:
        # convert the django orm objects
        # into the serialized form.
        exam_serialized_data = ProctoredExamSerializer(active_exam.proctored_exam).data
        active_exam_serialized_data = ProctoredExamStudentAttemptSerializer(active_exam).data
        student_allowances = ProctoredExamStudentAllowance.get_allowances_for_user(
            active_exam.proctored_exam.id, user_id
        )
        allowance_serialized_data = [ProctoredExamStudentAllowanceSerializer(allowance).data for allowance in
                                     student_allowances]
        result.append({
            'exam': exam_serialized_data,
            'attempt': active_exam_serialized_data,
            'allowances': allowance_serialized_data
        })

    return result


def check_prerequisites(exam, user_id):
    """
    Check if prerequisites are satisfied for user to take the exam
    """
    credit_service = get_runtime_service('credit')
    credit_state = credit_service.get_credit_state(user_id, exam['course_id'])
    if not credit_state:
        return exam
    credit_requirement_status = credit_state.get('credit_requirement_status', [])

    prerequisite_status = _are_prerequirements_satisfied(
        credit_requirement_status,
        evaluate_for_requirement_name=exam['content_id'],
        filter_out_namespaces=['grade']
    )

    exam.update({
        'prerequisite_status': prerequisite_status
    })

    if not prerequisite_status['are_prerequisites_satisifed']:
        # do we have any declined prerequisites, if so, then we
        # will auto-decline this proctored exam
        if prerequisite_status['declined_prerequisites']:
            _create_and_decline_attempt(exam['id'], user_id)
            return exam

        if prerequisite_status['failed_prerequisites']:
            prerequisite_status['failed_prerequisites'] = _resolve_prerequisite_links(
                exam,
                prerequisite_status['failed_prerequisites']
            )
        else:
            prerequisite_status['pending_prerequisites'] = _resolve_prerequisite_links(
                exam,
                prerequisite_status['pending_prerequisites']
            )
    return exam


def _get_ordered_prerequisites(prerequisites_statuses, filter_out_namespaces=None):
    """
    Apply filter and ordering of requirements status in our credit_state dictionary. This will
    return a list of statuses, filtered according to the filter_lambda (if non-None). We do this to ensure
    that we check for satisfactory fulfillment of prerequistes that we do so IN THE RIGHT ORDER
    """

    _filter_out_namespaces = filter_out_namespaces if filter_out_namespaces else []

    filtered_list = [
        status
        for status in prerequisites_statuses
        if status['namespace'] not in _filter_out_namespaces
    ]
    sorted_list = sorted(filtered_list, key=lambda status: status['order'])

    return sorted_list


def _are_prerequirements_satisfied(
        prerequisites_statuses,
        evaluate_for_requirement_name=None,
        filter_out_namespaces=None
):
    """
    Returns a dict about the fulfillment of any pre-requisites in order to this exam
    as proctored. The pre-requisites are taken from the credit requirements table. So if ordering
    of requirements are - say - ICRV1, Proctoring1, ICRV2, and Proctoring2, then the user cannot take
    Proctoring2 until there is an explicit pass on ICRV1, Proctoring1, ICRV2...

    NOTE: If evaluate_for_requirement_name=None that means check all requirements

    Return (dict):

        {
            # If all prerequisites are satisfied
            'are_prerequisites_satisifed': True/False,

            # A list of prerequisites that have been satisfied
            'satisfied_prerequisites': [...]

            # A list of prerequisites that have failed
            'failed_prerequisites': [....],

            # A list of prerequisites that are still pending
            'pending_prerequisites': [...],
        }

    NOTE: We filter out any 'grade' requirement since the student will most likely not have fulfilled
    those requirements while he/she is in the course
    """

    satisfied_prerequisites = []
    failed_prerequisites = []
    pending_prerequisites = []
    declined_prerequisites = []

    # insure an ordered and filtered list
    # we remove 'grade' requirements since those cannot be
    # satisfied while student is in the middle of a course
    requirement_statuses = _get_ordered_prerequisites(
        prerequisites_statuses,
        filter_out_namespaces=filter_out_namespaces
    )

    # find ourselves in the list
    ourself = None
    if evaluate_for_requirement_name:
        for idx, requirement in enumerate(requirement_statuses):
            if requirement['name'] == evaluate_for_requirement_name:
                ourself = requirement
                break

    # we are not in the list of requirements, look at all requirements
    if not ourself:
        idx = len(requirement_statuses)

    # now that we have the index of ourselves in the ordered list, we can walk backwards
    # and inspect all prerequisites

    # we don't look at ourselves
    idx = idx - 1
    while idx >= 0:
        requirement = requirement_statuses[idx]
        status = requirement['status']
        if status == 'satisfied':
            satisfied_prerequisites.append(requirement)
        elif status == 'failed':
            failed_prerequisites.append(requirement)
        elif status == 'declined':
            declined_prerequisites.append(requirement)
        else:
            pending_prerequisites.append(requirement)

        idx = idx - 1

    return {
        # all prequisites are satisfied if there are no failed or pending requirement
        # statuses
        'are_prerequisites_satisifed': (
            not failed_prerequisites and not pending_prerequisites and not declined_prerequisites
        ),
        # note that we reverse the list here, because we assempled it by walking backwards
        'satisfied_prerequisites': list(reversed(satisfied_prerequisites)),
        'failed_prerequisites': list(reversed(failed_prerequisites)),
        'pending_prerequisites': list(reversed(pending_prerequisites)),
        'declined_prerequisites': list(reversed(declined_prerequisites))
    }


JUMPTO_SUPPORTED_NAMESPACES = [
    'proctored_exam',
]


def _resolve_prerequisite_links(exam, prerequisites):
    """
    This will inject a jumpto URL into the list of prerequisites so that a user
    can click through
    """

    for prerequisite in prerequisites:
        jumpto_url = None
        if prerequisite['namespace'] in JUMPTO_SUPPORTED_NAMESPACES and prerequisite['name']:
            jumpto_url = reverse('jump_to', args=[exam['course_id'], prerequisite['name']])

        prerequisite['jumpto_url'] = jumpto_url

    return prerequisites


STATUS_SUMMARY_MAP = {
    '_default': {
        'short_description': ugettext_noop('Taking As Proctored Exam'),
        'suggested_icon': 'fa-pencil-square-o',
        'in_completed_state': False
    },
    ProctoredExamStudentAttemptStatus.eligible: {
        'short_description': ugettext_noop('Proctored Option Available'),
        'suggested_icon': 'fa-pencil-square-o',
        'in_completed_state': False
    },
    ProctoredExamStudentAttemptStatus.declined: {
        'short_description': ugettext_noop('Taking As Open Exam'),
        'suggested_icon': 'fa-pencil-square-o',
        'in_completed_state': False
    },
    ProctoredExamStudentAttemptStatus.submitted: {
        'short_description': ugettext_noop('Pending Session Review'),
        'suggested_icon': 'fa-spinner fa-spin',
        'in_completed_state': True
    },
    ProctoredExamStudentAttemptStatus.second_review_required: {
        'short_description': ugettext_noop('Pending Session Review'),
        'suggested_icon': 'fa-spinner fa-spin',
        'in_completed_state': True
    },
    ProctoredExamStudentAttemptStatus.verified: {
        'short_description': ugettext_noop('Passed Proctoring'),
        'suggested_icon': 'fa-check',
        'in_completed_state': True
    },
    ProctoredExamStudentAttemptStatus.rejected: {
        'short_description': ugettext_noop('Failed Proctoring'),
        'suggested_icon': 'fa-exclamation-triangle',
        'in_completed_state': True
    },
    ProctoredExamStudentAttemptStatus.error: {
        'short_description': ugettext_noop('Failed Proctoring'),
        'suggested_icon': 'fa-exclamation-triangle',
        'in_completed_state': True
    },
    ProctoredExamStudentAttemptStatus.expired: {
        'short_description': ugettext_noop('Proctored Option No Longer Available'),
        'suggested_icon': 'fa-times-circle',
        'in_completed_state': False
    }
}


PRACTICE_STATUS_SUMMARY_MAP = {
    '_default': {
        'short_description': ugettext_noop('Ungraded Practice Exam'),
        'suggested_icon': '',
        'in_completed_state': False
    },
    ProctoredExamStudentAttemptStatus.submitted: {
        'short_description': ugettext_noop('Practice Exam Completed'),
        'suggested_icon': 'fa-check',
        'in_completed_state': True
    },
    ProctoredExamStudentAttemptStatus.error: {
        'short_description': ugettext_noop('Practice Exam Failed'),
        'suggested_icon': 'fa-exclamation-triangle',
        'in_completed_state': True
    }
}

TIMED_EXAM_STATUS_SUMMARY_MAP = {
    '_default': {
        'short_description': ugettext_noop('Timed Exam'),
        'suggested_icon': 'fa-clock-o',
        'in_completed_state': False
    }
}


def get_attempt_status_summary(user_id, course_id, content_id):
    """
    Collects a summary about the status of the attempt.

    Summary is collected for the user in the course_id and content_id.

    If the exam is timed exam only then we simply
    return the dictionary with timed exam default summary

    Return will be:
    None: Not applicable
    - or -
    {
        'status': ['eligible', 'declined', 'submitted', 'verified', 'rejected'],
        'short_description': <short description of status>,
        'suggested_icon': <recommended font-awesome icon to use>,
        'in_completed_state': <if the status is considered in a 'completed' state>
    }
    """

    try:
        exam = get_exam_by_content_id(course_id, content_id)
    except ProctoredExamNotFoundException:
        # this really shouldn't happen, but log it at least
        log.exception(
            ('Requested attempt status summary for user_id=%(user_id)s, but could not find exam '
             'in course_id=%(course_id)s with content_id=%(content_id)s'),
            {
                'user_id': user_id,
                'course_id': course_id,
                'content_id': content_id,
            }
        )
        return None

    # check if the exam is not proctored
    if not exam['is_proctored']:
        summary = {}
        summary.update(TIMED_EXAM_STATUS_SUMMARY_MAP['_default'])
        # Note: translate the short description as it was stored unlocalized
        summary.update({
            'short_description': _(summary['short_description'])  # pylint: disable=translation-of-non-string
        })
        return summary

    # let's check credit eligibility
    credit_service = get_runtime_service('credit')
    credit_state = None  # explicit assignment
    not_practice_exam = not exam.get('is_practice_exam')

    # practice exams always has an attempt status regardless of
    # eligibility
    if credit_service and not_practice_exam:
        credit_state = credit_service.get_credit_state(user_id, str(course_id), return_course_info=True)
        user = USER_MODEL.objects.get(id=user_id)
        if not user.has_perm('edx_proctoring.can_take_proctored_exam', exam):
            return None

    attempt = get_current_exam_attempt(exam['id'], user_id)
    due_date_is_passed = has_due_date_passed(credit_state.get('course_end_date')) if credit_state else False

    if attempt:
        status = attempt['status']
    elif not_practice_exam and due_date_is_passed:
        status = ProctoredExamStudentAttemptStatus.expired
    else:
        status = ProctoredExamStudentAttemptStatus.eligible

    status_map = STATUS_SUMMARY_MAP if not_practice_exam else PRACTICE_STATUS_SUMMARY_MAP

    summary = {}
    if status in status_map:
        summary.update(status_map[status])
    else:
        summary.update(status_map['_default'])

    # Note: translate the short description as it was stored unlocalized
    summary.update({
        'status': status,
        'short_description': _(summary['short_description'])  # pylint: disable=translation-of-non-string
    })

    return summary


# pylint: disable=invalid-name
def get_last_verified_onboarding_attempts_per_user(users_list, backend):
    """
    Returns a dictionary of last verified proctored onboarding attempt for a specific backend,
    keyed off the user_id within the passed in users_list, if attempts exist.
    This only considers attempts within the last two years, as attempts
    before this point are considered expired.

    Parameters:
        * users: A list of users object of which we are checking the attempts
        * proctoring_backend: The name of the proctoring backend

    Returns:
        A dictionary:
        {
            342455 (user_id): attempt_object(attempt_id=1233),
            455454 (user_id): attempt_object(attempt_id=34303),
        }
    """
    attempts = ProctoredExamStudentAttempt.objects.get_last_verified_proctored_onboarding_attempts(
        users_list,
        backend,
    )
    user_attempt_dict = {}
    for attempt in attempts:
        user_id = attempt.user_id
        if not user_attempt_dict.get(user_id):
            user_attempt_dict[user_id] = attempt
    return user_attempt_dict


def _does_time_remain(attempt):
    """
    Helper function returns True if time remains for an attempt and False
    otherwise. Called from _get_timed_exam_view(), _get_practice_exam_view()
    and _get_proctored_exam_view()
    """
    does_time_remain = False
    has_started_exam = (
        attempt and
        attempt.get('started_at') and
        ProctoredExamStudentAttemptStatus.is_incomplete_status(attempt.get('status'))
    )
    if has_started_exam:
        expires_at = attempt['started_at'] + timedelta(minutes=attempt['allowed_time_limit_mins'])
        does_time_remain = datetime.now(pytz.UTC) < expires_at
    return does_time_remain


# pylint: disable=inconsistent-return-statements
def _get_timed_exam_view(exam, context, exam_id, user_id, course_id):
    """
    Returns a rendered view for the Timed Exams
    """
    student_view_template = None
    attempt = get_current_exam_attempt(exam_id, user_id)
    has_time_expired = False

    attempt_status = attempt['status'] if attempt else None
    has_due_date = exam['due_date'] is not None
    if not attempt_status or attempt_status == ProctoredExamStudentAttemptStatus.created:
        if is_exam_passed_due(exam, user=user_id):
            student_view_template = 'timed_exam/expired.html'
        else:
            student_view_template = 'timed_exam/entrance.html'
    elif is_exam_passed_due(exam, user_id) and ProctoredExamStudentAttemptStatus.is_incomplete_status(attempt_status):
        # When the exam is past due, we should prevent learners from accessing the exam even if
        # they already accessed the exam before, but haven't completed.
        student_view_template = 'timed_exam/expired.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.timed_out:
        raise NotImplementedError('There is no defined rendering for ProctoredExamStudentAttemptStatus.timed_out!')
    elif attempt_status == ProctoredExamStudentAttemptStatus.started:
        # when we're taking the exam we should not override the view
        return None
    elif attempt_status == ProctoredExamStudentAttemptStatus.ready_to_submit:
        student_view_template = 'timed_exam/ready_to_submit.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.submitted:
        # If we are not hiding the exam after the due_date has passed,
        # check if the exam's due_date has passed. If so, return None
        # so that the user can see their exam answers in read only mode.
        if not exam['hide_after_due'] and is_exam_passed_due(exam, user=user_id):
            has_context_updated = verify_and_add_wait_deadline(context, exam, user_id)
            if not has_context_updated:
                return None

        student_view_template = 'timed_exam/submitted.html'

        current_datetime = datetime.now(pytz.UTC)
        start_time = attempt['started_at']
        end_time = attempt['completed_at']
        attempt_duration_sec = (end_time - start_time).total_seconds()
        allowed_duration_sec = attempt['allowed_time_limit_mins'] * 60
        since_exam_ended_sec = (current_datetime - end_time).total_seconds()

        # if the user took >= the available time, then the exam must have expired.
        # but we show expiry message only when the exam was taken recently (less than SHOW_EXPIRY_MESSAGE_DURATION)
        if attempt_duration_sec >= allowed_duration_sec and since_exam_ended_sec < SHOW_EXPIRY_MESSAGE_DURATION:
            has_time_expired = True

    if student_view_template:
        template = loader.get_template(student_view_template)
        allowed_time_limit_mins = attempt.get('allowed_time_limit_mins', None) if attempt else None

        if not allowed_time_limit_mins:
            # no existing attempt or user has not started exam yet, so compute the user's allowed
            # time limit, including any accommodations or time saved from a previous attempt
            allowed_time_limit_mins = _calculate_allowed_mins(exam, user_id)

        total_time = humanized_time(allowed_time_limit_mins)

        # According to WCAG, there is no need to allow for extra time if > 20 hours allowed
        hide_extra_time_footer = exam['time_limit_mins'] > 20 * 60

        progress_page_url = ''
        try:
            progress_page_url = reverse('progress', args=[course_id])
        except NoReverseMatch:
            log.exception(
                "Can't find progress url for course_id=%(course_id)s",
                {
                    'course_id': course_id,
                }
            )

        context.update({
            'total_time': total_time,
            'hide_extra_time_footer': hide_extra_time_footer,
            'will_be_revealed': has_due_date and not exam['hide_after_due'],
            'exam_id': exam_id,
            'exam_name': exam['exam_name'],
            'progress_page_url': progress_page_url,
            'does_time_remain': _does_time_remain(attempt),
            'has_time_expired': has_time_expired,
            'enter_exam_endpoint': reverse('edx_proctoring:proctored_exam.attempt.collection'),
            'change_state_url': reverse(
                'edx_proctoring:proctored_exam.attempt',
                args=[attempt['id']]
            ) if attempt else '',
            'course_id': course_id,
        })
        return template.render(context)


def _calculate_allowed_mins(exam, user_id):
    """
    Returns the allowed minutes w.r.t due date
    """
    due_datetime = get_exam_due_date(exam, user_id)
    allowed_time_limit_mins = exam['time_limit_mins']

    current_attempt = get_current_exam_attempt(exam['id'], user_id)
    if current_attempt and current_attempt['time_remaining_seconds']:
        # if resuming from a previous attempt, use the time remaining
        allowed_time_limit_mins = int(current_attempt['time_remaining_seconds'] / 60)
    else:
        # add in the allowed additional time
        allowance_extra_mins = ProctoredExamStudentAllowance.get_additional_time_granted(exam.get('id'), user_id)
        if allowance_extra_mins:
            allowed_time_limit_mins += allowance_extra_mins

    if due_datetime:
        current_datetime = datetime.now(pytz.UTC)
        if current_datetime + timedelta(minutes=allowed_time_limit_mins) > due_datetime:
            # e.g current_datetime=09:00, due_datetime=10:00 and allowed_mins=120(2hours)
            # then allowed_mins should be 60(1hour)
            allowed_time_limit_mins = max(int((due_datetime - current_datetime).total_seconds() / 60), 0)

    return allowed_time_limit_mins


def _get_proctored_exam_context(exam, attempt, user_id, course_id, is_practice_exam=False):
    """
    Common context variables for the Proctored and Practice exams' templates.
    """
    password_url = ''
    try:
        password_assistance_url = reverse('password_assistance')
        scheme = 'https' if getattr(settings, 'HTTPS', 'on') == 'on' else 'http'
        password_url = f'{scheme}://{constants.SITE_NAME}{password_assistance_url}'
    except NoReverseMatch:
        log.exception("Can't find password reset link")

    has_due_date = exam['due_date'] is not None
    attempt_time = attempt.get('allowed_time_limit_mins', None) if attempt else None

    # if there is no attempt or an attempt with no time limit attribute, calculate the allowed time
    # also, if the attempt is in the ready to resume status, calculate the allowed time to correctly
    # display the time remaining
    if not attempt_time or (attempt and is_attempt_ready_to_resume(attempt)):
        attempt_time = _calculate_allowed_mins(exam, user_id)

    total_time = humanized_time(attempt_time)
    progress_page_url = ''
    try:
        progress_page_url = reverse('progress', args=[course_id])
    except NoReverseMatch:
        log.exception(
            "Can't find progress url for course_id=%(course_id)s",
            {
                'course_id': course_id,
            }
        )

    provider = get_backend_provider(exam)

    context = {
        'platform_name': settings.PLATFORM_NAME,
        'total_time': total_time,
        'exam_id': exam['id'],
        'progress_page_url': progress_page_url,
        'is_sample_attempt': is_practice_exam,
        'has_due_date': has_due_date,
        'has_due_date_passed': is_exam_passed_due(exam, user=user_id),
        'able_to_reenter_exam': _does_time_remain(attempt) and not provider.should_block_access_to_exam_material(),
        'enter_exam_endpoint': reverse('edx_proctoring:proctored_exam.attempt.collection'),
        'exam_started_poll_url': reverse(
            'edx_proctoring:proctored_exam.attempt',
            args=[attempt['id']]
        ) if attempt else '',
        'change_state_url': reverse(
            'edx_proctoring:proctored_exam.attempt',
            args=[attempt['id']]
        ) if attempt else '',
        'update_is_status_acknowledge_url': reverse(
            'edx_proctoring:proctored_exam.attempt.review_status',
            args=[attempt['id']]
        ) if attempt else '',
        'link_urls': settings.PROCTORING_SETTINGS.get('LINK_URLS', {}),
        'tech_support_email': settings.TECH_SUPPORT_EMAIL,
        'proctoring_escalation_email': _get_proctoring_escalation_email(exam['course_id']),
        'exam_review_policy': _get_review_policy_by_exam_id(exam['id']),
        'backend_js_bundle': provider.get_javascript(),
        'provider_tech_support_email': provider.tech_support_email,
        'provider_tech_support_phone': provider.tech_support_phone,
        'provider_name': provider.verbose_name,
        'learner_notification_from_email': provider.learner_notification_from_email,
        'integration_specific_email': get_integration_specific_email(provider),
        'exam_display_name': exam['exam_name'],
        'reset_link': password_url,
        'ping_interval': provider.ping_interval,
        'can_view_content_past_due': constants.CONTENT_VIEWABLE_PAST_DUE_DATE,
    }
    if attempt:
        context['exam_code'] = attempt['attempt_code']
        if attempt['status'] in (ProctoredExamStudentAttemptStatus.created,
                                 ProctoredExamStudentAttemptStatus.download_software_clicked):
            # since this may make an http request, let's not include it on every page
            provider_attempt = provider.get_attempt(attempt)
            download_url = provider_attempt.get('download_url', None) or provider.get_software_download_url()

            context.update({
                'backend_instructions': provider_attempt.get('instructions', None),
                'software_download_url': download_url,
            })
    return context


# pylint: disable=inconsistent-return-statements
def _get_practice_exam_view(exam, context, exam_id, user_id, course_id):
    """
    Returns a rendered view for the practice Exams
    """
    user = USER_MODEL.objects.get(id=user_id)

    if not user.has_perm('edx_proctoring.can_take_proctored_exam', exam):
        return None

    student_view_template = None

    attempt = get_current_exam_attempt(exam_id, user_id)

    attempt_status = attempt['status'] if attempt else None

    if not user.is_active:
        student_view_template = 'proctored_exam/inactive_account.html'
    elif not attempt_status:
        student_view_template = 'practice_exam/entrance.html'
    elif is_attempt_ready_to_resume(attempt):
        student_view_template = 'proctored_exam/ready_to_resume.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.started:
        provider = get_backend_provider(exam)
        if provider.should_block_access_to_exam_material():
            student_view_template = 'proctored_exam/error_wrong_browser.html'
        else:
            # when we're taking the exam we should not override the view
            return None
    elif attempt_status in [ProctoredExamStudentAttemptStatus.created,
                            ProctoredExamStudentAttemptStatus.download_software_clicked]:
        student_view_template = 'proctored_exam/instructions.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.ready_to_start:
        student_view_template = 'proctored_exam/ready_to_start.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.error:
        student_view_template = 'practice_exam/error.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.submitted:
        student_view_template = 'practice_exam/submitted.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.ready_to_submit:
        student_view_template = 'proctored_exam/ready_to_submit.html'

    if student_view_template:
        template = loader.get_template(student_view_template)
        context.update(_get_proctored_exam_context(exam, attempt, user_id, course_id, is_practice_exam=True))
        return template.render(context)


# pylint: disable=inconsistent-return-statements
def _get_onboarding_exam_view(exam, context, exam_id, user_id, course_id):
    """
    Returns a rendered view for onboarding exams, which for some backends establish a user's profile
    """
    user = USER_MODEL.objects.get(id=user_id)

    if not user.has_perm('edx_proctoring.can_take_proctored_exam', exam):
        return None

    student_view_template = None

    attempt = get_current_exam_attempt(exam_id, user_id)

    attempt_status = attempt['status'] if attempt else None

    if not user.is_active:
        student_view_template = 'proctored_exam/inactive_account.html'
    elif not attempt_status:
        # if exam due date has passed, then we can't take the exam
        if is_exam_passed_due(exam, user_id):
            student_view_template = 'proctored_exam/expired.html'
        else:
            student_view_template = 'onboarding_exam/entrance.html'
    elif is_attempt_ready_to_resume(attempt):
        student_view_template = 'proctored_exam/ready_to_resume.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.started:
        # when we're taking the exam we should not override the view
        return None
    elif attempt_status in [ProctoredExamStudentAttemptStatus.created,
                            ProctoredExamStudentAttemptStatus.download_software_clicked]:
        student_view_template = 'proctored_exam/instructions.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.ready_to_start:
        student_view_template = 'proctored_exam/ready_to_start.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.error:
        student_view_template = 'onboarding_exam/error.html'
    elif attempt_status in [ProctoredExamStudentAttemptStatus.submitted,
                            ProctoredExamStudentAttemptStatus.second_review_required]:
        student_view_template = 'onboarding_exam/submitted.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.ready_to_submit:
        student_view_template = 'onboarding_exam/ready_to_submit.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.verified:
        student_view_template = 'onboarding_exam/verified.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.rejected:
        student_view_template = 'onboarding_exam/rejected.html'

    if student_view_template:
        template = loader.get_template(student_view_template)
        context.update(_get_proctored_exam_context(exam, attempt, user_id, course_id, is_practice_exam=True))
        return template.render(context)


# pylint: disable=inconsistent-return-statements
def _get_proctored_exam_view(exam, context, exam_id, user_id, course_id):
    """
    Returns a rendered view for the Proctored Exams
    """
    student_view_template = None

    user = USER_MODEL.objects.get(id=user_id)

    if not user.has_perm('edx_proctoring.can_take_proctored_exam', exam):
        return None

    attempt = get_current_exam_attempt(exam_id, user_id)

    attempt_status = attempt['status'] if attempt else None

    # if user has declined the attempt, then we don't show the
    # proctored exam, a quick exit....
    if attempt_status == ProctoredExamStudentAttemptStatus.declined:
        return None

    if not user.is_active:
        student_view_template = 'proctored_exam/inactive_account.html'
    elif not attempt_status:
        # student has not started an attempt
        # so, show them:
        #       1) If there are failed prerequisites then block user and say why
        #       2) If there are pending prerequisites then block user and allow them to remediate them
        #       3) If there are declined prerequisites, then we auto-decline proctoring since user
        #          explicitly declined their interest in credit
        #       4) Otherwise - all prerequisites are satisfied - then give user
        #          option to take exam as proctored

        # get information about prerequisites

        credit_requirement_status = context.get('credit_state', {}).get('credit_requirement_status', [])

        prerequisite_status = _are_prerequirements_satisfied(
            credit_requirement_status,
            evaluate_for_requirement_name=exam['content_id'],
            filter_out_namespaces=['grade']
        )

        # add any prerequisite information, if applicable
        context.update({
            'prerequisite_status': prerequisite_status
        })

        # if exam due date has passed, then we can't take the exam
        if is_exam_passed_due(exam, user_id):
            student_view_template = 'proctored_exam/expired.html'
        elif not prerequisite_status['are_prerequisites_satisifed']:
            # do we have any declined prerequisites, if so, then we
            # will auto-decline this proctored exam
            if prerequisite_status['declined_prerequisites']:
                # user hasn't a record of attempt, create one now
                # so we can mark it as declined
                _create_and_decline_attempt(exam_id, user_id)
                return None

            # do we have failed prerequisites? That takes priority in terms of
            # messaging
            if prerequisite_status['failed_prerequisites']:
                # Let's resolve the URLs to jump to this prequisite
                prerequisite_status['failed_prerequisites'] = _resolve_prerequisite_links(
                    exam,
                    prerequisite_status['failed_prerequisites']
                )
                student_view_template = 'proctored_exam/failed-prerequisites.html'
            else:
                # Let's resolve the URLs to jump to this prequisite
                prerequisite_status['pending_prerequisites'] = _resolve_prerequisite_links(
                    exam,
                    prerequisite_status['pending_prerequisites']
                )
                student_view_template = 'proctored_exam/pending-prerequisites.html'
        else:
            student_view_template = 'proctored_exam/entrance.html'
            # emit an event that the user was presented with the option
            # to start timed exam
            emit_event(exam, 'option-presented')
    elif is_exam_passed_due(exam, user_id) and ProctoredExamStudentAttemptStatus.is_incomplete_status(attempt_status):
        # When the exam is past due, we should prevent learners from accessing the exam even if
        # they already accessed the exam before, but haven't completed.
        student_view_template = 'proctored_exam/expired.html'
    elif is_attempt_ready_to_resume(attempt):
        student_view_template = 'proctored_exam/ready_to_resume.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.started:
        provider = get_backend_provider(exam)
        if provider.should_block_access_to_exam_material():
            student_view_template = 'proctored_exam/error_wrong_browser.html'
        else:
            # when we're taking the exam we should not override the view
            return None
    elif attempt_status in [ProctoredExamStudentAttemptStatus.created,
                            ProctoredExamStudentAttemptStatus.download_software_clicked]:
        student_view_template = 'proctored_exam/instructions.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.ready_to_start:
        student_view_template = 'proctored_exam/ready_to_start.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.error:
        student_view_template = 'proctored_exam/error.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.timed_out:
        raise NotImplementedError('There is no defined rendering for ProctoredExamStudentAttemptStatus.timed_out!')
    elif attempt_status == ProctoredExamStudentAttemptStatus.submitted:
        student_view_template = None if (_was_review_status_acknowledged(
            attempt['is_status_acknowledged'],
            exam
        ) and constants.CONTENT_VIEWABLE_PAST_DUE_DATE) else 'proctored_exam/submitted.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.second_review_required:
        # the student should still see a 'submitted'
        # rendering even if the review needs a 2nd review
        student_view_template = None if (_was_review_status_acknowledged(
            attempt['is_status_acknowledged'],
            exam
        ) and constants.CONTENT_VIEWABLE_PAST_DUE_DATE) else 'proctored_exam/submitted.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.verified:
        student_view_template = None if (_was_review_status_acknowledged(
            attempt['is_status_acknowledged'],
            exam
        ) and constants.CONTENT_VIEWABLE_PAST_DUE_DATE) else 'proctored_exam/verified.html'
        has_context_updated = verify_and_add_wait_deadline(context, exam, user_id)
        # The edge case where student has already acknowledged the result
        # but the course team changed the grace period
        if has_context_updated and not student_view_template:
            student_view_template = 'proctored_exam/verified.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.rejected:
        student_view_template = None if (_was_review_status_acknowledged(
            attempt['is_status_acknowledged'],
            exam
        ) and constants.CONTENT_VIEWABLE_PAST_DUE_DATE) else 'proctored_exam/rejected.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.ready_to_submit:
        student_view_template = 'proctored_exam/ready_to_submit.html'
    elif attempt_status in ProctoredExamStudentAttemptStatus.onboarding_errors:
        student_view_template = 'proctored_exam/onboarding_error.html'
        context['onboarding_status'] = attempt['status']
        context['support_email_subject'] = _('Onboarding status question')
        onboarding_exam = ProctoredExam.objects.filter(course_id=course_id,
                                                       is_active=True,
                                                       is_practice_exam=True).first()
        context['onboarding_link'] = reverse('jump_to', args=[course_id, onboarding_exam.content_id])

    if student_view_template:
        template = loader.get_template(student_view_template)
        context.update(_get_proctored_exam_context(exam, attempt, user_id, course_id))
        return template.render(context)


def get_student_view(user_id, course_id, content_id,
                     context, user_role='student'):
    """
    Helper method that will return the view HTML related to the exam control
    flow (i.e. entering, expired, completed, etc.) If there is no specific
    content to display, then None will be returned and the caller should
    render it's own view
    """

    # non-student roles should never see any proctoring related
    # screens
    if user_role != 'student':
        return None

    course_end_date = context.get('credit_state', {}).get('course_end_date', None)

    exam_id = None
    try:
        exam = get_exam_by_content_id(course_id, content_id)
        if not exam['is_active']:
            # Exam is no longer active
            # Note, we don't hard delete exams since we need to retain
            # data
            return None

        # Just in case the due date has been changed because of the
        # self-paced courses, use the due date from the context
        if exam['due_date'] != context.get('due_date', None):
            exam['due_date'] = context.get('due_date', None)

        exam_id = exam['id']
    except ProctoredExamNotFoundException:
        # This really shouldn't happen
        # as Studio will be setting this up
        exam_id = create_exam(
            course_id=course_id,
            content_id=str(content_id),
            exam_name=context['display_name'],
            time_limit_mins=context['default_time_limit_mins'],
            is_proctored=context.get('is_proctored', False),
            is_practice_exam=context.get('is_practice_exam', False),
            due_date=context.get('due_date', None),
            hide_after_due=context.get('hide_after_due', False),
        )
        exam = get_exam_by_content_id(course_id, content_id)

    is_practice_exam = exam['is_proctored'] and exam['is_practice_exam']
    is_proctored_exam = exam['is_proctored'] and not exam['is_practice_exam']
    is_timed_exam = not exam['is_proctored'] and not exam['is_practice_exam']

    exam_backend = get_backend_provider(name=exam['backend'])

    sub_view_func = None
    if is_timed_exam:
        sub_view_func = _get_timed_exam_view
    elif is_practice_exam and not has_due_date_passed(course_end_date):
        if exam_backend.supports_onboarding:
            sub_view_func = _get_onboarding_exam_view
        else:
            sub_view_func = _get_practice_exam_view
    elif is_proctored_exam and not has_due_date_passed(course_end_date):
        sub_view_func = _get_proctored_exam_view

    if sub_view_func:
        return sub_view_func(exam, context, exam_id, user_id, course_id)
    return None


def get_exam_violation_report(course_id, include_practice_exams=False):
    """
    Returns proctored exam attempts for the course id, including review details.
    Violation status messages are aggregated as a list per attempt for each
    violation type.
    """

    attempts_by_code = {
        attempt['attempt_code']: {
            'course_id': attempt['proctored_exam']['course_id'],
            'exam_name': attempt['proctored_exam']['exam_name'],
            'username': attempt['user']['username'],
            'email': attempt['user']['email'],
            'attempt_code': attempt['attempt_code'],
            'allowed_time_limit_mins': attempt['allowed_time_limit_mins'],
            'is_sample_attempt': attempt['is_sample_attempt'],
            'started_at': attempt['started_at'],
            'completed_at': attempt['completed_at'],
            'status': attempt['status'],
            'review_status': None,
            'provider': attempt['proctored_exam']['backend'],
            'user_id': attempt['user']['id']

        } for attempt in get_all_exam_attempts(course_id)
    }

    reviews = ProctoredExamSoftwareSecureReview.objects.prefetch_related(
        'proctoredexamsoftwaresecurecomment_set'
    ).filter(
        exam__course_id=course_id,
        exam__is_practice_exam=include_practice_exams
    )

    for review in reviews:
        attempt_code = review.attempt_code
        if attempt_code in attempts_by_code:
            attempts_by_code[attempt_code]['review_status'] = review.review_status

            for comment in review.proctoredexamsoftwaresecurecomment_set.all():
                comments_key = f'{comment.status} Comments'

                if comments_key not in attempts_by_code[attempt_code]:
                    attempts_by_code[attempt_code][comments_key] = []

                attempts_by_code[attempt_code][comments_key].append(comment.comment)

    return sorted(list(attempts_by_code.values()), key=lambda a: a['exam_name'])


def is_backend_dashboard_available(course_id):
    """
    Returns whether the backend for this course supports the instructor dashboard feature
    """
    exams = ProctoredExam.get_all_exams_for_course(
        course_id,
        active_only=True
    )
    for exam in exams:
        if get_backend_provider(name=exam.backend).has_dashboard:
            return True
    return False


def does_backend_support_onboarding(backend):
    """
    Returns whether this backend supports onboarding exams.
    """
    try:
        return get_backend_provider(name=backend).supports_onboarding
    except NotImplementedError:
        log.exception(
            'No proctoring backend configured for backend=%(backend)s',
            {
                'backend': backend,
            }
        )
        return False


def get_exam_configuration_dashboard_url(course_id, content_id):
    """
    Returns the exam configuration dashboard URL, if the exam exists and the backend
    has an exam configuration dashboard. Otherwise, returns None.
    """
    try:
        exam = get_exam_by_content_id(course_id, content_id)
    except ProctoredExamNotFoundException:
        log.exception(
            ('Cannot find the proctored exam in course_id=%(course_id)s with '
             'content_id=%(content_id)s'),
            {
                'course_id': course_id,
                'content_id': content_id,
            }
        )
        return None

    if is_backend_dashboard_available(course_id):
        base_url = reverse(
            'edx_proctoring:instructor_dashboard_exam', args=(course_id, exam['id'])
        )
        return f'{base_url}?config=true'

    return None


def get_integration_specific_email(provider):
    """
    Return the edX contact email to use for a particular provider.
    """
    return getattr(provider, 'integration_specific_email', None) or constants.DEFAULT_CONTACT_EMAIL


def get_enrollments_can_take_proctored_exams(course_id, text_search=None):
    """
    Return all enrollments for a course from the LMS Enrollments runtime API.

    Parameters:
    * course_id: course ID for the course
    * text_search: the string against which to do a match on users' username or email; optional
    """
    enrollments_service = get_runtime_service('enrollments')
    return enrollments_service.get_enrollments_can_take_proctored_exams(course_id, text_search)


def get_onboarding_attempt_data_for_learner(course_id, user, backend):
    """
    Return the onboarding status and expiration date for a learner in a specific course. If no
    onboarding status is associated with the course, check to see if the
    learner is approved for onboarding in another course

    Parameters:
        * course_id: course ID for the course
        * user: User object
        * backend: proctoring provider to filter exams on
    """
    data = {'onboarding_status': None, 'expiration_date': None}
    attempts = ProctoredExamStudentAttempt.objects.get_proctored_practice_attempts_by_course_id(course_id, [user])

    # Default to the most recent attempt in the course if there are no verified attempts
    relevant_attempt = attempts[0] if attempts else None
    for attempt in attempts:
        if attempt.status == ProctoredExamStudentAttemptStatus.verified:
            relevant_attempt = attempt
            break

    # If there is no verified attempt in the current course, check for a verified attempt in another course
    verified_attempt = None
    if not relevant_attempt or relevant_attempt.status != ProctoredExamStudentAttemptStatus.verified:
        attempt_dict = get_last_verified_onboarding_attempts_per_user(
            [user],
            backend,
        )
        verified_attempt = attempt_dict.get(user.id)

    if verified_attempt:
        data['onboarding_status'] = InstructorDashboardOnboardingAttemptStatus.other_course_approved
        data['expiration_date'] = verified_attempt.modified + timedelta(days=constants.VERIFICATION_DAYS_VALID)
    elif relevant_attempt:
        data['onboarding_status'] = relevant_attempt.status

    return data
