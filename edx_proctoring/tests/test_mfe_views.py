"""
Tests for the MFE proctored exam views.
"""
import json
from opaque_keys.edx.locator import BlockUsageLocator, CourseLocator

from django.contrib.auth import get_user_model
from django.urls import reverse

from edx_proctoring.models import ProctoredExam

from .utils import ProctoredExamTestCase


User = get_user_model()


class ProctoredExamAttemptsMFEViewTests(ProctoredExamTestCase):
    """
    Tests for the ProctoredExamView
    """
    def test_get_exam_by_id(self):
        """
        Tests the Get Exam by course id and usage key endpoint.
        """
        COURSE_KEY = CourseLocator(org='TEST', course='TEST01', run='2021')
        USAGE_KEY = BlockUsageLocator(course_key=COURSE_KEY, block_type='sequential+block', block_id='exam')
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='test_course',
            content_id=USAGE_KEY,
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )

        print(proctored_exam.content_id, str(proctored_exam.content_id))
        url = reverse(
            'proctored_exam_attempts',
            kwargs={
                'course_id': proctored_exam.course_id,
                'content_id': proctored_exam.content_id
            }
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['course_id'], proctored_exam.course_id)
        self.assertEqual(response_data['exam_name'], proctored_exam.exam_name)
        self.assertEqual(response_data['content_id'], proctored_exam.content_id)
        self.assertEqual(response_data['external_id'], proctored_exam.external_id)
        self.assertEqual(response_data['time_limit_mins'], proctored_exam.time_limit_mins)
