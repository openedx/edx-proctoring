# pylint: disable=too-many-lines
"""
All tests for the proctored_exams.py
"""
import json
import pytz
import ddt
from mock import Mock
from freezegun import freeze_time
from httmock import HTTMock
from string import Template  # pylint: disable=deprecated-module
from datetime import datetime, timedelta
from django.test.client import Client
from django.core.urlresolvers import reverse, NoReverseMatch
from django.contrib.auth.models import User

from edx_proctoring.models import (
    ProctoredExam,
    ProctoredExamStudentAttempt,
    ProctoredExamStudentAllowance,
    ProctoredExamStudentAttemptStatus,
)
from edx_proctoring.views import require_staff
from edx_proctoring.api import (
    create_exam,
    create_exam_attempt,
    get_exam_attempt_by_id,
)

from .utils import (
    LoggedInTestCase
)

from edx_proctoring.urls import urlpatterns
from edx_proctoring.backends.tests.test_review_payload import TEST_REVIEW_PAYLOAD
from edx_proctoring.backends.tests.test_software_secure import mock_response_content
from edx_proctoring.tests.test_services import MockCreditService
from edx_proctoring.runtime import set_runtime_service, get_runtime_service


class ProctoredExamsApiTests(LoggedInTestCase):
    """
    All tests for the views.py
    """

    def setUp(self):
        """
        Build out test harnessing
        """
        super(ProctoredExamsApiTests, self).setUp()
        set_runtime_service('credit', MockCreditService())

    def test_no_anonymous_access(self):
        """
        Make sure we cannot access any API methods without being logged in
        """
        self.client = Client()  # use AnonymousUser on the API calls
        for urlpattern in urlpatterns:
            if hasattr(urlpattern, 'name') and '.anonymous.' not in urlpattern.name:
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
        set_runtime_service('credit', MockCreditService())

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
            'is_practice_exam': False,
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
            'is_practice_exam': False,
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

    def test_get_exam_by_course_id(self):
        """
        Tests the Get Exam by course id endpoint
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
            reverse('edx_proctoring.proctored_exam.exams_by_course_id', kwargs={
                'course_id': proctored_exam.course_id
            })
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data[0]['course_id'], proctored_exam.course_id)
        self.assertEqual(response_data[0]['exam_name'], proctored_exam.exam_name)
        self.assertEqual(response_data[0]['content_id'], proctored_exam.content_id)
        self.assertEqual(response_data[0]['external_id'], proctored_exam.external_id)
        self.assertEqual(response_data[0]['time_limit_mins'], proctored_exam.time_limit_mins)

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


@ddt.ddt
class TestStudentProctoredExamAttempt(LoggedInTestCase):
    """
    Tests for the StudentProctoredExamAttempt
    """
    def setUp(self):
        super(TestStudentProctoredExamAttempt, self).setUp()
        self.user.is_staff = True
        self.user.save()
        self.second_user = User(username='tester2', email='tester2@test.com')
        self.second_user.save()
        self.client.login_user(self.user)
        self.student_taking_exam = User()
        self.student_taking_exam.save()

    def test_start_exam_create(self):
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
            reverse('edx_proctoring.proctored_exam.attempt.collection'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertGreater(response_data['exam_attempt_id'], 0)

    def test_start_exam(self):
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
            'start_clock': False,
        }
        response = self.client.post(
            reverse('edx_proctoring.proctored_exam.attempt.collection'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertGreater(response_data['exam_attempt_id'], 0)

        old_attempt_id = response_data['exam_attempt_id']

        # make sure the exam has not started
        attempt = get_exam_attempt_by_id(old_attempt_id)
        self.assertIsNone(attempt['started_at'])

        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.attempt', args=[old_attempt_id]),
            {
                'action': 'start',
            }
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['exam_attempt_id'], old_attempt_id)

        # make sure the exam started
        attempt = get_exam_attempt_by_id(old_attempt_id)
        self.assertIsNotNone(attempt['started_at'])

    def test_attempt_readback(self):
        """
        Confirms that an attempt can be read
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
            reverse('edx_proctoring.proctored_exam.attempt.collection'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        attempt_id = response_data['exam_attempt_id']
        self.assertGreater(attempt_id, 0)

        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.attempt', args=[attempt_id])
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['id'], attempt_id)
        self.assertEqual(response_data['proctored_exam']['id'], proctored_exam.id)
        self.assertIsNotNone(response_data['started_at'])
        self.assertIsNone(response_data['completed_at'])

    def test_attempt_status_error(self):
        """
        Test to confirm that attempt status is marked as error, because client
        has stopped sending it's polling timestamp
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
            reverse('edx_proctoring.proctored_exam.attempt.collection'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        attempt_id = response_data['exam_attempt_id']
        self.assertEqual(attempt_id, 1)

        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.attempt', args=[attempt_id])
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'started')
        attempt_code = response_data['attempt_code']

        # test the polling callback point
        response = self.client.get(
            reverse(
                'edx_proctoring.anonymous.proctoring_poll_status',
                args=[attempt_code]
            )
        )
        self.assertEqual(response.status_code, 200)

        # now reset the time to 2 minutes in the future.
        reset_time = datetime.now(pytz.UTC) + timedelta(minutes=2)
        with freeze_time(reset_time):
            response = self.client.get(
                reverse('edx_proctoring.proctored_exam.attempt', args=[attempt_id])
            )
            self.assertEqual(response.status_code, 200)
            response_data = json.loads(response.content)
            self.assertEqual(response_data['status'], 'error')

    def test_attempt_callback_timeout(self):
        """
        Ensures that the polling from the client will cause the
        server to transition to timed_out if the user runs out of time
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
            reverse('edx_proctoring.proctored_exam.attempt.collection'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        attempt_id = response_data['exam_attempt_id']
        self.assertEqual(attempt_id, 1)

        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.attempt', args=[attempt_id])
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'started')
        attempt_code = response_data['attempt_code']

        # test the polling callback point
        response = self.client.get(
            reverse(
                'edx_proctoring.anonymous.proctoring_poll_status',
                args=[attempt_code]
            )
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'started')

        # set time to be in future
        reset_time = datetime.now(pytz.UTC) + timedelta(minutes=180)
        with freeze_time(reset_time):
            # Now the callback should transition us away from started
            response = self.client.get(
                reverse(
                    'edx_proctoring.anonymous.proctoring_poll_status',
                    args=[attempt_code]
                )
            )
            self.assertEqual(response.status_code, 200)
            response_data = json.loads(response.content)
            self.assertEqual(response_data['status'], 'submitted')

    def test_remove_attempt(self):
        """
        Confirms that an attempt can be removed
        """
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )

        response = self.client.delete(
            reverse('edx_proctoring.proctored_exam.attempt', args=[1])
        )

        self.assertEqual(response.status_code, 400)

        attempt_data = {
            'exam_id': proctored_exam.id,
            'external_id': proctored_exam.external_id,
            'start_clock': True,
        }
        response = self.client.post(
            reverse('edx_proctoring.proctored_exam.attempt.collection'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        attempt_id = response_data['exam_attempt_id']
        self.assertGreater(attempt_id, 0)

        response = self.client.delete(
            reverse('edx_proctoring.proctored_exam.attempt', args=[attempt_id])
        )

        self.assertEqual(response.status_code, 200)

    def test_read_others_attempt(self):
        """
        Confirms that we cnanot read someone elses attempt
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
            reverse('edx_proctoring.proctored_exam.attempt.collection'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        attempt_id = response_data['exam_attempt_id']
        self.assertGreater(attempt_id, 0)

        self.client.login_user(self.second_user)
        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.attempt', args=[attempt_id])
        )
        self.assertEqual(response.status_code, 400)

    def test_read_non_existing_attempt(self):
        """
        Confirms that we cannot read a non-existing attempt
        """
        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.attempt', args=[0])
        )
        self.assertEqual(response.status_code, 400)

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
            reverse('edx_proctoring.proctored_exam.attempt.collection'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertGreater(response_data['exam_attempt_id'], 0)

        response = self.client.post(
            reverse('edx_proctoring.proctored_exam.attempt.collection'),
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
        Stop an exam
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
            reverse('edx_proctoring.proctored_exam.attempt.collection'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertGreater(response_data['exam_attempt_id'], 0)
        old_attempt_id = response_data['exam_attempt_id']

        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.attempt', args=[old_attempt_id]),
            {
                'action': 'stop',
            }
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['exam_attempt_id'], old_attempt_id)

    @ddt.data(
        ('submit', ProctoredExamStudentAttemptStatus.submitted),
        ('decline', ProctoredExamStudentAttemptStatus.declined)
    )
    @ddt.unpack
    def test_submit_exam_attempt(self, action, expected_status):
        """
        Tries to submit an exam
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
            reverse('edx_proctoring.proctored_exam.attempt.collection'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertGreater(response_data['exam_attempt_id'], 0)
        old_attempt_id = response_data['exam_attempt_id']

        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.attempt', args=[old_attempt_id]),
            {
                'action': action,
            }
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['exam_attempt_id'], old_attempt_id)

        attempt = get_exam_attempt_by_id(response_data['exam_attempt_id'])

        self.assertEqual(attempt['status'], expected_status)

        # we should not be able to restart it
        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.attempt', args=[old_attempt_id]),
            {
                'action': 'start',
            }
        )

        self.assertEqual(response.status_code, 400)

        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.attempt', args=[old_attempt_id]),
            {
                'action': 'stop',
            }
        )

        self.assertEqual(response.status_code, 400)

    def test_get_exam_attempts(self):
        """
        Test to get the exam attempts in a course.
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
            reverse('edx_proctoring.proctored_exam.attempt.collection'),
            attempt_data
        )
        url = reverse('edx_proctoring.proctored_exam.attempts.course', kwargs={'course_id': proctored_exam.course_id})
        self.assertEqual(response.status_code, 200)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(len(response_data['proctored_exam_attempts']), 1)

        attempt = response_data['proctored_exam_attempts'][0]
        self.assertEqual(attempt['proctored_exam']['id'], proctored_exam.id)
        self.assertEqual(attempt['user']['id'], self.user.id)

        url = '{url}?page={invalid_page_no}'.format(url=url, invalid_page_no=9999)
        # url with the invalid page # still gives us the first page result.
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(len(response_data['proctored_exam_attempts']), 1)

    def test_exam_attempts_not_staff(self):
        """
        Test to get the exam attempts in a course.
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
            reverse('edx_proctoring.proctored_exam.attempt.collection'),
            attempt_data
        )
        url = reverse('edx_proctoring.proctored_exam.attempts.course', kwargs={'course_id': proctored_exam.course_id})

        self.user.is_staff = False
        self.user.save()

        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_get_filtered_exam_attempts(self):
        """
        Test to get the exam attempts in a course.
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
            'start_clock': False,
            'attempt_proctored': False
        }
        # create a exam attempt
        response = self.client.post(
            reverse('edx_proctoring.proctored_exam.attempt.collection'),
            attempt_data
        )
        self.assertEqual(response.status_code, 200)

        self.client.login_user(self.second_user)
        # create a new exam attempt for second student
        response = self.client.post(
            reverse('edx_proctoring.proctored_exam.attempt.collection'),
            attempt_data
        )
        self.assertEqual(response.status_code, 200)

        self.client.login_user(self.user)
        response = self.client.get(
            reverse(
                'edx_proctoring.proctored_exam.attempts.search',
                kwargs={
                    'course_id': proctored_exam.course_id,
                    'search_by': 'tester'
                }
            )
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)

        self.assertEqual(len(response_data['proctored_exam_attempts']), 2)
        attempt = response_data['proctored_exam_attempts'][0]
        self.assertEqual(attempt['proctored_exam']['id'], proctored_exam.id)
        self.assertEqual(attempt['user']['id'], self.second_user.id)

        attempt = response_data['proctored_exam_attempts'][1]
        self.assertEqual(attempt['proctored_exam']['id'], proctored_exam.id)
        self.assertEqual(attempt['user']['id'], self.user.id)

    def test_paginated_exam_attempts(self):
        """
        Test to get the paginated exam attempts in a course.
        """
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )

        # create number of exam attempts
        for i in range(90):
            ProctoredExamStudentAttempt.create_exam_attempt(
                proctored_exam.id, i, 'test_name{0}'.format(i), i + 1,
                'test_attempt_code{0}'.format(i), True, False, 'test_external_id{0}'.format(i)
            )

        self.client.login_user(self.user)
        response = self.client.get(
            reverse(
                'edx_proctoring.proctored_exam.attempts.course',
                kwargs={
                    'course_id': proctored_exam.course_id
                }
            )
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)

        self.assertEqual(len(response_data['proctored_exam_attempts']), 25)
        self.assertTrue(response_data['pagination_info']['has_next'])
        self.assertEqual(response_data['pagination_info']['total_pages'], 4)
        self.assertEqual(response_data['pagination_info']['current_page'], 1)

    def test_stop_others_attempt(self):
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
            reverse('edx_proctoring.proctored_exam.attempt.collection'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertGreater(response_data['exam_attempt_id'], 0)
        old_attempt_id = response_data['exam_attempt_id']

        self.client.login_user(self.second_user)
        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.attempt', args=[old_attempt_id]),
            {}
        )

        self.assertEqual(response.status_code, 400)

    def test_stop_unstarted_attempt(self):
        """
        Start an exam (create an exam attempt)
        """

        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.attempt', args=[0]),
            {}
        )

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['detail'], 'Attempted to access attempt_id 0 but it does not exist.')

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
            reverse('edx_proctoring.proctored_exam.attempt.collection')
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotIn('exam_display_name', data)

        attempt_data = {
            'exam_id': proctored_exam.id,
            'user_id': self.user.id,
            'external_id': proctored_exam.external_id,
            'start_clock': True
        }
        response = self.client.post(
            reverse('edx_proctoring.proctored_exam.attempt.collection'),
            attempt_data
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.attempt.collection')
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['exam_display_name'], 'Test Exam')
        self.assertEqual(data['low_threshold_sec'], 1080)
        self.assertEqual(data['critically_low_threshold_sec'], 270)

    def test_get_expired_attempt(self):
        """
        Test Case for retrieving student proctored exam attempt status after it has expired
        """
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=-90
        )

        attempt_data = {
            'exam_id': proctored_exam.id,
            'user_id': self.user.id,
            'external_id': proctored_exam.external_id,
            'start_clock': True
        }
        response = self.client.post(
            reverse('edx_proctoring.proctored_exam.attempt.collection'),
            attempt_data
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.attempt.collection')
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['time_remaining_seconds'], 0)

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
            reverse('edx_proctoring.proctored_exam.attempt.collection')
        )
        self.assertEqual(response.status_code, 200)

        attempt_data = {
            'exam_id': proctored_exam.id,
            'user_id': self.student_taking_exam.id,
            'external_id': proctored_exam.external_id
        }
        response = self.client.post(
            reverse('edx_proctoring.proctored_exam.attempt.collection'),
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
            reverse('edx_proctoring.proctored_exam.attempt.collection')
        )
        self.assertEqual(response.status_code, 200)

    def test_declined_attempt(self):
        """
        Makes sure that a declined proctored attempt means that he/she fails credit requirement.
        """
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            is_proctored=True,
            time_limit_mins=90
        )
        attempt_data = {
            'exam_id': proctored_exam.id,
            'start_clock': False,
            'attempt_proctored': False
        }
        # create a exam attempt
        response = self.client.post(
            reverse('edx_proctoring.proctored_exam.attempt.collection'),
            attempt_data
        )
        self.assertEqual(response.status_code, 200)

        # make sure we failed the requirement status

        credit_service = get_runtime_service('credit')
        credit_status = credit_service.get_credit_state(self.user.id, proctored_exam.course_id)

        self.assertEqual(len(credit_status['credit_requirement_status']), 1)
        self.assertEqual(
            credit_status['credit_requirement_status'][0]['status'],
            'failed'
        )

    def test_exam_callback(self):
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

        # create an attempt but don't start it
        attempt_data = {
            'exam_id': proctored_exam.id,
            'external_id': proctored_exam.external_id,
            'start_clock': False,
        }
        response = self.client.post(
            reverse('edx_proctoring.proctored_exam.attempt.collection'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)

        self.assertTrue('exam_attempt_id' in response_data)

        attempt_id = response_data['exam_attempt_id']

        # exam should not have started
        attempt = get_exam_attempt_by_id(attempt_id)
        attempt_code = attempt['attempt_code']
        self.assertIsNone(attempt['started_at'])

        response = self.client.get(
            reverse(
                'edx_proctoring.anonymous.proctoring_launch_callback.start_exam',
                args=[attempt_code]
            )
        )
        self.assertEqual(response.status_code, 200)

        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertEqual(attempt['status'], 'ready_to_start')

        # test the polling callback point
        response = self.client.get(
            reverse(
                'edx_proctoring.anonymous.proctoring_poll_status',
                args=[attempt_code]
            )
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'ready_to_start')

    def test_bad_exam_code_callback(self):
        """
        Assert that we get a 404 when doing a callback on an exam code that does not exist
        """
        response = self.client.get(
            reverse(
                'edx_proctoring.anonymous.proctoring_launch_callback.start_exam',
                args=['foo']
            )
        )
        self.assertEqual(response.status_code, 404)

        # test the polling callback point as well
        response = self.client.get(
            reverse(
                'edx_proctoring.anonymous.proctoring_poll_status',
                args=['foo']
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_review_callback(self):
        """
        Simulates a callback from the proctoring service with the
        review data
        """

        exam_id = create_exam(
            course_id='foo/bar/baz',
            content_id='content',
            exam_name='Sample Exam',
            time_limit_mins=10,
            is_proctored=True
        )

        # be sure to use the mocked out SoftwareSecure handlers
        with HTTMock(mock_response_content):
            attempt_id = create_exam_attempt(
                exam_id,
                self.user.id,
                taking_as_proctored=True
            )

        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertIsNotNone(attempt['external_id'])

        test_payload = Template(TEST_REVIEW_PAYLOAD).substitute(
            attempt_code=attempt['attempt_code'],
            external_id=attempt['external_id']
        )

        response = self.client.post(
            reverse('edx_proctoring.anonymous.proctoring_review_callback'),
            data=test_payload,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

    def test_review_caseinsensitive(self):
        """
        Simulates a callback from the proctoring service with the
        review data when we have different casing on the
        external_id property
        """

        exam_id = create_exam(
            course_id='foo/bar/baz',
            content_id='content',
            exam_name='Sample Exam',
            time_limit_mins=10,
            is_proctored=True
        )

        # be sure to use the mocked out SoftwareSecure handlers
        with HTTMock(mock_response_content):
            attempt_id = create_exam_attempt(
                exam_id,
                self.user.id,
                taking_as_proctored=True
            )

        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertIsNotNone(attempt['external_id'])

        test_payload = Template(TEST_REVIEW_PAYLOAD).substitute(
            attempt_code=attempt['attempt_code'],
            external_id=attempt['external_id'].upper()
        )

        response = self.client.post(
            reverse('edx_proctoring.anonymous.proctoring_review_callback'),
            data=test_payload,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

    def test_review_bad_contenttype(self):
        """
        Simulates a callback from the proctoring service when the
        Content-Type is malformed
        """

        exam_id = create_exam(
            course_id='foo/bar/baz',
            content_id='content',
            exam_name='Sample Exam',
            time_limit_mins=10,
            is_proctored=True
        )

        # be sure to use the mocked out SoftwareSecure handlers
        with HTTMock(mock_response_content):
            attempt_id = create_exam_attempt(
                exam_id,
                self.user.id,
                taking_as_proctored=True
            )

        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertIsNotNone(attempt['external_id'])

        test_payload = Template(TEST_REVIEW_PAYLOAD).substitute(
            attempt_code=attempt['attempt_code'],
            external_id=attempt['external_id'].upper()
        )

        response = self.client.post(
            reverse('edx_proctoring.anonymous.proctoring_review_callback'),
            data=test_payload,
            content_type='foo'
        )
        self.assertEqual(response.status_code, 200)

    def test_review_mismatch(self):
        """
        Simulates a callback from the proctoring service with the
        review data but the external_ids don't match
        """

        exam_id = create_exam(
            course_id='foo/bar/baz',
            content_id='content',
            exam_name='Sample Exam',
            time_limit_mins=10,
            is_proctored=True
        )

        # be sure to use the mocked out SoftwareSecure handlers
        with HTTMock(mock_response_content):
            attempt_id = create_exam_attempt(
                exam_id,
                self.user.id,
                taking_as_proctored=True
            )

        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertIsNotNone(attempt['external_id'])

        test_payload = Template(TEST_REVIEW_PAYLOAD).substitute(
            attempt_code=attempt['attempt_code'],
            external_id='mismatch'
        )

        response = self.client.post(
            reverse('edx_proctoring.anonymous.proctoring_review_callback'),
            data=test_payload,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_review_callback_get(self):
        """
        We don't support any http METHOD other than GET
        """

        response = self.client.get(
            reverse('edx_proctoring.anonymous.proctoring_review_callback'),
        )

        self.assertEqual(response.status_code, 405)


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
            'user_info': self.student_taking_exam.username,
            'key': 'a_key',
            'value': '30'
        }
        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.allowance'),
            allowance_data
        )
        self.assertEqual(response.status_code, 200)

    def test_add_invalid_allowance(self):
        """
        Add allowance for a invalid user_info.
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
            'user_info': 'invalid_user',
            'key': 'a_key',
            'value': '30'
        }
        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.allowance'),
            allowance_data
        )
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data['detail'], u"Cannot find user against invalid_user")

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
            'user_info': self.student_taking_exam.email,
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

    def test_get_allowances_for_course(self):
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
            'user_info': self.student_taking_exam.username,
            'key': 'a_key',
            'value': '30'
        }
        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.allowance'),
            allowance_data
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.allowance', kwargs={'course_id': proctored_exam.course_id})
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]['proctored_exam']['course_id'], proctored_exam.course_id)
        self.assertEqual(response_data[0]['key'], allowance_data['key'])


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
