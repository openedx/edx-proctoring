# pylint: disable=too-many-branches, too-many-lines, too-many-statements

"""
In-Proc API (aka Library) for the edx_proctoring subsystem. This is not to be confused with a HTTP REST
API which is in the views.py file, per edX coding standards
"""
import pytz
import uuid
import logging

from datetime import datetime, timedelta

from django.utils.translation import ugettext as _
from django.conf import settings
from django.template import Context, loader
from django.core.urlresolvers import reverse, NoReverseMatch
from django.core.mail.message import EmailMessage

from edx_proctoring import constants
from edx_proctoring.exceptions import (
    ProctoredExamAlreadyExists,
    ProctoredExamNotFoundException,
    StudentExamAttemptAlreadyExistsException,
    StudentExamAttemptDoesNotExistsException,
    StudentExamAttemptedAlreadyStarted,
    ProctoredExamIllegalStatusTransition,
    ProctoredExamPermissionDenied,
)
from edx_proctoring.models import (
    ProctoredExam,
    ProctoredExamStudentAllowance,
    ProctoredExamStudentAttempt,
    ProctoredExamStudentAttemptStatus,
    ProctoredExamReviewPolicy,
)
from edx_proctoring.serializers import (
    ProctoredExamSerializer,
    ProctoredExamStudentAttemptSerializer,
    ProctoredExamStudentAllowanceSerializer,
)
from edx_proctoring.utils import humanized_time

from edx_proctoring.backends import get_backend_provider
from edx_proctoring.runtime import get_runtime_service

log = logging.getLogger(__name__)


def is_feature_enabled():
    """
    Returns if this feature has been enabled in our FEATURE flags
    """

    return hasattr(settings, 'FEATURES') and settings.FEATURES.get('ENABLE_PROCTORED_EXAMS', False)


def create_exam(course_id, content_id, exam_name, time_limit_mins,
                is_proctored=True, is_practice_exam=False, external_id=None, is_active=True):
    """
    Creates a new ProctoredExam entity, if the course_id/content_id pair do not already exist.
    If that pair already exists, then raise exception.

    Returns: id (PK)
    """

    if ProctoredExam.get_exam_by_content_id(course_id, content_id) is not None:
        raise ProctoredExamAlreadyExists

    proctored_exam = ProctoredExam.objects.create(
        course_id=course_id,
        content_id=content_id,
        external_id=external_id,
        exam_name=exam_name,
        time_limit_mins=time_limit_mins,
        is_proctored=is_proctored,
        is_practice_exam=is_practice_exam,
        is_active=is_active
    )

    log_msg = (
        u'Created exam ({exam_id}) with parameters: course_id={course_id}, '
        u'content_id={content_id}, exam_name={exam_name}, time_limit_mins={time_limit_mins}, '
        u'is_proctored={is_proctored}, is_practice_exam={is_practice_exam}, '
        u'external_id={external_id}, is_active={is_active}'.format(
            exam_id=proctored_exam.id,
            course_id=course_id, content_id=content_id,
            exam_name=exam_name, time_limit_mins=time_limit_mins,
            is_proctored=is_proctored, is_practice_exam=is_practice_exam,
            external_id=external_id, is_active=is_active
        )
    )
    log.info(log_msg)

    return proctored_exam.id


def update_exam(exam_id, exam_name=None, time_limit_mins=None,
                is_proctored=None, is_practice_exam=None, external_id=None, is_active=None):
    """
    Given a Django ORM id, update the existing record, otherwise raise exception if not found.
    If an argument is not passed in, then do not change it's current value.

    Returns: id
    """

    log_msg = (
        u'Updating exam_id {exam_id} with parameters '
        u'exam_name={exam_name}, time_limit_mins={time_limit_mins}, '
        u'is_proctored={is_proctored}, is_practice_exam={is_practice_exam}, '
        u'external_id={external_id}, is_active={is_active}'.format(
            exam_id=exam_id, exam_name=exam_name, time_limit_mins=time_limit_mins,
            is_proctored=is_proctored, is_practice_exam=is_practice_exam,
            external_id=external_id, is_active=is_active
        )
    )
    log.info(log_msg)

    proctored_exam = ProctoredExam.get_exam_by_id(exam_id)
    if proctored_exam is None:
        raise ProctoredExamNotFoundException

    if exam_name is not None:
        proctored_exam.exam_name = exam_name
    if time_limit_mins is not None:
        proctored_exam.time_limit_mins = time_limit_mins
    if is_proctored is not None:
        proctored_exam.is_proctored = is_proctored
    if is_practice_exam is not None:
        proctored_exam.is_practice_exam = is_practice_exam
    if external_id is not None:
        proctored_exam.external_id = external_id
    if is_active is not None:
        proctored_exam.is_active = is_active
    proctored_exam.save()
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
        raise ProctoredExamNotFoundException

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
        raise ProctoredExamNotFoundException

    serialized_exam_object = ProctoredExamSerializer(proctored_exam)
    return serialized_exam_object.data


def add_allowance_for_user(exam_id, user_info, key, value):
    """
    Adds (or updates) an allowance for a user within a given exam
    """

    log_msg = (
        'Adding allowance "{key}" with value "{value}" for exam_id {exam_id} '
        'for user {user_info} '.format(
            key=key, value=value, exam_id=exam_id, user_info=user_info
        )
    )
    log.info(log_msg)

    ProctoredExamStudentAllowance.add_allowance_for_user(exam_id, user_info, key, value)


def get_allowances_for_course(course_id):
    """
    Get all the allowances for the course.
    """
    student_allowances = ProctoredExamStudentAllowance.get_allowances_for_course(course_id)
    return [ProctoredExamStudentAllowanceSerializer(allowance).data for allowance in student_allowances]


def remove_allowance_for_user(exam_id, user_id, key):
    """
    Deletes an allowance for a user within a given exam.
    """
    log_msg = (
        'Removing allowance "{key}" for exam_id {exam_id} for user_id {user_id} '.format(
            key=key, exam_id=exam_id, user_id=user_id
        )
    )
    log.info(log_msg)

    student_allowance = ProctoredExamStudentAllowance.get_allowance_for_user(exam_id, user_id, key)
    if student_allowance is not None:
        student_allowance.delete()


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
                attempt['proctored_exam']['id'],
                attempt['user']['id'],
                ProctoredExamStudentAttemptStatus.timed_out
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


def get_exam_attempt(exam_id, user_id):
    """
    Return an existing exam attempt for the given student
    """
    exam_attempt_obj = ProctoredExamStudentAttempt.objects.get_exam_attempt(exam_id, user_id)
    return _get_exam_attempt(exam_attempt_obj)


def get_exam_attempt_by_id(attempt_id):
    """
    Return an existing exam attempt for the given student
    """
    exam_attempt_obj = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_id(attempt_id)
    return _get_exam_attempt(exam_attempt_obj)


def get_exam_attempt_by_code(attempt_code):
    """
    Signals the beginning of an exam attempt when we only have
    an attempt code
    """

    exam_attempt_obj = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_code(attempt_code)
    return _get_exam_attempt(exam_attempt_obj)


def update_exam_attempt(attempt_id, **kwargs):
    """
    update exam_attempt
    """
    exam_attempt_obj = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_id(attempt_id)
    for key, value in kwargs.items():
        # only allow a limit set of fields to update
        # namely because status transitions can trigger workflow
        if key not in ['last_poll_timestamp', 'last_poll_ipaddr']:
            err_msg = (
                'You cannot call into update_exam_attempt to change '
                'field {key}'.format(key=key)
            )
            raise ProctoredExamPermissionDenied(err_msg)
        setattr(exam_attempt_obj, key, value)
    exam_attempt_obj.save()


def create_exam_attempt(exam_id, user_id, taking_as_proctored=False):
    """
    Creates an exam attempt for user_id against exam_id. There should only be
    one exam_attempt per user per exam. Multiple attempts by user will be archived
    in a separate table
    """
    # for now the student is allowed the exam default

    log_msg = (
        'Creating exam attempt for exam_id {exam_id} for '
        'user_id {user_id} with taking as proctored = {taking_as_proctored}'.format(
            exam_id=exam_id, user_id=user_id, taking_as_proctored=taking_as_proctored
        )
    )
    log.info(log_msg)

    exam = get_exam_by_id(exam_id)
    existing_attempt = ProctoredExamStudentAttempt.objects.get_exam_attempt(exam_id, user_id)
    if existing_attempt:
        if existing_attempt.is_sample_attempt:
            # Archive the existing attempt by deleting it.
            existing_attempt.delete_exam_attempt()
        else:
            err_msg = (
                'Cannot create new exam attempt for exam_id = {exam_id} and '
                'user_id = {user_id} because it already exists!'
            ).format(exam_id=exam_id, user_id=user_id)

            raise StudentExamAttemptAlreadyExistsException(err_msg)

    allowed_time_limit_mins = exam['time_limit_mins']

    # add in the allowed additional time
    allowance_extra_mins = ProctoredExamStudentAllowance.get_additional_time_granted(exam_id, user_id)
    if allowance_extra_mins:
        allowed_time_limit_mins += allowance_extra_mins

    attempt_code = unicode(uuid.uuid4()).upper()

    external_id = None
    review_policy = ProctoredExamReviewPolicy.get_review_policy_for_exam(exam_id)
    review_policy_exception = ProctoredExamStudentAllowance.get_review_policy_exception(exam_id, user_id)

    if taking_as_proctored:
        scheme = 'https' if getattr(settings, 'HTTPS', 'on') == 'on' else 'http'
        callback_url = '{scheme}://{hostname}{path}'.format(
            scheme=scheme,
            hostname=settings.SITE_NAME,
            path=reverse(
                'edx_proctoring.anonymous.proctoring_launch_callback.start_exam',
                args=[attempt_code]
            )
        )

        # get the name of the user, if the service is available
        full_name = None

        credit_service = get_runtime_service('credit')
        if credit_service:
            credit_state = credit_service.get_credit_state(user_id, exam['course_id'])
            full_name = credit_state['profile_fullname']

        context = {
            'time_limit_mins': allowed_time_limit_mins,
            'attempt_code': attempt_code,
            'is_sample_attempt': exam['is_practice_exam'],
            'callback_url': callback_url,
            'full_name': full_name,
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
        external_id = get_backend_provider().register_exam_attempt(
            exam,
            context=context,
        )

    attempt = ProctoredExamStudentAttempt.create_exam_attempt(
        exam_id,
        user_id,
        '',  # student name is TBD
        allowed_time_limit_mins,
        attempt_code,
        taking_as_proctored,
        exam['is_practice_exam'],
        external_id,
        review_policy_id=review_policy.id if review_policy else None,
    )

    log_msg = (
        'Created exam attempt ({attempt_id}) for exam_id {exam_id} for '
        'user_id {user_id} with taking as proctored = {taking_as_proctored} '
        'with allowed time limit minutes of {allowed_time_limit_mins}. '
        'Attempt_code {attempt_code} was generated which has a '
        'external_id of {external_id}'.format(
            attempt_id=attempt.id, exam_id=exam_id, user_id=user_id,
            taking_as_proctored=taking_as_proctored,
            allowed_time_limit_mins=allowed_time_limit_mins,
            attempt_code=attempt_code,
            external_id=external_id
        )
    )
    log.info(log_msg)

    return attempt.id


def start_exam_attempt(exam_id, user_id):
    """
    Signals the beginning of an exam attempt for a given
    exam_id. If one already exists, then an exception should be thrown.

    Returns: exam_attempt_id (PK)
    """

    existing_attempt = ProctoredExamStudentAttempt.objects.get_exam_attempt(exam_id, user_id)

    if not existing_attempt:
        err_msg = (
            'Cannot start exam attempt for exam_id = {exam_id} '
            'and user_id = {user_id} because it does not exist!'
        ).format(exam_id=exam_id, user_id=user_id)

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
            'Cannot start exam attempt for attempt_code = {attempt_code} '
            'because it does not exist!'
        ).format(attempt_code=attempt_code)

        raise StudentExamAttemptDoesNotExistsException(err_msg)

    return _start_exam_attempt(existing_attempt)


def _start_exam_attempt(existing_attempt):
    """
    Helper method
    """

    if existing_attempt.started_at and existing_attempt.status == ProctoredExamStudentAttemptStatus.started:
        # cannot restart an attempt
        err_msg = (
            'Cannot start exam attempt for exam_id = {exam_id} '
            'and user_id = {user_id} because it has already started!'
        ).format(exam_id=existing_attempt.proctored_exam.id, user_id=existing_attempt.user_id)

        raise StudentExamAttemptedAlreadyStarted(err_msg)

    update_attempt_status(
        existing_attempt.proctored_exam_id,
        existing_attempt.user_id,
        ProctoredExamStudentAttemptStatus.started
    )

    return existing_attempt.id


def stop_exam_attempt(exam_id, user_id):
    """
    Marks the exam attempt as completed (sets the completed_at field and updates the record)
    """
    return update_attempt_status(exam_id, user_id, ProctoredExamStudentAttemptStatus.ready_to_submit)


def mark_exam_attempt_timeout(exam_id, user_id):
    """
    Marks the exam attempt as timed_out
    """
    return update_attempt_status(exam_id, user_id, ProctoredExamStudentAttemptStatus.timed_out)


def mark_exam_attempt_as_ready(exam_id, user_id):
    """
    Marks the exam attemp as ready to start
    """
    return update_attempt_status(exam_id, user_id, ProctoredExamStudentAttemptStatus.ready_to_start)


def update_attempt_status(exam_id, user_id, to_status, raise_if_not_found=True, cascade_effects=True):
    """
    Internal helper to handle state transitions of attempt status
    """

    log_msg = (
        'Updating attempt status for exam_id {exam_id} '
        'for user_id {user_id} to status {to_status}'.format(
            exam_id=exam_id, user_id=user_id, to_status=to_status
        )
    )
    log.info(log_msg)

    # In some configuration we may treat timeouts the same
    # as the user saying he/she wises to submit the exam
    alias_timeout = (
        to_status == ProctoredExamStudentAttemptStatus.timed_out and
        not settings.PROCTORING_SETTINGS.get('ALLOW_TIMED_OUT_STATE', False)
    )
    if alias_timeout:
        to_status = ProctoredExamStudentAttemptStatus.submitted

    exam_attempt_obj = ProctoredExamStudentAttempt.objects.get_exam_attempt(exam_id, user_id)
    if exam_attempt_obj is None:
        if raise_if_not_found:
            raise StudentExamAttemptDoesNotExistsException('Error. Trying to look up an exam that does not exist.')
        else:
            return

    #
    # don't allow state transitions from a completed state to an incomplete state
    # if a re-attempt is desired then the current attempt must be deleted
    #
    in_completed_status = ProctoredExamStudentAttemptStatus.is_completed_status(exam_attempt_obj.status)
    to_incompleted_status = ProctoredExamStudentAttemptStatus.is_incomplete_status(to_status)

    if in_completed_status and to_incompleted_status:
        err_msg = (
            'A status transition from {from_status} to {to_status} was attempted '
            'on exam_id {exam_id} for user_id {user_id}. This is not '
            'allowed!'.format(
                from_status=exam_attempt_obj.status,
                to_status=to_status,
                exam_id=exam_id,
                user_id=user_id
            )
        )
        raise ProctoredExamIllegalStatusTransition(err_msg)

    # special case logic, if we are in a completed status we shouldn't allow
    # for a transition to 'Error' state
    if in_completed_status and to_status == ProctoredExamStudentAttemptStatus.error:
        err_msg = (
            'A status transition from {from_status} to {to_status} was attempted '
            'on exam_id {exam_id} for user_id {user_id}. This is not '
            'allowed!'.format(
                from_status=exam_attempt_obj.status,
                to_status=to_status,
                exam_id=exam_id,
                user_id=user_id
            )
        )
        raise ProctoredExamIllegalStatusTransition(err_msg)

    # OK, state transition is fine, we can proceed
    exam_attempt_obj.status = to_status
    exam_attempt_obj.save()

    # see if the status transition this changes credit requirement status
    if ProctoredExamStudentAttemptStatus.needs_credit_status_update(to_status):

        # trigger credit workflow, as needed
        credit_service = get_runtime_service('credit')

        exam = get_exam_by_id(exam_id)
        if to_status == ProctoredExamStudentAttemptStatus.verified:
            verification = 'satisfied'
        elif to_status == ProctoredExamStudentAttemptStatus.submitted:
            verification = 'submitted'
        else:
            verification = 'failed'

        log_msg = (
            'Calling set_credit_requirement_status for '
            'user_id {user_id} on {course_id} for '
            'content_id {content_id}. Status: {status}'.format(
                user_id=exam_attempt_obj.user_id,
                course_id=exam['course_id'],
                content_id=exam_attempt_obj.proctored_exam.content_id,
                status=verification
            )
        )
        log.info(log_msg)

        credit_service.set_credit_requirement_status(
            user_id=exam_attempt_obj.user_id,
            course_key_or_id=exam['course_id'],
            req_namespace='proctored_exam',
            req_name=exam_attempt_obj.proctored_exam.content_id,
            status=verification
        )

    if cascade_effects and ProctoredExamStudentAttemptStatus.is_a_cascadable_failure(to_status):
        if to_status == ProctoredExamStudentAttemptStatus.declined:
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
        _exams = ProctoredExam.get_all_exams_for_course(
            exam_attempt_obj.proctored_exam.course_id,
            active_only=True
        )

        # we just want other exams which are proctored and are not practice
        exams = [
            exam
            for exam in _exams
            if (
                exam.content_id != exam_attempt_obj.proctored_exam.content_id and
                exam.is_proctored and not exam.is_practice_exam
            )
        ]

        for exam in exams:
            # see if there was an attempt on those other exams already
            attempt = get_exam_attempt(exam.id, user_id)
            if attempt and ProctoredExamStudentAttemptStatus.is_completed_status(attempt['status']):
                # don't touch any completed statuses
                # we won't revoke those
                continue

            if not attempt:
                create_exam_attempt(exam.id, user_id, taking_as_proctored=False)

            # update any new or existing status to declined
            update_attempt_status(
                exam.id,
                user_id,
                ProctoredExamStudentAttemptStatus.declined,
                cascade_effects=False
            )

    if to_status == ProctoredExamStudentAttemptStatus.submitted:
        # also mark the exam attempt completed_at timestamp
        # after we submit the attempt
        exam_attempt_obj.completed_at = datetime.now(pytz.UTC)
        exam_attempt_obj.save()

    # if we have transitioned to started and haven't set our
    # started_at timestamp, do so now
    add_start_time = (
        to_status == ProctoredExamStudentAttemptStatus.started and
        not exam_attempt_obj.started_at
    )
    if add_start_time:
        exam_attempt_obj.started_at = datetime.now(pytz.UTC)
        exam_attempt_obj.save()

    # email will be send when the exam is proctored and not practice exam
    # and the status is verified, submitted or rejected
    should_send_status_email = (
        exam_attempt_obj.taking_as_proctored and
        not exam_attempt_obj.is_sample_attempt and
        ProctoredExamStudentAttemptStatus.needs_status_change_email(exam_attempt_obj.status)
    )
    if should_send_status_email:
        # trigger credit workflow, as needed
        credit_service = get_runtime_service('credit')

        # call service to get course name.
        credit_state = credit_service.get_credit_state(
            exam_attempt_obj.user_id,
            exam_attempt_obj.proctored_exam.course_id,
            return_course_name=True
        )

        send_proctoring_attempt_status_email(
            exam_attempt_obj,
            credit_state.get('course_name', _('your course'))
        )

    return exam_attempt_obj.id


def send_proctoring_attempt_status_email(exam_attempt_obj, course_name):
    """
    Sends an email about change in proctoring attempt status.
    """

    course_info_url = ''
    email_template = loader.get_template('emails/proctoring_attempt_status_email.html')
    try:
        course_info_url = reverse('courseware.views.course_info', args=[exam_attempt_obj.proctored_exam.course_id])
    except NoReverseMatch:
        # we are allowing a failure here since we can't guarantee
        # that we are running in-proc with the edx-platform LMS
        # (for example unit tests)
        pass

    scheme = 'https' if getattr(settings, 'HTTPS', 'on') == 'on' else 'http'
    course_url = '{scheme}://{site_name}{course_info_url}'.format(
        scheme=scheme,
        site_name=constants.SITE_NAME,
        course_info_url=course_info_url
    )

    body = email_template.render(
        Context({
            'course_url': course_url,
            'course_name': course_name,
            'exam_name': exam_attempt_obj.proctored_exam.exam_name,
            'status': ProctoredExamStudentAttemptStatus.get_status_alias(exam_attempt_obj.status),
            'platform': constants.PLATFORM_NAME,
            'contact_email': constants.CONTACT_EMAIL,
        })
    )

    subject = (
        _('Proctoring Session Results Update for {course_name} {exam_name}').format(
            course_name=course_name,
            exam_name=exam_attempt_obj.proctored_exam.exam_name
        )
    )

    email = EmailMessage(
        body=body,
        from_email=constants.FROM_EMAIL,
        to=[exam_attempt_obj.user.email],
        subject=subject
    )
    email.content_subtype = "html"
    email.send()


def remove_exam_attempt(attempt_id):
    """
    Removes an exam attempt given the attempt id.
    """

    log_msg = (
        'Removing exam attempt {attempt_id}'.format(attempt_id=attempt_id)
    )
    log.info(log_msg)

    existing_attempt = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_id(attempt_id)
    if not existing_attempt:
        err_msg = (
            'Cannot remove attempt for attempt_id = {attempt_id} '
            'because it does not exist!'
        ).format(attempt_id=attempt_id)

        raise StudentExamAttemptDoesNotExistsException(err_msg)

    username = existing_attempt.user.username
    user_id = existing_attempt.user.id
    course_id = existing_attempt.proctored_exam.course_id
    content_id = existing_attempt.proctored_exam.content_id
    to_status = existing_attempt.status

    existing_attempt.delete_exam_attempt()
    instructor_service = get_runtime_service('instructor')

    if instructor_service:
        instructor_service.delete_student_attempt(username, course_id, content_id)

    # see if the status transition this changes credit requirement status
    if ProctoredExamStudentAttemptStatus.needs_credit_status_update(to_status):
        # trigger credit workflow, as needed
        credit_service = get_runtime_service('credit')
        credit_service.remove_credit_requirement_status(
            user_id=user_id,
            course_key_or_id=course_id,
            req_namespace=u'proctored_exam',
            req_name=content_id
        )


def get_all_exams_for_course(course_id):
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
    exams = ProctoredExam.get_all_exams_for_course(course_id)

    return [ProctoredExamSerializer(proctored_exam).data for proctored_exam in exams]


def get_all_exam_attempts(course_id):
    """
    Returns all the exam attempts for the course id.
    """
    exam_attempts = ProctoredExamStudentAttempt.objects.get_all_exam_attempts(course_id)
    return [ProctoredExamStudentAttemptSerializer(active_exam).data for active_exam in exam_attempts]


def get_filtered_exam_attempts(course_id, search_by):
    """
    returns all exam attempts for a course id filtered by  the search_by string in user names and emails.
    """
    exam_attempts = ProctoredExamStudentAttempt.objects.get_filtered_exam_attempts(course_id, search_by)
    return [ProctoredExamStudentAttemptSerializer(active_exam).data for active_exam in exam_attempts]


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


def _check_credit_eligibility(credit_state):
    """
    Inspects the credit_state payload which
    reflects status of all credit requirements
    and returns True if all pre-requisites have
    been passed and False if otherwise
    """

    # check both conditions
    return (
        _check_eligibility_of_enrollment_mode(credit_state) and
        _check_eligibility_of_prerequisites(credit_state)
    )


def _check_eligibility_of_enrollment_mode(credit_state):
    """
    Inspects that the enrollment mode of the user
    is valid for proctoring
    """

    # Allow only the verified students to take the exam as a proctored exam
    # Also make an exception for the honor students to take the "practice exam" as a proctored exam.
    # For the rest of the enrollment modes, None is returned which shows the exam content
    # to the student rather than the proctoring prompt.
    return credit_state['enrollment_mode'] == 'verified'


def _check_eligibility_of_prerequisites(credit_state):
    """
    Inspects that the user has completed all prerequiste
    steps required to be allowed to take a proctored exam
    """

    # also, if there are in-course reverifications requirements
    # then make sure those has a 'satisfied' status
    for requirement in credit_state['credit_requirement_status']:
        if requirement['namespace'] == 'reverification':
            if requirement['status'] == 'failed':
                return False

    return True


STATUS_SUMMARY_MAP = {
    '_default': {
        'short_description': _('Taking As Proctored Exam'),
        'suggested_icon': 'fa-pencil-square-o',
        'in_completed_state': False
    },
    ProctoredExamStudentAttemptStatus.eligible: {
        'short_description': _('Proctored Option Available'),
        'suggested_icon': 'fa-pencil-square-o',
        'in_completed_state': False
    },
    ProctoredExamStudentAttemptStatus.declined: {
        'short_description': _('Taking As Open Exam'),
        'suggested_icon': 'fa-pencil-square-o',
        'in_completed_state': False
    },
    ProctoredExamStudentAttemptStatus.submitted: {
        'short_description': _('Pending Session Review'),
        'suggested_icon': 'fa-spinner fa-spin',
        'in_completed_state': True
    },
    ProctoredExamStudentAttemptStatus.verified: {
        'short_description': _('Passed Proctoring'),
        'suggested_icon': 'fa-check',
        'in_completed_state': True
    },
    ProctoredExamStudentAttemptStatus.rejected: {
        'short_description': _('Failed Proctoring'),
        'suggested_icon': 'fa-exclamation-triangle',
        'in_completed_state': True
    },
    ProctoredExamStudentAttemptStatus.error: {
        'short_description': _('Failed Proctoring'),
        'suggested_icon': 'fa-exclamation-triangle',
        'in_completed_state': True
    }
}


PRACTICE_STATUS_SUMMARY_MAP = {
    '_default': {
        'short_description': _('Ungraded Practice Exam'),
        'suggested_icon': '',
        'in_completed_state': False
    },
    ProctoredExamStudentAttemptStatus.submitted: {
        'short_description': _('Practice Exam Completed'),
        'suggested_icon': 'fa-check',
        'in_completed_state': True
    },
    ProctoredExamStudentAttemptStatus.error: {
        'short_description': _('Practice Exam Failed'),
        'suggested_icon': 'fa-exclamation-triangle',
        'in_completed_state': True
    }
}

TIMED_EXAM_STATUS_SUMMARY_MAP = {
    '_default': {
        'short_description': _('Timed Exam'),
        'suggested_icon': 'fa-clock-o',
        'in_completed_state': False
    }
}


def get_attempt_status_summary(user_id, course_id, content_id):
    """
    Returns a summary about the status of the attempt for the user
    in the course_id and content_id

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
    except ProctoredExamNotFoundException, ex:
        # this really shouldn't happen, but log it at least
        log.exception(ex)
        return None

    # check if the exam is not proctored
    if not exam['is_proctored']:
        return TIMED_EXAM_STATUS_SUMMARY_MAP['_default']

    # let's check credit eligibility
    credit_service = get_runtime_service('credit')
    # practice exams always has an attempt status regardless of
    # eligibility
    if credit_service and not exam['is_practice_exam']:
        credit_state = credit_service.get_credit_state(user_id, unicode(course_id))
        if not _check_credit_eligibility(credit_state):
            return None

    attempt = get_exam_attempt(exam['id'], user_id)
    status = attempt['status'] if attempt else ProctoredExamStudentAttemptStatus.eligible

    status_map = STATUS_SUMMARY_MAP if not exam['is_practice_exam'] else PRACTICE_STATUS_SUMMARY_MAP

    summary = None
    if status in status_map:
        summary = status_map[status]
    else:
        summary = status_map['_default']

    summary.update({"status": status})

    return summary


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


def _get_timed_exam_view(exam, context, exam_id, user_id, course_id):
    """
    Returns a rendered view for the Timed Exams
    """
    student_view_template = None
    attempt = get_exam_attempt(exam_id, user_id)

    attempt_status = attempt['status'] if attempt else None

    if not attempt_status:
        student_view_template = 'timed_exam/entrance.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.started:
        # when we're taking the exam we should override the view
        return None
    elif attempt_status == ProctoredExamStudentAttemptStatus.ready_to_submit:
        student_view_template = 'timed_exam/ready_to_submit.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.submitted:
        student_view_template = 'timed_exam/submitted.html'

    if student_view_template:
        template = loader.get_template(student_view_template)
        django_context = Context(context)

        allowed_time_limit_mins = attempt['allowed_time_limit_mins'] if attempt else None

        if not allowed_time_limit_mins:
            # no existing attempt, so compute the user's allowed
            # time limit, including any accommodations

            allowed_time_limit_mins = exam['time_limit_mins']
            allowance = ProctoredExamStudentAllowance.get_allowance_for_user(
                exam_id,
                user_id,
                "Additional time (minutes)"
            )

            if allowance:
                allowed_time_limit_mins += int(allowance.value)

        total_time = humanized_time(allowed_time_limit_mins)
        progress_page_url = ''
        try:
            progress_page_url = reverse(
                'courseware.views.progress',
                args=[course_id]
            )
        except NoReverseMatch:
            # we are allowing a failure here since we can't guarantee
            # that we are running in-proc with the edx-platform LMS
            # (for example unit tests)
            pass

        django_context.update({
            'total_time': total_time,
            'exam_id': exam_id,
            'progress_page_url': progress_page_url,
            'does_time_remain': _does_time_remain(attempt),
            'enter_exam_endpoint': reverse('edx_proctoring.proctored_exam.attempt.collection'),
            'change_state_url': reverse(
                'edx_proctoring.proctored_exam.attempt',
                args=[attempt['id']]
            ) if attempt else '',
        })
        return template.render(django_context)


def _get_proctored_exam_context(exam, attempt, course_id, is_practice_exam=False):
    """
    Common context variables for the Proctored and Practice exams' templates.
    """
    attempt_time = attempt['allowed_time_limit_mins'] if attempt else exam['time_limit_mins']
    total_time = humanized_time(attempt_time)
    progress_page_url = ''
    try:
        progress_page_url = reverse(
            'courseware.views.progress',
            args=[course_id]
        )
    except NoReverseMatch:
        # we are allowing a failure here since we can't guarantee
        # that we are running in-proc with the edx-platform LMS
        # (for example unit tests)
        pass

    return {
        'platform_name': settings.PLATFORM_NAME,
        'total_time': total_time,
        'exam_id': exam['id'],
        'progress_page_url': progress_page_url,
        'is_sample_attempt': is_practice_exam,
        'does_time_remain': _does_time_remain(attempt),
        'enter_exam_endpoint': reverse('edx_proctoring.proctored_exam.attempt.collection'),
        'exam_started_poll_url': reverse(
            'edx_proctoring.proctored_exam.attempt',
            args=[attempt['id']]
        ) if attempt else '',
        'change_state_url': reverse(
            'edx_proctoring.proctored_exam.attempt',
            args=[attempt['id']]
        ) if attempt else '',
        'link_urls': settings.PROCTORING_SETTINGS.get('LINK_URLS', {}),
    }


def _get_practice_exam_view(exam, context, exam_id, user_id, course_id):
    """
    Returns a rendered view for the practice Exams
    """
    student_view_template = None

    attempt = get_exam_attempt(exam_id, user_id)

    attempt_status = attempt['status'] if attempt else None

    if not attempt_status:
        student_view_template = 'practice_exam/entrance.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.started:
        # when we're taking the exam we should override the view
        return None
    elif attempt_status == ProctoredExamStudentAttemptStatus.created:
        provider = get_backend_provider()
        student_view_template = 'proctored_exam/instructions.html'
        context.update({
            'exam_code': attempt['attempt_code'],
            'software_download_url': provider.get_software_download_url(),
        })
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
        django_context = Context(context)
        django_context.update(_get_proctored_exam_context(exam, attempt, course_id, is_practice_exam=True))
        return template.render(django_context)


def _get_proctored_exam_view(exam, context, exam_id, user_id, course_id):
    """
    Returns a rendered view for the Proctored Exams
    """
    student_view_template = None

    # see if only 'verified' track students should see this *except* if it is a practice exam
    check_mode_and_eligibility = (
        settings.PROCTORING_SETTINGS.get('MUST_BE_VERIFIED_TRACK', True) and
        'credit_state' in context and
        context['credit_state'] and not
        exam['is_practice_exam']
    )

    attempt = None
    if check_mode_and_eligibility:
        credit_state = context['credit_state']

        has_mode = _check_eligibility_of_enrollment_mode(credit_state)
        has_prerequisites = False
        if has_mode:
            has_prerequisites = _check_eligibility_of_prerequisites(credit_state)

        # see if the user has passed all pre-requisite credit eligibility
        # checks, otherwise just show the user the exam unproctored
        if not has_mode or not has_prerequisites:
            # if we are in the right mode and if we don't have
            # pre-requisites, then we implicitly decline the exam
            if has_mode:
                attempt = get_exam_attempt(exam_id, user_id)
                if not attempt:
                    # user hasn't a record of attempt, create one now
                    # so we can mark it as declined
                    create_exam_attempt(exam_id, user_id)

                update_attempt_status(
                    exam_id,
                    user_id,
                    ProctoredExamStudentAttemptStatus.declined,
                    raise_if_not_found=False
                )

            # don't override context, let the courseware show
            return None
    attempt = get_exam_attempt(exam_id, user_id)

    attempt_status = attempt['status'] if attempt else None

    # if user has declined the attempt, then we don't show the
    # proctored exam
    if attempt_status == ProctoredExamStudentAttemptStatus.declined:
        return None

    if not attempt_status:
        student_view_template = 'proctored_exam/entrance.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.started:
        # when we're taking the exam we should override the view
        return None
    elif attempt_status == ProctoredExamStudentAttemptStatus.created:
        provider = get_backend_provider()
        student_view_template = 'proctored_exam/instructions.html'
        context.update({
            'exam_code': attempt['attempt_code'],
            'software_download_url': provider.get_software_download_url(),
        })
    elif attempt_status == ProctoredExamStudentAttemptStatus.ready_to_start:
        student_view_template = 'proctored_exam/ready_to_start.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.error:
        student_view_template = 'proctored_exam/error.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.timed_out:
        raise NotImplementedError('There is no defined rendering for ProctoredExamStudentAttemptStatus.timed_out!')
    elif attempt_status == ProctoredExamStudentAttemptStatus.submitted:
        student_view_template = 'proctored_exam/submitted.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.verified:
        student_view_template = 'proctored_exam/verified.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.rejected:
        student_view_template = 'proctored_exam/rejected.html'
    elif attempt_status == ProctoredExamStudentAttemptStatus.ready_to_submit:
        student_view_template = 'proctored_exam/ready_to_submit.html'

    if student_view_template:
        template = loader.get_template(student_view_template)
        django_context = Context(context)
        django_context.update(_get_proctored_exam_context(exam, attempt, course_id))
        return template.render(django_context)


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

    exam_id = None
    try:
        exam = get_exam_by_content_id(course_id, content_id)
        if not exam['is_active']:
            # Exam is no longer active
            # Note, we don't hard delete exams since we need to retain
            # data
            return None

        exam_id = exam['id']
    except ProctoredExamNotFoundException:
        # This really shouldn't happen
        # as Studio will be setting this up
        exam_id = create_exam(
            course_id=course_id,
            content_id=unicode(content_id),
            exam_name=context['display_name'],
            time_limit_mins=context['default_time_limit_mins'],
            is_proctored=context.get('is_proctored', False),
            is_practice_exam=context.get('is_practice_exam', False)
        )
        exam = get_exam_by_content_id(course_id, content_id)

    is_practice_exam = exam['is_proctored'] and exam['is_practice_exam']
    is_proctored_exam = exam['is_proctored'] and not exam['is_practice_exam']
    is_timed_exam = not exam['is_proctored'] and not exam['is_practice_exam']

    if is_timed_exam:
        return _get_timed_exam_view(exam, context, exam_id, user_id, course_id)
    elif is_practice_exam:
        return _get_practice_exam_view(exam, context, exam_id, user_id, course_id)
    elif is_proctored_exam:
        return _get_proctored_exam_view(exam, context, exam_id, user_id, course_id)

    return None
