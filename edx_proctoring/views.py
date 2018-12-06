"""
Proctored Exams HTTP-based API endpoints
"""

from __future__ import absolute_import

import json
import logging
import six

from django.conf import settings
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.urls import reverse, NoReverseMatch
from django.shortcuts import redirect
from django.utils.translation import ugettext as _
from django.utils.decorators import method_decorator

from rest_framework import status
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.response import Response
from rest_framework.views import APIView

from edx_proctoring import constants
from edx_proctoring.api import (
    create_exam,
    update_exam,
    get_exam_by_id,
    get_exam_by_content_id,
    start_exam_attempt,
    stop_exam_attempt,
    add_allowance_for_user,
    remove_allowance_for_user,
    get_active_exams_for_user,
    create_exam_attempt,
    get_allowances_for_course,
    get_all_exams_for_course,
    get_exam_attempt_by_id,
    get_exam_attempt_by_external_id,
    remove_exam_attempt,
    update_attempt_status,
    update_exam_attempt,
    has_due_date_passed,
    get_backend_provider,
    mark_exam_attempt_as_ready,
)
from edx_proctoring.exceptions import (
    ProctoredBaseException,
    ProctoredExamReviewAlreadyExists,
    ProctoredExamPermissionDenied,
    StudentExamAttemptDoesNotExistsException,
)
from edx_proctoring.runtime import get_runtime_service
from edx_proctoring.serializers import ProctoredExamSerializer, ProctoredExamStudentAttemptSerializer
from edx_proctoring.models import (
    ProctoredExamStudentAttempt,
    ProctoredExam,
    ProctoredExamSoftwareSecureComment,
    ProctoredExamSoftwareSecureReview,
)
from edx_proctoring.statuses import (
    ProctoredExamStudentAttemptStatus,
    ReviewStatus,
    SoftwareSecureReviewStatus,
)

from edx_proctoring.utils import (
    AuthenticatedAPIView,
    get_time_remaining_for_attempt,
    locate_attempt_by_attempt_code,
    humanized_time,
    emit_event,
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
        else:
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


def handle_proctored_exception(exc, name=None):
    """
    converts proctoring exceptions into standard restframework responses
    """
    if isinstance(exc, ProctoredBaseException):
        LOG.exception(name)
        return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': six.text_type(exc)})


class ProctoredAPIView(AuthenticatedAPIView):
    """
    Overrides AuthenticatedAPIView to handle proctoring exceptions
    """
    def handle_exception(self, exc):
        """
        converts proctoring exceptions into standard restframework responses
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
        HTTP POST: Starts an exam attempt.
        HTTP PUT: Stops an exam attempt.
        HTTP GET: Returns the status of an exam attempt.


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
    """

    def get(self, request, attempt_id):
        """
        HTTP GET Handler. Returns the status of the exam attempt.
        """
        attempt = get_exam_attempt_by_id(attempt_id)

        if not attempt:
            err_msg = (
                'Attempted to access attempt_id {attempt_id} but '
                'it does not exist.'.format(
                    attempt_id=attempt_id
                )
            )
            raise StudentExamAttemptDoesNotExistsException(err_msg)
        else:
            # make sure the the attempt belongs to the calling user_id
            if attempt['user']['id'] != request.user.id:
                err_msg = (
                    'Attempted to access attempt_id {attempt_id} but '
                    'does not have access to it.'.format(
                        attempt_id=attempt_id
                    )
                )
                raise ProctoredExamPermissionDenied(err_msg)

            # add in the computed time remaining as a helper
            time_remaining_seconds = get_time_remaining_for_attempt(attempt)

            attempt['time_remaining_seconds'] = time_remaining_seconds

            accessibility_time_string = _('you have {remaining_time} remaining').format(
                remaining_time=humanized_time(int(round(time_remaining_seconds / 60.0, 0))))

            # special case if we are less than a minute, since we don't produce
            # text translations of granularity at the seconds range
            if time_remaining_seconds < 60:
                accessibility_time_string = _('you have less than a minute remaining')

            attempt['accessibility_time_string'] = accessibility_time_string
        return Response(attempt)

    def put(self, request, attempt_id):
        """
        HTTP POST handler. To stop an exam.
        """
        attempt = get_exam_attempt_by_id(attempt_id)

        if not attempt:
            err_msg = (
                'Attempted to access attempt_id {attempt_id} but '
                'it does not exist.'.format(
                    attempt_id=attempt_id
                )
            )
            raise StudentExamAttemptDoesNotExistsException(err_msg)

        # make sure the the attempt belongs to the calling user_id
        if attempt['user']['id'] != request.user.id:
            err_msg = (
                'Attempted to access attempt_id {attempt_id} but '
                'does not have access to it.'.format(
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
        elif action == 'error':
            exam_attempt_id = update_attempt_status(
                attempt['proctored_exam']['id'],
                request.user.id,
                ProctoredExamStudentAttemptStatus.error
            )
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
                'Attempted to access attempt_id {attempt_id} but '
                'it does not exist.'.format(
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

            if provider:
                desktop_application_js_url = provider.get_javascript()
            else:
                desktop_application_js_url = ''

            exam_url_path = ''
            try:
                # resolve the LMS url, note we can't assume we're running in
                # a same process as the LMS
                exam_url_path = reverse('jump_to', args=[exam['course_id'], exam['content_id']])
            except NoReverseMatch:
                LOG.exception("Can't find exam url for course %s", exam['course_id'])

            response_dict = {
                'in_timed_exam': True,
                'taking_as_proctored': attempt['taking_as_proctored'],
                'exam_type': (
                    _('timed') if not attempt['taking_as_proctored'] else
                    (_('practice') if attempt['is_sample_attempt'] else _('proctored'))
                ),
                'exam_display_name': exam['exam_name'],
                'exam_url_path': exam_url_path,
                'time_remaining_seconds': time_remaining_seconds,
                'low_threshold_sec': low_threshold,
                'critically_low_threshold_sec': critically_low_threshold,
                'course_id': exam['course_id'],
                'attempt_id': attempt['id'],
                'accessibility_time_string': _('you have {remaining_time} remaining').format(
                    remaining_time=humanized_time(int(round(time_remaining_seconds / 60.0, 0)))
                ),
                'attempt_status': attempt['status'],
                'desktop_application_js_url': desktop_application_js_url
            }
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
        if not exam.get("is_practice_exam") and has_due_date_passed(exam.get('due_date')):
            raise ProctoredExamPermissionDenied(
                'Attempted to access expired exam with exam_id {exam_id}'.format(exam_id=exam_id)
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
            attempt_url = reverse('edx_proctoring.proctored_exam.attempts.search', args=[course_id, search_by])
        else:
            exam_attempts = ProctoredExamStudentAttempt.objects.get_all_exam_attempts(
                course_id
            )
            attempt_url = reverse('edx_proctoring.proctored_exam.attempts.course', args=[course_id])

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
        returns the get_active_exams_for_user
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
                'Attempted to access attempt_id {attempt_id} but '
                'does not have access to it.'.format(
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
            LOG.warning("Attempt code %r cannot be found.", external_id)
            return Response(data='You have entered an exam code that is not valid.', status=404)
        if attempt['status'] in [ProctoredExamStudentAttemptStatus.created,
                                 ProctoredExamStudentAttemptStatus.download_software_clicked]:
            mark_exam_attempt_as_ready(attempt['proctored_exam']['id'], attempt['user']['id'])
        return Response(data='OK')


class BaseReviewCallback(object):
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
                    'We already have a review submitted from SoftwareSecure regarding '
                    'attempt_code {attempt_code}. We do not allow for updates!'.format(
                        attempt_code=attempt_code
                    )
                )
                raise ProctoredExamReviewAlreadyExists(err_msg)

            # we allow updates
            warn_msg = (
                'We already have a review submitted from SoftwareSecure regarding '
                'attempt_code {attempt_code}. We have been configured to allow for '
                'updates and will continue...'.format(
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
        review.raw_data = json.dumps(backend_review)
        review.student_id = attempt['user']['id']
        review.exam_id = attempt['proctored_exam']['id']
        # set reviewed_by to None because it was reviewed by our 3rd party
        # service provider, not a user in our database
        review.reviewed_by = None

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

        # we could have gotten a review for an archived attempt
        # this should *not* cause an update in our credit
        # eligibility table
        if review.review_status in SoftwareSecureReviewStatus.passing_statuses:
            attempt_status = ProctoredExamStudentAttemptStatus.verified
        elif not constants.REQUIRE_FAILURE_SECOND_REVIEWS:
            attempt_status = ProctoredExamStudentAttemptStatus.rejected
        else:
            # if we are not allowed to store 'rejected' on this
            # code path, then put status into 'second_review_required'
            attempt_status = ProctoredExamStudentAttemptStatus.second_review_required

        if review.review_status in SoftwareSecureReviewStatus.notify_support_for_status:
            instructor_service = get_runtime_service('instructor')
            if instructor_service:
                instructor_service.send_support_notification(
                    course_id=attempt['proctored_exam']['course_id'],
                    exam_name=attempt['proctored_exam']['exam_name'],
                    student_username=attempt['user']['username'],
                    review_status=review.review_status
                )

        if not attempt.get('is_archived', False):
            # updating attempt status will trigger workflow
            # (i.e. updating credit eligibility table)
            # archived attempts should not trigger the workflow
            update_attempt_status(
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
            raise StudentExamAttemptDoesNotExistsException('not found')
        self.make_review(attempt, request.data)
        return Response(data='OK')


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
                'Could not locate attempt_code: {attempt_code}'.format(attempt_code=attempt_code)
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
        if exam_id:
            exam = get_exam_by_id(exam_id)
        else:
            found_backend = None
            for exam in get_all_exams_for_course(course_id, True):
                exam_backend = exam['backend'] or settings.PROCTORING_BACKENDS.get('DEFAULT', None)
                if found_backend and exam_backend != found_backend:
                    # In this case, what are we supposed to do?!
                    # It should not be possible to get in this state, because
                    # course teams will be prevented from updating the backend after the course start date
                    error_message = "Multiple backends for course %r %r != %r" % (course_id,
                                                                                  found_backend,
                                                                                  exam['backend'])
                    return Response(data=error_message, status=400)
                else:
                    found_backend = exam_backend
        if exam is None:
            error = _('No exams in course {course_id}.').format(course_id=course_id)
        else:
            backend = get_backend_provider(exam)
            if backend:
                user = {
                    'id': request.user.id,
                    'full_name': request.user.get_full_name(),
                    'email': request.user.email
                }
                url = backend.get_instructor_url(exam['course_id'], user, exam_id=exam_id)
                if url:
                    return redirect(url)
                else:
                    error = _('No instructor dashboard for {proctor_service}').format(
                        proctor_service=backend.verbose_name)
            else:
                error = _('No proctored exams in course {course_id}').format(course_id=course_id)
        return Response(data=error, status=404, headers={'X-Frame-Options': 'sameorigin'})
