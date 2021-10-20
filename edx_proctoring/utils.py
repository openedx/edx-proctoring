"""
Helpers for the HTTP APIs
"""

import base64
import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone

import pytz
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers.algorithms import AES
from cryptography.hazmat.primitives.ciphers.modes import CBC
from cryptography.hazmat.primitives.padding import PKCS7
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from edx_when import api as when_api
from eventtracking import tracker
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey, UsageKey
from opaque_keys.edx.locator import BlockUsageLocator
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from django.conf import settings
from django.urls import reverse
from django.utils.translation import ugettext as _

from edx_proctoring.models import ProctoredExamStudentAttempt
from edx_proctoring.runtime import get_runtime_service
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus

log = logging.getLogger(__name__)

AES_BLOCK_SIZE_BYTES = int(AES.block_size / 8)


class AuthenticatedAPIView(APIView):
    """
    Authenticate APi View.
    """
    authentication_classes = (SessionAuthentication, JwtAuthentication)
    permission_classes = (IsAuthenticated,)


def get_time_remaining_for_attempt(attempt):
    """
    Returns the remaining time (in seconds) on an attempt
    """

    # returns 0 if the attempt has not been started yet.
    if attempt['started_at'] is None:
        return 0

    # need to adjust for allowances
    expires_at = attempt['started_at'] + timedelta(minutes=attempt['allowed_time_limit_mins'])

    now_utc = datetime.now(pytz.UTC)

    if expires_at > now_utc:
        time_remaining_seconds = (expires_at - now_utc).total_seconds()
    else:
        time_remaining_seconds = 0

    return time_remaining_seconds


def humanized_time(time_in_minutes):
    """
    Converts the given value in minutes to a more human readable format
    1 -> 1 Minute
    2 -> 2 Minutes
    60 -> 1 hour
    90 -> 1 hour and 30 Minutes
    120 -> 2 hours
    """
    hours = int(time_in_minutes / 60)
    minutes = time_in_minutes % 60

    hours_present = False
    if hours == 0:
        hours_present = False
        template = ""
    elif hours == 1:
        template = _("{num_of_hours} hour")
        hours_present = True
    elif hours >= 2:
        template = _("{num_of_hours} hours")
        hours_present = True
    else:
        template = "error"

    if template != "error":
        if minutes == 0:
            if not hours_present:
                template = _("{num_of_minutes} minutes")
        elif minutes == 1:
            if hours_present:
                template += _(" and {num_of_minutes} minute")
            else:
                template += _("{num_of_minutes} minute")
        else:
            if hours_present:
                template += _(" and {num_of_minutes} minutes")
            else:
                template += _("{num_of_minutes} minutes")

    human_time = template.format(num_of_hours=hours, num_of_minutes=minutes)
    return human_time


def locate_attempt_by_attempt_code(attempt_code):
    """
    Helper method to look up an attempt by attempt_code. This can be either in
    the ProctoredExamStudentAttempt *OR* ProctoredExamStudentAttemptHistory tables
    we will return a tuple of (attempt, is_archived_attempt)
    """
    attempt_obj = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_code(attempt_code)
    if attempt_obj:
        return attempt_obj, False

    # retrieve attempt from history
    attempt_obj = ProctoredExamStudentAttempt.get_historic_attempt_by_code(attempt_code)

    if attempt_obj:
        return attempt_obj, True

    # still can't find, error out
    log.error(
        'Could not locate attempt_code=%(attempt_code)s',
        {
            'attempt_code': attempt_code,
        }
    )
    return None, None


def emit_event(exam, event_short_name, attempt=None, override_data=None):
    """
    Helper method to emit an analytics event
    """

    exam_type = (
        'timed' if not exam['is_proctored'] else
        ('practice' if exam['is_practice_exam'] else 'proctored')
    )

    # establish baseline schema for event 'context'
    context = {
        'course_id': exam['course_id']
    }

    # establish baseline schema for event 'data'
    data = {
        'exam_id': exam['id'],
        'exam_content_id': exam['content_id'],
        'exam_name': exam['exam_name'],
        'exam_default_time_limit_mins': exam['time_limit_mins'],
        'exam_is_proctored': exam['is_proctored'],
        'exam_is_practice_exam': exam['is_practice_exam'],
        'exam_is_active': exam['is_active']
    }

    if attempt:
        # if an attempt is passed in then use that to add additional baseline
        # schema elements

        # let's compute the relative time we're firing the event
        # compared to the start time, if the attempt has already started.
        # This can be used to determine how far into an attempt a given
        # event occured (e.g. "time to complete exam")
        attempt_event_elapsed_time_secs = (
            (datetime.now(pytz.UTC) - attempt['started_at']).total_seconds() if attempt['started_at'] else
            None
        )

        attempt_data = {
            'attempt_id': attempt['id'],
            'attempt_user_id': attempt['user']['id'],
            'attempt_started_at': attempt['started_at'],
            'attempt_completed_at': attempt['completed_at'],
            'attempt_code': attempt['attempt_code'],
            'attempt_allowed_time_limit_mins': attempt['allowed_time_limit_mins'],
            'attempt_status': attempt['status'],
            'attempt_event_elapsed_time_secs': attempt_event_elapsed_time_secs
        }
        data.update(attempt_data)
        name = '.'.join(['edx', 'special_exam', exam_type, 'attempt', event_short_name])
    else:
        name = '.'.join(['edx', 'special_exam', exam_type, event_short_name])

    # allow caller to override event data
    if override_data:
        data.update(override_data)

    _emit_event(name, context, data)


def _emit_event(name, context, data):
    """
    Do the actual integration into the event-tracker
    """

    try:
        if context:
            # try to parse out the org_id from the course_id
            if 'course_id' in context:
                try:
                    course_key = CourseKey.from_string(context['course_id'])
                    context['org_id'] = course_key.org
                except InvalidKeyError:
                    # leave org_id blank
                    pass

            with tracker.get_tracker().context(name, context):
                tracker.emit(name, data)
        else:
            # if None is passed in then we don't construct the 'with' context stack
            tracker.emit(name, data)
    except KeyError:
        # This happens when a default tracker has not been registered by the host application
        # aka LMS. This is normal when running unit tests in isolation.
        log.warning(
            'Analytics tracker not properly configured. '
            'If this message appears in a production environment, please investigate'
        )


def obscured_user_id(user_id, *extra):
    """
    Obscures the user id, returning a sha1 hash
    Any extra information can be added to the hash
    """
    obs_hash = hmac.new(settings.PROCTORING_USER_OBFUSCATION_KEY.encode('ascii'), digestmod=hashlib.sha1)
    obs_hash.update(str(user_id).encode('utf-8'))
    obs_hash.update(b''.join(str(ext).encode('utf-8') for ext in extra))
    return obs_hash.hexdigest()


def has_due_date_passed(due_datetime):
    """
    Return True if due date is lesser than current datetime, otherwise False
    and if due_datetime is None then we don't have to consider the due date for return False
    """
    if due_datetime:
        return due_datetime <= datetime.now(pytz.UTC)
    return False


def get_course_end_date(course_id):
    """
    Return the end date for the given course id
    """
    end_date = None
    dates = when_api.get_dates_for_course(course_id)
    end_dates = list(filter(lambda elem: elem[0][1] == 'end', dates.items()))
    if end_dates and end_dates[0][1]:
        try:
            end_date = end_dates[0][1].replace(tzinfo=timezone.utc)
        except (AttributeError, TypeError):
            log.error('Could not retrieve course end date for course_id=%(course_id)s', {'course_id': course_id})
    return end_date


def has_end_date_passed(course_id):
    """
    Return True if the course end date has passed, otherwise False
    """
    return has_due_date_passed(get_course_end_date(course_id))


def get_exam_due_date(exam, user=None):
    """
    Return the due date for the exam.
    Uses edx_when to lookup the date for the subsection.
    """
    due_date = when_api.get_date_for_block(exam['course_id'], exam['content_id'], 'due', user=user)
    return due_date or exam['due_date']


def verify_and_add_wait_deadline(context, exam, user_id):
    """
    Verify if the wait deadline should be added to template context.

    If the grace period is present and is valid after the exam
    has passed due date, for the given user, add the wait deadline to context. If the due
    date is not present, which happens for self-paced courses, no context
    update will take place.
    """
    exam_due_date = get_exam_due_date(exam, user_id)
    if not (context.get('grace_period', False) and exam_due_date):
        return False
    wait_deadline = exam_due_date + context['grace_period']
    if not has_due_date_passed(wait_deadline):
        context.update(
            {'wait_deadline': wait_deadline.isoformat()}
        )
        return True
    return False


def is_reattempting_exam(from_status, to_status):
    """
    Returns a boolean representing whether or not a user is trying to reattempt an exam.

    Given user's exam is in progress, and he is kicked out due to low bandwidth or
    closes the secure browser. Its expected that the user should not be able to restart
    the exam workflow.
    This behavior is being implemented due to edX's integrity constraints.
    """
    return (
        ProctoredExamStudentAttemptStatus.is_in_progress_status(from_status) and
        ProctoredExamStudentAttemptStatus.is_pre_started_status(to_status)
    )


def get_visibility_check_date(course_schedule, usage_key):
    """
    Utility function to return the date, of which
    we should use to test the learner's visibility to the exam

    Returns one of the following:
        * The due date of the course structure usage_key
        * The course end date
        * The max datetime if no course_end date specified
    """
    visibility_check_date = course_schedule.course_end or pytz.utc.localize(datetime.max)
    exam_schedule_item = course_schedule.sequences.get(usage_key)
    if exam_schedule_item and exam_schedule_item.due:
        visibility_check_date = exam_schedule_item.due

    return visibility_check_date


def get_exam_type(exam, provider):
    """ Helper that returns exam type and humanized name by backend provider and exam params. """
    is_practice_exam = exam['is_proctored'] and exam['is_practice_exam']
    is_timed_exam = not exam['is_proctored'] and not exam['is_practice_exam']

    exam_type, humanized_type = 'proctored', _('a proctored exam')

    if is_timed_exam:
        exam_type, humanized_type = 'timed', _('a timed exam')
    elif is_practice_exam:
        if provider and provider.supports_onboarding:
            exam_type, humanized_type = 'onboarding', _('an onboarding exam')
        else:
            exam_type, humanized_type = 'practice', _('a practice exam')

    return {
        'type': exam_type,
        'humanized_type': humanized_type,
    }


def resolve_exam_url_for_learning_mfe(course_id, content_id):
    """ Helper that builds the url to the exam for the MFE app learning. """
    course_key = CourseKey.from_string(course_id)
    usage_key = UsageKey.from_string(content_id)
    url = f'{settings.LEARNING_MICROFRONTEND_URL}/course/{course_key}/{usage_key}'
    return url


def get_exam_url(course_id, content_id, is_learning_mfe):
    """ Helper to build exam url depending if it is requested for the learning MFE app or not. """
    if is_learning_mfe:
        return resolve_exam_url_for_learning_mfe(course_id, content_id)
    return reverse('jump_to', args=[course_id, content_id])


def get_user_course_outline_details(user, course_id):
    """ Helper to get user's course outline details """
    learning_sequences_service = get_runtime_service('learning_sequences')
    course_key = CourseKey.from_string(course_id)
    details = learning_sequences_service.get_user_course_outline_details(
        course_key, user, pytz.utc.localize(datetime.now())
    )
    return details


def categorize_inaccessible_exams_by_date(onboarding_exams, details):
    """
    Categorize a list of inaccessible onboarding exams based on whether they are
    inaccessible because they are in the future, because they are in the past, or because
    they are inaccessible for reason unrelated to the exam schedule (e.g. visibility settings,
    content gating, etc.)

    Parameters:
    * onboarding_exams: a list of onboarding exams
    * details: a UserCourseOutlineData returned by the learning sequences API

    Returns: a tuple containing three lists
    * non_date_inaccessible_exams: a list of onboarding exams not accessible to the learner for
      reasons other than the exam schedule
    * future_exams: a list of onboarding exams not accessible to the learner because the exams are released
      in the future
    * past_due_exams: a list of onboarding exams not accessible to the learner because the exams are past their
      due date
    """
    non_date_inaccessible_exams = []
    future_exams = []
    past_due_exams = []

    for onboarding_exam in onboarding_exams:
        usage_key = BlockUsageLocator.from_string(onboarding_exam.content_id)
        if usage_key not in details.outline.accessible_sequences:
            sequence_schedule = details.schedule.sequences.get(usage_key)

            if sequence_schedule:
                effective_start = details.schedule.sequences.get(usage_key).effective_start
                due_date = get_visibility_check_date(details.schedule, usage_key)

                if effective_start and pytz.utc.localize(datetime.now()) < effective_start:
                    future_exams.append(onboarding_exam)
                elif due_date and pytz.utc.localize(datetime.now()) > due_date:
                    past_due_exams.append(onboarding_exam)
                else:
                    non_date_inaccessible_exams.append(onboarding_exam)
            else:
                # if the sequence schedule is not available, then the sequence is not available
                # to the learner
                non_date_inaccessible_exams.append(onboarding_exam)

    return non_date_inaccessible_exams, future_exams, past_due_exams


def encrypt_and_encode(data, key):
    """ Encrypts and encodes data using a key """
    return base64.urlsafe_b64encode(aes_encrypt(data, key))


def decode_and_decrypt(encoded_data, key):
    """ Decrypts and decodes data using a key """
    return aes_decrypt(base64.urlsafe_b64decode(encoded_data), key)


def aes_encrypt(data, key):
    """
    Return a version of the data that has been encrypted
    """
    cipher = Cipher(AES(key), CBC(generate_aes_iv(key)), backend=default_backend())
    padded_data = pad(data)
    encryptor = cipher.encryptor()
    return encryptor.update(padded_data) + encryptor.finalize()


def aes_decrypt(encrypted_data, key):
    """
    Decrypt encrypted_data using the provided key
    """
    cipher = Cipher(AES(key), CBC(generate_aes_iv(key)), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(encrypted_data) + decryptor.finalize()
    return unpad(padded_data)


def generate_aes_iv(key):
    """
    Return the initialization vector for a given AES key
    """
    return (
        hashlib.md5(key + hashlib.md5(key).hexdigest().encode('utf-8'))
        .hexdigest()[:AES_BLOCK_SIZE_BYTES].encode('utf-8')
    )


def pad(data):
    """ Pad the given data such that it fits into the proper AES block size """
    if not isinstance(data, (bytes, bytearray)):
        data = data.encode()

    padder = PKCS7(AES.block_size).padder()
    return padder.update(data) + padder.finalize()


def unpad(padded_data):
    """  remove all padding from the given padded_data """
    unpadder = PKCS7(AES.block_size).unpadder()
    return unpadder.update(padded_data) + unpadder.finalize()
