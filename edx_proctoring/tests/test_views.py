"""
All tests for the proctored_exams.py
"""
from django.test.client import Client
from django.core.urlresolvers import reverse, NoReverseMatch
from edx_proctoring.models import ProctoredExam

from .utils import (
    LoggedInTestCase
)

from edx_proctoring.urls import urlpatterns


class ProctoredExamsApiTests(LoggedInTestCase):
    """
    All tests for the views.py
    """

    def setUp(self):
        """
        Build out test harnessing
        """
        super(ProctoredExamsApiTests, self).setUp()

    def test_no_anonymous_access(self):
        """
        Make sure we cannot access any API methods without being logged in
        """

        self.client = Client()  # use AnonymousUser on the API calls

        for urlpattern in urlpatterns:
            if hasattr(urlpattern, 'name'):
                try:
                    response = self.client.get(reverse(urlpattern.name))
                except NoReverseMatch:
                    # some of our URL mappings may require a argument substitution
                    try:
                        response = self.client.get(reverse(urlpattern.name, args=[0]))
                    except NoReverseMatch:
                        # some require 2 args.
                        response = self.client.get(reverse(urlpattern.name, args=["0/0/0", 0]))

                self.assertEqual(response.status_code, 403)


class StudentProctoredExamAttempt(LoggedInTestCase):
    """
    Tests for StudentProctoredExamAttempt
    """
    def test_get_exam_attempt(self):
        """
        Test Case for retrieving student proctored exam attempt status.
        """

        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.attempt')
        )
        self.assertEqual(response.status_code, 200)


class ProctoredExamViewTests(LoggedInTestCase):
    """
    Tests for the ProctoredExamView
    """
    def test_create_exam(self):
        """
        Test the POST method of the exam endpoint to create an exam.
        """
        exam_data = {
            'course_id': "a/b/c",
            'exam_name': "midterm1",
            'content_id': '123aXqe0',
            'time_limit_mins': 90,
            'external_id': '123',
            'is_proctored': True,
            'is_active': True
        }
        response = self.client.post(
            reverse('edx_proctoring.proctored_exam.exam'),
            exam_data
        )

        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.data['exam_id'], 0)

        # Now lookup the exam by giving the exam_id returned and match the data.
        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.exam_by_id', kwargs={'exam_id': response.data['exam_id']})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['course_id'], exam_data['course_id'])
        self.assertEqual(response.data['exam_name'], exam_data['exam_name'])
        self.assertEqual(response.data['content_id'], exam_data['content_id'])
        self.assertEqual(response.data['external_id'], exam_data['external_id'])
        self.assertEqual(response.data['time_limit_mins'], exam_data['time_limit_mins'])

    def test_get_exam_by_id(self):
        """
        Tests the Get Exam by id endpoint
        """
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='test_course',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )

        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.exam_by_id', kwargs={'exam_id': proctored_exam.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['course_id'], proctored_exam.course_id)
        self.assertEqual(response.data['exam_name'], proctored_exam.exam_name)
        self.assertEqual(response.data['content_id'], proctored_exam.content_id)
        self.assertEqual(response.data['external_id'], proctored_exam.external_id)
        self.assertEqual(response.data['time_limit_mins'], proctored_exam.time_limit_mins)
