# pylint: disable=too-many-branches
# pylint: disable=too-many-statements

"""
In-Proc API (aka Library) for the edx_proctoring subsystem. This is not to be confused with a HTTP REST
API which is in the views.py file, per edX coding standards
"""
import pytz
import uuid
from datetime import datetime, timedelta
from django.conf import settings
from django.template import Context, loader
from django.core.urlresolvers import reverse, NoReverseMatch

from edx_proctoring.exceptions import (
    ProctoredExamAlreadyExists,
    ProctoredExamNotFoundException,
    StudentExamAttemptAlreadyExistsException,
    StudentExamAttemptDoesNotExistsException,
    StudentExamAttemptedAlreadyStarted,
)
from edx_proctoring.models import (
    ProctoredExam,
    ProctoredExamStudentAllowance,
    ProctoredExamStudentAttempt,
    ProctoredExamStudentAttemptStatus,
)
from edx_proctoring.serializers import (
    ProctoredExamSerializer,
    ProctoredExamStudentAttemptSerializer,
    ProctoredExamStudentAllowanceSerializer,
)
from edx_proctoring.utils import humanized_time

from edx_proctoring.backends import get_backend_provider
from edx_proctoring.runtime import get_runtime_service


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
    return proctored_exam.id


def update_exam(exam_id, exam_name=None, time_limit_mins=None,
                is_proctored=None, is_practice_exam=None, external_id=None, is_active=None):
    """
    Given a Django ORM id, update the existing record, otherwise raise exception if not found.
    If an argument is not passed in, then do not change it's current value.

    Returns: id
    """
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
    student_allowance = ProctoredExamStudentAllowance.get_allowance_for_user(exam_id, user_id, key)
    if student_allowance is not None:
        student_allowance.delete()


def _update_exam_attempt_status(attempt):
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
        attempt.get('status') == ProctoredExamStudentAttemptStatus.started
    )
    if has_started_exam:
        now_utc = datetime.now(pytz.UTC)
        expires_at = attempt['started_at'] + timedelta(minutes=attempt['allowed_time_limit_mins'])
        has_time_expired = now_utc > expires_at

        if has_time_expired:
            exam_attempt_obj = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_id(attempt['id'])
            exam_attempt_obj.status = ProctoredExamStudentAttemptStatus.timed_out
            exam_attempt_obj.save()
            attempt = ProctoredExamStudentAttemptSerializer(exam_attempt_obj).data

    return attempt


def _get_exam_attempt(exam_attempt_obj):
    """
    Helper method to commonalize the two query patterns
    """
    serialized_attempt_obj = ProctoredExamStudentAttemptSerializer(exam_attempt_obj)
    attempt = serialized_attempt_obj.data if exam_attempt_obj else None
    attempt = _update_exam_attempt_status(attempt)

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


def update_exam_attempt(attempt_id, **kwargs):
    """
    update exam_attempt
    """
    exam_attempt_obj = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_id(attempt_id)
    for key, value in kwargs.items():
        setattr(exam_attempt_obj, key, value)
    exam_attempt_obj.save()


def get_exam_attempt_by_code(attempt_code):
    """
    Signals the beginning of an exam attempt when we only have
    an attempt code
    """

    exam_attempt_obj = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_code(attempt_code)
    serialized_attempt_obj = ProctoredExamStudentAttemptSerializer(exam_attempt_obj)
    return serialized_attempt_obj.data if exam_attempt_obj else None


def create_exam_attempt(exam_id, user_id, taking_as_proctored=False):
    """
    Creates an exam attempt for user_id against exam_id. There should only be
    one exam_attempt per user per exam. Multiple attempts by user will be archived
    in a separate table
    """
    # for now the student is allowed the exam default

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
    allowance = ProctoredExamStudentAllowance.get_allowance_for_user(
        exam_id,
        user_id,
        "Additional time (minutes)"
    )

    if allowance:
        allowance_extra_mins = int(allowance.value)
        allowed_time_limit_mins += allowance_extra_mins

    attempt_code = unicode(uuid.uuid4()).upper()

    external_id = None
    if taking_as_proctored:
        callback_url = 'http://{hostname}{path}'.format(
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

        # now call into the backend provider to register exam attempt
        external_id = get_backend_provider().register_exam_attempt(
            exam,
            context={
                'time_limit_mins': allowed_time_limit_mins,
                'attempt_code': attempt_code,
                'is_sample_attempt': exam['is_practice_exam'],
                'callback_url': callback_url,
                'full_name': full_name,
            }
        )

    attempt = ProctoredExamStudentAttempt.create_exam_attempt(
        exam_id,
        user_id,
        '',  # student name is TBD
        allowed_time_limit_mins,
        attempt_code,
        taking_as_proctored,
        exam['is_practice_exam'],
        external_id
    )
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

    if existing_attempt.started_at:
        # cannot restart an attempt
        err_msg = (
            'Cannot start exam attempt for exam_id = {exam_id} '
            'and user_id = {user_id} because it has already started!'
        ).format(exam_id=existing_attempt.proctored_exam.id, user_id=existing_attempt.user_id)

        raise StudentExamAttemptedAlreadyStarted(err_msg)

    existing_attempt.start_exam_attempt()

    return existing_attempt.id


def stop_exam_attempt(exam_id, user_id):
    """
    Marks the exam attempt as completed (sets the completed_at field and updates the record)
    """
    exam_attempt_obj = ProctoredExamStudentAttempt.objects.get_exam_attempt(exam_id, user_id)
    if exam_attempt_obj is None:
        raise StudentExamAttemptDoesNotExistsException('Error. Trying to stop an exam that does not exist.')
    else:
        exam_attempt_obj.completed_at = datetime.now(pytz.UTC)
        exam_attempt_obj.status = ProctoredExamStudentAttemptStatus.completed
        exam_attempt_obj.save()
        return exam_attempt_obj.id


def mark_exam_attempt_timeout(exam_id, user_id):
    """
    Marks the exam attempt as timed_out
    """
    exam_attempt_obj = ProctoredExamStudentAttempt.objects.get_exam_attempt(exam_id, user_id)
    if exam_attempt_obj is None:
        raise StudentExamAttemptDoesNotExistsException('Error. Trying to time out an exam that does not exist.')
    else:
        exam_attempt_obj.status = ProctoredExamStudentAttemptStatus.timed_out
        exam_attempt_obj.save()
        return exam_attempt_obj.id


def mark_exam_attempt_as_ready(exam_id, user_id):
    """
    Marks the exam attemp as ready to start
    """

    exam_attempt_obj = ProctoredExamStudentAttempt.objects.get_exam_attempt(exam_id, user_id)
    if exam_attempt_obj is None:
        raise StudentExamAttemptDoesNotExistsException('Error. Trying to time out an exam that does not exist.')
    else:
        exam_attempt_obj.status = ProctoredExamStudentAttemptStatus.ready_to_start
        exam_attempt_obj.save()
        return exam_attempt_obj.id


def remove_exam_attempt(attempt_id):
    """
    Removes an exam attempt given the attempt id.
    """

    existing_attempt = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_id(attempt_id)

    if not existing_attempt:
        err_msg = (
            'Cannot remove attempt for attempt_id = {attempt_id} '
            'because it does not exist!'
        ).format(attempt_id=attempt_id)

        raise StudentExamAttemptDoesNotExistsException(err_msg)

    existing_attempt.delete_exam_attempt()


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

    student_view_template = None

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

    is_proctored = exam['is_proctored']

    # see if only 'verified' track students should see this *except* if it is a practice exam
    check_mode = (
        settings.PROCTORING_SETTINGS.get('MUST_BE_VERIFIED_TRACK', True) and
        'credit_state' in context and
        context['credit_state'] and not
        exam['is_practice_exam']
    )

    if check_mode:
        # Allow only the verified students to take the exam as a proctored exam
        # Also make an exception for the honor students to take the "practice exam" as a proctored exam.
        # For the rest of the enrollment modes, None is returned which shows the exam content
        # to the student rather than the proctoring prompt.

        if context['credit_state']['enrollment_mode'] != 'verified':
            return None

    attempt = get_exam_attempt(exam_id, user_id)
    has_started_exam = attempt and attempt.get('started_at')
    has_time_expired = False
    if has_started_exam:
        if attempt.get('status') == 'error':
            student_view_template = 'proctoring/seq_proctored_exam_error.html'
        else:
            now_utc = datetime.now(pytz.UTC)
            expires_at = attempt['started_at'] + timedelta(minutes=attempt['allowed_time_limit_mins'])
            has_time_expired = now_utc > expires_at

    # make sure the attempt has been marked as timed_out, if need be
    if has_time_expired and attempt['status'] == ProctoredExamStudentAttemptStatus.started:
        mark_exam_attempt_timeout(exam_id, user_id)
        # refetch since we are transitioning state
        attempt = get_exam_attempt(exam_id, user_id)

    if not has_started_exam:
        # determine whether to show a timed exam only entrance screen
        # or a screen regarding proctoring

        if is_proctored:
            if not attempt:
                if exam['is_practice_exam']:
                    student_view_template = 'proctoring/seq_proctored_practice_exam_entrance.html'
                else:
                    student_view_template = 'proctoring/seq_proctored_exam_entrance.html'
            else:
                provider = get_backend_provider()
                student_view_template = 'proctoring/seq_proctored_exam_instructions.html'
                context.update({
                    'exam_code': attempt['attempt_code'],
                    'software_download_url': provider.get_software_download_url(),
                })
        else:
            student_view_template = 'proctoring/seq_timed_exam_entrance.html'
    elif attempt['status'] == ProctoredExamStudentAttemptStatus.timed_out:
        student_view_template = 'proctoring/seq_timed_exam_expired.html'
    elif attempt['status'] == ProctoredExamStudentAttemptStatus.submitted:
        if attempt['is_sample_attempt']:
            student_view_template = 'proctoring/seq_proctored_practice_exam_submitted.html'
        else:
            student_view_template = 'proctoring/seq_proctored_exam_submitted.html'
    elif attempt['status'] == ProctoredExamStudentAttemptStatus.verified:
        student_view_template = 'proctoring/seq_proctored_exam_verified.html'
    elif attempt['status'] == ProctoredExamStudentAttemptStatus.rejected:
        student_view_template = 'proctoring/seq_proctored_exam_rejected.html'
    elif attempt['status'] == ProctoredExamStudentAttemptStatus.completed:
        if is_proctored:
            student_view_template = 'proctoring/seq_proctored_exam_completed.html'
        else:
            student_view_template = 'proctoring/seq_timed_exam_completed.html'

    if student_view_template:
        template = loader.get_template(student_view_template)
        django_context = Context(context)
        total_time = humanized_time(context['default_time_limit_mins'])
        progress_page_url = ''
        try:
            progress_page_url = reverse(
                'courseware.views.progress',
                args=[course_id]
            )
        except NoReverseMatch:
            pass

        django_context.update({
            'platform_name': settings.PLATFORM_NAME,
            'total_time': total_time,
            'exam_id': exam_id,
            'progress_page_url': progress_page_url,
            'is_sample_attempt': attempt['is_sample_attempt'] if attempt else False,
            'enter_exam_endpoint': reverse('edx_proctoring.proctored_exam.attempt.collection'),
            'exam_started_poll_url': reverse(
                'edx_proctoring.proctored_exam.attempt',
                args=[attempt['id']]
            ) if attempt else ''
        })
        return template.render(django_context)

    return None
