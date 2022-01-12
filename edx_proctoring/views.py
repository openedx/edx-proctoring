"""
Proctored Exams HTTP-based API endpoints
"""

import codecs
import json
import logging
from urllib.parse import urlencode

import waffle  # pylint: disable=invalid-django-waffle-import
from crum import get_current_request
from edx_django_utils.monitoring import set_custom_attribute
from opaque_keys.edx.locator import BlockUsageLocator
from rest_framework import status
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _

from edx_proctoring import constants
from edx_proctoring.api import (
    add_allowance_for_user,
    add_bulk_allowances,
    check_prerequisites,
    create_exam,
    create_exam_attempt,
    get_active_exams_for_user,
    get_all_exams_for_course,
    get_allowances_for_course,
    get_backend_provider,
    get_current_exam_attempt,
    get_enrollments_can_take_proctored_exams,
    get_exam_attempt_by_external_id,
    get_exam_attempt_by_id,
    get_exam_attempt_data,
    get_exam_by_content_id,
    get_exam_by_id,
    get_last_verified_onboarding_attempts_per_user,
    get_onboarding_attempt_data_for_learner,
    get_onboarding_exam_link,
    get_proctoring_settings_by_exam_id,
    get_review_policy_by_exam_id,
    get_total_allowed_time_for_exam,
    get_user_attempts_by_exam_id,
    is_exam_passed_due,
    mark_exam_attempt_as_ready,
    mark_exam_attempt_as_ready_to_resume,
    remove_allowance_for_user,
    remove_exam_attempt,
    reset_practice_exam,
    start_exam_attempt,
    stop_exam_attempt,
    update_attempt_status,
    update_exam,
    update_exam_attempt
)
from edx_proctoring.constants import (
    ONBOARDING_PROFILE_INSTRUCTOR_DASHBOARD_API,
    PING_FAILURE_PASSTHROUGH_TEMPLATE,
    REDS_API_REDIRECT
)
from edx_proctoring.exceptions import (
    AllowanceValueNotAllowedException,
    BackendProviderOnboardingProfilesException,
    ProctoredBaseException,
    ProctoredExamNotFoundException,
    ProctoredExamPermissionDenied,
    ProctoredExamReviewAlreadyExists,
    ProctoredExamReviewPolicyNotFoundException,
    StudentExamAttemptDoesNotExistsException
)
from edx_proctoring.models import (
    ProctoredExam,
    ProctoredExamSoftwareSecureComment,
    ProctoredExamSoftwareSecureReview,
    ProctoredExamStudentAllowance,
    ProctoredExamStudentAllowanceHistory,
    ProctoredExamStudentAttempt
)
from edx_proctoring.runtime import get_runtime_service
from edx_proctoring.serializers import (
    ProctoredExamSerializer,
    ProctoredExamStudentAllowanceSerializer,
    ProctoredExamStudentAttemptSerializer
)
from edx_proctoring.statuses import (
    InstructorDashboardOnboardingAttemptStatus,
    ProctoredExamStudentAttemptStatus,
    ReviewStatus,
    SoftwareSecureReviewStatus,
    VerificientOnboardingProfileStatus
)
from edx_proctoring.utils import (
    AuthenticatedAPIView,
    categorize_inaccessible_exams_by_date,
    encrypt_and_encode,
    get_exam_type,
    get_exam_url,
    get_time_remaining_for_attempt,
    get_user_course_outline_details,
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
        course_id = request.data.get('course_id') or kwargs.get('course_id', None)
        exam_id = request.data.get('exam_id') or kwargs.get('exam_id', None)
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


class ProctoredExamAttemptView(ProctoredAPIView):
    """
    Endpoint for getting timed or proctored exam and its attempt data.
    /edx_proctoring/v1/proctored_exam/attempt/course_id/{course_id}

    Supports:
        HTTP GET:
            ** Scenarios **
            ?content_id=123
            returns an existing exam
            ?is_learning_mfe=true
            returns attempt data with `exam_url_path` built for the learning mfe

            Returns an existing exam (by course_id and content id) with latest related attempt.
            and active attempt for any exam in progress (for the timer feature)
            {
                'exam': {
                    ...
                    attempt: { ... }
                },
                'active_attempt': { ... },
            }
    """
    def get(self, request, course_id, content_id=None):
        """
        HTTP GET handler. Returns exam with attempt and active attempt
        """
        active_attempt_data = {}
        attempt_data = {}
        active_exam = {}

        is_learning_mfe = request.GET.get('is_learning_mfe') in ['1', 'true', 'True']
        content_id = request.GET.get('content_id', content_id)

        active_exams = get_active_exams_for_user(request.user.id)
        if active_exams:
            # Even if there is more than one exam, we want the first one.
            # Normally this should not be an issue as there will be list of one item.
            active_exam_info = active_exams[0]
            active_exam = active_exam_info['exam']
            active_attempt = active_exam_info['attempt']
            active_attempt_data = get_exam_attempt_data(
                active_exam.get('id'),
                active_attempt.get('id'),
                is_learning_mfe=is_learning_mfe
            )

        if not content_id:
            response_dict = {
                'exam': {},
                'active_attempt': active_attempt_data,
            }
            return Response(data=response_dict, status=status.HTTP_200_OK)

        if active_exam and active_exam.get('course_id') == course_id and active_exam.get('content_id') == content_id:
            exam = active_exam
            exam.update({'attempt': active_attempt_data})
        else:
            try:
                exam = get_exam_by_content_id(course_id, content_id)
                attempt = get_current_exam_attempt(exam.get('id'), request.user.id)
                if attempt:
                    attempt_data = get_exam_attempt_data(
                        exam.get('id'),
                        attempt.get('id'),
                        is_learning_mfe=is_learning_mfe
                    )
                else:
                    # calculate total allowed time for the exam including
                    # allowance time to show on the MFE entrance pages
                    exam['total_time'] = get_total_allowed_time_for_exam(exam, request.user.id)

                    # Exam hasn't been started yet but it is proctored so needs to be checked
                    # if prerequisites are satisfied. We only do this for proctored exam hence
                    # additional check 'not exam['is_practice_exam']', meaning we do not check
                    # prerequisites for practice or onboarding exams
                    if exam['is_proctored'] and not exam['is_practice_exam']:
                        exam = check_prerequisites(exam, request.user.id)

                # if user hasn't completed required onboarding exam before taking
                # proctored exam we need to navigate them to it with a link
                if (exam['is_proctored'] and attempt_data and
                        attempt_data['attempt_status'] in ProctoredExamStudentAttemptStatus.onboarding_errors):
                    exam['onboarding_link'] = get_onboarding_exam_link(course_id, request.user, is_learning_mfe)
                exam.update({'attempt': attempt_data})
            except ProctoredExamNotFoundException:
                exam = {}
        if exam:
            provider = get_backend_provider(exam)
            exam['type'] = get_exam_type(exam, provider)['type']
            exam['passed_due_date'] = is_exam_passed_due(exam, user=request.user.id)
        response_dict = {
            'exam': exam,
            'active_attempt': active_attempt_data,
        }

        return Response(data=response_dict, status=status.HTTP_200_OK)


class ProctoredSettingsView(ProctoredAPIView):
    """
    Endpoint for getting settings for proctored exam.

    edx_proctoring/v1/settings/exam_id/{exam_id}

    Supports:
        HTTP GET:
            ** Scenarios **
            Returns proctoring_settings and exam_proctoring_backend config for proctored exam
            {
                "contact_us": "support@example.com"
                "platform_name": "Platform Name"
                "link_urls": { ... },
                "exam_proctoring_backend": { ... }
            }

    """
    def get(self, request, exam_id):
        """
        HTTP GET handler. Returns proctoring_settings and exam_proctoring_backend config for proctored exam.
        """
        response_dict = get_proctoring_settings_by_exam_id(exam_id)

        return Response(data=response_dict, status=status.HTTP_200_OK)


class ProctoredExamReviewPolicyView(ProctoredAPIView):
    """
    Endpoint for getting review policy for proctored exam.

    edx_proctoring/v1/proctored_exam/review_policy/exam_id/{exam_id}

    Supports:
        HTTP GET:
            ** Scenarios **
            Returns review policy for proctored exam
            {
                "review_policy": "Example review policy."
            }

    """
    def get(self, request, exam_id):
        """
        HTTP GET handler. Returns review policy for proctored exam.
        """
        try:
            review_policy = get_review_policy_by_exam_id(exam_id)['review_policy']
        except ProctoredExamReviewPolicyNotFoundException as exc:
            LOG.warning(str(exc))
            review_policy = None
        return Response(data=dict(review_policy=review_policy), status=status.HTTP_200_OK)


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
        /edx_proctoring/v1/user_onboarding/status?course_id={course_id}&username={username}&is_learning_mfe={}

    **Query Parameters**
        * 'course_id': The unique identifier for the course.
        * 'username': Optional. If not given, the endpoint will return the user's own status.
            ** In order to view other users' statuses, the user must be course or global staff.
        * 'is_learning_mfe': Optional. If set to True, onboarding link will point to the learning mfe application page.

    **Response Values**
        * 'onboarding_status': String specifying the learner's onboarding status.
            ** Will return NULL if there are no onboarding attempts, or the given user does not exist
        * 'onboarding_link': Link to the onboarding exam, if the exam is currently available to the learner.
        * 'onboarding_expiration_date': If the learner's onboarding profile is approved in a different
          course, the expiration date will be included. Will return NULL otherwise.
        * 'onboarding_release_date': The date that the onboarding exam will be released.
        * 'onboarding_past_due': Whether the onboarding exam is past due. All onboarding exams in the course must
          be past due in order for onboarding_past_due to be true.
    """
    def get(self, request):  # pylint: disable=too-many-statements
        """
        HTTP GET handler. Returns the learner's onboarding status.
        """
        data = {
            'onboarding_status': None,
            'onboarding_link': None,
            'expiration_date': None,
            'onboarding_past_due': False,
        }

        username = request.GET.get('username')
        course_id = request.GET.get('course_id')
        is_learning_mfe = request.GET.get('is_learning_mfe') in ['1', 'true', 'True']

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
                if (
                    (course_id and not is_user_course_or_global_staff(request.user, course_id)) or
                    (not course_id and not request.user.is_staff)
                ):
                    return Response(
                        status=status.HTTP_403_FORBIDDEN,
                        data={'detail': _('Must be a Staff User to Perform this request.')}
                    )

        # If there are multiple onboarding exams, use the last created exam accessible to the user
        onboarding_exams = list(ProctoredExam.get_practice_proctored_exams_for_course(course_id).order_by('-created'))
        if not onboarding_exams or not get_backend_provider(name=onboarding_exams[0].backend).supports_onboarding:
            return Response(
                status=404,
                data={'detail': _('There is no onboarding exam related to this course id.')}
            )

        # If there are multiple onboarding exams, use the first exam accessible to the user
        backend = get_backend_provider(name=onboarding_exams[0].backend)

        user = get_user_model().objects.get(username=(username or request.user.username))
        details = get_user_course_outline_details(user, course_id)

        # in order to gather information about future or past due exams, we must determine which exams
        # are inaccessible for other reasons (e.g. visibility settings, content gating, etc.), so that
        # we can correctly filter them out of the onboarding exams in the course
        categorized_exams = categorize_inaccessible_exams_by_date(onboarding_exams, details)
        (non_date_inaccessible_exams, future_exams, past_due_exams) = categorized_exams

        # remove onboarding exams not accessible to learners
        for onboarding_exam in non_date_inaccessible_exams:
            onboarding_exams.remove(onboarding_exam)

        if not onboarding_exams:
            LOG.info(
                'User user_id=%(user_id)s has no accessible onboarding exams in course course_id=%(course_id)s',
                {
                    'user_id': user.id,
                    'course_id': course_id,
                }
            )
            return Response(
                status=404,
                data={'detail': _('There is no onboarding exam accessible to this user.')}
            )

        currently_available_exams = [
            onboarding_exam
            for onboarding_exam in onboarding_exams
            if onboarding_exam not in future_exams and onboarding_exam not in past_due_exams
        ]

        if currently_available_exams:
            onboarding_exam = currently_available_exams[0]
            data['onboarding_link'] = get_exam_url(course_id, onboarding_exam.content_id, is_learning_mfe)
        elif future_exams:
            onboarding_exam = future_exams[0]
        else:
            data['onboarding_past_due'] = True
            onboarding_exam = past_due_exams[0]

        onboarding_exam_usage_key = BlockUsageLocator.from_string(onboarding_exam.content_id)
        effective_start = details.schedule.sequences.get(onboarding_exam_usage_key).effective_start
        data['onboarding_release_date'] = effective_start.isoformat()
        data['review_requirements_url'] = backend.help_center_article_url

        # get onboarding attempt info for the learner from django model
        onboarding_attempt_data = get_onboarding_attempt_data_for_learner(course_id, user, onboarding_exam.backend)
        data['onboarding_status'] = onboarding_attempt_data['onboarding_status']
        data['expiration_date'] = onboarding_attempt_data['expiration_date']

        if constants.ONBOARDING_PROFILE_API:
            try:
                obs_user_id = obscured_user_id(user.id, onboarding_exam.backend)
                onboarding_profile_data = backend.get_onboarding_profile_info(course_id, user_id=obs_user_id)
            except BackendProviderOnboardingProfilesException as exc:
                # if backend raises exception, log message and return data from onboarding exam attempt
                LOG.warning(
                    'Failed to use backend onboarding status API endpoint for user_id=%(user_id)s'
                    'in course_id=%(course_id)s because backend failed to respond. Onboarding status'
                    'will be determined by the user\'s onboarding attempts. '
                    'Status: %(status)s, Response: %(response)s.',
                    {
                        'user_id': user.id,
                        'course_id': course_id,
                        'response': str(exc),
                        'status': exc.http_status,
                    }
                )
                return Response(data)

            if onboarding_profile_data is None:
                return Response(
                    data=_('No onboarding status API for {proctor_service}').format(
                        proctor_service=backend.verbose_name
                    ),
                    status=404,
                )

            readable_status = \
                VerificientOnboardingProfileStatus.get_edx_status_from_profile_status(
                    onboarding_profile_data['status']
                )
            expiration_date = onboarding_profile_data['expiration_date']

            if readable_status != data['onboarding_status']:
                LOG.error(
                    'Backend onboarding status API endpoint info for user_id=%(user_id)s'
                    'in course_id=%(course_id)s differs from system info. Endpoint onboarding attempt'
                    'has status=%(endpoint_status)s. System onboarding attempt has status=%(system_status)s.',
                    {
                        'user_id': user.id,
                        'course_id': course_id,
                        'endpoint_status': readable_status,
                        'system_status': data['onboarding_status'],
                    }
                )

            data['onboarding_status'] = readable_status
            data['expiration_date'] = expiration_date
            LOG.info(
                'Used backend onboarding status API endpoint to retrieve user_id=%(user_id)s'
                'in course_id=%(course_id)s',
                {
                    'user_id': user.id,
                    'course_id': course_id,
                }
            )

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
                * enrollment_mode: the user's enrollment mode for the course
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
        # pylint: disable=too-many-statements

        # get last created onboarding exam if there are multiple
        onboarding_exam = (ProctoredExam.get_practice_proctored_exams_for_course(course_id)
                           .order_by('-created').first())
        if not onboarding_exam or not get_backend_provider(name=onboarding_exam.backend).supports_onboarding:
            return Response(
                status=404,
                data={'detail': _('There is no onboarding exam related to this course id.')}
            )

        data_page = request.GET.get('page', 1)
        text_search = request.GET.get('text_search')
        status_filters = request.GET.get('statuses')

        enrollments = get_enrollments_can_take_proctored_exams(course_id, text_search)
        users = []
        enrollment_modes_by_user_id = {}
        for enrollment in enrollments:
            users.append(enrollment.user)
            enrollment_modes_by_user_id[enrollment.user.id] = enrollment.mode

        onboarding_data = []
        use_onboarding_profile_api = waffle.switch_is_active(ONBOARDING_PROFILE_INSTRUCTOR_DASHBOARD_API)

        # add custom attribute to better track performance of this endpoint against the
        # number of proctoring eligible enrollments in the given course
        set_custom_attribute('num_proctoring_eligible_enrollments', len(enrollments))
        set_custom_attribute('onboarding_profile_api_enabled', use_onboarding_profile_api)

        if use_onboarding_profile_api:
            backend = get_backend_provider(name=onboarding_exam.backend)

            onboarding_profile_info, api_response_error = self._get_onboarding_info(
                backend,
                course_id,
                status_filters
            )

            if api_response_error:
                # if backend raises exception, log message and return data from onboarding exam attempt
                LOG.warning(
                    'Failed to use backend onboarding status API endpoint for course_id=%(course_id)s'
                    'with query parameters text_search: %(text_search_filter)s, status: %(status_filters)s'
                    'because backend failed to respond. Onboarding status'
                    'will be determined by the users\'s onboarding attempts. '
                    'Status: %(status)s, Response: %(response)s.',
                    {
                        'course_id': course_id,
                        'text_search_filter': text_search,
                        'status_filters': status_filters,
                        'response': str(api_response_error),
                        'status': api_response_error.http_status,
                    }
                )

                return Response(
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    data={'detail': _('The onboarding service is temporarily unavailable. Please try again later.')}
                )

            LOG.info(
                'Backend onboarding API returned %(num_profiles)s from the proctoring provider '
                'for course %(course_id)s.',
                {
                    'num_profiles': len(onboarding_profile_info),
                    'course_id': course_id,
                }
            )

            obscured_user_ids_to_users = {obscured_user_id(user.id, onboarding_exam.backend): user for user in users}

            missing_user_ids = []
            for onboarding_profile in onboarding_profile_info:
                obscured_id = onboarding_profile['user_id']
                user = obscured_user_ids_to_users.get(obscured_id)

                if not user:
                    missing_user_ids.append(onboarding_profile['user_id'])
                    continue

                onboarding_status = onboarding_profile['status']
                data = {
                    'username': user.username,
                    'enrollment_mode': enrollment_modes_by_user_id.get(user.id),
                    'status': VerificientOnboardingProfileStatus.get_instructor_status_from_profile_status(
                        onboarding_status
                    ),
                    'modified': None,
                }
                onboarding_data.append(data)
                del obscured_user_ids_to_users[obscured_id]

            if missing_user_ids:
                LOG.warning(
                    'Users are present in response whose obscured user IDs do not exist in list of learners '
                    'enrolled in course %(course_id)s with proctoring eligible enrollments. There are a total '
                    'of %(num_missing_ids)s of these. A sample of these IDs is %(obs_id_sample)s.',
                    {
                        'course_id': course_id,
                        'num_missing_ids': len(missing_user_ids),
                        'obs_id_sample': missing_user_ids[0:5],
                    }
                )

            if status_filters is None or 'not_started' in status_filters:
                for (obscured_id, user) in obscured_user_ids_to_users.items():
                    # remaining learners that are not represented in the API response
                    # have not started onboarding
                    data = {
                        'username': user.username,
                        'enrollment_mode': enrollment_modes_by_user_id.get(user.id),
                        'status': InstructorDashboardOnboardingAttemptStatus.not_started,
                        'modified': None,
                    }
                    onboarding_data.append(data)
        else:
            onboarding_data = self._get_onboarding_info_no_onboarding_api(
                course_id,
                onboarding_exam,
                users,
                enrollment_modes_by_user_id,
            )
            onboarding_data = self._filter_onboarding_data_by_status_filters(onboarding_data, status_filters)

        query_params = self._get_query_params(text_search, status_filters)
        paginated_data = self._paginate_data(onboarding_data, data_page, onboarding_exam.course_id, query_params)

        # add modified time to each user in the paginated data, as Verificient's API does not currently return this data
        results = paginated_data['results']
        response_users = [get_user_model().objects.get(username=(user['username'])) for user in results]
        response_onboarding_data = self._get_onboarding_info_no_onboarding_api(
            course_id,
            onboarding_exam,
            response_users,
            enrollment_modes_by_user_id
        )

        # Get modified date for each learner. Once the onboarding provider has included
        # a modified date in their payload, this can be removed.
        modified_dict = {}
        for attempt in response_onboarding_data:
            username = attempt['username']
            modified_dict[username] = attempt['modified']

        for user in results:
            user['modified'] = modified_dict[user['username']]

        paginated_data['results'] = results
        paginated_data['use_onboarding_profile_api'] = use_onboarding_profile_api

        return Response(paginated_data)

    def _get_onboarding_info_no_onboarding_api(self, course_id, onboarding_exam, users, enrollment_modes_by_user_id):
        """
        Get the onboarding data for a list of users without using the proctoring provider's onboarding API.
        This is used as fallback behavior either when the ONBOARDING_PROFILE_INSTRUCTOR_DASHBOARD_API waffle
        flag is not enabled or when the aforementioned flag is enabled but the API call fails.

        Parameters:
        * course_id: the course ID of the course
        * onboarding_exam: the ProctoredExam object representing the onboarding exam in the course
        * users: a list of users for whom we should return onboarding profile data
        * enrollment_modes_by_user_id: a mapping between users and their enrollment mode in the course
        """
        # get onboarding attempts for users for the course
        onboarding_attempts = ProctoredExamStudentAttempt.objects.get_proctored_practice_attempts_by_course_id(
            course_id,
            users
        ).values('user_id', 'status', 'modified', 'id')

        # get all of the last verified onboarding attempts of these users
        last_verified_attempt_dict = get_last_verified_onboarding_attempts_per_user(
            users,
            onboarding_exam.backend,
        )

        # select a verified, or most recent, exam attempt per user
        onboarding_attempts_per_user = self._get_relevant_attempt_per_user(onboarding_attempts)
        onboarding_data = []
        for user in users:
            user_attempt = onboarding_attempts_per_user.get(user.id, {})
            other_verified_attempt = last_verified_attempt_dict.get(user.id)

            data = {
                'username': user.username,
                'enrollment_mode': enrollment_modes_by_user_id.get(user.id),
            }

            if (
                other_verified_attempt and
                (
                    not user_attempt or
                    (user_attempt and user_attempt.get('status') != ProctoredExamStudentAttemptStatus.verified)
                )
            ):
                data['status'] = InstructorDashboardOnboardingAttemptStatus.other_course_approved
                data['modified'] = other_verified_attempt.modified
            else:
                attempt_status = user_attempt.get('status')

                # If the learner's most recent attempt is in the "onboarding_reset" state,
                # return the onboarding_reset_past_due state.
                # This is a consequence of a bug in our software that allows a learner to end up
                # with their only or their most recent exam attempt being in the "onboarding_reset" state.
                # The learner should not end up in this state, but while we work on a fix, we should not
                # display "null" in the Instructor Dashboard Student Onboarding Panel.
                # TODO: remove as part of MST-745
                if user_attempt.get('status') == ProctoredExamStudentAttemptStatus.onboarding_reset:
                    onboarding_status = InstructorDashboardOnboardingAttemptStatus.onboarding_reset_past_due
                else:
                    onboarding_status = \
                        InstructorDashboardOnboardingAttemptStatus.get_onboarding_status_from_attempt_status(
                            attempt_status
                        )

                data['status'] = onboarding_status
                data['modified'] = user_attempt.get('modified')

            onboarding_data.append(data)

        return onboarding_data

    def _filter_onboarding_data_by_status_filters(self, onboarding_data, status_filters):
        """
        Filter the list of dictionaries onboarding_data by status_filters.

        Parameters:
        * onboarding_data: a list of dictionaries representing learners's onboarding profile information
        * status_filters: a comma separated list of statuses to filter onboarding_data by
        """
        # filter the data by status filter
        # we filter late than the text_search because users without exam attempts
        # will have an onboarding status of "not_started", and we want to be
        # able to filter on that status
        filtered_onboarding_data = onboarding_data
        if status_filters:
            statuses = set(status_filters.split(','))
            filtered_onboarding_data = [
                data for data
                in onboarding_data
                if data['status'] in statuses
            ]

        return filtered_onboarding_data

    def _get_query_params(self, text_search, status_filters):
        """
        Return the query parameters as a dictionary, only including key value pairs
        for supplied keys.

        Parameters:
        * text_search: the text search query parameter
        * status_filters: the statuses filter query parameter
        """
        query_params = {}
        if text_search:
            query_params['text_search'] = text_search
        if status_filters:
            query_params['statuses'] = status_filters
        return query_params

    def _get_relevant_attempt_per_user(self, attempts):
        """
        Given an ordered list of attempts, return, for each learner, their most recent
        exam attempt. If the learner has a verified attempt, always return verified.
        If possible, do not return a reset attempt.
        Parameters:
        * attempts: an iterable of attempt objects
        """
        onboarding_attempts_per_user = {}

        for attempt in attempts:
            existing_attempt = onboarding_attempts_per_user.get(attempt['user_id'])

            if existing_attempt:
                # Always return a verified attempt if it exists.
                if attempt['status'] == ProctoredExamStudentAttemptStatus.verified:
                    onboarding_attempts_per_user[attempt['user_id']] = attempt
                # Always return a non reset attempt if its ID is greater
                if (
                    existing_attempt['status'] == ProctoredExamStudentAttemptStatus.onboarding_reset
                    and existing_attempt['id'] < attempt['id']
                ):
                    onboarding_attempts_per_user[attempt['user_id']] = attempt
            else:
                onboarding_attempts_per_user[attempt['user_id']] = attempt

        return onboarding_attempts_per_user

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

    def _get_onboarding_info(self, backend, course_id, status_filters):
        """
        Get a list of all onboarding profiles from the proctoring provider
        """
        http_error = None
        results = []
        onboarding_profile_kwargs = {}

        if not status_filters:
            status_filters = [None]
        else:
            status_filters = status_filters.split(',')

        onboarding_status_filters = [
            VerificientOnboardingProfileStatus.get_profile_status_from_filter(status_filter)
            for status_filter in status_filters
            if status_filter is not None
        ]
        onboarding_status_filter_string = ",".join(onboarding_status_filters)
        onboarding_profile_kwargs['status'] = onboarding_status_filter_string

        LOG.info(
            'Onboarding profile kwargs for course %(course_id)s are %(onboarding_kwargs)s.',
            {
                'course_id': course_id,
                'onboarding_kwargs': onboarding_profile_kwargs,
            }
        )
        try:
            request = backend.get_onboarding_profile_info(
                course_id, **onboarding_profile_kwargs
            )
            return request.get('results'), http_error
        except BackendProviderOnboardingProfilesException as exc:
            http_error = exc
            # return on the earliest error
            return results, http_error


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
        user_id = request.user.id

        if not attempt:
            err_msg = (
                f'Attempted to get attempt_id={attempt_id} but this attempt does not '
                'exist.'
            )
            raise StudentExamAttemptDoesNotExistsException(err_msg)
        # make sure the the attempt belongs to the calling user_id
        if attempt['user']['id'] != user_id:
            err_msg = (
                f'user_id={user_id} attempted to get attempt_id={attempt_id} but '
                'does not have authorization.'
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
        user_id = request.user.id

        if not attempt:
            err_msg = (
                f'Attempted to update attempt_id={attempt_id} but it does not exist.'
            )
            raise StudentExamAttemptDoesNotExistsException(err_msg)

        course_id = attempt['proctored_exam']['course_id']
        action = request.data.get('action')
        detail = request.data.get('detail')

        err_msg = (
            f'user_id={user_id} attempted to update attempt_id={attempt_id} in '
            f'course_id={course_id} but does not have access to it. (action={action})'
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
            LOG.warning(
                'Browser JS reported problem with proctoring desktop application. Error detail: '
                '%(error_detail)s. Did block user: %(should_block_user)s. user_id=%(user_id)s, '
                'course_id=%(course_id)s, exam_id=%(exam_id)s, attempt_id=%(attempt_id)s',
                {
                    'should_block_user': should_block_user,
                    'user_id': user_id,
                    'course_id': course_id,
                    'exam_id': attempt['proctored_exam']['id'],
                    'attempt_id': attempt_id,
                    'error_detail': detail,
                }
            )
        elif action == 'decline':
            exam_attempt_id = update_attempt_status(
                attempt_id,
                ProctoredExamStudentAttemptStatus.declined
            )
        elif action == 'mark_ready_to_resume':
            exam_attempt_id = mark_exam_attempt_as_ready_to_resume(attempt_id)

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
                f'Attempted to delete attempt_id={attempt_id} but this attempt does not '
                'exist.'
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
            response_dict = get_exam_attempt_data(exam.get('id'), attempt.get('id'))

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
        user_id = request.user.id
        exam = get_exam_by_id(exam_id)

        # Bypassing the due date check for practice exam
        # because student can attempt the practice after the due date
        if not exam.get("is_practice_exam") and is_exam_passed_due(exam, request.user):
            raise ProctoredExamPermissionDenied(
                f'user_id={user_id} attempted to create an attempt for expired exam '
                f"with exam_id={exam_id} in course_id={exam['course_id']}"
            )

        exam_attempt_id = create_exam_attempt(
            exam_id=exam_id,
            user_id=user_id,
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
            start_exam_attempt(exam_id, user_id)

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


class ExamBulkAllowanceView(ProctoredAPIView):
    """
    Endpoint for the Exam Allowance
    /edx_proctoring/v1/proctored_exam/bulk_allowance

    Supports:
        HTTP PUT: Creates or Updates the allowances for multiple users and multiple exams.

    HTTP PUT
    Adds or updates multiple exam and student allowances.
    PUT data : {
        "course_id": "a/b/c",
        "exam_ids": [1, 2, 3],
        "user_ids": [1, 2],
        "allowance_type": 'extra_time',
        "value": '10'
    }

    **PUT data Parameters**
        * course_id: ID of the course, used to determine if the requesting user is course staff.
        * exam_ids: The set of unique identifiers for the exams.
        * user_ids: The set of unique identifiers for the students.
        * allowance_type: key for the allowance entry, either ADDITIONAL_TIME or TIME_MULTIPLIER
        * value: value for the allowance entry.

    **Response Values**
        * returns Nothing. Add or update the allowances for the users and exams.
    """

    @method_decorator(require_course_or_global_staff)
    def put(self, request, course_id=None):  # pylint: disable=unused-argument
        """
        HTTP PUT handler. Adds or updates Allowances for many exams and students
        """
        try:
            exams = request.data.get('exam_ids', '')
            users = request.data.get('user_ids', '')

            # We need to remove whitespace from the exam ids as they are ints
            filtered_ids = ''.join(exams.split())
            filtered_users = ''.join(users.split())
            data, successes, failures = add_bulk_allowances(
                # We only want to pass ints that are not empty
                exam_ids=[each_exam for each_exam in filtered_ids.split(',') if each_exam],
                user_ids=[each_user.strip() for each_user in filtered_users.split(',') if each_user],
                allowance_type=request.data.get('allowance_type', None),
                value=request.data.get('value', None)
            )
            if successes == 0:
                return Response(
                    status=status.HTTP_400_BAD_REQUEST,
                    data={"detail": _("Enter a valid username or email"), "field": _("user_info")}
                )
            if failures > 0:
                return Response(
                    status=status.HTTP_207_MULTI_STATUS,
                    data=data
                )
            return Response(
                    status=status.HTTP_200_OK
            )
        except AllowanceValueNotAllowedException:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={"detail": _("Enter a valid positive value number"), "field": _("allowance_value")}
                )


class GroupedExamAllowancesByStudent(ProctoredAPIView):
    """
    Endpoint for the StudentProctoredGroupedExamAttemptsByCourse

    Supports:
        HTTP GET: return information about learners' allowances

    **Expected Response**
        HTTP GET:
            The response will contain a dictionary with the allowances of a course grouped by student.
            For example:
            {{'student1':
                        [{'id': 4, 'created': '2021-06-21T14:47:17.847221Z',
                        'modified': '2021-06-21T14:47:17.847221Z',
                        'user': {'id': 4, 'username': 'student1',
                        'email': 'student1@test.com'},
                        'key': 'additional_time_granted', 'value': '30',
                        'proctored_exam': {'id': 2, 'course_id': 'a/b/c', 'content_id': 'test_content2',
                        'external_id': None, 'exam_name': 'Test Exam2', 'time_limit_mins': 90,
                        'is_proctored': False, 'is_practice_exam': False,
                        'is_active': True, 'due_date': None,
                        'hide_after_due': False, 'backend': None}}}

    **Exceptions**
        HTTP GET:
            * 403 if the requesting user is not staff or course staff for the course associated with
            the supplied course ID
    """
    @method_decorator(require_course_or_global_staff)
    def get(self, request, course_id):
        """
        HTTP GET Handler.
        """

        # Get all allowances from the course
        all_allowances = ProctoredExamStudentAllowance.get_allowances_for_course(course_id)

        grouped_allowances = {}

        # Process allowances so they are grouped by username
        for allowance in all_allowances:
            serialied_allowance = ProctoredExamStudentAllowanceSerializer(allowance).data
            username = serialied_allowance['user']['username']
            grouped_allowances.setdefault(username, []).append(serialied_allowance)

        response_data = grouped_allowances

        return Response(response_data)


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
        HTTP PUT: Update the is_status_acknowledged flag
    """
    def put(self, request, attempt_id):     # pylint: disable=unused-argument
        """
        Update the is_status_acknowledged flag for the specific attempt
        """
        if not getattr(settings, 'PROCTORED_EXAM_VIEWABLE_PAST_DUE', False):
            return Response(
                status=404,
                data={'detail': _('Cannot update attempt review status')}
            )

        attempt = get_exam_attempt_by_id(attempt_id)

        # make sure the the attempt belongs to the calling user_id
        if attempt and attempt['user']['id'] != request.user.id:
            err_msg = (
                f'user_id={request.user.id} attempted to update attempt_id={attempt_id} '
                f"review status to acknowledged in exam_id={attempt['proctored_exam']['id']}, but does not "
                'have authorization.'
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
            LOG.warning(
                'Attempt cannot be found by external_id=%(external_id)s',
                {'external_id': external_id}
            )
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

        if not backend:
            LOG.warning(
                (
                    'Tried to mark review on an exam attempt that is no longer a proctored exam.'
                    'The exam id=%(exam_id)s, exam.is_proctored=%(is_proctored)s,'
                    'exam.course_id=%(course_id)s and attempt_id=%(attempt_id)s'
                    'The review status will not be preserved on this attempt'
                ),
                {
                    'attempt_id': attempt['id'],
                    'exam_id': attempt['proctored_exam']['id'],
                    'is_proctored': attempt['proctored_exam']['is_proctored'],
                    'course_id': attempt['proctored_exam']['course_id'],
                }
            )
            return Response(data='Exam no longer proctored', status=412)

        # this method should convert the payload into a normalized format
        backend_review = backend.on_review_callback(attempt, data)

        # do we already have a review for this attempt?!? We may not allow updates
        review = ProctoredExamSoftwareSecureReview.get_review_by_attempt_code(attempt_code)

        if review:
            if not constants.ALLOW_REVIEW_UPDATES:
                err_msg = (
                    f'We already have a review submitted regarding attempt_code={attempt_code}. '
                    f'We do not allow for updates! (backend={backend})'
                )
                raise ProctoredExamReviewAlreadyExists(err_msg)

            # we allow updates
            LOG.warning(
                ('We already have a review submitted from our proctoring provider regarding '
                 'attempt_code=%(attempt_code)s. We have been configured to allow for '
                 'updates and will continue... (backend=%(backend)s)'),
                {'attempt_code': attempt_code, 'backend': backend}
            )
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
                'user=%(user)s does not have the required permissions to submit '
                'a review for attempt_code=%(attempt_code)s.',
                {'user': review.reviewed_by, 'attempt_code': attempt_code}
            )

        video_review_link = backend_review.get('payload', {}).get('videoReviewLink')
        if video_review_link:
            aes_key_str = backend.get_video_review_aes_key()
            if aes_key_str:
                aes_key = codecs.decode(aes_key_str, "hex")
                review.encrypted_video_url = encrypt_and_encode(video_review_link.encode("utf-8"), aes_key)

        # redact the video link from the raw data
        if 'videoReviewLink' in data:
            del data['videoReviewLink']
        review.raw_data = json.dumps(data)

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
                    f"{reverse('edx_proctoring:instructor_dashboard_exam', args=[course_id, exam_id])}"
                    f"?attempt={attempt['external_id']}"
                )
                instructor_service.send_support_notification(
                    course_id=attempt['proctored_exam']['course_id'],
                    exam_name=attempt['proctored_exam']['exam_name'],
                    student_username=attempt['user']['username'],
                    review_status=review.review_status,
                    review_url=review_url,
                )
        return Response(data='OK')


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
                f'Attempted to access exam attempt with external_id={external_id} '
                'but it does not exist.'
            )
            raise StudentExamAttemptDoesNotExistsException(err_msg)
        if request.user.has_perm('edx_proctoring.can_review_attempt', attempt):
            resp = self.make_review(attempt, request.data)
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
            err_msg = f'Could not locate attempt_code={attempt_code}'
            raise StudentExamAttemptDoesNotExistsException(err_msg)
        serialized = ProctoredExamStudentAttemptSerializer(attempt_obj).data
        serialized['is_archived'] = is_archived
        return self.make_review(
            serialized,
            request.data,
            backend=provider
        )


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
                    error_message = (
                        f'Multiple backends for course {course_id} '
                        f'{existing_backend_name} != {exam_backend_name}'
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

        encrypted_video_review_url = None
        if waffle.switch_is_active(REDS_API_REDIRECT) and attempt_id:
            attempt = get_exam_attempt_by_external_id(attempt_id)
            if attempt:
                reviews = ProctoredExamSoftwareSecureReview.objects.filter(attempt_code=attempt['attempt_code'])
                encrypted_video_review_url = reviews[0].encrypted_video_url if reviews else None

        url = backend.get_instructor_url(
            exam['course_id'],
            user,
            exam_id=ext_exam_id,
            attempt_id=attempt_id,
            show_configuration_dashboard=show_configuration_dashboard,
            encrypted_video_review_url=encrypted_video_review_url
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
                LOG.info(
                    'Retiring user_id=%(user_id)s from backend=%(backend)s',
                    {'user_id': user_id, 'backend': backend_name}
                )
                try:
                    result = get_backend_provider(name=backend_name).retire_user(backend_user_id)
                except ProctoredBaseException:
                    LOG.exception(
                        'Failed to delete user_id=%(user_id)s (backend_user_id=%(backend_user_id)s) from '
                        'backend=%(backend)s',
                        {
                            'user_id': user_id,
                            'backend_user_id': backend_user_id,
                            'backend': backend_name
                        }
                    )
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
