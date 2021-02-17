"""
Proctored Exams HTTP-based API endpoints
"""

import json
import logging
from urllib.parse import urlencode

import waffle
from crum import get_current_request
from rest_framework import status
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
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
    get_enrollments_for_course,
    get_exam_attempt_by_external_id,
    get_exam_attempt_by_id,
    get_exam_by_content_id,
    get_exam_by_id,
    get_user_attempts_by_exam_id,
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
from edx_proctoring.statuses import (
    InstructorDashboardOnboardingAttemptStatus,
    ProctoredExamStudentAttemptStatus,
    ReviewStatus,
    SoftwareSecureReviewStatus
)
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
        return Response(status=exc.http_status, data={'detail': str(exc)})


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
            resp = super().handle_exception(exc)
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


class StudentOnboardingStatusView(ProctoredAPIView):
    """
    Endpoint for the StudentOnboardingStatusView

    Supports:
        HTTP GET: returns the learner's onboarding status relative to the given course_id

    HTTP GET
        /edx_proctoring/v1/user_onboarding/status?course_id={course_id}&username={username}

    **Query Parameters**
        * 'course_id': The unique identifier for the course.
        * 'username': Optional. If not given, the endpoint will return the user's own status.
            ** In order to view other users' statuses, the user must be course or global staff.

    **Response Values**
        * 'onboarding_status': String specifying the learner's onboarding status.
            ** Will return NULL if there are no onboarding attempts, or the given user does not exist
        * 'onboarding_link': Link to the onboarding exam.
    """
    def get(self, request):
        """
        HTTP GET handler. Returns the learner's onboarding status.
        """
        data = {
            'onboarding_status': None,
            'onboarding_link': None
        }

        attempt_filters = {
            'proctored_exam__is_practice_exam': True,
            'taking_as_proctored': True,
            'user__username': request.user.username
        }

        username = request.GET.get('username')
        course_id = request.GET.get('course_id')

        if not course_id:
            # This parameter is currently required, as the onboarding experience is tied
            # to a single course. However, this could be dropped in future iterations.
            return Response(
                status=400,
                data={'detail': _('Missing required query parameter course_id')}
            )

        if username:
            # Check that the user is staff if trying to view another user's status
            if username != request.user.username:
                if ((course_id and not is_user_course_or_global_staff(request.user, course_id)) or
                        (not course_id and not request.user.is_staff)):
                    return Response(
                        status=status.HTTP_403_FORBIDDEN,
                        data={'detail': _('Must be a Staff User to Perform this request.')}
                    )
            attempt_filters['user__username'] = username

        # If there are multiple onboarding exams, use the first exam
        onboarding_exam = ProctoredExam.objects.filter(
            course_id=course_id,
            is_active=True,
            is_practice_exam=True,
            is_proctored=True
        ).order_by('-created').first()
        if (not onboarding_exam
                or not get_backend_provider(name=onboarding_exam.backend).supports_onboarding):
            return Response(
                status=404,
                data={'detail': _('There is no onboarding exam related to this course id.')}
            )

        user = get_user_model().objects.get(username=(username or request.user.username))
        serialized_onboarding_exam = ProctoredExamSerializer(onboarding_exam).data

        if not user.has_perm('edx_proctoring.can_take_proctored_exam', serialized_onboarding_exam):
            return Response(
                status=404,
                data={'detail': _('There is no exam accessible to this user.')}
            )

        # Also filter attempts by the course_id
        attempt_filters['proctored_exam__course_id'] = course_id

        data['onboarding_link'] = reverse('jump_to', args=[course_id, onboarding_exam.content_id])

        attempts = ProctoredExamStudentAttempt.objects.filter(**attempt_filters).order_by('-modified')
        if len(attempts) == 0:
            # If there are no attempts, return the data with 'onboarding_status' set to None
            return Response(data)

        # Default to the most recent attempt if there are no verified attempts
        relevant_attempt = attempts[0]
        for attempt in attempts:
            if attempt.status == ProctoredExamStudentAttemptStatus.verified:
                relevant_attempt = attempt
        data['onboarding_status'] = relevant_attempt.status

        return Response(data)


class StudentOnboardingStatusByCourseView(ProctoredAPIView):
    """
    Endpoint for the StudentOnboardingStatusByCourseView

    Supports:
        HTTP GET: return information about learners' onboarding status relative to the given course_id

    HTTP GET
        /edx_proctoring/v1/user_onboarding/status/course_id/{course_id}?page={}&text_search={}&status={}

    **Query Parameters**
        * page: Optional. The page of the paginated data requested. If this parameter is not provided,
          it defaults to 1.
        * text_search: Optional. A search string to perform a case insensitive search for users by either their username
          or email.
        * statuses: Optional. A string representing status(es) of InstructorDashboardOnboardingAttemptStatus
          to filter the exam attempts by.

    **Response Values**
        HTTP GET:
            The response will contain a dictionary with the following keys.
            * results: a list of dictionaries, where each dictionary contains the following
              information about a learner's onboarding status:
                * username: the user's username
                * status: the status of the user's onboarding attempt as should be displayed by
                  the Instructor Dashboard; it will be one of InstructorDashboardOnboardingAttemptStatus
                * modified: the date and time the user last modified the onboarding exam attempt;
                  the value will be None if no attempt in an onboarding exam exists for this user
            * count: the total number of results
            * previous: a link to the previous page of results, if it exists - None otherwise
            * next: a link to the next page of results, if it exists - None otherwise
            * num_pages: the total number of pages of results

    **Exceptions**
        HTTP GET:
            * 404 if the requesting user is not staff or course staff for the course associated with
            the supplied course ID
            * 404 if there is no onboarding exam in the course associated with the supplied course ID
    """
    @method_decorator(require_course_or_global_staff)
    def get(self, request, course_id):
        """
        HTTP GET handler.
        """
        # get last created onboarding exam if there are multiple
        onboarding_exam = (ProctoredExam.get_practice_proctored_exams_for_course(course_id)
                           .order_by('-created').first())
        if not onboarding_exam or not get_backend_provider(name=onboarding_exam.backend).supports_onboarding:
            return Response(
                status=404,
                data={'detail': _('There is no onboarding exam related to this course id.')}
            )
        serialized_onboarding_exam = ProctoredExamSerializer(onboarding_exam).data

        data_page = request.GET.get('page', 1)
        text_search = request.GET.get('text_search')
        statuses_filter = request.GET.get('statuses')

        enrollments = get_enrollments_for_course(course_id)
        # filter down enrollments for users that can take proctored exams
        allowed_enrollments_users = [
            enrollment.user
            for enrollment
            in enrollments
            if enrollment.user.has_perm('edx_proctoring.can_take_proctored_exam', serialized_onboarding_exam)
        ]

        # filter allowed_enrollments_users by text_search
        allowed_enrollments_users = self._filter_users_by_username_or_email(allowed_enrollments_users, text_search)

        # get exam attempts for users for the exam
        exam_attempts = ProctoredExamStudentAttempt.objects.get_exam_attempts_for_users_by_exam_id(
            onboarding_exam.id,
            allowed_enrollments_users
        ).values('user_id', 'status', 'modified')

        # select the most recent exam attempt per user
        exam_attempts_per_user = self._get_most_recent_exam_attempt_per_user(exam_attempts)

        onboarding_data = []
        for user in allowed_enrollments_users:
            user_attempt = exam_attempts_per_user.get(user.id, {})

            data = {}
            data['username'] = user.username
            data['status'] = (InstructorDashboardOnboardingAttemptStatus
                              .get_onboarding_status_from_attempt_status(user_attempt.get('status')))
            data['modified'] = user_attempt.get('modified')

            onboarding_data.append(data)

        # filter the data by status filter
        # we filter late than the text_search because users without exam attempts
        # will have an onboarding status of "not_started", and we want to be
        # able to filter on that status
        if statuses_filter:
            statuses = set(statuses_filter.split(','))
            onboarding_data = [
                data for data
                in onboarding_data
                if data['status'] in statuses
            ]

        query_params = self._get_query_params(text_search, statuses_filter)
        paginated_data = self._paginate_data(onboarding_data, data_page, onboarding_exam.course_id, query_params)
        return Response(paginated_data)

    def _get_query_params(self, text_search, statuses_filter):
        """
        Return the query parameters as a dictionary, only including key value pairs
        for supplied keys.

        Parameters:
        * text_search: the text search query parameter
        * statuses_filter: the statuses filter query parameter
        """
        query_params = {}
        if text_search:
            query_params['text_search'] = text_search
        if statuses_filter:
            query_params['statuses'] = statuses_filter
        return query_params

    def _get_most_recent_exam_attempt_per_user(self, attempts):
        """
        Given attempts, return, for each learner, their most recent exam attempt.

        Parameters:
        * attempts: an iterable of attempt objects
        """
        exam_attempts_per_user = {}
        for attempt in attempts:
            existing_attempt = exam_attempts_per_user.get(attempt['user_id'])

            if existing_attempt:
                if attempt['modified'] > existing_attempt['modified']:
                    exam_attempts_per_user[attempt['user_id']] = attempt
            else:
                exam_attempts_per_user[attempt['user_id']] = attempt

        return exam_attempts_per_user

    def _filter_users_by_username_or_email(self, users, text_search):
        """
        Given users, return users for whom there is insensitive partial or full match of
        either their username or email.

        Parameters:
        * users: users against which to do the search
        * text_search: the string aginst which to do a match
        """
        if text_search:
            text_search = text_search.lower()
            return [
                user
                for user in users
                if text_search in user.username.lower() or text_search in user.email.lower()
            ]
        return users

    def _paginate_data(self, data, page_number, course_id, query_params):
        """
        Given data and a page number, return the page of data requested by the page number,
        along with pagination metadata.

        Parameters:
        * data: the data to be paginated
        * page_number: the page number requested
        * course_id: the course ID associated with the data; this is used to generate next and previous links
        """
        paginator = Paginator(data, ATTEMPTS_PER_PAGE)
        data_page = paginator.get_page(page_number)

        return {
            'count': len(data),
            'previous': self._get_url(
                course_id, **query_params, page=data_page.number-1
                ) if data_page.has_previous() else None,
            'next': self._get_url(
                course_id, **query_params, page=data_page.number+1
                ) if data_page.has_next() else None,
            'num_pages': paginator.num_pages,
            'results': data_page.object_list,
        }

    def _get_url(self, course_id, **kwargs):
        """
        Get url for the view with correct query string.

        Parameters:
        * course_id: the course ID for the course
        * kwargs: the key value pairs to use in the query string
        """
        url = reverse('edx_proctoring:user_onboarding.status.course',
                      kwargs={'course_id': course_id}
                      )
        query_string = urlencode(kwargs)
        return url + '?' + query_string


class StudentProctoredExamAttempt(ProctoredAPIView):
    """
    Endpoint for the StudentProctoredExamAttempt
    /edx_proctoring/v1/proctored_exam/attempt

    Supports:
        HTTP PUT: Update an exam attempt's status.
        HTTP GET: Returns the status of an exam attempt.
        HTTP DELETE: Delete an exam attempt.


    HTTP PUT
    Updates the exam attempt status based on a provided action.
    PUT data : {
        ....
    }

    PUT Query Parameters
        'attempt_id': The unique identifier for the proctored exam attempt.

    PUT data Parameters
        'action': The action to perform on the proctored exam attempt, specified by the `attempt_id` query paremeter.

    **Response Values**
        * {'exam_attempt_id': ##}, The exam_attempt_id of the Proctored Exam Attempt.


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
        HTTP PUT handler to update exam attempt status based on an action.

        Parameters:
            request: The request object.
            attempt_id: The attempt ID of the proctored exam attempt whose status should be changed.

        Returns:
            A Response object containing the `exam_attempt_id`.

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

        course_id = attempt['proctored_exam']['id']
        user_id = request.user.id
        action = request.data.get('action')

        err_msg = (
            'Attempted to access attempt_id {attempt_id} but '
            'does not have access to it.'.format(
                attempt_id=attempt_id
            )
        )

        # only allow a staff user to change another user's exam attempt status via the 'mark_ready_to_resume' action
        # all other requests to change another user's attempt status raise a ProctoredExamPermissionDenied exception
        requested_user_id = request.data.get('user_id')
        if requested_user_id:
            if (course_id and is_user_course_or_global_staff(request.user, course_id)
                    and action == 'mark_ready_to_resume'):
                user_id = int(requested_user_id)
            else:
                raise ProctoredExamPermissionDenied(err_msg)

        # make sure the the attempt belongs to the user_id
        if attempt['user']['id'] != user_id:
            raise ProctoredExamPermissionDenied(err_msg)

        if action == 'stop':
            exam_attempt_id = stop_exam_attempt(
                attempt_id
            )
        elif action == 'start':
            exam_attempt_id = start_exam_attempt(
                exam_id=attempt['proctored_exam']['id'],
                user_id=user_id
            )
        elif action == 'submit':
            exam_attempt_id = update_attempt_status(
                attempt_id,
                ProctoredExamStudentAttemptStatus.submitted
            )
        elif action == 'click_download_software':
            exam_attempt_id = update_attempt_status(
                attempt_id,
                ProctoredExamStudentAttemptStatus.download_software_clicked
            )
        elif action == 'reset_attempt':
            exam_attempt_id = reset_practice_exam(
                attempt['proctored_exam']['id'],
                user_id,
                requesting_user=request.user,
            )
        elif action == 'error':
            backend = attempt['proctored_exam']['backend']
            waffle_name = PING_FAILURE_PASSTHROUGH_TEMPLATE.format(backend)
            should_block_user = not (backend and waffle.switch_is_active(waffle_name)) and (
                not attempt['status'] == ProctoredExamStudentAttemptStatus.submitted
            )
            if should_block_user:
                update_exam_attempt(
                    attempt_id,
                    time_remaining_seconds=get_time_remaining_for_attempt(attempt)
                )
                exam_attempt_id = update_attempt_status(
                    attempt_id,
                    ProctoredExamStudentAttemptStatus.error
                )
            else:
                exam_attempt_id = False
            LOG.warning('Browser JS reported problem with proctoring desktop '
                        'application. Did block user: %s, for attempt: %s',
                        should_block_user,
                        attempt['id'])
        elif action == 'decline':
            exam_attempt_id = update_attempt_status(
                attempt_id,
                ProctoredExamStudentAttemptStatus.declined
            )
        elif action == 'mark_ready_to_resume':
            exam_attempt_id = update_attempt_status(
                attempt_id,
                ProctoredExamStudentAttemptStatus.ready_to_resume
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
                     (_('an onboarding exam') if (provider and provider.supports_onboarding) else
                      _('a practice exam')))
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
                exam_attempt_id,
                ProctoredExamStudentAttemptStatus.declined
            )
        elif start_immediately:
            start_exam_attempt(exam_id, request.user.id)

        data = {'exam_attempt_id': exam_attempt_id}
        return Response(data)


class StudentProctoredGroupedExamAttemptsByCourse(ProctoredAPIView):
    """
    Endpoint for the StudentProctoredGroupedExamAttemptsByCourse

    Supports:
        HTTP GET: return information about learners' attempts

    **Expected Response**
        HTTP GET:
            The response will contain a dictionary with pagination info and a key `proctored_exam_attempts`
            * proctored_exam_attempts: a list of dictionaries, where each dictionary contains all fields
              for the most current exam attempt, and a key `all_attempts`, whose value
              is a list of all attempts associated with a user and exam

    **Exceptions**
        HTTP GET:
            * 403 if the requesting user is not staff or course staff for the course associated with
            the supplied course ID
    """
    @method_decorator(require_course_or_global_staff)
    def get(self, request, course_id, search_by=None):
        """
        HTTP GET Handler.
        """
        if search_by is not None:
            exam_attempts = ProctoredExamStudentAttempt.objects.get_filtered_exam_attempts(
                course_id, search_by
            )
            attempt_url = reverse('edx_proctoring:proctored_exam.attempts.grouped.search', args=[course_id, search_by])
        else:
            exam_attempts = ProctoredExamStudentAttempt.objects.get_all_exam_attempts(
                course_id
            )
            attempt_url = reverse('edx_proctoring:proctored_exam.attempts.grouped.course', args=[course_id])

        # get the most recent attempt for each unique user/exam combination
        most_recent_attempts = list(self._get_first_exam_attempt_per_user(exam_attempts).values())

        paginator = Paginator(most_recent_attempts, ATTEMPTS_PER_PAGE)
        page = request.GET.get('page')
        exam_attempts_page = paginator.get_page(page)

        grouped_attempts = []

        for attempt in exam_attempts_page.object_list:
            # serialize data
            serialized_attempt = ProctoredExamStudentAttemptSerializer(attempt).data
            user_id = serialized_attempt['user']['id']
            exam_id = serialized_attempt['proctored_exam']['id']
            # add all attempts that aren't the most recently created
            grouped_past_attempts = get_user_attempts_by_exam_id(user_id, exam_id)
            serialized_attempt['all_attempts'] = grouped_past_attempts
            grouped_attempts.append(serialized_attempt)

        response_data = {
            'proctored_exam_attempts': grouped_attempts,
            'pagination_info': {
                'has_previous': exam_attempts_page.has_previous(),
                'has_next': exam_attempts_page.has_next(),
                'current_page': exam_attempts_page.number,
                'total_pages': exam_attempts_page.paginator.num_pages,
            },
            'attempt_url': attempt_url

        }
        return Response(response_data)

    def _get_first_exam_attempt_per_user(self, attempts):
        """
        Given attempts, return, for each learner, their most recent exam attempt on each exam.

        Parameters:
        * attempts: an iterable of attempt objects, sorted by most recently created
        """
        exam_attempts_per_user = {}
        for attempt in attempts:
            # use unique combination of user id and exam id
            user_exam_key = str(attempt.user_id) + "-" + str(attempt.proctored_exam_id)
            existing_attempt = exam_attempts_per_user.get(user_exam_key)

            # we know that the first time we encounter a unique user_exam key, it will
            # be for the most recent attempt
            if not existing_attempt:
                exam_attempts_per_user[user_exam_key] = attempt

        return exam_attempts_per_user


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
        exam_attempts_page = paginator.get_page(page)

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
            LOG.warning(u"Attempt code %r cannot be found.", external_id)
            return Response(data='You have entered an exam code that is not valid.', status=404)
        if attempt['status'] in [ProctoredExamStudentAttemptStatus.created,
                                 ProctoredExamStudentAttemptStatus.download_software_clicked]:
            mark_exam_attempt_as_ready(attempt['id'])
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
                    'We already have a review submitted regarding '
                    'attempt_code {attempt_code}. We do not allow for updates!'.format(
                        attempt_code=attempt_code
                    )
                )
                raise ProctoredExamReviewAlreadyExists(err_msg)

            # we allow updates
            warn_msg = (
                'We already have a review submitted from our proctoring provider regarding '
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
                'User %(user)s does not have the required permissions to submit '
                'a review for attempt_code %(attempt_code)s.',
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
                    '{}?attempt={}'.format(
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
                'Attempted to access external exam id {external_id} but '
                'it does not exist.'.format(
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
                data=_('No exams in course {course_id}.').format(course_id=course_id),
                status=404,
                headers={'X-Frame-Options': 'sameorigin'}
            )
        if not backend:
            return Response(
                data=_('No proctored exams in course {course_id}').format(course_id=course_id),
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
                data=_('No instructor dashboard for {proctor_service}').format(
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
    def post(self, request, user_id, **kwargs):  # pylint: disable=unused-argument
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
                LOG.info('retiring user %s from %s', user_id, backend_name)
                try:
                    result = get_backend_provider(name=backend_name).retire_user(backend_user_id)
                except ProctoredBaseException:
                    LOG.exception('attempting to delete %s (%s) from %s', user_id, backend_user_id, backend_name)
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


class StudentProctoredExamResetAttempts(ProctoredAPIView):
    """
    Endpoint for deleting all attempts associated with a given exam and a given user
    """

    @method_decorator(require_course_or_global_staff)
    def delete(self, request, exam_id, user_id):
        """
        HTTP DELETE handler, deletes all attempts for a given exam and username
        """
        attempts = ProctoredExamStudentAttempt.objects.filter(user_id=user_id, proctored_exam_id=exam_id)
        if len(attempts) == 0:
            return Response(data='There are no attempts related to this user id and exam id', status=404)
        for attempt in attempts:
            remove_exam_attempt(attempt.id, request.user)
        return Response()
