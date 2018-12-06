# pylint: disable=too-many-lines, invalid-name
"""
All tests for the proctored_exams.py
"""

from __future__ import absolute_import

from datetime import datetime, timedelta
import json
import ddt
from freezegun import freeze_time
from httmock import HTTMock
from mock import Mock, patch
import pytz

from django.test.client import Client
from django.urls import reverse, NoReverseMatch
from django.contrib.auth.models import User

from edx_proctoring.models import (
    ProctoredExam,
    ProctoredExamStudentAttempt,
    ProctoredExamStudentAllowance,
)
from edx_proctoring.exceptions import (
    ProctoredExamIllegalStatusTransition,
    StudentExamAttemptDoesNotExistsException, ProctoredExamPermissionDenied)
from edx_proctoring.views import require_staff, require_course_or_global_staff
from edx_proctoring.api import (
    create_exam,
    create_exam_attempt,
    get_exam_attempt_by_id,
    update_attempt_status,
    _calculate_allowed_mins
)
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus
from edx_proctoring.serializers import ProctoredExamSerializer
from edx_proctoring.backends.tests.test_review_payload import create_test_review_payload
from edx_proctoring.backends.tests.test_software_secure import mock_response_content
from edx_proctoring.runtime import set_runtime_service, get_runtime_service
from edx_proctoring.urls import urlpatterns

from .test_services import MockCreditService, MockInstructorService
from .utils import LoggedInTestCase


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
            'is_active': True,
            'hide_after_due': False,
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
            'is_active': True,
            'hide_after_due': False,
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
            json.dumps(updated_exam_data),
            content_type='application/json'
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

    def test_decorator_require_course_or_global_staff(self):  # pylint: disable=invalid-name
        """
        Test assert require_course_or_global_staff before hitting any api url.
        """
        func = Mock()
        decorated_func = require_course_or_global_staff(func)
        request = self.mock_request()
        response = decorated_func(request)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(func.called)

    def mock_request(self):
        """
        mock request
        """
        request = Mock()
        request.data = {}
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
            json.dumps(updated_exam_data),
            content_type='application/json'
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
            time_limit_mins=90,
            is_active=True
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
        message = 'The exam_id does not exist.'
        self.assertEqual(response_data['detail'], message)

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

        set_runtime_service('credit', MockCreditService())
        set_runtime_service('instructor', MockInstructorService(is_user_course_staff=True))

    def _create_exam_attempt(self):
        """
        Create and start the exam attempt, and return the exam attempt object
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

        # Starting exam attempt
        response = self.client.post(
            reverse('edx_proctoring.proctored_exam.attempt.collection'),
            attempt_data
        )
        self.assertEqual(response.status_code, 200)

        return ProctoredExamStudentAttempt.objects.get_exam_attempt(proctored_exam.id, self.user.id)

    def _test_exam_attempt_creation(self):
        """
        Create proctored exam and exam attempt and verify the status of the attempt is "created"
        """

        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_proctored=True,
            backend='test',
        )
        attempt_id = create_exam_attempt(proctored_exam.id, self.user.id, True)
        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertEqual(attempt['status'], "created")

        return attempt

    def _test_repeated_start_exam_callbacks(self, attempt):
        """
        Given an exam attempt, call the start exam callback twice to verify
        that the status in not incorrectly reverted
        """

        # hit callback and verify that exam status is 'ready to start'
        attempt_id = attempt['id']
        code = attempt['attempt_code']
        self.client.get(
            reverse('edx_proctoring.anonymous.proctoring_launch_callback.start_exam', kwargs={'attempt_code': code})
        )
        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertEqual(attempt['status'], "ready_to_start")

        # update exam status to 'started'
        exam_id = attempt['proctored_exam']['id']
        user_id = attempt['user']['id']
        update_attempt_status(exam_id, user_id, ProctoredExamStudentAttemptStatus.started)
        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertEqual(attempt['status'], "started")

        # hit callback again and verify that status is still 'started' and not 'ready to start'
        self.client.get(
            reverse('edx_proctoring.anonymous.proctoring_launch_callback.start_exam', kwargs={'attempt_code': code})
        )
        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertEqual(attempt['status'], "started")
        self.assertNotEqual(attempt['status'], "ready_to_start")

    @ddt.data(
        ('fakeexternalid', 404, ProctoredExamStudentAttemptStatus.created),
        ('testexternalid', 200, ProctoredExamStudentAttemptStatus.ready_to_start)
    )
    @ddt.unpack
    def test_authenticated_start_callback(self, ext_id, http_status, status):
        attempt = self._test_exam_attempt_creation()

        attempt_id = attempt['id']
        response = self.client.post(
            reverse('edx_proctoring.proctored_exam.attempt.ready_callback', kwargs={'external_id': ext_id})
        )
        self.assertEqual(response.status_code, http_status)
        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertEqual(attempt['status'], status)

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
            json.dumps({
                'action': 'start',
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['exam_attempt_id'], old_attempt_id)

        # make sure the exam started
        attempt = get_exam_attempt_by_id(old_attempt_id)
        self.assertIsNotNone(attempt['started_at'])

    def test_start_exam_callback_when_created(self):
        """
        Test that hitting software secure callback URL twice when the attempt state begins at
        'created' does not change the state from 'started' back to 'ready to start'
        """
        attempt = self._test_exam_attempt_creation()
        self._test_repeated_start_exam_callbacks(attempt)

    def test_start_exam_callback_when_download_software_clicked(self):
        """
        Test that hitting software secure callback URL twice when the attempt state begins at
        'download_software_clicked' does not change the state from 'started' back to 'ready to start'
        """
        # Create an exam.
        attempt = self._test_exam_attempt_creation()

        # Update attempt status to 'download_software_clicked'
        exam_id = attempt['proctored_exam']['id']
        user_id = attempt['user']['id']
        update_attempt_status(exam_id, user_id, ProctoredExamStudentAttemptStatus.download_software_clicked)

        self._test_repeated_start_exam_callbacks(attempt)

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
        # make sure we have the accessible human string
        self.assertEqual(response_data['accessibility_time_string'], 'you have 1 hour and 30 minutes remaining')

        # check the special casing of the human string when under a minute
        reset_time = datetime.now(pytz.UTC) + timedelta(minutes=90, seconds=30)
        with freeze_time(reset_time):
            response = self.client.get(
                reverse('edx_proctoring.proctored_exam.attempt', args=[attempt_id])
            )
            self.assertEqual(response.status_code, 200)
            response_data = json.loads(response.content)

            self.assertEqual(response_data['accessibility_time_string'], 'you have less than a minute remaining')

    def test_timer_remaining_time(self):
        """
        Test that remaining time is calculated correctly
        """
        # Create an exam with 30 hours ( 30 * 60)  total time
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=1800
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
        # check that we get timer around 30 hours minus some seconds
        self.assertLessEqual(107990, response_data['time_remaining_seconds'])
        self.assertLessEqual(response_data['time_remaining_seconds'], 108000)
        # check that humanized time
        self.assertEqual(response_data['accessibility_time_string'], 'you have 30 hours remaining')

    def test_time_due_date_between_two_days(self):
        """
        Test that we get correct total time left to attempt if due date is 24+ hours from now and we have set 24+ hours
        time_limit_mins ( 27 hours ) i.e it is like 1 day and 3 hours total time left to attempt the exam.
        """
        # Create an exam with 30 hours ( 1800 minutes ) total time with expected 27 hours time left to attempt.
        expected_total_minutes = 27 * 60
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=1800,
            due_date=datetime.now(pytz.UTC) + timedelta(minutes=expected_total_minutes),
        )
        # _calculate_allowed_mins expects serialized object
        serialized_exam_object = ProctoredExamSerializer(proctored_exam)
        serialized_exam_object = serialized_exam_object.data

        total_minutes = _calculate_allowed_mins(serialized_exam_object, self.user.id)

        # Check that timer has > 24 hours
        self.assertGreater(total_minutes / 60, 24)
        # Get total_minutes around 27 hours. We are checking range here because while testing some seconds have passed.
        self.assertLessEqual(expected_total_minutes - 1, total_minutes)
        self.assertLessEqual(total_minutes, expected_total_minutes)

    def test_attempt_ready_to_start(self):
        """
        Test to get an attempt with ready_to_start status
        and will return the response_data with time time_remaining_seconds to 0
        """
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )
        attempt = ProctoredExamStudentAttempt.create_exam_attempt(
            proctored_exam.id, self.user.id, 'test_user',
            'test_attempt_code', True, False, 'test_external_id'
        )
        attempt.status = ProctoredExamStudentAttemptStatus.ready_to_start
        attempt.save()

        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.attempt', args=[attempt.id])
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['id'], attempt.id)
        self.assertEqual(response_data['proctored_exam']['id'], proctored_exam.id)
        self.assertIsNone(response_data['started_at'])
        self.assertIsNone(response_data['completed_at'])
        self.assertEqual(response_data['time_remaining_seconds'], 0)

    def test_attempt_status_for_exception(self):
        """
        Test to confirm that exception will not effect the API call
        """
        exam_attempt = self._create_exam_attempt()
        exam_attempt.status = ProctoredExamStudentAttemptStatus.verified
        exam_attempt.save()

        # now reset the time to 2 minutes in the future.
        reset_time = datetime.now(pytz.UTC) + timedelta(minutes=2)
        with patch('edx_proctoring.api.update_attempt_status', Mock(side_effect=ProctoredExamIllegalStatusTransition)):
            with freeze_time(reset_time):
                response = self.client.get(
                    reverse('edx_proctoring.proctored_exam.attempt', args=[exam_attempt.id])
                )
                self.assertEqual(response.status_code, 200)

    def test_attempt_status_stickiness(self):
        """
        Test to confirm that a status timeout error will not alter a completed state
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
        self.assertEqual(response_data['status'], ProctoredExamStudentAttemptStatus.started)

        # now switched to a submitted state
        update_attempt_status(
            proctored_exam.id,
            self.user.id,
            ProctoredExamStudentAttemptStatus.submitted
        )

        # now reset the time to 2 minutes in the future.
        reset_time = datetime.now(pytz.UTC) + timedelta(minutes=2)
        with freeze_time(reset_time):
            response = self.client.get(
                reverse('edx_proctoring.proctored_exam.attempt', args=[attempt_id])
            )
            self.assertEqual(response.status_code, 200)
            response_data = json.loads(response.content)
            # make sure the submitted status is sticky
            self.assertEqual(
                response_data['status'],
                ProctoredExamStudentAttemptStatus.submitted
            )

    def test_attempt_with_duedate_expired(self):
        """
        Tests that an exam with duedate passed cannot be accessed
        """
        # create an exam with duedate passed
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            due_date=datetime.now(pytz.UTC) - timedelta(minutes=10),
        )
        attempt_data = {
            'exam_id': proctored_exam.id,
            'external_id': proctored_exam.external_id,
            'start_clock': True,
        }

        # Starting exam attempt
        response = self.client.post(
            reverse('edx_proctoring.proctored_exam.attempt.collection'),
            attempt_data
        )
        self.assertEqual(response.status_code, 400)
        self.assertRaises(ProctoredExamPermissionDenied)

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

        self.user.is_staff = False
        self.user.save()
        response = self.client.delete(
            reverse('edx_proctoring.proctored_exam.attempt', args=[attempt_id])
        )

        self.assertEqual(response.status_code, 200)

    def test_remove_attempt_non_staff(self):
        """
        Confirms that an attempt cannot be removed
        by the not staff/global user
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

        # now set the user is_staff to False
        # and also user is not a course staff
        self.user.is_staff = False
        self.user.save()
        set_runtime_service('instructor', MockInstructorService(is_user_course_staff=False))

        response = self.client.delete(
            reverse('edx_proctoring.proctored_exam.attempt', args=[attempt_id])
        )

        self.assertEqual(response.status_code, 403)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['detail'], 'Must be a Staff User to Perform this request.')

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
            json.dumps({
                'action': 'stop',
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['exam_attempt_id'], old_attempt_id)

    def test_download_software_clicked_action(self):
        """
        Test if the download_software_clicked state is set
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
            json.dumps(attempt_data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertGreater(response_data['exam_attempt_id'], 0)
        old_attempt_id = response_data['exam_attempt_id']

        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.attempt', args=[old_attempt_id]),
            json.dumps({
                'action': 'click_download_software',
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['exam_attempt_id'], old_attempt_id)

        attempt = get_exam_attempt_by_id(old_attempt_id)
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.download_software_clicked)

    @ddt.data(
        ('submit', ProctoredExamStudentAttemptStatus.submitted),
        ('decline', ProctoredExamStudentAttemptStatus.declined),
        ('error', ProctoredExamStudentAttemptStatus.error),
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
            json.dumps({
                'action': action,
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['exam_attempt_id'], old_attempt_id)

        attempt = get_exam_attempt_by_id(response_data['exam_attempt_id'])

        self.assertEqual(attempt['status'], expected_status)

        # we should not be able to restart it
        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.attempt', args=[old_attempt_id]),
            json.dumps({
                'action': 'start',
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)

        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.attempt', args=[old_attempt_id]),
            json.dumps({
                'action': 'stop',
            }),
            content_type='application/json'
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

    def test_exam_attempts_not_global_staff(self):
        """
        Test to get both timed and proctored exam attempts
        in a course as a course staff
        """
        # Create an timed_exam.
        timed_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_proctored=False
        )
        attempt_data = {
            'exam_id': timed_exam.id,
            'user_id': self.student_taking_exam.id,
            'external_id': timed_exam.external_id
        }
        self.client.post(
            reverse('edx_proctoring.proctored_exam.attempt.collection'),
            attempt_data
        )

        # Create a proctored exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content1',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_proctored=True
        )
        attempt_data = {
            'exam_id': proctored_exam.id,
            'user_id': self.student_taking_exam.id,
            'external_id': proctored_exam.external_id
        }
        self.client.post(
            reverse('edx_proctoring.proctored_exam.attempt.collection'),
            attempt_data
        )
        url = reverse('edx_proctoring.proctored_exam.attempts.course', kwargs={'course_id': proctored_exam.course_id})

        self.user.is_staff = False
        self.user.save()

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        # assert that both timed and proctored exam attempts are in response data
        # so the len should be 2
        self.assertEqual(len(response_data['proctored_exam_attempts']), 2)
        self.assertEqual(
            response_data['proctored_exam_attempts'][0]['proctored_exam']['is_proctored'],
            proctored_exam.is_proctored
        )
        self.assertEqual(
            response_data['proctored_exam_attempts'][1]['proctored_exam']['is_proctored'],
            timed_exam.is_proctored
        )

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

    def test_get_filtered_timed_exam_attempts(self):  # pylint: disable=invalid-name
        """
        Test to get the filtered timed exam attempts in a course.
        """
        # Create an exam.
        timed_exm = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_proctored=False
        )
        attempt_data = {
            'exam_id': timed_exm.id,
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

        self.user.is_staff = False
        self.user.save()
        self.client.login_user(self.user)
        response = self.client.get(
            reverse(
                'edx_proctoring.proctored_exam.attempts.search',
                kwargs={
                    'course_id': timed_exm.course_id,
                    'search_by': 'tester'
                }
            )
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)

        self.assertEqual(len(response_data['proctored_exam_attempts']), 2)
        attempt = response_data['proctored_exam_attempts'][0]
        self.assertEqual(attempt['proctored_exam']['id'], timed_exm.id)
        self.assertEqual(attempt['user']['id'], self.second_user.id)

        attempt = response_data['proctored_exam_attempts'][1]
        self.assertEqual(attempt['proctored_exam']['id'], timed_exm.id)
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
                proctored_exam.id, i, 'test_name{0}'.format(i),
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
        # make sure we have the accessible human string
        self.assertEqual(data['accessibility_time_string'], 'you have 1 hour and 30 minutes remaining')

    def test_get_exam_attempt_with_non_staff_user(self):  # pylint: disable=invalid-name
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
        # make sure we have the accessible human string
        self.assertEqual(data['accessibility_time_string'], 'you have 1 hour and 30 minutes remaining')

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
        data = json.loads(response.content)

        attempt = get_exam_attempt_by_id(data['exam_attempt_id'])
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.submitted)

        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.attempt.collection')
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertNotIn('time_remaining_seconds', data)

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

        # make sure we declined the requirement status

        credit_service = get_runtime_service('credit')
        credit_status = credit_service.get_credit_state(self.user.id, proctored_exam.course_id)

        self.assertEqual(len(credit_status['credit_requirement_status']), 1)
        self.assertEqual(
            credit_status['credit_requirement_status'][0]['status'],
            'declined'
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

        self.assertIn('exam_attempt_id', response_data)

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

        test_payload = create_test_review_payload(
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

        test_payload = create_test_review_payload(
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

        test_payload = create_test_review_payload(
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

        test_payload = create_test_review_payload(
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

    @ddt.data(
        (True, True, 'practice'),
        (True, False, 'proctored'),
        (False, False, 'timed')
    )
    @ddt.unpack
    def test_exam_type(self, is_proctored, is_practice, expected_exam_type):
        """
        Testing the exam type
        """
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_proctored=is_proctored,
            is_practice_exam=is_practice
        )

        ProctoredExamStudentAttempt.objects.create(
            proctored_exam=proctored_exam,
            user=self.user,
            allowed_time_limit_mins=90,
            taking_as_proctored=is_proctored,
            is_sample_attempt=is_practice,
            external_id=proctored_exam.external_id,
            status=ProctoredExamStudentAttemptStatus.started
        )

        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.attempt.collection')
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['exam_type'], expected_exam_type)

    def _create_proctored_exam_attempt_with_duedate(self, due_date=datetime.now(pytz.UTC), user=None):
        """
        Test the ProctoredExamAttemptReviewStatus view
        Create the proctored exam with due date
        """
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            external_id='123aXqe3',
            time_limit_mins=30,
            is_proctored=True,
            due_date=due_date
        )

        return ProctoredExamStudentAttempt.objects.create(
            proctored_exam=proctored_exam,
            user=user if user else self.user,
            allowed_time_limit_mins=30,
            taking_as_proctored=True,
            external_id=proctored_exam.external_id,
            status=ProctoredExamStudentAttemptStatus.started
        )

    def test_attempt_review_status_callback(self):
        """
        Test the ProctoredExamAttemptReviewStatus view
        """
        attempt = self._create_proctored_exam_attempt_with_duedate(
            due_date=datetime.now(pytz.UTC) + timedelta(minutes=40)
        )

        response = self.client.put(
            reverse(
                'edx_proctoring.proctored_exam.attempt.review_status',
                args=[attempt.id]
            ),
            {},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

    def test_attempt_review_status_callback_with_doesnotexit_exception(self):
        """
        Test the ProctoredExamAttemptReviewStatus view with does not exit exception
        """
        self._create_proctored_exam_attempt_with_duedate(
            due_date=datetime.now(pytz.UTC) + timedelta(minutes=40)
        )

        response = self.client.put(
            reverse(
                'edx_proctoring.proctored_exam.attempt.review_status',
                args=['5']
            ),
            {},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertRaises(StudentExamAttemptDoesNotExistsException)

    def test_attempt_review_status_callback_with_permission_exception(self):
        """
        Test the ProctoredExamAttemptReviewStatus view with permission exception
        """

        # creating new user for creating exam attempt
        user = User(username='tester_', email='tester@test.com_')
        user.save()

        attempt = self._create_proctored_exam_attempt_with_duedate(
            due_date=datetime.now(pytz.UTC) + timedelta(minutes=40),
            user=user
        )

        response = self.client.put(
            reverse(
                'edx_proctoring.proctored_exam.attempt.review_status',
                args=[attempt.id]
            ),
            {},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertRaises(ProctoredExamPermissionDenied)


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

        set_runtime_service('instructor', MockInstructorService(is_user_course_staff=True))

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
            time_limit_mins=90,
            is_active=True
        )
        allowance_data = {
            'exam_id': proctored_exam.id,
            'user_info': self.student_taking_exam.username,
            'key': 'a_key',
            'value': '30'
        }
        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
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
            time_limit_mins=90,
            is_active=True
        )
        allowance_data = {
            'exam_id': proctored_exam.id,
            'user_info': 'invalid_user',
            'key': 'a_key',
            'value': '30'
        }
        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data['detail'], u"Cannot find user against invalid_user")

    def test_add_invalid_allowance_value(self):
        """
        Add allowance for a invalid user_info.
        """
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True
        )
        allowance_data = {
            'exam_id': proctored_exam.id,
            'user_info': self.student_taking_exam.username,
            'key': 'additional_time_granted',
            'value': 'invalid_value'
        }
        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(
            response_data['detail'],
            u'allowance_value "invalid_value" should be non-negative integer value.'
        )

    def test_add_allowance_for_inactive_exam(self):
        """
        Adding allowance for an inactive exam returns a 400 error.
        """
        # Create an inactive exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=False
        )
        allowance_data = {
            'exam_id': proctored_exam.id,
            'user_info': self.student_taking_exam.username,
            'key': 'a_key',
            'value': '30'
        }
        # Try to add an allowance
        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        # Returns a 400 status.
        self.assertEqual(response.status_code, 400)

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
            time_limit_mins=90,
            is_active=True
        )
        allowance_data = {
            'exam_id': proctored_exam.id,
            'user_info': self.student_taking_exam.email,
            'key': 'a_key',
            'value': '30'
        }
        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        allowance_data.pop('value')

        response = self.client.delete(
            reverse('edx_proctoring.proctored_exam.allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

    def test_add_allowance_non_staff_user(self):  # pylint: disable=invalid-name
        """
        Test to add allowance with not staff/global user
        returns forbidden response.
        """
        self.user.is_staff = False
        self.user.save()
        set_runtime_service('instructor', MockInstructorService(is_user_course_staff=False))
        # Create an exam.
        timed_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_proctored=False
        )
        allowance_data = {
            'exam_id': timed_exam.id,
            'user_info': self.student_taking_exam.username,
            'key': 'a_key',
            'value': '30'
        }
        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 403)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['detail'], 'Must be a Staff User to Perform this request.')

    def test_get_allowances_for_course(self):
        """
        Get allowances for a user for an exam.
        """
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True
        )
        allowance_data = {
            'exam_id': proctored_exam.id,
            'user_info': self.student_taking_exam.username,
            'key': 'a_key',
            'value': '30'
        }
        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
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

    def test_get_allowance_non_staff_user(self):  # pylint: disable=invalid-name
        """
        Test to get allowance of a user with not staff/global user
        returns forbidden response.
        """
        self.user.is_staff = False
        self.user.save()
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True,
            is_proctored=False
        )
        allowance_data = {
            'exam_id': proctored_exam.id,
            'user_info': self.student_taking_exam.username,
            'key': 'a_key',
            'value': '30'
        }
        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        # update the Instructor Mock service to return the course staff to False
        # which will return in the Forbidden request.
        set_runtime_service('instructor', MockInstructorService(is_user_course_staff=False))
        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.allowance', kwargs={'course_id': proctored_exam.course_id})
        )

        self.assertEqual(response.status_code, 403)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['detail'], 'Must be a Staff User to Perform this request.')

    def test_get_timed_exam_allowances_for_course(self):  # pylint: disable=invalid-name
        """
        get the timed exam allowances for the course
        """
        self.user.is_staff = False
        self.user.save()

        # Create an timed exam.
        timed_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True,
            is_proctored=False
        )
        allowance_data = {
            'exam_id': timed_exam.id,
            'user_info': self.student_taking_exam.username,
            'key': 'a_key',
            'value': '30'
        }
        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        # Create proctored exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content1',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True,
            is_proctored=True
        )
        allowance_data = {
            'exam_id': proctored_exam.id,
            'user_info': self.student_taking_exam.username,
            'key': 'a_key',
            'value': '30'
        }
        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.allowance', kwargs={'course_id': proctored_exam.course_id})
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        # assert that both timed and proctored exams allowance are in response data
        # so the len should be 2
        self.assertEqual(len(response_data), 2)
        self.assertEqual(response_data[0]['proctored_exam']['course_id'], timed_exam.course_id)
        self.assertEqual(response_data[0]['proctored_exam']['content_id'], timed_exam.content_id)
        self.assertEqual(response_data[0]['key'], allowance_data['key'])

    def test_get_allowances_for_inactive_exam(self):
        """
        Get allowances for a for an inactive exam should be allowed.
        """
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True
        )
        allowance_data = {
            'exam_id': proctored_exam.id,
            'user_info': self.student_taking_exam.username,
            'key': 'a_key',
            'value': '30'
        }
        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        # now make the exam inactive
        proctored_exam.is_active = False
        proctored_exam.save()

        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.allowance', kwargs={'course_id': proctored_exam.course_id})
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(len(response_data), 1)
        self.assertEqual(response_data[0]['proctored_exam']['course_id'], proctored_exam.course_id)
        self.assertEqual(response_data[0]['key'], allowance_data['key'])

    def test_remove_allowance_for_inactive_exam(self):
        """
        Removing allowance for a user for an inactive exam should be allowed.
        """
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True
        )
        allowance_data = {
            'exam_id': proctored_exam.id,
            'user_info': self.student_taking_exam.email,
            'key': 'a_key',
            'value': '30'
        }

        # Add allowance
        response = self.client.put(
            reverse('edx_proctoring.proctored_exam.allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        allowance_data.pop('value')

        # now make the exam inactive
        proctored_exam.is_active = False
        proctored_exam.save()

        response = self.client.delete(
            reverse('edx_proctoring.proctored_exam.allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
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


class TestInstructorDashboard(LoggedInTestCase):
    """
    Tests for launching the instructor dashboard
    """
    def setUp(self):
        super(TestInstructorDashboard, self).setUp()
        self.user.is_staff = True
        self.user.save()
        self.second_user = User(username='tester2', email='tester2@test.com')
        self.second_user.save()
        self.client.login_user(self.user)

        set_runtime_service('instructor', MockInstructorService(is_user_course_staff=True))

    def test_launch_for_course(self):
        course_id = 'a/b/c'

        ProctoredExam.objects.create(
            course_id=course_id,
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True,
            is_proctored=True,
        )

        expected_url = '/instructor/%s/' % course_id
        response = self.client.get(
            reverse('edx_proctoring.instructor_dashboard_course', args=[course_id])
        )
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    def test_launch_for_exam(self):
        course_id = 'a/b/c'

        proctored_exam = ProctoredExam.objects.create(
            course_id=course_id,
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True,
            is_proctored=True,
        )
        exam_id = proctored_exam.id

        expected_url = '/instructor/%s/?exam=%s' % (course_id, exam_id)
        response = self.client.get(
            reverse('edx_proctoring.instructor_dashboard_exam', kwargs={'course_id': course_id, 'exam_id': exam_id})
        )
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    def test_error_with_multiple_backends(self):
        course_id = 'a/b/c'

        ProctoredExam.objects.create(
            course_id=course_id,
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True,
            is_proctored=True,
            backend='test',
        )
        ProctoredExam.objects.create(
            course_id=course_id,
            content_id='test_content2',
            exam_name='Test Exam',
            external_id='123aXqe4',
            time_limit_mins=90,
            is_active=True,
            is_proctored=True,
            backend='null',
        )
        response = self.client.get(
            reverse('edx_proctoring.instructor_dashboard_course',
                    kwargs={'course_id': course_id})
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Multiple backends for course', response.data)

    def test_error_with_no_exams(self):
        course_id = 'a/b/c'
        response = self.client.get(
            reverse('edx_proctoring.instructor_dashboard_course',
                    kwargs={'course_id': course_id})
        )
        self.assertEqual(response.status_code, 404)

        # test the case of no PROCTORED exams
        ProctoredExam.objects.create(
            course_id=course_id,
            content_id='test_content',
            exam_name='Timed Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True,
            is_proctored=False,
            backend='software_secure',
        )
        response = self.client.get(
            reverse('edx_proctoring.instructor_dashboard_course',
                    kwargs={'course_id': course_id})
        )
        self.assertEqual(response.status_code, 404)

    def test_error_with_no_dashboard(self):
        course_id = 'a/b/d'

        ProctoredExam.objects.create(
            course_id=course_id,
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True,
            is_proctored=True,
            backend='software_secure',
        )
        response = self.client.get(
            reverse('edx_proctoring.instructor_dashboard_course',
                    kwargs={'course_id': course_id})
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual('No instructor dashboard for RPNow', response.data)
