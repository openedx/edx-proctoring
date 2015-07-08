"""
All tests for the proctored_exams.py
"""
import json
from datetime import datetime
from django.test.client import Client
from django.core.urlresolvers import reverse, NoReverseMatch
import pytz
from edx_proctoring.models import ProctoredExam, ProctoredExamStudentAttempt, ProctoredExamStudentAllowance
from edx_proctoring.views import require_staff
from django.contrib.auth.models import User

from .utils import (
    LoggedInTestCase
)
from mock import Mock

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
                        try:
                            response = self.client.get(reverse(urlpattern.name, args=["0/0/0"]))
                        except NoReverseMatch:
                            # some require 2 args.
                            response = self.client.get(reverse(urlpattern.name, args=["0/0/0", 0]))

                self.assertEqual(response.status_code, 403)


class ProctoredExamViewTests(LoggedInTestCase):
    """
    Tests for the ProctoredExamView
    """
    def setUp(self):
        super(ProctoredExamViewTests, self).setUp()
        self.user.is_staff = True
        self.user.save()
        self.client.login_user(self.user)

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
        response_data = json.loads(response.content)
        self.assertGreater(response_data['exam_id'], 0)

        # Now lookup the exam by giving the exam_id returned and match the data.
        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.exam_by_id', kwargs={'exam_id': response_data['exam_id']})
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['course_id'], exam_data['course_id'])
        self.assertEqual(response_data['exam_name'], exam_data['exam_name'])
        self.assertEqual(response_data['content_id'], exam_data['content_id'])
        self.assertEqual(response_data['external_id'], exam_data['external_id'])
        self.assertEqual(response_data['time_limit_mins'], exam_data['time_limit_mins'])

    def test_create_duplicate_exam(self):
        """
        Tests the POST method error handling if a duplicate exam is created.
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
        response_data = json.loads(response.content)
        self.assertGreater(response_data['exam_id'], 0)

        response = self.client.post(
            reverse('edx_proctoring.proctored_exam.exam'),
            exam_data
        )

        self.assertEqual(response.status_code, 400)

    def test_update_existing_exam(self):
        """
        Test the PUT method of the exam endpoint to update an existing exam.
        """
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='123aXqe0',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )

        exam_id = proctored_exam.id

        updated_exam_data = {
            'exam_id': exam_id,
            'exam_name': "midterm1",
            'time_limit_mins': 90,
            'external_id': '123',
            'is_proctored': True,
            'is_active': True
        }
        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.exam'),
            updated_exam_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['exam_id'], exam_id)

        # Now lookup the exam by giving the exam_id returned and match the data.
        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.exam_by_id', kwargs={'exam_id': response_data['exam_id']})
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['course_id'], proctored_exam.course_id)
        self.assertEqual(response_data['content_id'], proctored_exam.content_id)
        self.assertEqual(response_data['exam_name'], updated_exam_data['exam_name'])
        self.assertEqual(response_data['external_id'], updated_exam_data['external_id'])
        self.assertEqual(response_data['time_limit_mins'], updated_exam_data['time_limit_mins'])

    def test_decorator_staff_user(self):
        """
        Test assert require_staff before hitting any api url.
        """
        func = Mock()
        decorated_func = require_staff(func)
        request = self.mock_request()
        response = decorated_func(request)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(func.called)

    def mock_request(self):
        """
        mock request
        """
        request = Mock()
        self.user.is_staff = False
        self.user.save()
        request.user = self.user
        return request

    def test_update_non_existing_exam(self):
        """
        Test the PUT method of the exam endpoint to update an existing exam.
        In case the exam_id is not found, it should return a bad request.
        """
        exam_id = 99999

        updated_exam_data = {
            'exam_id': exam_id,
            'exam_name': "midterm1",
            'time_limit_mins': 90,
            'external_id': '123',
            'is_proctored': True,
            'is_active': True
        }
        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.exam'),
            updated_exam_data
        )

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertEqual(response_data, {'detail': 'The exam_id does not exist.'})

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
        response_data = json.loads(response.content)
        self.assertEqual(response_data['course_id'], proctored_exam.course_id)
        self.assertEqual(response_data['exam_name'], proctored_exam.exam_name)
        self.assertEqual(response_data['content_id'], proctored_exam.content_id)
        self.assertEqual(response_data['external_id'], proctored_exam.external_id)
        self.assertEqual(response_data['time_limit_mins'], proctored_exam.time_limit_mins)

    def test_get_exam_by_bad_id(self):
        """
        Tests the Get Exam by id endpoint
        """
        # Create an exam.
        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.exam_by_id', kwargs={'exam_id': 99999})
        )
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['detail'], 'The exam_id does not exist.')

    def test_get_exam_by_content_id(self):
        """
        Tests the Get Exam by content id endpoint
        """
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )

        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.exam_by_content_id', kwargs={
                'course_id': proctored_exam.course_id,
                'content_id': proctored_exam.content_id
            })
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['course_id'], proctored_exam.course_id)
        self.assertEqual(response_data['exam_name'], proctored_exam.exam_name)
        self.assertEqual(response_data['content_id'], proctored_exam.content_id)
        self.assertEqual(response_data['external_id'], proctored_exam.external_id)
        self.assertEqual(response_data['time_limit_mins'], proctored_exam.time_limit_mins)

    def test_get_exam_by_bad_content_id(self):
        """
        Tests the Get Exam by content id endpoint
        """
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )

        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.exam_by_content_id', kwargs={
                'course_id': 'c/d/e',
                'content_id': proctored_exam.content_id
            })
        )
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['detail'], 'The exam with course_id, content_id does not exist.')

    def test_get_exam_insufficient_args(self):
        """
        Tests the Get Exam by content id endpoint
        """
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )

        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.exam_by_content_id', kwargs={
                'course_id': proctored_exam.course_id,
                'content_id': proctored_exam.content_id
            })
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['course_id'], proctored_exam.course_id)
        self.assertEqual(response_data['exam_name'], proctored_exam.exam_name)
        self.assertEqual(response_data['content_id'], proctored_exam.content_id)
        self.assertEqual(response_data['external_id'], proctored_exam.external_id)
        self.assertEqual(response_data['time_limit_mins'], proctored_exam.time_limit_mins)


class TestStudentProctoredExamAttempt(LoggedInTestCase):
    """
    Tests for the StudentProctoredExamAttempt
    """
    def setUp(self):
        super(TestStudentProctoredExamAttempt, self).setUp()
        self.user.is_staff = True
        self.user.save()
        self.client.login_user(self.user)
        self.student_taking_exam = User()
        self.student_taking_exam.save()

    def test_start_exam_attempt(self):
        """
        Start an exam (create an exam attempt)
        """
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )
        attempt_data = {
            'exam_id': proctored_exam.id,
            'external_id': proctored_exam.external_id,
            'start_clock': True,
        }
        response = self.client.post(
            reverse('edx_proctoring.proctored_exam.attempt'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertGreater(response_data['exam_attempt_id'], 0)

    def test_restart_exam_attempt(self):
        """
        Start an exam that has already started should raise error.
        """
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )
        attempt_data = {
            'exam_id': proctored_exam.id,
            'external_id': proctored_exam.external_id
        }
        response = self.client.post(
            reverse('edx_proctoring.proctored_exam.attempt'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertGreater(response_data['exam_attempt_id'], 0)

        response = self.client.post(
            reverse('edx_proctoring.proctored_exam.attempt'),
            attempt_data
        )
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertEqual(
            response_data['detail'],
            'Cannot create new exam attempt for exam_id = 1 and user_id = 1 because it already exists!'
        )

    def test_stop_exam_attempt(self):
        """
        Start an exam (create an exam attempt)
        """
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )
        attempt_data = {
            'exam_id': proctored_exam.id,
            'user_id': self.student_taking_exam.id,
            'external_id': proctored_exam.external_id
        }
        response = self.client.post(
            reverse('edx_proctoring.proctored_exam.attempt'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertGreater(response_data['exam_attempt_id'], 0)
        old_attempt_id = response_data['exam_attempt_id']

        stop_attempt_data = {
            'exam_id': proctored_exam.id,
            'user_id': self.student_taking_exam.id
        }

        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.attempt'),
            stop_attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['exam_attempt_id'], old_attempt_id)

    def test_stop_unstarted_attempt(self):
        """
        Start an exam (create an exam attempt)
        """
        # Create an exam.
        attempt_data = {
            'exam_id': 999999,
            'user_id': self.student_taking_exam.id,
            'external_id': "123456"
        }
        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.attempt'),
            attempt_data
        )

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['detail'], 'Error. Trying to stop an exam that is not in progress.')

    def test_get_exam_attempt(self):
        """
        Test Case for retrieving student proctored exam attempt status.
        """
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )
        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.attempt')
        )
        self.assertEqual(response.status_code, 200)

        attempt_data = {
            'exam_id': proctored_exam.id,
            'user_id': self.student_taking_exam.id,
            'external_id': proctored_exam.external_id
        }
        response = self.client.post(
            reverse('edx_proctoring.proctored_exam.attempt'),
            attempt_data
        )
        self.assertEqual(response.status_code, 200)

        ProctoredExamStudentAttempt.objects.filter(
            proctored_exam_id=proctored_exam.id,
            user_id=self.user.id,
            external_id=proctored_exam.external_id,
        ).update(
            started_at=datetime.now(pytz.UTC)
        )

        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.attempt')
        )
        self.assertEqual(response.status_code, 200)

    def test_get_expired_exam_attempt(self):
        """
        Test to get the exam the time for which has finished.
        """

        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )
        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.attempt')
        )
        self.assertEqual(response.status_code, 200)

        attempt_data = {
            'exam_id': proctored_exam.id,
            'user_id': self.student_taking_exam.id,
            'external_id': proctored_exam.external_id
        }
        response = self.client.post(
            reverse('edx_proctoring.proctored_exam.attempt'),
            attempt_data
        )
        self.assertEqual(response.status_code, 200)

        ProctoredExamStudentAttempt.objects.filter(
            proctored_exam_id=proctored_exam.id,
            user_id=self.user.id,
            external_id=proctored_exam.external_id,
        ).update(
            started_at=datetime.now(pytz.UTC).replace(year=2013)
        )

        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.attempt')
        )
        self.assertEqual(response.status_code, 200)


class TestExamAllowanceView(LoggedInTestCase):
    """
    Tests for the ExamAllowanceView
    """
    def setUp(self):
        super(TestExamAllowanceView, self).setUp()
        self.user.is_staff = True
        self.user.save()
        self.client.login_user(self.user)
        self.student_taking_exam = User()
        self.student_taking_exam.save()

    def test_add_allowance_for_user(self):
        """
        Add allowance for a user for an exam.
        """
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )
        allowance_data = {
            'exam_id': proctored_exam.id,
            'user_id': self.student_taking_exam.id,
            'key': 'a_key',
            'value': '30'
        }
        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.allowance'),
            allowance_data
        )
        self.assertEqual(response.status_code, 200)

    def test_remove_allowance_for_user(self):
        """
        Remove allowance for a user for an exam.
        """
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )
        allowance_data = {
            'exam_id': proctored_exam.id,
            'user_id': self.student_taking_exam.id,
            'key': 'a_key',
            'value': '30'
        }
        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.allowance'),
            allowance_data
        )
        self.assertEqual(response.status_code, 200)

        allowance_data.pop('value')

        response = self.client.delete(
            reverse('edx_proctoring.proctored_exam.allowance'),
            allowance_data
        )
        self.assertEqual(response.status_code, 200)


class TestActiveExamsForUserView(LoggedInTestCase):
    """
    Tests for the ActiveExamsForUserView
    """
    def setUp(self):
        super(TestActiveExamsForUserView, self).setUp()
        self.user.is_staff = True
        self.user.save()
        self.client.login_user(self.user)
        self.student_taking_exam = User()
        self.student_taking_exam.save()

    def test_get_active_exams_for_user(self):
        """
        Test to get all the exams the user is currently taking.
        """

        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )
        ProctoredExamStudentAttempt.objects.create(
            proctored_exam_id=proctored_exam.id,
            user_id=self.student_taking_exam.id,
            external_id='123aXqe3',
            started_at=datetime.now(pytz.UTC),
            allowed_time_limit_mins=90
        )

        ProctoredExamStudentAllowance.objects.create(
            proctored_exam_id=proctored_exam.id,
            user_id=self.student_taking_exam.id,
            key='a_key',
            value="30"
        )

        exams_query_data = {
            'user_id': self.student_taking_exam.id,
            'course_id': proctored_exam.course_id
        }
        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.active_exams_for_user'),
            exams_query_data
        )
        self.assertEqual(response.status_code, 200)
