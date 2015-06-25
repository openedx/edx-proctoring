"""
Proctored Exams HTTP-based API endpoints
"""

import logging
from django.db import IntegrityError

from rest_framework import status
from rest_framework.response import Response
from edx_proctoring.api import create_exam

from .utils import AuthenticatedAPIView

LOG = logging.getLogger("edx_proctoring_views")


class StudentProctoredExamStatus(AuthenticatedAPIView):
    """
    Returns the status of the proctored exam.
    """

    def get(self, request):  # pylint: disable=unused-argument
        """
        HTTP GET Handler
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


class CreateExamView(AuthenticatedAPIView):
    """
    Creates a new Exam.

    POST /edx_proctoring/v1/proctored_exam/create
    {
        "course_id": "edX/DemoX/Demo_Course",
        "content_id": "",
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

    """
    def post(self, request):
        """
        Http POST handler.
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
                data={"message": u"Trying to create a duplicate exam."}
            )


