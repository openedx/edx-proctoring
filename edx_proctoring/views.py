"""
Proctored Exams HTTP-based API endpoints
"""

import logging

from rest_framework import status
from rest_framework.response import Response

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
