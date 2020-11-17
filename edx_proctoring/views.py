"""
Proctored Exams HTTP-based API endpoints
"""

import json
import logging

import waffle
from crum import get_current_request
from rest_framework import status
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.shortcuts import redirect
from django.urls import NoReverseMatch, reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _

from edx_proctoring import constants
from edx_proctoring.api import (
    add_allowance_for_user,
    create_exam,
    create_exam_attempt,
    get_active_exams_for_user,
    get_all_exams_for_course,
    get_allowances_for_course,
    get_backend_provider,
    get_exam_attempt_by_external_id,
    get_exam_attempt_by_id,
    get_exam_by_content_id,
    get_exam_by_id,
    is_exam_passed_due,
    mark_exam_attempt_as_ready,
    remove_allowance_for_user,
    remove_exam_attempt,
    reset_practice_exam,
    start_exam_attempt,
    stop_exam_attempt,
    update_attempt_status,
    update_exam,
    update_exam_attempt
)
from edx_proctoring.constants import PING_FAILURE_PASSTHROUGH_TEMPLATE
from edx_proctoring.exceptions import (
    ProctoredBaseException,
    ProctoredExamPermissionDenied,
    ProctoredExamReviewAlreadyExists,
    StudentExamAttemptDoesNotExistsException
)
from edx_proctoring.models import (
    ProctoredExam,
    ProctoredExamSoftwareSecureComment,
    ProctoredExamSoftwareSecureReview,
    ProctoredExamStudentAllowance,
    ProctoredExamStudentAllowanceHistory,
    ProctoredExamStudentAttempt,
    ProctoredExamStudentAttemptHistory
)
from edx_proctoring.runtime import get_runtime_service
from edx_proctoring.serializers import ProctoredExamSerializer, ProctoredExamStudentAttemptSerializer
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus, ReviewStatus, SoftwareSecureReviewStatus
from edx_proctoring.utils import (
    AuthenticatedAPIView,
    get_time_remaining_for_attempt,
    humanized_time,
    locate_attempt_by_attempt_code,
    obscured_user_id
)

ATTEMPTS_PER_PAGE = 25

LOG = logging.getLogger("edx_proctoring_views")


def require_staff(func):
    """View decorator that requires that the user have staff permissions. """
    def wrapped(request, *args, **kwargs):  # pylint: disable=missing-docstring
        if request.user.is_staff:
            return func(request, *args, **kwargs)
        return Response(
            status=status.HTTP_403_FORBIDDEN,
            data={"detail": "Must be a Staff User to Perform this request."}
        )
    return wrapped


def require_course_or_global_staff(func):
    """View decorator that requires that the user have staff permissions. """
    def wrapped(request, *args, **kwargs):  # pylint: disable=missing-docstring
        instructor_service = get_runtime_service('instructor')
        course_id = kwargs.get('course_id', None)
        exam_id = request.data.get('exam_id', None)
        attempt_id = kwargs.get('attempt_id', None)
        if request.user.is_staff:
            return func(request, *args, **kwargs)
        if course_id is None:
            if exam_id is not None:
                exam = ProctoredExam.get_exam_by_id(exam_id)
                course_id = exam.course_id
            elif attempt_id is not None:
                exam_attempt = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_id(attempt_id)
                course_id = exam_attempt.proctored_exam.course_id
            else:
                response_message = _("could not determine the course_id")
                return Response(
                    status=status.HTTP_403_FORBIDDEN,
                    data={"detail": response_message}
                )
        if instructor_service.is_course_staff(request.user, course_id):
            return func(request, *args, **kwargs)
        return Response(
            status=status.HTTP_403_FORBIDDEN,
            data={"detail": _("Must be a Staff User to Perform this request.")}
        )

    return wrapped


def is_user_course_or_global_staff(user, course_id):
    """
    Return whether a user is course staff for a given course, described by the course_id,
    or is global staff.
    """
    instructor_service = get_runtime_service('instructor')

    return user.is_staff or instructor_service.is_course_staff(user, course_id)


def handle_proctored_exception(exc, name=None):  # pylint: disable=inconsistent-return-statements
    """
    Converts proctoring exceptions into standard restframework responses
    """
    if isinstance(exc, ProctoredBaseException):
        LOG.exception(name)
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': str(exc)})


class ProctoredAPIView(AuthenticatedAPIView):
    """
    Overrides AuthenticatedAPIView to handle proctoring exceptions
    """
    def handle_exception(self, exc):
        """
        Converts proctoring exceptions into standard restframework responses
        """
        resp = handle_proctored_exception(exc, name=self.__class__.__name__)
        if not resp:
            resp = super(ProctoredAPIView, self).handle_exception(exc)
        return resp


class ProctoredExamView(ProctoredAPIView):
    """
    Endpoint for the Proctored Exams
    /edx_proctoring/v1/proctored_exam/exam

    Supports:
        HTTP POST: Creates a new Exam.
        HTTP PUT: Updates an existing Exam.
        HTTP GET: Returns an existing exam (by id or by content id)

    HTTP POST
    Creates a new Exam.
    Expected POST data: {
        "course_id": "edX/DemoX/Demo_Course",
        "content_id": 123,
        "exam_name": "Midterm",
        "time_limit_mins": 90,
        "is_proctored": true,
        "is_practice_exam": false,
        "external_id": "12213DASAD",
        "is_active": true
    }

    **POST data Parameters**
        * course_id: The unique identifier for the course.
        * content_id: This will be the pointer to the id of the piece of course_ware which is the proctored exam.
        * exam_name: This is the display name of the Exam (Midterm etc).
        * time_limit_mins: Time limit (in minutes) that a student can finish this exam.
        * is_proctored: Whether this exam actually is proctored or not.
        * is_proctored: Whether this exam will be for practice only.
        * external_id: This will be a integration specific ID - say to SoftwareSecure.
        * is_active: Whether this exam will be active.


    **Response Values**
        * {'exam_id': ##}, The exam_id of the created Proctored Exam.

    **Exceptions**
        * HTTP_400_BAD_REQUEST, data={"message": "Trying to create a duplicate exam."}

    HTTP PUT
    Updates an existing Exam.
    PUT data : {
        "exam_id": 533,
        "exam_name": "Final",
        "time_limit_mins": 120,
        "is_proctored": true,
        "is_practice_exam": false,
        "external_id": 235
        "is_active": true
    }

    **PUT data Parameters**
        see the POST data parameters

    **Response Values**
        * {'exam_id': ##}, The exam_id of the created Proctored Exam.


    HTTP GET
        ** Scenarios **
        ?exam_id=533
        returns an existing exam  object matching the exam_id

        ?course_id=edX/DemoX/Demo_Course&content_id=123
        returns an existing exam object matching the course_id and the content_id
    """
    @method_decorator(require_staff)
    def post(self, request):
        """
        Http POST handler. Creates an exam.
        """
        serializer = ProctoredExamSerializer(data=request.data)
        if serializer.is_valid():
            exam_id = create_exam(
                course_id=request.data.get('course_id', None),
                content_id=request.data.get('content_id', None),
                exam_name=request.data.get('exam_name', None),
                time_limit_mins=request.data.get('time_limit_mins', None),
                is_proctored=request.data.get('is_proctored', None),
                is_practice_exam=request.data.get('is_practice_exam', None),
                external_id=request.data.get('external_id', None),
                is_active=request.data.get('is_active', None),
                hide_after_due=request.data.get('hide_after_due', None),
            )
            rstat = status.HTTP_200_OK
            data = {'exam_id': exam_id}
        else:
            rstat = status.HTTP_400_BAD_REQUEST
            data = serializer.errors
        return Response(status=rstat, data=data)

    @method_decorator(require_staff)
    def put(self, request):
        """
        HTTP PUT handler. To update an exam.
        calls the update_exam
        """
        exam_id = update_exam(
            exam_id=request.data.get('exam_id', None),
            exam_name=request.data.get('exam_name', None),
            time_limit_mins=request.data.get('time_limit_mins', None),
            is_proctored=request.data.get('is_proctored', None),
            is_practice_exam=request.data.get('is_practice_exam', None),
            external_id=request.data.get('external_id', None),
            is_active=request.data.get('is_active', None),
            hide_after_due=request.data.get('hide_after_due', None),
        )
        return Response({'exam_id': exam_id})

    def get(self, request, exam_id=None, course_id=None, content_id=None):  # pylint: disable=unused-argument
        """
        HTTP GET handler.
            Scenarios:
                by exam_id: calls get_exam_by_id()
                by course_id, content_id: get_exam_by_content_id()

        """
        if exam_id:
            data = get_exam_by_id(exam_id)
        elif course_id is not None:
            if content_id is not None:
                # get by course_id & content_id
                data = get_exam_by_content_id(course_id, content_id)
            else:
                data = get_all_exams_for_course(
                    course_id=course_id,
                    active_only=True
                )
        return Response(data)


class StudentProctoredExamAttempt(ProctoredAPIView):
    """
    Endpoint for the StudentProctoredExamAttempt
    /edx_proctoring/v1/proctored_exam/attempt

    Supports:
        HTTP PUT: Stops an exam attempt.
        HTTP GET: Returns the status of an exam attempt.
        HTTP DELETE: Delete an exam attempt.


    HTTP PUT
    Stops the existing exam attempt in progress
    PUT data : {
        ....
    }

    **PUT data Parameters**
        * exam_id: The unique identifier for the proctored exam attempt.

    **Response Values**
        * {'exam_attempt_id': ##}, The exam_attempt_id of the Proctored Exam Attempt..


    HTTP GET
        ** Scenarios **
        return the status of the exam attempt

    HTTP DELETE
        ** Scenarios **
        Removes an exam attempt and resets progress. Limited to course staff
    """

    def get(self, request, attempt_id):
        """
        HTTP GET Handler. Returns the status of the exam attempt.
        """
        attempt = get_exam_attempt_by_id(attempt_id)

        if not attempt:
            err_msg = (
                u'Attempted to access attempt_id {attempt_id} but '
                u'it does not exist.'.format(
                    attempt_id=attempt_id
                )
            )
            raise StudentExamAttemptDoesNotExistsException(err_msg)
        # make sure the the attempt belongs to the calling user_id
        if attempt['user']['id'] != request.user.id:
            err_msg = (
                u'Attempted to access attempt_id {attempt_id} but '
                u'does not have access to it.'.format(
                    attempt_id=attempt_id
                )
            )
            raise ProctoredExamPermissionDenied(err_msg)

        # add in the computed time remaining as a helper
        time_remaining_seconds = get_time_remaining_for_attempt(attempt)

        attempt['time_remaining_seconds'] = time_remaining_seconds

        accessibility_time_string = _(u'you have {remaining_time} remaining').format(
            remaining_time=humanized_time(int(round(time_remaining_seconds / 60.0, 0))))

        # special case if we are less than a minute, since we don't produce
        # text translations of granularity at the seconds range
        if time_remaining_seconds < 60:
            accessibility_time_string = _(u'you have less than a minute remaining')

        attempt['accessibility_time_string'] = accessibility_time_string
        return Response(attempt)

    def put(self, request, attempt_id):
        """
        HTTP PUT handler. To stop an exam.
        """
        attempt = get_exam_attempt_by_id(attempt_id)

        if not attempt:
            err_msg = (
                u'Attempted to access attempt_id {attempt_id} but '
                u'it does not exist.'.format(
                    attempt_id=attempt_id
                )
            )
            raise StudentExamAttemptDoesNotExistsException(err_msg)

        # make sure the the attempt belongs to the calling user_id
        if attempt['user']['id'] != request.user.id:
            err_msg = (
                u'Attempted to access attempt_id {attempt_id} but '
                u'does not have access to it.'.format(
                    attempt_id=attempt_id
                )
            )
            raise ProctoredExamPermissionDenied(err_msg)

        action = request.data.get('action')

        if action == 'stop':
            exam_attempt_id = stop_exam_attempt(
                exam_id=attempt['proctored_exam']['id'],
                user_id=request.user.id
            )
        elif action == 'start':
            exam_attempt_id = start_exam_attempt(
                exam_id=attempt['proctored_exam']['id'],
                user_id=request.user.id
            )
        elif action == 'submit':
            exam_attempt_id = update_attempt_status(
                attempt['proctored_exam']['id'],
                request.user.id,
                ProctoredExamStudentAttemptStatus.submitted
            )
        elif action == 'click_download_software':
            exam_attempt_id = update_attempt_status(
                attempt['proctored_exam']['id'],
                request.user.id,
                ProctoredExamStudentAttemptStatus.download_software_clicked
            )
        elif action == 'reset_attempt':
            exam_attempt_id = reset_practice_exam(
                attempt['proctored_exam']['id'],
                request.user.id,
            )
        elif action == 'error':
            backend = attempt['proctored_exam']['backend']
            waffle_name = PING_FAILURE_PASSTHROUGH_TEMPLATE.format(backend)
            should_block_user = not (backend and waffle.switch_is_active(waffle_name)) and (
                not attempt['status'] == ProctoredExamStudentAttemptStatus.submitted
            )
            if should_block_user:
                exam_attempt_id = update_attempt_status(
                    attempt['proctored_exam']['id'],
                    request.user.id,
                    ProctoredExamStudentAttemptStatus.error
                )
            else:
                exam_attempt_id = False
            LOG.warning(u'Browser JS reported problem with proctoring desktop '
                        u'application. Did block user: %s, for attempt: %s',
                        should_block_user,
                        attempt['id'])
        elif action == 'decline':
            exam_attempt_id = update_attempt_status(
                attempt['proctored_exam']['id'],
                request.user.id,
                ProctoredExamStudentAttemptStatus.declined
            )
        data = {"exam_attempt_id": exam_attempt_id}
        return Response(data)

    @method_decorator(require_course_or_global_staff)
    def delete(self, request, attempt_id):  # pylint: disable=unused-argument
        """
        HTTP DELETE handler. Removes an exam attempt.
        """
        attempt = get_exam_attempt_by_id(attempt_id)

        if not attempt:
            err_msg = (
                u'Attempted to access attempt_id {attempt_id} but '
                u'it does not exist.'.format(
                    attempt_id=attempt_id
                )
            )
            raise StudentExamAttemptDoesNotExistsException(err_msg)

        remove_exam_attempt(attempt_id, request.user)
        return Response()


class StudentProctoredExamAttemptCollection(ProctoredAPIView):
    """
    Endpoint for the StudentProctoredExamAttempt
    /edx_proctoring/v1/proctored_exam/attempt

    Supports:
        HTTP POST: Starts an exam attempt.
        HTTP PUT: Stops an exam attempt.
        HTTP GET: Returns the status of an exam attempt.

    HTTP POST
    create an exam attempt.
    Expected POST data: {
        "exam_id": "1",
        "external_id": "123",
        "start_clock": "True" or "true"
    }

    **POST data Parameters**
        * exam_id: The unique identifier for the course.
        * external_id: This will be a integration specific ID - say to SoftwareSecure.
        * start_clock: Whether to start the exam attempt immediately


    **Response Values**
        * {'exam_attempt_id': ##}, The exam_attempt_id of the created Proctored Exam Attempt.

    **Exceptions**
        * HTTP_400_BAD_REQUEST

    HTTP PUT
    Stops the existing exam attempt in progress
    PUT data : {
        "exam_id": 1
    }

    **PUT data Parameters**
        * exam_id: The unique identifier for the proctored exam attempt.

    **Response Values**
        * {'exam_attempt_id': ##}, The exam_attempt_id of the Proctored Exam Attempt..


    HTTP GET
        ** Scenarios **
        return the status of the exam attempt
    """

    def get(self, request):  # pylint: disable=unused-argument
        """
        HTTP GET Handler. Returns the status of the exam attempt.
        """

        exams = get_active_exams_for_user(request.user.id)

        if exams:
            exam_info = exams[0]

            exam = exam_info['exam']
            attempt = exam_info['attempt']

            provider = get_backend_provider(exam)

            time_remaining_seconds = get_time_remaining_for_attempt(attempt)

            proctoring_settings = getattr(settings, 'PROCTORING_SETTINGS', {})
            low_threshold_pct = proctoring_settings.get('low_threshold_pct', .2)
            critically_low_threshold_pct = proctoring_settings.get('critically_low_threshold_pct', .05)

            low_threshold = int(low_threshold_pct * float(attempt['allowed_time_limit_mins']) * 60)
            critically_low_threshold = int(
                critically_low_threshold_pct * float(attempt['allowed_time_limit_mins']) * 60
            )

            exam_url_path = ''
            try:
                # resolve the LMS url, note we can't assume we're running in
                # a same process as the LMS
                exam_url_path = reverse('jump_to', args=[exam['course_id'], exam['content_id']])
            except NoReverseMatch:
                LOG.exception(u"Can't find exam url for course %s", exam['course_id'])

            response_dict = {
                'in_timed_exam': True,
                'taking_as_proctored': attempt['taking_as_proctored'],
                'exam_type': (
                    _('a timed exam') if not attempt['taking_as_proctored'] else
                    (_('a proctored exam') if not attempt['is_sample_attempt'] else
                     (_('an onboarding exam') if provider.supports_onboarding else _('a practice exam')))
                ),
                'exam_display_name': exam['exam_name'],
                'exam_url_path': exam_url_path,
                'time_remaining_seconds': time_remaining_seconds,
                'low_threshold_sec': low_threshold,
                'critically_low_threshold_sec': critically_low_threshold,
                'course_id': exam['course_id'],
                'attempt_id': attempt['id'],
                'accessibility_time_string': _(u'you have {remaining_time} remaining').format(
                    remaining_time=humanized_time(int(round(time_remaining_seconds / 60.0, 0)))
                ),
                'attempt_status': attempt['status'],
                'exam_started_poll_url': reverse(
                    'edx_proctoring:proctored_exam.attempt',
                    args=[attempt['id']]
                ),

            }

            if provider:
                response_dict['desktop_application_js_url'] = provider.get_javascript()
                response_dict['ping_interval'] = provider.ping_interval
            else:
                response_dict['desktop_application_js_url'] = ''

        else:
            response_dict = {
                'in_timed_exam': False,
                'is_proctored': False
            }

        return Response(data=response_dict, status=status.HTTP_200_OK)

    def post(self, request):
        """
        HTTP POST handler. To create an exam attempt.
        """
        start_immediately = request.data.get('start_clock', 'false').lower() == 'true'
        exam_id = request.data.get('exam_id', None)
        attempt_proctored = request.data.get('attempt_proctored', 'false').lower() == 'true'
        exam = get_exam_by_id(exam_id)

        # Bypassing the due date check for practice exam
        # because student can attempt the practice after the due date
        if not exam.get("is_practice_exam") and is_exam_passed_due(exam, request.user):
            raise ProctoredExamPermissionDenied(
                u'Attempted to access expired exam with exam_id {exam_id}'.format(exam_id=exam_id)
            )

        exam_attempt_id = create_exam_attempt(
            exam_id=exam_id,
            user_id=request.user.id,
            taking_as_proctored=attempt_proctored
        )

        # if use elected not to take as proctored exam, then
        # use must take as open book, and loose credit eligibility
        if exam['is_proctored'] and not attempt_proctored:
            update_attempt_status(
                exam_id,
                request.user.id,
                ProctoredExamStudentAttemptStatus.declined
            )
        elif start_immediately:
            start_exam_attempt(exam_id, request.user.id)

        data = {'exam_attempt_id': exam_attempt_id}
        return Response(data)


class StudentProctoredExamAttemptsByCourse(ProctoredAPIView):
    """
    This endpoint is called by the Instructor Dashboard to get
    paginated attempts in a course

    A search parameter is optional
    """
    @method_decorator(require_course_or_global_staff)
    def get(self, request, course_id, search_by=None):  # pylint: disable=unused-argument
        """
        HTTP GET Handler. Returns the status of the exam attempt.
        Course and Global staff can view both timed and proctored exam attempts.
        """
        if search_by is not None:
            exam_attempts = ProctoredExamStudentAttempt.objects.get_filtered_exam_attempts(
                course_id, search_by
            )
            attempt_url = reverse('edx_proctoring:proctored_exam.attempts.search', args=[course_id, search_by])
        else:
            exam_attempts = ProctoredExamStudentAttempt.objects.get_all_exam_attempts(
                course_id
            )
            attempt_url = reverse('edx_proctoring:proctored_exam.attempts.course', args=[course_id])

        paginator = Paginator(exam_attempts, ATTEMPTS_PER_PAGE)
        page = request.GET.get('page')
        try:
            exam_attempts_page = paginator.page(page)
        except PageNotAnInteger:
            # If page is not an integer, deliver first page.
            exam_attempts_page = paginator.page(1)
        except EmptyPage:
            # If page is out of range (e.g. 9999), deliver last page of results.
            exam_attempts_page = paginator.page(paginator.num_pages)

        data = {
            'proctored_exam_attempts': [
                ProctoredExamStudentAttemptSerializer(attempt).data for
                attempt in exam_attempts_page.object_list
            ],
            'pagination_info': {
                'has_previous': exam_attempts_page.has_previous(),
                'has_next': exam_attempts_page.has_next(),
                'current_page': exam_attempts_page.number,
                'total_pages': exam_attempts_page.paginator.num_pages,
            },
            'attempt_url': attempt_url

        }
        return Response(data)


class ExamAllowanceView(ProctoredAPIView):
    """
    Endpoint for the Exam Allowance
    /edx_proctoring/v1/proctored_exam/allowance

    Supports:
        HTTP PUT: Creates or Updates the allowance for a user.
        HTTP DELETE: Removed an allowance for a user.

    HTTP PUT
    Adds or updated the proctored exam allowance.
    PUT data : {
        "exam_id": 533,
        "user_id": 1,
        "key": 'extra_time',
        "value": '10'
    }

    **PUT data Parameters**
        * exam_id: The unique identifier for the course.
        * user_id: The unique identifier for the student.
        * key: key for the allowance entry
        * value: value for the allowance entry.

    **Response Values**
        * returns Nothing. Add or update the allowance for the user proctored exam.

    DELETE data : {
        "exam_id": 533,
        "user_id": 1,
        "key": 'extra_time'
    }
    **DELETE data Parameters**
        * exam_id: The unique identifier for the course.
        * user_id: The unique identifier for the student.
        * key: key for the user allowance.

    **Response Values**
        * returns Nothing. deletes the allowance for the user proctored exam.
    """
    @method_decorator(require_course_or_global_staff)
    def get(self, request, course_id):  # pylint: disable=unused-argument
        """
        HTTP GET handler. Get all allowances for a course.
        Course and Global staff can view both timed and proctored exam allowances.
        """
        result_set = get_allowances_for_course(
            course_id=course_id
        )
        return Response(result_set)

    @method_decorator(require_course_or_global_staff)
    def put(self, request):
        """
        HTTP GET handler. Adds or updates Allowance
        """
        return Response(add_allowance_for_user(
            exam_id=request.data.get('exam_id', None),
            user_info=request.data.get('user_info', None),
            key=request.data.get('key', None),
            value=request.data.get('value', None)
        ))

    @method_decorator(require_course_or_global_staff)
    def delete(self, request):
        """
        HTTP DELETE handler. Removes Allowance.
        """
        return Response(remove_allowance_for_user(
            exam_id=request.data.get('exam_id', None),
            user_id=request.data.get('user_id', None),
            key=request.data.get('key', None)
        ))


class ActiveExamsForUserView(ProctoredAPIView):
    """
    Endpoint for the Active Exams for a user.
    /edx_proctoring/v1/proctored_exam/active_exams_for_user

    Supports:
        HTTP GET: returns a list of active exams for the user
    """
    def get(self, request):
        """
        Returns the get_active_exams_for_user
        """
        return Response(get_active_exams_for_user(
            user_id=request.data.get('user_id', None),
            course_id=request.data.get('course_id', None)
        ))


class ProctoredExamAttemptReviewStatus(ProctoredAPIView):
    """
    Endpoint for updating exam attempt's review status to acknowledged.
    edx_proctoring/v1/proctored_exam/attempt/(<attempt_id>)/review_status$

    Supports:
        HTTP PUT: Update the is_status_acknowledge flag
    """
    def put(self, request, attempt_id):     # pylint: disable=unused-argument
        """
        Update the is_status_acknowledge flag for the specific attempt
        """
        attempt = get_exam_attempt_by_id(attempt_id)

        # make sure the the attempt belongs to the calling user_id
        if attempt and attempt['user']['id'] != request.user.id:
            err_msg = (
                u'Attempted to access attempt_id {attempt_id} but '
                u'does not have access to it.'.format(
                    attempt_id=attempt_id
                )
            )
            raise ProctoredExamPermissionDenied(err_msg)

        update_exam_attempt(attempt_id, is_status_acknowledged=True)

        return Response()


class ExamReadyCallback(ProctoredAPIView):
    """
    Called by REST based proctoring backends to indicate that the learner is able to
    proceed with the exam.
    """
    def post(self, request, external_id):  # pylint: disable=unused-argument
        """
        Post callback handler
        """
        attempt = get_exam_attempt_by_external_id(external_id)
        if not attempt:
            LOG.warning(u"Attempt code %r cannot be found.", external_id)
            return Response(data='You have entered an exam code that is not valid.', status=404)
        if attempt['status'] in [ProctoredExamStudentAttemptStatus.created,
                                 ProctoredExamStudentAttemptStatus.download_software_clicked]:
            mark_exam_attempt_as_ready(attempt['proctored_exam']['id'], attempt['user']['id'])
        return Response(data='OK')


class BaseReviewCallback:
    """
    Base class for review callbacks.
    make_review handles saving reviews and review comments.
    """
    def make_review(self, attempt, data, backend=None):
        """
        Save the review and review comments
        """
        attempt_code = attempt['attempt_code']
        if not backend:
            backend = get_backend_provider(attempt['proctored_exam'])

        # this method should convert the payload into a normalized format
        backend_review = backend.on_review_callback(attempt, data)

        # do we already have a review for this attempt?!? We may not allow updates
        review = ProctoredExamSoftwareSecureReview.get_review_by_attempt_code(attempt_code)

        if review:
            if not constants.ALLOW_REVIEW_UPDATES:
                err_msg = (
                    u'We already have a review submitted regarding '
                    u'attempt_code {attempt_code}. We do not allow for updates!'.format(
                        attempt_code=attempt_code
                    )
                )
                raise ProctoredExamReviewAlreadyExists(err_msg)

            # we allow updates
            warn_msg = (
                u'We already have a review submitted from our proctoring provider regarding '
                u'attempt_code {attempt_code}. We have been configured to allow for '
                u'updates and will continue...'.format(
                    attempt_code=attempt_code
                )
            )
            LOG.warning(warn_msg)
        else:
            # this is first time we've received this attempt_code, so
            # make a new record in the review table
            review = ProctoredExamSoftwareSecureReview()

        # first, validate that the backend review status is valid
        ReviewStatus.validate(backend_review['status'])
        # For now, we'll convert the standard review status to the old
        # software secure review status.
        # In the future, the old data should be standardized.
        review.review_status = SoftwareSecureReviewStatus.from_standard_status.get(backend_review['status'])

        review.attempt_code = attempt_code
        review.raw_data = json.dumps(data)
        review.student_id = attempt['user']['id']
        review.exam_id = attempt['proctored_exam']['id']

        try:
            review.reviewed_by = get_user_model().objects.get(email=data['reviewed_by'])
        except (ObjectDoesNotExist, KeyError):
            review.reviewed_by = None

        # If the reviewing user is a user in the system (user may be None for automated reviews) and does
        # not have permission to submit a review, log a warning.
        course_id = attempt['proctored_exam']['course_id']
        if review.reviewed_by is not None and not is_user_course_or_global_staff(review.reviewed_by, course_id):
            LOG.warning(
                u'User %(user)s does not have the required permissions to submit '
                u'a review for attempt_code %(attempt_code)s.',
                {'user': review.reviewed_by, 'attempt_code': attempt_code}
            )

        review.save()

        # go through and populate all of the specific comments
        for comment in backend_review.get('comments', []):
            comment = ProctoredExamSoftwareSecureComment(
                review=review,
                start_time=comment.get('start', 0),
                stop_time=comment.get('stop', 0),
                duration=comment.get('duration', 0),
                comment=comment['comment'],
                status=comment['status']
            )
            comment.save()

        if review.should_notify:
            instructor_service = get_runtime_service('instructor')
            request = get_current_request()
            if instructor_service and request:
                course_id = attempt['proctored_exam']['course_id']
                exam_id = attempt['proctored_exam']['id']
                review_url = request.build_absolute_uri(
                    u'{}?attempt={}'.format(
                        reverse('edx_proctoring:instructor_dashboard_exam', args=[course_id, exam_id]),
                        attempt['external_id']
                    ))
                instructor_service.send_support_notification(
                    course_id=attempt['proctored_exam']['course_id'],
                    exam_name=attempt['proctored_exam']['exam_name'],
                    student_username=attempt['user']['username'],
                    review_status=review.review_status,
                    review_url=review_url,
                )


class ProctoredExamReviewCallback(ProctoredAPIView, BaseReviewCallback):
    """
    Authenticated callback from 3rd party proctoring service.
    """
    def post(self, request, external_id):
        """
        Called when 3rd party proctoring service has finished its review of
        an attempt.
        """
        attempt = get_exam_attempt_by_external_id(external_id)
        if attempt is None:
            err_msg = (
                u'Attempted to access external exam id {external_id} but '
                u'it does not exist.'.format(
                    external_id=external_id
                )
            )
            raise StudentExamAttemptDoesNotExistsException(err_msg)
        if request.user.has_perm('edx_proctoring.can_review_attempt', attempt):
            self.make_review(attempt, request.data)
            resp = Response(data='OK')
        else:
            resp = Response(status=403)
        return resp


class IgnoreClientContentNegotiation(BaseContentNegotiation):
    """
    This specialized class allows for more tolerance regarding
    what the passed in Content-Type is. This is taken directly
    from the Django REST Framework:

    http://tomchristie.github.io/rest-framework-2-docs/api-guide/content-negotiation
    """
    def select_parser(self, request, parsers):
        """
        Select the first parser in the `.parser_classes` list.
        """
        return parsers[0]

    def select_renderer(self, request, renderers, format_suffix):  # pylint: disable=signature-differs
        """
        Select the first renderer in the `.renderer_classes` list.
        """
        return (renderers[0], renderers[0].media_type)


class AnonymousReviewCallback(BaseReviewCallback, APIView):
    """
    This endpoint is called by a SoftwareSecure when
    there are results available for us to record

    NOTE: This endpoint is deprecated, in favor of using the authenticated endpoint at:
    /edx_proctoring/v1/proctored_exam/attempt/123/reviewed
    """

    content_negotiation_class = IgnoreClientContentNegotiation

    def handle_exception(self, exc):
        """ Helper method for exception handling """
        resp = handle_proctored_exception(exc, name=self.__class__.__name__)
        if not resp:
            resp = APIView.handle_exception(self, exc)
        return resp

    def post(self, request):
        """
        Post callback handler
        """
        provider = get_backend_provider({'backend': 'software_secure'})

        # call down into the underlying provider code
        attempt_code = request.data.get('examMetaData', {}).get('examCode')
        attempt_obj, is_archived = locate_attempt_by_attempt_code(attempt_code)
        if not attempt_obj:
            # still can't find, error out
            err_msg = (
                u'Could not locate attempt_code: {attempt_code}'.format(attempt_code=attempt_code)
            )
            raise StudentExamAttemptDoesNotExistsException(err_msg)
        serialized = ProctoredExamStudentAttemptSerializer(attempt_obj).data
        serialized['is_archived'] = is_archived
        self.make_review(serialized,
                         request.data,
                         backend=provider)
        return Response('OK')


class InstructorDashboard(AuthenticatedAPIView):
    """
    Redirects to the instructor dashboard for reviewing exams on the configured backend
    """
    @method_decorator(require_course_or_global_staff)
    def get(self, request, course_id, exam_id=None):
        """
        Redirect to dashboard for a given course and optional exam_id
        """
        exam = None
        backend = None
        ext_exam_id = None
        attempt_id = None
        show_configuration_dashboard = False

        if exam_id:
            exam = get_exam_by_id(exam_id)
            backend = get_backend_provider(exam=exam)
            # the exam_id in the url is our database id (for ease of lookups)
            # but the backend needs its external id for the instructor dashboard
            ext_exam_id = exam['external_id']
            attempt_id = request.GET.get('attempt', None)

            # only show the configuration dashboard if an exam_id is passed in
            show_configuration_dashboard = request.GET.get('config', '').lower() == 'true'
        else:
            existing_backend_name = None
            for exam in get_all_exams_for_course(course_id, True):
                if not exam.get('is_proctored'):
                    # We should only get backends of exams which are configured to be proctored
                    continue

                exam_backend_name = exam.get('backend')
                backend = get_backend_provider(name=exam_backend_name)
                if existing_backend_name and exam_backend_name != existing_backend_name:
                    # In this case, what are we supposed to do?!
                    # It should not be possible to get in this state, because
                    # course teams will be prevented from updating the backend after the course start date
                    error_message = u"Multiple backends for course %r %r != %r" % (
                        course_id,
                        existing_backend_name,
                        exam_backend_name
                    )
                    return Response(data=error_message, status=400)
                existing_backend_name = exam_backend_name

        if not exam:
            return Response(
                data=_(u'No exams in course {course_id}.').format(course_id=course_id),
                status=404,
                headers={'X-Frame-Options': 'sameorigin'}
            )
        if not backend:
            return Response(
                data=_(u'No proctored exams in course {course_id}').format(course_id=course_id),
                status=404,
                headers={'X-Frame-Options': 'sameorigin'}
            )
        user = {
            'id': obscured_user_id(request.user.id, exam['backend']),
            'full_name': request.user.profile.name,
            'email': request.user.email
        }

        url = backend.get_instructor_url(
            exam['course_id'],
            user,
            exam_id=ext_exam_id,
            attempt_id=attempt_id,
            show_configuration_dashboard=show_configuration_dashboard
        )
        if not url:
            return Response(
                data=_(u'No instructor dashboard for {proctor_service}').format(
                    proctor_service=backend.verbose_name
                ),
                status=404,
                headers={'X-Frame-Options': 'sameorigin'}
            )
        return redirect(url)


class BackendUserManagementAPI(AuthenticatedAPIView):
    """
    Manage user information stored on the backends
    """
    def post(self, request, user_id):  # pylint: disable=unused-argument
        """
        Deletes all user data for the particular user_id
        from all configured backends
        """
        if not request.user.has_perm('accounts.can_retire_user'):
            return Response(status=403)
        results = {}
        code = 200
        seen = set()
        # pylint: disable=no-member
        attempts = ProctoredExamStudentAttempt.objects.filter(user_id=user_id).select_related('proctored_exam')
        if attempts:
            for attempt in attempts:
                backend_name = attempt.proctored_exam.backend
                if backend_name in seen or not attempt.taking_as_proctored:
                    continue
                backend_user_id = obscured_user_id(user_id, backend_name)
                LOG.info(u'retiring user %s from %s', user_id, backend_name)
                try:
                    result = get_backend_provider(name=backend_name).retire_user(backend_user_id)
                except ProctoredBaseException:
                    LOG.exception(u'attempting to delete %s (%s) from %s', user_id, backend_user_id, backend_name)
                    result = False
                if result is not None:
                    results[backend_name] = result
                    if not result:
                        code = 500
                seen.add(backend_name)
        return Response(data=results, status=code)


class UserRetirement(AuthenticatedAPIView):
    """
    Retire user personally-identifiable information (PII) for a user
    """
    def _retire_exam_attempts_user_info(self, user_id):
        """ Remove PII for exam attempts and exam history """
        attempts = ProctoredExamStudentAttempt.objects.filter(user_id=user_id)
        if attempts:
            for attempt in attempts:
                attempt.student_name = ''
                attempt.last_poll_ipaddr = None
                attempt.save()

        attempts_history = ProctoredExamStudentAttemptHistory.objects.filter(user_id=user_id)
        if attempts_history:
            for attempt_history in attempts_history:
                attempt_history.student_name = ''
                attempt_history.last_poll_ipaddr = None
                attempt_history.save()

    def _retire_user_allowances(self, user_id):
        """ Clear user allowance values """
        allowances = ProctoredExamStudentAllowance.objects.filter(user=user_id)
        for allowance in allowances:
            allowance.value = ''
            allowance.save()

        allowances_history = ProctoredExamStudentAllowanceHistory.objects.filter(user=user_id)
        for allowance_history in allowances_history:
            allowance_history.value = ''
            allowance_history.save()

    def post(self, request, user_id):  # pylint: disable=unused-argument
        """ Obfuscates all PII for a given user_id """
        if not request.user.has_perm('accounts.can_retire_user'):
            return Response(status=403)
        code = 204

        self._retire_exam_attempts_user_info(user_id)
        self._retire_user_allowances(user_id)

        return Response(status=code)
