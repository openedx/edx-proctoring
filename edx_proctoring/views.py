"""
Proctored Exams HTTP-based API endpoints
"""

import logging
import pytz
from datetime import datetime, timedelta

from django.utils.decorators import method_decorator
from django.conf import settings
from django.core.urlresolvers import reverse, NoReverseMatch

from rest_framework import status
from rest_framework.response import Response
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
)
from edx_proctoring.exceptions import (
    ProctoredBaseException,
    ProctoredExamNotFoundException,
    UserNotFoundException,
    ProctoredExamPermissionDenied,
    StudentExamAttemptDoesNotExistsException,
)
from edx_proctoring.serializers import ProctoredExamSerializer

from .utils import AuthenticatedAPIView

LOG = logging.getLogger("edx_proctoring_views")


def require_staff(func):
    """View decorator that requires that the user have staff permissions. """
    def wrapped(request, *args, **kwargs):  # pylint: disable=missing-docstring
        if request.user.is_staff:
            return func(request, *args, **kwargs)
        else:
            return Response(
                status=status.HTTP_403_FORBIDDEN,
                data={"detail": "Must be a Staff User to Perform this request."}
            )
    return wrapped


class ProctoredExamView(AuthenticatedAPIView):
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
        "external_id": "12213DASAD",
        "is_active": true
    }

    **POST data Parameters**
        * course_id: The unique identifier for the course.
        * content_id: This will be the pointer to the id of the piece of course_ware which is the proctored exam.
        * exam_name: This is the display name of the Exam (Midterm etc).
        * time_limit_mins: Time limit (in minutes) that a student can finish this exam.
        * is_proctored: Whether this exam actually is proctored or not.
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
        serializer = ProctoredExamSerializer(data=request.DATA)
        if serializer.is_valid():
            exam_id = create_exam(
                course_id=request.DATA.get('course_id', None),
                content_id=request.DATA.get('content_id', None),
                exam_name=request.DATA.get('exam_name', None),
                time_limit_mins=request.DATA.get('time_limit_mins', None),
                is_proctored=request.DATA.get('is_proctored', None),
                external_id=request.DATA.get('external_id', None),
                is_active=request.DATA.get('is_active', None)
            )
            return Response({'exam_id': exam_id})
        else:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data=serializer.errors
            )

    @method_decorator(require_staff)
    def put(self, request):
        """
        HTTP PUT handler. To update an exam.
        calls the update_exam
        """
        try:
            exam_id = update_exam(
                exam_id=request.DATA.get('exam_id', None),
                exam_name=request.DATA.get('exam_name', None),
                time_limit_mins=request.DATA.get('time_limit_mins', None),
                is_proctored=request.DATA.get('is_proctored', None),
                external_id=request.DATA.get('external_id', None),
                is_active=request.DATA.get('is_active', None),
            )
            return Response({'exam_id': exam_id})
        except ProctoredExamNotFoundException:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={"detail": "The exam_id does not exist."}
            )

    def get(self, request, exam_id=None, course_id=None, content_id=None):  # pylint: disable=unused-argument
        """
        HTTP GET handler.
            Scenarios:
                by exam_id: calls get_exam_by_id()
                by course_id, content_id: get_exam_by_content_id()

        """

        if exam_id:
            try:
                return Response(
                    data=get_exam_by_id(exam_id),
                    status=status.HTTP_200_OK
                )
            except ProctoredExamNotFoundException:
                return Response(
                    status=status.HTTP_400_BAD_REQUEST,
                    data={"detail": "The exam_id does not exist."}
                )
        else:
            if course_id is not None:
                if content_id is not None:
                    # get by course_id & content_id
                    try:
                        return Response(
                            data=get_exam_by_content_id(course_id, content_id),
                            status=status.HTTP_200_OK
                        )
                    except ProctoredExamNotFoundException:
                        return Response(
                            status=status.HTTP_400_BAD_REQUEST,
                            data={"detail": "The exam with course_id, content_id does not exist."}
                        )
                else:
                    result_set = get_all_exams_for_course(
                        course_id=course_id
                    )
                    return Response(result_set)


class StudentProctoredExamAttempt(AuthenticatedAPIView):
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

        try:
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
            if attempt['user_id'] != request.user.id:
                err_msg = (
                    'Attempted to access attempt_id {attempt_id} but '
                    'does not have access to it.'.format(
                        attempt_id=attempt_id
                    )
                )
                raise ProctoredExamPermissionDenied(err_msg)

            return Response(
                data=attempt,
                status=status.HTTP_200_OK
            )

        except ProctoredBaseException, ex:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={"detail": str(ex)}
            )

    def put(self, request, attempt_id):
        """
        HTTP POST handler. To stop an exam.
        """
        try:
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
            if attempt['user_id'] != request.user.id:
                err_msg = (
                    'Attempted to access attempt_id {attempt_id} but '
                    'does not have access to it.'.format(
                        attempt_id=attempt_id
                    )
                )
                raise ProctoredExamPermissionDenied(err_msg)

            exam_attempt_id = stop_exam_attempt(
                exam_id=attempt['proctored_exam_id'],
                user_id=request.user.id
            )
            return Response({"exam_attempt_id": exam_attempt_id})

        except ProctoredBaseException, ex:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={"detail": str(ex)}
            )


class StudentProctoredExamAttemptCollection(AuthenticatedAPIView):
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

    def get(self, request):
        """
        HTTP GET Handler. Returns the status of the exam attempt.
        """

        exams = get_active_exams_for_user(request.user.id)

        if exams:
            exam_info = exams[0]

            exam = exam_info['exam']
            attempt = exam_info['attempt']

            # need to adjust for allowances
            expires_at = attempt['started_at'] + timedelta(minutes=attempt['allowed_time_limit_mins'])
            now_utc = datetime.now(pytz.UTC)

            if expires_at > now_utc:
                time_remaining_seconds = (expires_at - now_utc).seconds
            else:
                time_remaining_seconds = 0

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
                exam_url_path = reverse(
                    'courseware.views.jump_to',
                    args=[exam['course_id'], exam['content_id']]
                )
            except NoReverseMatch:
                pass

            response_dict = {
                'in_timed_exam': True,
                'taking_as_proctored': attempt['taking_as_proctored'],
                'exam_display_name': exam['exam_name'],
                'exam_url_path': exam_url_path,
                'time_remaining_seconds': time_remaining_seconds,
                'low_threshold_sec': low_threshold,
                'critically_low_threshold_sec': critically_low_threshold,
            }
        else:
            response_dict = {
                'in_timed_exam': False,
                'is_proctored': False,
            }

        return Response(
            data=response_dict,
            status=status.HTTP_200_OK
        )

    def post(self, request):
        """
        HTTP POST handler. To create an exam attempt.
        """
        start_immediately = request.DATA.get('start_clock', 'false').lower() == 'true'
        exam_id = request.DATA.get('exam_id', None)
        attempt_proctored = request.DATA.get('attempt_proctored', 'false').lower() == 'true'
        try:
            exam_attempt_id = create_exam_attempt(
                exam_id=exam_id,
                user_id=request.user.id,
                taking_as_proctored=attempt_proctored
            )

            if start_immediately:
                start_exam_attempt(exam_id, request.user.id)

            return Response({'exam_attempt_id': exam_attempt_id})

        except ProctoredBaseException, ex:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={"detail": str(ex)}
            )


class ExamAllowanceView(AuthenticatedAPIView):
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
    @method_decorator(require_staff)
    def get(self, request, course_id):  # pylint: disable=unused-argument
        """
        HTTP GET handler. Get all allowances for a course.
        """
        result_set = get_allowances_for_course(
            course_id=course_id
        )
        return Response(result_set)

    @method_decorator(require_staff)
    def put(self, request):
        """
        HTTP GET handler. Adds or updates Allowance
        """
        try:
            return Response(add_allowance_for_user(
                exam_id=request.DATA.get('exam_id', None),
                user_info=request.DATA.get('user_info', None),
                key=request.DATA.get('key', None),
                value=request.DATA.get('value', None)
            ))

        except UserNotFoundException, ex:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={"detail": str(ex)}
            )

    @method_decorator(require_staff)
    def delete(self, request):
        """
        HTTP DELETE handler. Removes Allowance.
        """
        return Response(remove_allowance_for_user(
            exam_id=request.DATA.get('exam_id', None),
            user_id=request.DATA.get('user_id', None),
            key=request.DATA.get('key', None)
        ))


class ActiveExamsForUserView(AuthenticatedAPIView):
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
            user_id=request.DATA.get('user_id', None),
            course_id=request.DATA.get('course_id', None)
        ))
