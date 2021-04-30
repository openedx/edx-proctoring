"""
Tests for the MFE proctored exam views.
"""
import json

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
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='test_course',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )

        url = reverse(
            'mfe_api:proctored_exam.exam_attempts',
            kwargs={
                'course_id': proctored_exam.course_id,
                'usage_id': 'block-v1:RG+RG01+2021+type@sequential+block@fa0b1fad8c8247e58da27e09c0b76205'
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

    # def test_get_exam_by_bad_id(self):
    #     """
    #     Tests the Get Exam by id endpoint
    #     """
    #     # Create an exam.
    #     response = self.client.get(
    #         reverse('edx_proctoring:proctored_exam.exam_by_id', kwargs={'exam_id': 99999})
    #     )
    #     self.assertEqual(response.status_code, 400)
    #     response_data = json.loads(response.content.decode('utf-8'))
    #     self.assertEqual(
    #         response_data['detail'],
    #         'Attempted to get exam_id=99999, but this exam does not exist.',
    #     )
    #
    # def test_get_exam_by_content_id(self):
    #     """
    #     Tests the Get Exam by content id endpoint
    #     """
    #     # Create an exam.
    #     proctored_exam = ProctoredExam.objects.create(
    #         course_id='a/b/c',
    #         content_id='test_content',
    #         exam_name='Test Exam',
    #         external_id='123aXqe3',
    #         time_limit_mins=90
    #     )
    #
    #     response = self.client.get(
    #         reverse('edx_proctoring:proctored_exam.exam_by_content_id', kwargs={
    #             'course_id': proctored_exam.course_id,
    #             'content_id': proctored_exam.content_id
    #         })
    #     )
    #     self.assertEqual(response.status_code, 200)
    #     response_data = json.loads(response.content.decode('utf-8'))
    #     self.assertEqual(response_data['course_id'], proctored_exam.course_id)
    #     self.assertEqual(response_data['exam_name'], proctored_exam.exam_name)
    #     self.assertEqual(response_data['content_id'], proctored_exam.content_id)
    #     self.assertEqual(response_data['external_id'], proctored_exam.external_id)
    #     self.assertEqual(response_data['time_limit_mins'], proctored_exam.time_limit_mins)
    #
    # def test_get_exam_by_course_id(self):
    #     """
    #     Tests the Get Exam by course id endpoint
    #     """
    #     # Create an exam.
    #     proctored_exam = ProctoredExam.objects.create(
    #         course_id='a/b/c',
    #         content_id='test_content',
    #         exam_name='Test Exam',
    #         external_id='123aXqe3',
    #         time_limit_mins=90,
    #         is_active=True
    #     )
    #
    #     response = self.client.get(
    #         reverse('edx_proctoring:proctored_exam.exams_by_course_id', kwargs={
    #             'course_id': proctored_exam.course_id
    #         })
    #     )
    #     self.assertEqual(response.status_code, 200)
    #     response_data = json.loads(response.content.decode('utf-8'))
    #     self.assertEqual(response_data[0]['course_id'], proctored_exam.course_id)
    #     self.assertEqual(response_data[0]['exam_name'], proctored_exam.exam_name)
    #     self.assertEqual(response_data[0]['content_id'], proctored_exam.content_id)
    #     self.assertEqual(response_data[0]['external_id'], proctored_exam.external_id)
    #     self.assertEqual(response_data[0]['time_limit_mins'], proctored_exam.time_limit_mins)
    #
    # def test_get_exam_by_bad_content_id(self):
    #     """
    #     Tests the Get Exam by content id endpoint
    #     """
    #     # Create an exam.
    #     proctored_exam = ProctoredExam.objects.create(
    #         course_id='a/b/c',
    #         content_id='test_content',
    #         exam_name='Test Exam',
    #         external_id='123aXqe3',
    #         time_limit_mins=90
    #     )
    #
    #     response = self.client.get(
    #         reverse('edx_proctoring:proctored_exam.exam_by_content_id', kwargs={
    #             'course_id': 'c/d/e',
    #             'content_id': proctored_exam.content_id
    #         })
    #     )
    #     self.assertEqual(response.status_code, 400)
    #     response_data = json.loads(response.content.decode('utf-8'))
    #     message = (
    #         'Cannot find proctored exam in course_id=c/d/e with content_id={content_id}'.format(
    #             content_id=proctored_exam.content_id,
    #         )
    #     )
    #     self.assertEqual(response_data['detail'], message)
    #
    # def test_get_exam_insufficient_args(self):
    #     """
    #     Tests the Get Exam by content id endpoint
    #     """
    #     # Create an exam.
    #     proctored_exam = ProctoredExam.objects.create(
    #         course_id='a/b/c',
    #         content_id='test_content',
    #         exam_name='Test Exam',
    #         external_id='123aXqe3',
    #         time_limit_mins=90
    #     )
    #
    #     response = self.client.get(
    #         reverse('edx_proctoring:proctored_exam.exam_by_content_id', kwargs={
    #             'course_id': proctored_exam.course_id,
    #             'content_id': proctored_exam.content_id
    #         })
    #     )
    #     self.assertEqual(response.status_code, 200)
    #     response_data = json.loads(response.content.decode('utf-8'))
    #     self.assertEqual(response_data['course_id'], proctored_exam.course_id)
    #     self.assertEqual(response_data['exam_name'], proctored_exam.exam_name)
    #     self.assertEqual(response_data['content_id'], proctored_exam.content_id)
    #     self.assertEqual(response_data['external_id'], proctored_exam.external_id)
    #     self.assertEqual(response_data['time_limit_mins'], proctored_exam.time_limit_mins)
