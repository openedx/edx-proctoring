"""
Proctored Exams HTTP-based API endpoints
"""

import logging
from django.db import IntegrityError
from django.db.models import Model

from rest_framework import status
from rest_framework.response import Response
from edx_proctoring.api import create_exam, update_exam, get_exam_by_id, get_exam_by_content_id, start_exam_attempt, \
    stop_exam_attempt, add_allowance_for_user, remove_allowance_for_user, get_active_exams_for_user

from .utils import AuthenticatedAPIView

LOG = logging.getLogger("edx_proctoring_views")


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
        "time_limit_mins": "90",
        "is_proctored": true,
        "external_id": "",
        "is_active": true,
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
    def post(self, request):
        """
        Http POST handler. Creates an exam.
        """
        try:
            exam_id = create_exam(
                course_id=request.DATA.get('course_id', ""),
                content_id=request.DATA.get('content_id', ""),
                exam_name=request.DATA.get('exam_name', ""),
                time_limit_mins=request.DATA.get('time_limit_mins', ""),
                is_proctored=True if request.DATA.get('is_proctored', "False").lower()=='true' else False,
                external_id=request.DATA.get('external_id', ""),
                is_active=True if request.DATA.get('is_active', "").lower()=='true' else False,
            )
            return Response({'exam_id': exam_id})
        except IntegrityError:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={"detail": "Trying to create a duplicate exam."}
            )

    def put(self, request):
        """
        HTTP PUT handler. To update an exam.
        calls the update_exam
        """
        try:
            exam_id = update_exam(
                exam_id=request.DATA.get('exam_id', ""),
                exam_name=request.DATA.get('exam_name', ""),
                time_limit_mins=request.DATA.get('time_limit_mins', ""),
                is_proctored=True if request.DATA.get('is_proctored', "False").lower()=='true' else False,
                external_id=request.DATA.get('external_id', ""),
                is_active=True if request.DATA.get('is_active', "").lower()=='true' else False,
            )
            return Response({'exam_id': exam_id})
        except Model.DoesNotExist:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={"detail": "The exam_id does not exist."}
            )

    def get(self, request):
        """
        HTTP GET handler.
            Scenarios:
                by exam_id: calls get_exam_by_id()
                by course_id, content_id: get_exam_by_content_id()

        """

        course_id = request.QUERY_PARAMS.get('course_id', None)
        content_id = request.QUERY_PARAMS.get('content_id', None)
        exam_id = request.QUERY_PARAMS.get('exam_id', None)

        if exam_id:
            try:
                return Response(
                    data=get_exam_by_id(exam_id),
                    status=status.HTTP_200_OK
                )
            except Model.DoesNotExist:
                return Response(
                    status=status.HTTP_400_BAD_REQUEST,
                    data={"detail": "The exam_id does not exist."}
                )
        elif course_id is not None and content_id is not None:
            try:
                return Response(
                    data=get_exam_by_content_id(course_id, content_id),
                    status=status.HTTP_200_OK
                )
            except Model.DoesNotExist:
                return Response(
                    status=status.HTTP_400_BAD_REQUEST,
                    data={"detail": "The exam with course_id, content_id does not exist."}
                )
        else:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={"detail": "Bad input data."}
            )


class StudentProctoredExamAttempt(AuthenticatedAPIView):
    """
    Endpoint for the StudentProctoredExamAttempt
    /edx_proctoring/v1/proctored_exam/exam

    """

    def get(self, request):  # pylint: disable=unused-argument
        """
        HTTP GET Handler. Returns the status of the exam attempt.
        """

        response_dict = {
            'in_timed_exam': True,
            'is_proctored': True,
            'exam_display_name': 'Midterm',
            'exam_url_path': '',
            'time_remaining_seconds': 45,
            'low_threshold': 30,
            'critically_low_threshold': 15,
        }

        return Response(
            data=response_dict,
            status=status.HTTP_200_OK
        )

    def post(self, request):
        """
        HTTP POST handler. To start an exam.
        """
        try:
            exam_attempt_id = start_exam_attempt(
                exam_id=request.DATA.get('exam_id', ""),
                user_id=request.DATA.get('user_id', ""),
                external_id=request.DATA.get('external_id', "")
            )
            return Response({'exam_attempt_id': exam_attempt_id})

        except Exception:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={"detail": "Exam already started."}
            )


    def put(self, request):
        """
        HTTP POST handler. To stop an exam.
        """
        try:
            exam_attempt_id = stop_exam_attempt(
                exam_id=request.DATA.get('exam_id', ""),
                user_id=request.DATA.get('user_id', "")
            )
            return Response({"exam_attempt_id": exam_attempt_id})

        except Exception:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={"detail": "Exam Not in progress."}
            )


class ExamAllowanceView(AuthenticatedAPIView):
    """

    """
    def put(self, request):
        """
        HTTP GET handler. Adds or updates Allowance
        """
        try:
            return Response(add_allowance_for_user(
                exam_id=request.DATA.get('exam_id', ""),
                user_id=request.DATA.get('user_id', ""),
                key=request.DATA.get('key', ""),
                value=request.DATA.get('value', "")
            ))
        except:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={"detail": "Could not add Allowance."}
            )


    def delete(self, request):
        """
        HTTP DELETE handler. Removes Allowance.
        """
        try:
            return Response(remove_allowance_for_user(
                exam_id=request.DATA.get('exam_id', ""),
                user_id=request.DATA.get('user_id', ""),
                key=request.DATA.get('key', "")
            ))
        except:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={"detail": "Could not remove Allowance."}
            )

class ActiveExamsForUserView(AuthenticatedAPIView):
    """

    """
    def get(self, request):
        """
        returns the get_active_exams_for_user
        """
        try:
            return Response(get_active_exams_for_user(
                user_id=request.DATA.get('user_id', ""),
                course_id=request.DATA.get('course_id', "")
            ))
        except:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={"detail": "Error."}
            )
