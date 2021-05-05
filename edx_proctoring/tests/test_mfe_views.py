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
    def test_get_exam_attempt_data(self):
        """
        Tests the Get Exam by course id and usage key endpoint.
        """
        course_key = CourseLocator(org='TEST', course='TEST01', run='2021')
        usage_key = BlockUsageLocator(
            course_key=course_key, block_type='sequential+block', block_id='27da21b2259e44a4a4ce8fa21daa3158'
        )
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='course-v1:TEST+TEST01+2021',
            content_id=usage_key,
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )

        url = reverse(
            'edx_proctoring:proctored_exam_attempts',
            kwargs={
                'course_id': proctored_exam.course_id,
                'content_id': proctored_exam.content_id
            }
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        exam_data = response_data['exam']
        self.assertEqual(exam_data['course_id'], proctored_exam.course_id)
        self.assertEqual(exam_data['exam_name'], proctored_exam.exam_name)
        self.assertEqual(exam_data['content_id'], str(proctored_exam.content_id))
        self.assertEqual(exam_data['external_id'], proctored_exam.external_id)
        self.assertEqual(exam_data['time_limit_mins'], proctored_exam.time_limit_mins)
