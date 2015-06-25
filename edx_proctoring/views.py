"""
Proctored Exams HTTP-based API endpoints
"""

import logging
from django.db import IntegrityError
from django.db.models import Model

from rest_framework import status
from rest_framework.response import Response
from edx_proctoring.api import create_exam, update_exam

from .utils import AuthenticatedAPIView

LOG = logging.getLogger("edx_proctoring_views")


class ProctoredExamView(AuthenticatedAPIView):
    """

    /edx_proctoring/v1/proctored_exam/exam

    HTTP POST
    Creates a new Exam.
    {
        "course_id": "edX/DemoX/Demo_Course",
        "content_id": 123,
        "exam_name": "Midterm",
        "time_limit_mins": "90",
        "is_proctored": true,
        "external_id": "",
        "is_active": true,
    }

    **Post Parameters**
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
    exam_id,
    exam_name=None,
    time_limit_mins=None,
    is_proctored=None,
    external_id=None,
    is_active=None

    HTTP GET
    returns an existing exam
    Scenarios
       by id
       by content id

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
        by id
        by content id

        """

class StudentProctoredExamAttempt(AuthenticatedAPIView):
    """
    Returns the status of the proctored exam.
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

        return Response(response_dict, status=status.HTTP_200_OK)

    def post(self, request):
        """
        HTTP POST handler. To start an exam.
        """

    def put(self, request):
        """
        HTTP POST handler. To stop an exam.
        """


class ExamAllowanceView(AuthenticatedAPIView):
    """

    """
    def put(self, request):
        """
        HTTP GET handler. Adds or updates Allowance
        """
    def delete(self, request):
        """
        HTTP DELETE handler. Removes Allowance.
        """

class ActiveExamsForUserView(AuthenticatedAPIView):
    """

    """
    def get(self, request):
        """
        returns the get_active_exams_for_user
        """
