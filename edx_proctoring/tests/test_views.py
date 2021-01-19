# pylint: disable=too-many-lines, invalid-name
"""
All tests for the proctored_exams.py
"""

import json
from datetime import datetime, timedelta
from math import ceil, floor

import ddt
import pytz
from freezegun import freeze_time
from httmock import HTTMock
from mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test.client import Client
from django.urls import NoReverseMatch, reverse

from edx_proctoring.api import (
    _calculate_allowed_mins,
    add_allowance_for_user,
    create_exam,
    create_exam_attempt,
    get_backend_provider,
    get_exam_attempt_by_id,
    update_attempt_status
)
from edx_proctoring.backends.tests.test_review_payload import create_test_review_payload
from edx_proctoring.backends.tests.test_software_secure import mock_response_content
from edx_proctoring.exceptions import (
    ProctoredExamIllegalStatusTransition,
    ProctoredExamPermissionDenied,
    StudentExamAttemptDoesNotExistsException
)
from edx_proctoring.models import (
    ProctoredExam,
    ProctoredExamStudentAllowance,
    ProctoredExamStudentAllowanceHistory,
    ProctoredExamStudentAttempt,
    ProctoredExamStudentAttemptHistory
)
from edx_proctoring.runtime import get_runtime_service, set_runtime_service
from edx_proctoring.serializers import ProctoredExamSerializer
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus
from edx_proctoring.urls import urlpatterns
from edx_proctoring.views import require_course_or_global_staff, require_staff
from mock_apps.models import Profile

from .test_services import MockCreditService, MockGradesService, MockInstructorService
from .utils import LoggedInTestCase

User = get_user_model()


class ProctoredExamsApiTests(LoggedInTestCase):
    """
    All tests for the views.py
    """

    def setUp(self):
        """
        Build out test harnessing
        """
        super().setUp()
        set_runtime_service('credit', MockCreditService())

    def test_no_anonymous_access(self):
        """
        Make sure we cannot access any API methods without being logged in
        """
        self.client = Client()  # use AnonymousUser on the API calls
        for urlpattern in urlpatterns:
            if hasattr(urlpattern, 'name') and 'anonymous.' not in urlpattern.name:
                name = 'edx_proctoring:%s' % urlpattern.name
                try:
                    response = self.client.get(reverse(name))
                except NoReverseMatch:
                    # some of our URL mappings may require a argument substitution
                    try:
                        response = self.client.get(reverse(name, args=[0]))
                    except NoReverseMatch:
                        try:
                            response = self.client.get(reverse(name, args=["0/0/0"]))
                        except NoReverseMatch:
                            # some require 2 args.
                            response = self.client.get(reverse(name, args=["0/0/0", 0]))

                self.assertEqual(response.status_code, 403)


class ProctoredExamViewTests(LoggedInTestCase):
    """
    Tests for the ProctoredExamView
    """
    def setUp(self):
        super().setUp()
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
            reverse('edx_proctoring:proctored_exam.exam'),
            exam_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertGreater(response_data['exam_id'], 0)

        # Now lookup the exam by giving the exam_id returned and match the data.
        response = self.client.get(
            reverse('edx_proctoring:proctored_exam.exam_by_id', kwargs={'exam_id': response_data['exam_id']})
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.exam'),
            exam_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertGreater(response_data['exam_id'], 0)

        response = self.client.post(
            reverse('edx_proctoring:proctored_exam.exam'),
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
            reverse('edx_proctoring:proctored_exam.exam'),
            json.dumps(updated_exam_data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['exam_id'], exam_id)

        # Now lookup the exam by giving the exam_id returned and match the data.
        response = self.client.get(
            reverse('edx_proctoring:proctored_exam.exam_by_id', kwargs={'exam_id': response_data['exam_id']})
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.exam'),
            json.dumps(updated_exam_data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.exam_by_id', kwargs={'exam_id': proctored_exam.id})
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.exam_by_id', kwargs={'exam_id': 99999})
        )
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.exam_by_content_id', kwargs={
                'course_id': proctored_exam.course_id,
                'content_id': proctored_exam.content_id
            })
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.exams_by_course_id', kwargs={
                'course_id': proctored_exam.course_id
            })
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.exam_by_content_id', kwargs={
                'course_id': 'c/d/e',
                'content_id': proctored_exam.content_id
            })
        )
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.exam_by_content_id', kwargs={
                'course_id': proctored_exam.course_id,
                'content_id': proctored_exam.content_id
            })
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['course_id'], proctored_exam.course_id)
        self.assertEqual(response_data['exam_name'], proctored_exam.exam_name)
        self.assertEqual(response_data['content_id'], proctored_exam.content_id)
        self.assertEqual(response_data['external_id'], proctored_exam.external_id)
        self.assertEqual(response_data['time_limit_mins'], proctored_exam.time_limit_mins)


class TestStudentOnboardingStatusView(LoggedInTestCase):
    """
    Tests for StudentOnboardingStatusView
    """
    def setUp(self):
        super().setUp()
        set_runtime_service('credit', MockCreditService())
        set_runtime_service('instructor', MockInstructorService(is_user_course_staff=False))
        self.other_user = User.objects.create(username='otheruser', password='test')

    def _create_onboarding_exam(self):
        """
        Create an onboarding exam
        """
        onboarding_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True,
            is_proctored=True,
            is_practice_exam=True,
            backend='test',
        )
        return onboarding_exam

    def _create_onboarding_exam_attempt(self, onboarding_exam, user):
        """
        Create an exam attempt related to the given onboarding exam
        """
        attempt_id = create_exam_attempt(onboarding_exam.id, user.id, True)
        attempt = ProctoredExamStudentAttempt.objects.filter(id=attempt_id).first()
        return attempt

    def test_no_course_id(self):
        """
        Test that a request without a course_id returns 400 error
        """
        response = self.client.get(reverse('edx_proctoring:user_onboarding.status'))
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content.decode('utf-8'))
        message = 'Missing required query parameter course_id'
        self.assertEqual(response_data['detail'], message)

    def test_no_username(self):
        """
        Test that a request without a username returns the user's own onboarding status
        """
        onboarding_exam = self._create_onboarding_exam()
        # Create the user's own attempt
        own_attempt = self._create_onboarding_exam_attempt(onboarding_exam, self.user)
        own_attempt.status = ProctoredExamStudentAttemptStatus.submitted
        own_attempt.save()
        # Create another user's attempt
        other_attempt = self._create_onboarding_exam_attempt(onboarding_exam, self.other_user)
        other_attempt.status = ProctoredExamStudentAttemptStatus.verified
        other_attempt.save()
        # Assert that the onboarding status returned is 'submitted'
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + '?course_id={}'.format(onboarding_exam.course_id)
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['onboarding_status'], ProctoredExamStudentAttemptStatus.submitted)

    def test_unauthorized(self):
        """
        Test that non-staff cannot view other users' onboarding status
        """
        onboarding_exam = self._create_onboarding_exam()
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + '?username={}&course_id={}'.format(self.other_user.username, onboarding_exam.course_id)
        )
        self.assertEqual(response.status_code, 403)
        response_data = json.loads(response.content.decode('utf-8'))
        message = 'Must be a Staff User to Perform this request.'
        self.assertEqual(response_data['detail'], message)

    def test_staff_authorization(self):
        """
        Test that staff can view other users' onboarding status
        """
        self.user.is_staff = True
        self.user.save()
        onboarding_exam = self._create_onboarding_exam()
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + '?username={}&course_id={}'.format(self.other_user.username, onboarding_exam.course_id)
        )
        self.assertEqual(response.status_code, 200)
        # Should also work for course staff
        set_runtime_service('instructor', MockInstructorService(is_user_course_staff=True))
        self.user.is_staff = False
        self.user.save()
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + '?username={}&course_id={}'.format(self.other_user.username, onboarding_exam.course_id)
        )
        self.assertEqual(response.status_code, 200)

    def test_no_onboarding_exam(self):
        """
        Test that the request returns a 404 error if there is no matching onboarding exam
        """
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + '?course_id=edX/DemoX/Demo_Course'
        )
        self.assertEqual(response.status_code, 404)
        response_data = json.loads(response.content.decode('utf-8'))
        message = 'There is no onboarding exam related to this course id.'
        self.assertEqual(response_data['detail'], message)

    def test_no_exam_attempts(self):
        """
        Test that the onboarding status is None if there are no exam attempts
        """
        onboarding_exam = self._create_onboarding_exam()
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + '?course_id={}'.format(onboarding_exam.course_id)
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertIsNone(response_data['onboarding_status'])
        self.assertEqual(response_data['onboarding_link'], reverse(
            'jump_to',
            args=[onboarding_exam.course_id, onboarding_exam.content_id]
        ))

    def test_no_verified_attempts(self):
        """
        Test that if there are no verified attempts, the most recent status is returned
        """
        onboarding_exam = self._create_onboarding_exam()
        # Create first attempt
        attempt = self._create_onboarding_exam_attempt(onboarding_exam, self.user)
        attempt.status = ProctoredExamStudentAttemptStatus.timed_out
        attempt.save()
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + '?course_id={}'.format(onboarding_exam.course_id)
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['onboarding_status'], ProctoredExamStudentAttemptStatus.timed_out)
        self.assertEqual(response_data['onboarding_link'], reverse(
            'jump_to',
            args=[onboarding_exam.course_id, onboarding_exam.content_id]
        ))
        # Create second attempt and assert that most recent attempt is returned
        attempt = self._create_onboarding_exam_attempt(onboarding_exam, self.user)
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + '?course_id={}'.format(onboarding_exam.course_id)
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['onboarding_status'], ProctoredExamStudentAttemptStatus.created)
        self.assertEqual(response_data['onboarding_link'], reverse(
            'jump_to',
            args=[onboarding_exam.course_id, onboarding_exam.content_id]
        ))

    def test_get_verified_attempt(self):
        """
        Test that if there is at least one verified attempt, the status returned is always verified
        """
        onboarding_exam = self._create_onboarding_exam()
        # Create first attempt
        attempt = self._create_onboarding_exam_attempt(onboarding_exam, self.user)
        attempt.status = ProctoredExamStudentAttemptStatus.verified
        attempt.save()
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + '?course_id={}'.format(onboarding_exam.course_id)
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['onboarding_status'], ProctoredExamStudentAttemptStatus.verified)
        self.assertEqual(response_data['onboarding_link'], reverse(
            'jump_to',
            args=[onboarding_exam.course_id, onboarding_exam.content_id]
        ))
        # Create second attempt and assert that verified attempt is still returned
        attempt = self._create_onboarding_exam_attempt(onboarding_exam, self.user)
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + '?course_id={}'.format(onboarding_exam.course_id)
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['onboarding_status'], ProctoredExamStudentAttemptStatus.verified)
        self.assertEqual(response_data['onboarding_link'], reverse(
            'jump_to',
            args=[onboarding_exam.course_id, onboarding_exam.content_id]
        ))

    def test_only_onboarding_exam(self):
        """
        Test that only onboarding exam attempts are evaluated when requesting onboarding status
        """
        # Create an onboarding exam, along with a practice exam and
        # a proctored exam, all in the same course
        onboarding_exam = self._create_onboarding_exam()
        ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='practice_content',
            exam_name='Practice Exam',
            external_id='123aXqe4',
            time_limit_mins=90,
            is_active=True,
            is_practice_exam=True,
            backend='test',
        )
        ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='proctored_content',
            exam_name='Proctored Exam',
            external_id='123aXqe5',
            time_limit_mins=90,
            is_active=True,
            is_proctored=True,
            backend='test',
        )
        # Assert that the onboarding exam link is returned
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + '?course_id=a/b/c'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        onboarding_link = reverse('jump_to', args=['a/b/c', onboarding_exam.content_id])
        self.assertEqual(response_data['onboarding_link'], onboarding_link)

    def test_ignore_history_table(self):
        """
        Test that deleted attempts are not evaluated when requesting onboarding status
        """
        self.user.is_staff = True
        self.user.save()
        # Create an exam + attempt
        onboarding_exam = self._create_onboarding_exam()
        attempt = self._create_onboarding_exam_attempt(onboarding_exam, self.user)
        # Verify the attempt and assert that the status returns correctly
        attempt.status = ProctoredExamStudentAttemptStatus.verified
        attempt.save()
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + '?course_id={}'.format(onboarding_exam.course_id)
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['onboarding_status'], ProctoredExamStudentAttemptStatus.verified)
        # Delete the attempt
        self.client.delete(
            reverse('edx_proctoring:proctored_exam.attempt', args=[attempt.id])
        )
        # Assert that the status has been cleared and is no longer verified
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + '?course_id={}'.format(onboarding_exam.course_id)
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertIsNone(response_data['onboarding_status'])


@ddt.ddt
class TestStudentProctoredExamAttempt(LoggedInTestCase):
    """
    Tests for the StudentProctoredExamAttempt
    """
    def setUp(self):
        super().setUp()
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
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )
        self.assertEqual(response.status_code, 200)

        return ProctoredExamStudentAttempt.objects.get_current_exam_attempt(proctored_exam.id, self.user.id)

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
            reverse('edx_proctoring:anonymous.proctoring_launch_callback.start_exam', kwargs={'attempt_code': code})
        )
        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertEqual(attempt['status'], "ready_to_start")

        # update exam status to 'started'
        exam_id = attempt['proctored_exam']['id']
        user_id = attempt['user']['id']
        update_attempt_status(exam_id, user_id, ProctoredExamStudentAttemptStatus.started)
        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertEqual(attempt['status'], "started")

        # hit callback again and verify that status has moved to submitted
        self.client.get(
            reverse('edx_proctoring:anonymous.proctoring_launch_callback.start_exam', kwargs={'attempt_code': code})
        )
        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertEqual(attempt['status'], "submitted")
        self.assertNotEqual(attempt['status'], "started")
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
            reverse('edx_proctoring:proctored_exam.attempt.ready_callback', kwargs={'external_id': ext_id})
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
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertGreater(response_data['exam_attempt_id'], 0)

        old_attempt_id = response_data['exam_attempt_id']

        # make sure the exam has not started
        attempt = get_exam_attempt_by_id(old_attempt_id)
        self.assertIsNone(attempt['started_at'])

        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.attempt', args=[old_attempt_id]),
            json.dumps({
                'action': 'start',
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['exam_attempt_id'], old_attempt_id)

        # make sure the exam started
        attempt = get_exam_attempt_by_id(old_attempt_id)
        self.assertIsNotNone(attempt['started_at'])

    def test_start_exam_callback_when_created(self):
        """
        Test that hitting software secure callback URL twice when the attempt state begins at
        'created' changes the state from 'started' to 'submitted' and not back to 'ready to start'
        """
        attempt = self._test_exam_attempt_creation()
        self._test_repeated_start_exam_callbacks(attempt)

    def test_start_exam_callback_when_download_software_clicked(self):
        """
        Test that hitting software secure callback URL twice when the attempt state begins at
        'download_software_clicked' changes the state to 'submitted' and does not change the
        state from 'started' back to 'ready to start'
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
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        attempt_id = response_data['exam_attempt_id']
        self.assertGreater(attempt_id, 0)

        response = self.client.get(
            reverse('edx_proctoring:proctored_exam.attempt', args=[attempt_id])
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
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
                reverse('edx_proctoring:proctored_exam.attempt', args=[attempt_id])
            )
            self.assertEqual(response.status_code, 200)
            response_data = json.loads(response.content.decode('utf-8'))

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
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        attempt_id = response_data['exam_attempt_id']
        self.assertGreater(attempt_id, 0)

        response = self.client.get(
            reverse('edx_proctoring:proctored_exam.attempt', args=[attempt_id])
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['id'], attempt_id)
        self.assertEqual(response_data['proctored_exam']['id'], proctored_exam.id)
        self.assertIsNotNone(response_data['started_at'])
        self.assertIsNone(response_data['completed_at'])
        # check that we get timer around 30 hours minus some seconds
        self.assertLessEqual(107990, response_data['time_remaining_seconds'])
        self.assertLessEqual(response_data['time_remaining_seconds'], 108000)
        # check that humanized time
        self.assertEqual(response_data['accessibility_time_string'], 'you have 30 hours remaining')

    def test_save_time_on_error(self):
        """
        Test that remaining time is saved to the attempt when it reaches an error state
        """
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
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )
        response_data = json.loads(response.content.decode('utf-8'))
        attempt_id = response_data['exam_attempt_id']
        # Initial attempt without time saved
        attempt = ProctoredExamStudentAttempt.objects.get(id=attempt_id)
        self.assertIsNone(attempt.time_remaining_seconds)
        with freeze_time(datetime.now()):
            # Update the attempt to an error state
            self.client.put(
                reverse('edx_proctoring:proctored_exam.attempt', args=[attempt_id]),
                json.dumps({
                    'action': 'error',
                }),
                content_type='application/json'
            )
            attempt = ProctoredExamStudentAttempt.objects.get(id=attempt_id)
            response = self.client.get(
                reverse('edx_proctoring:proctored_exam.attempt', args=[attempt_id])
            )
            response_data = json.loads(response.content.decode('utf-8'))
            # Time saved to the attempt object should match the response
            self.assertIn(
                attempt.time_remaining_seconds,
                [floor(response_data['time_remaining_seconds']), ceil(response_data['time_remaining_seconds'])]
            )

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
            reverse('edx_proctoring:proctored_exam.attempt', args=[attempt.id])
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
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
                    reverse('edx_proctoring:proctored_exam.attempt', args=[exam_attempt.id])
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
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        attempt_id = response_data['exam_attempt_id']
        self.assertEqual(attempt_id, 1)

        response = self.client.get(
            reverse('edx_proctoring:proctored_exam.attempt', args=[attempt_id])
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
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
                reverse('edx_proctoring:proctored_exam.attempt', args=[attempt_id])
            )
            self.assertEqual(response.status_code, 200)
            response_data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )
        self.assertEqual(response.status_code, 403)
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
            reverse('edx_proctoring:proctored_exam.attempt', args=[1])
        )

        self.assertEqual(response.status_code, 400)

        attempt_data = {
            'exam_id': proctored_exam.id,
            'external_id': proctored_exam.external_id,
            'start_clock': True,
        }
        response = self.client.post(
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        attempt_id = response_data['exam_attempt_id']
        self.assertGreater(attempt_id, 0)

        self.user.is_staff = False
        self.user.save()
        response = self.client.delete(
            reverse('edx_proctoring:proctored_exam.attempt', args=[attempt_id])
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
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        attempt_id = response_data['exam_attempt_id']
        self.assertGreater(attempt_id, 0)

        # now set the user is_staff to False
        # and also user is not a course staff
        self.user.is_staff = False
        self.user.save()
        set_runtime_service('instructor', MockInstructorService(is_user_course_staff=False))

        response = self.client.delete(
            reverse('edx_proctoring:proctored_exam.attempt', args=[attempt_id])
        )

        self.assertEqual(response.status_code, 403)
        response_data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        attempt_id = response_data['exam_attempt_id']
        self.assertGreater(attempt_id, 0)

        self.client.login_user(self.second_user)
        response = self.client.get(
            reverse('edx_proctoring:proctored_exam.attempt', args=[attempt_id])
        )
        self.assertEqual(response.status_code, 403)

    def test_read_non_existing_attempt(self):
        """
        Confirms that we cannot read a non-existing attempt
        """
        response = self.client.get(
            reverse('edx_proctoring:proctored_exam.attempt', args=[0])
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
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertGreater(response_data['exam_attempt_id'], 0)

        response = self.client.post(
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertGreater(response_data['exam_attempt_id'], 0)
        old_attempt_id = response_data['exam_attempt_id']

        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.attempt', args=[old_attempt_id]),
            json.dumps({
                'action': 'stop',
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            json.dumps(attempt_data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertGreater(response_data['exam_attempt_id'], 0)
        old_attempt_id = response_data['exam_attempt_id']

        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.attempt', args=[old_attempt_id]),
            json.dumps({
                'action': 'click_download_software',
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertGreater(response_data['exam_attempt_id'], 0)
        old_attempt_id = response_data['exam_attempt_id']

        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.attempt', args=[old_attempt_id]),
            json.dumps({
                'action': action,
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['exam_attempt_id'], old_attempt_id)

        attempt = get_exam_attempt_by_id(response_data['exam_attempt_id'])

        self.assertEqual(attempt['status'], expected_status)

        # we should not be able to restart it
        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.attempt', args=[old_attempt_id]),
            json.dumps({
                'action': 'start',
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)

        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.attempt', args=[old_attempt_id]),
            json.dumps({
                'action': 'stop',
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)

    def test_reset_attempt_action(self):
        """
        Reset a submitted exam back to the created state
        """
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_practice_exam=True
        )
        attempt_data = {
            'exam_id': proctored_exam.id,
            'user_id': self.student_taking_exam.id,
            'external_id': proctored_exam.external_id
        }
        self.client.login_user(self.student_taking_exam)
        response = self.client.post(
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            json.dumps(attempt_data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertGreater(response_data['exam_attempt_id'], 0)
        old_attempt_id = response_data['exam_attempt_id']

        # reject exam, then attempt to reset progress
        set_runtime_service('grades', MockGradesService(rejected_exam_overrides_grade=False))
        update_attempt_status(
            proctored_exam.id, self.student_taking_exam.id, ProctoredExamStudentAttemptStatus.rejected
        )
        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.attempt', args=[old_attempt_id]),
            json.dumps({
                'action': 'reset_attempt',
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        new_attempt_id = response_data['exam_attempt_id']
        self.assertNotEqual(new_attempt_id, old_attempt_id)

        attempt = get_exam_attempt_by_id(new_attempt_id)
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.created)

    @patch('edx_proctoring.views.waffle.switch_is_active')
    def test_attempt_ping_failure_when_submitted(self, mocked_switch_is_active):
        """
        Ping failure should not cause an "error" state transition when
        the learner has submitted their exam. This could happen when
        the learner is browsing the LMS from multiple tabs.
        """
        attempt = self._test_exam_attempt_creation()
        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.attempt', args=[attempt['id']]),
            json.dumps({
                'action': 'submit',
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['exam_attempt_id'], attempt['id'])

        mocked_switch_is_active.return_value = False
        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.attempt', args=[attempt['id']]),
            json.dumps({
                'action': 'error',
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['exam_attempt_id'], False)

    @patch('edx_proctoring.views.waffle.switch_is_active')
    def test_attempt_ping_failure(self, mocked_switch_is_active):
        """
        Test ping failure when backend is configured to permit ping failures
        """
        attempt = self._test_exam_attempt_creation()
        attempt_id = attempt['id']
        attempt_initial_status = attempt['status']

        mocked_switch_is_active.return_value = True
        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.attempt', args=[attempt_id]),
            json.dumps({
                'action': 'error',
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['exam_attempt_id'], False)

        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertEqual(attempt['status'], attempt_initial_status)

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
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )
        url = reverse('edx_proctoring:proctored_exam.attempts.course', kwargs={'course_id': proctored_exam.course_id})
        self.assertEqual(response.status_code, 200)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(len(response_data['proctored_exam_attempts']), 1)

        attempt = response_data['proctored_exam_attempts'][0]
        self.assertEqual(attempt['proctored_exam']['id'], proctored_exam.id)
        self.assertEqual(attempt['user']['id'], self.user.id)

        url = '{url}?page={invalid_page_no}'.format(url=url, invalid_page_no=9999)
        # url with the invalid page # still gives us the first page result.
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
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
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )
        url = reverse('edx_proctoring:proctored_exam.attempts.course', kwargs={'course_id': proctored_exam.course_id})

        self.user.is_staff = False
        self.user.save()

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )
        self.assertEqual(response.status_code, 200)

        self.client.login_user(self.second_user)
        # create a new exam attempt for second student
        response = self.client.post(
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )
        self.assertEqual(response.status_code, 200)

        self.client.login_user(self.user)
        response = self.client.get(
            reverse(
                'edx_proctoring:proctored_exam.attempts.search',
                kwargs={
                    'course_id': proctored_exam.course_id,
                    'search_by': 'tester'
                }
            )
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))

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
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )
        self.assertEqual(response.status_code, 200)

        self.client.login_user(self.second_user)
        # create a new exam attempt for second student
        response = self.client.post(
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )
        self.assertEqual(response.status_code, 200)

        self.user.is_staff = False
        self.user.save()
        self.client.login_user(self.user)
        response = self.client.get(
            reverse(
                'edx_proctoring:proctored_exam.attempts.search',
                kwargs={
                    'course_id': timed_exm.course_id,
                    'search_by': 'tester'
                }
            )
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))

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
            user = User.objects.create(username='student{0}'.format(i), email='student{0}@test.com'.format(i))
            ProctoredExamStudentAttempt.create_exam_attempt(
                proctored_exam.id, user.id, 'test_name{0}'.format(i),
                'test_attempt_code{0}'.format(i), True, False, 'test_external_id{0}'.format(i)
            )

        self.client.login_user(self.user)
        response = self.client.get(
            reverse(
                'edx_proctoring:proctored_exam.attempts.course',
                kwargs={
                    'course_id': proctored_exam.course_id
                }
            )
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))

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
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertGreater(response_data['exam_attempt_id'], 0)
        old_attempt_id = response_data['exam_attempt_id']

        self.client.login_user(self.second_user)
        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.attempt', args=[old_attempt_id]),
            {},
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 403)

    def test_stop_unstarted_attempt(self):
        """
        Start an exam (create an exam attempt)
        """

        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.attempt', args=[0]),
            {}
        )

        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.attempt.collection')
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))
        self.assertNotIn('exam_display_name', data)

        attempt_data = {
            'exam_id': proctored_exam.id,
            'user_id': self.user.id,
            'external_id': proctored_exam.external_id,
            'start_clock': True
        }
        response = self.client.post(
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            reverse('edx_proctoring:proctored_exam.attempt.collection')
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.attempt.collection')
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))
        self.assertNotIn('exam_display_name', data)

        attempt_data = {
            'exam_id': proctored_exam.id,
            'user_id': self.user.id,
            'external_id': proctored_exam.external_id,
            'start_clock': True
        }
        response = self.client.post(
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            reverse('edx_proctoring:proctored_exam.attempt.collection')
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))

        attempt = get_exam_attempt_by_id(data['exam_attempt_id'])
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.submitted)

        response = self.client.get(
            reverse('edx_proctoring:proctored_exam.attempt.collection')
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.attempt.collection')
        )
        self.assertEqual(response.status_code, 200)

        attempt_data = {
            'exam_id': proctored_exam.id,
            'user_id': self.student_taking_exam.id,
            'external_id': proctored_exam.external_id
        }
        response = self.client.post(
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )
        self.assertEqual(response.status_code, 200)

        # pylint: disable=no-member
        ProctoredExamStudentAttempt.objects.filter(
            proctored_exam_id=proctored_exam.id,
            user_id=self.user.id,
            external_id=proctored_exam.external_id,
        ).update(
            started_at=datetime.now(pytz.UTC).replace(year=2013)
        )

        response = self.client.get(
            reverse('edx_proctoring:proctored_exam.attempt.collection')
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
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
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

    def _setup_for_test_exam_callback(self):
        """
        Helper method for setting up a proctored exam attempt via the public API
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
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))

        self.assertIn('exam_attempt_id', response_data)

        return response_data['exam_attempt_id']

    def test_exam_callback(self):
        """
        Start an exam (create an exam attempt)
        """
        attempt_id = self._setup_for_test_exam_callback()

        # exam should not have started
        attempt = get_exam_attempt_by_id(attempt_id)
        attempt_code = attempt['attempt_code']
        self.assertIsNone(attempt['started_at'])

        response = self.client.get(
            reverse(
                'edx_proctoring:anonymous.proctoring_launch_callback.start_exam',
                args=[attempt_code]
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('exam', response.cookies)

        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertEqual(attempt['status'], 'ready_to_start')

    def test_bad_exam_code_callback(self):
        """
        Assert that we get a 404 when doing a callback on an exam code that does not exist
        """
        response = self.client.get(
            reverse(
                'edx_proctoring:anonymous.proctoring_launch_callback.start_exam',
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
            reverse('edx_proctoring:anonymous.proctoring_review_callback'),
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
            reverse('edx_proctoring:anonymous.proctoring_review_callback'),
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
            reverse('edx_proctoring:anonymous.proctoring_review_callback'),
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
            reverse('edx_proctoring:anonymous.proctoring_review_callback'),
            data=test_payload,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_review_callback_get(self):
        """
        We don't support any http METHOD other than GET
        """

        response = self.client.get(
            reverse('edx_proctoring:anonymous.proctoring_review_callback'),
        )

        self.assertEqual(response.status_code, 405)

    @ddt.data(
        (True, True, 'an onboarding exam'),
        (True, False, 'a proctored exam'),
        (False, False, 'a timed exam')
    )
    @ddt.unpack
    def test_exam_type(self, is_proctored, is_practice, expected_exam_type):
        """
        Testing the exam type
        """
        self._test_exam_type(is_proctored, is_practice, expected_exam_type)

    def _test_exam_type(self, is_proctored, is_practice, expected_exam_type):
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
            reverse('edx_proctoring:proctored_exam.attempt.collection')
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(data['exam_type'], expected_exam_type)

    def test_practice_exam_type(self):
        """
        Test practice exam type with short special setup and teardown
        """
        test_backend = get_backend_provider(name='test')
        previous_value = test_backend.supports_onboarding
        test_backend.supports_onboarding = False
        self._test_exam_type(True, True, 'a practice exam')
        test_backend.supports_onboarding = previous_value

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
                'edx_proctoring:proctored_exam.attempt.review_status',
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
                'edx_proctoring:proctored_exam.attempt.review_status',
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
                'edx_proctoring:proctored_exam.attempt.review_status',
                args=[attempt.id]
            ),
            {},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 403)
        self.assertRaises(ProctoredExamPermissionDenied)

    def test_mark_ready_to_resume_attempt_for_self(self):
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
        )

        # POST an exam attempt.
        attempt_data = {
            'exam_id': proctored_exam.id,
            'external_id': proctored_exam.external_id,
            'start_clock': False,
        }

        response = self.client.post(
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )

        # Verify exam attempt was created correctly.
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertGreater(response_data['exam_attempt_id'], 0)

        old_attempt_id = response_data['exam_attempt_id']

        # Make sure the exam has not started.
        attempt = get_exam_attempt_by_id(old_attempt_id)
        self.assertIsNone(attempt['started_at'])

        # Transition the exam attempt into the error state.
        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.attempt', args=[old_attempt_id]),
            json.dumps({
                'action': 'error',
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['exam_attempt_id'], old_attempt_id)

        # Make sure the exam attempt is in the error state.
        attempt = get_exam_attempt_by_id(old_attempt_id)
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.error)

        # Transition the exam attempt into the ready_to_resume state.
        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.attempt', args=[old_attempt_id]),
            json.dumps({
                'action': 'mark_ready_to_resume',
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['exam_attempt_id'], old_attempt_id)

        # Make sure the exam attempt is in the ready_to_resume state.
        attempt = get_exam_attempt_by_id(old_attempt_id)
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.ready_to_resume)

    def test_mark_ready_to_resume_attempt_for_other_as_staff(self):
        """
        Assert that a staff user can submit a "mark_ready_to_resume" action on
        behalf of another user when supplying the user's id in the request body.
        """
        # Log in as student taking the exam.
        self.client.login_user(self.student_taking_exam)

        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
        )

        # POST an exam attempt.
        attempt_data = {
            'exam_id': proctored_exam.id,
            'external_id': proctored_exam.external_id,
            'start_clock': False,
        }

        response = self.client.post(
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )

        # Verify exam attempt was created correctly.
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertGreater(response_data['exam_attempt_id'], 0)

        old_attempt_id = response_data['exam_attempt_id']

        # Make sure the exam has not started.
        attempt = get_exam_attempt_by_id(old_attempt_id)
        self.assertIsNone(attempt['started_at'])

        # Transition the exam attempt into the error state.
        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.attempt', args=[old_attempt_id]),
            json.dumps({
                'action': 'error',
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['exam_attempt_id'], old_attempt_id)

        # Make sure the exam attempt is in the error state.
        attempt = get_exam_attempt_by_id(old_attempt_id)
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.error)

        # Log in the staff user.
        self.client.login_user(self.user)

        # Transition the exam attempt into the ready_to_resume state.
        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.attempt', args=[old_attempt_id]),
            json.dumps({
                'action': 'mark_ready_to_resume',
                'user_id': self.student_taking_exam.id,
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['exam_attempt_id'], old_attempt_id)

        # Make sure the exam attempt is in the ready_to_resume state.
        attempt = get_exam_attempt_by_id(old_attempt_id)
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.ready_to_resume)

    def test_mark_ready_to_resume_attempt_for_other_as_staff_no_user_id(self):
        """
        Assert that a staff user cannot submit any action on behalf of another user without
        specifying the user's id in the request body.Assert that a ProctoredExamPermissionDenied
        exception is raised and that the attempt is unchanged.
        """
        # Log in as student taking the exam.
        self.client.login_user(self.student_taking_exam)

        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
        )

        # POST an exam attempt.
        attempt_data = {
            'exam_id': proctored_exam.id,
            'external_id': proctored_exam.external_id,
            'start_clock': False,
        }

        response = self.client.post(
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )

        # Verify exam attempt was created correctly.
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertGreater(response_data['exam_attempt_id'], 0)

        old_attempt_id = response_data['exam_attempt_id']

        # Make sure the exam has not started.
        attempt = get_exam_attempt_by_id(old_attempt_id)
        self.assertIsNone(attempt['started_at'])

        # Transition the exam attempt into the error state.
        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.attempt', args=[old_attempt_id]),
            json.dumps({
                'action': 'error',
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['exam_attempt_id'], old_attempt_id)

        # Make sure the exam attempt is in the error state.
        attempt = get_exam_attempt_by_id(old_attempt_id)
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.error)

        # Log in the staff user.
        self.client.login_user(self.user)

        # Transition the exam attempt into the ready_to_resume state.
        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.attempt', args=[old_attempt_id]),
            json.dumps({
                'action': 'mark_ready_to_resume',
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 403)
        self.assertRaises(ProctoredExamPermissionDenied)

        # Make sure the exam attempt is in the old state.
        attempt = get_exam_attempt_by_id(old_attempt_id)
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.error)

    def test_mark_ready_to_resume_attempt_for_other_not_as_staff(self):
        """
        Assert that a non-staff user cannot submit any action on behalf of another user.
        Assert that a ProctoredExamPermissionDenied exception
        is raised and that the attempt is unchanged.
        """
        # Don't treat users as course staff by default, so that second_user is
        # not treated as course staff.
        set_runtime_service('instructor', MockInstructorService(is_user_course_staff=False))

        # Log in as student taking the exam.
        self.client.login_user(self.student_taking_exam)

        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
        )

        # POST an exam attempt.
        attempt_data = {
            'exam_id': proctored_exam.id,
            'external_id': proctored_exam.external_id,
            'start_clock': False,
        }

        response = self.client.post(
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )

        # Verify exam attempt was created correctly.
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertGreater(response_data['exam_attempt_id'], 0)

        old_attempt_id = response_data['exam_attempt_id']

        # Make sure the exam has not started.
        attempt = get_exam_attempt_by_id(old_attempt_id)
        self.assertIsNone(attempt['started_at'])

        # Transition the exam attempt into the error state.
        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.attempt', args=[old_attempt_id]),
            json.dumps({
                'action': 'error',
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['exam_attempt_id'], old_attempt_id)

        # Make sure the exam attempt is in the error state.
        attempt = get_exam_attempt_by_id(old_attempt_id)
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.error)

        # Log in the second non-staff user.
        self.client.login_user(self.second_user)

        # Transition the exam attempt into the ready_to_resume state.
        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.attempt', args=[old_attempt_id]),
            json.dumps({
                'action': 'mark_ready_to_resume',
                'user_id': self.student_taking_exam.id,
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 403)
        self.assertRaises(ProctoredExamPermissionDenied)

        # Make sure the exam attempt is in the old state.
        attempt = get_exam_attempt_by_id(old_attempt_id)
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.error)

    @ddt.data(
        'stop',
        'start',
        'submit',
        'click_download_software',
        'reset_attempt',
        'error',
        'decline',
    )
    def test_action_not_mark_ready_to_resume_attempt_for_other_as_staff(self, action):
        """
        Assert that a staff user cannot submit any action on behalf of another user other
        than "mark_ready_to_resume". Assert that a ProctoredExamPermissionDenied exception
        is raised and that the attempt is unchanged.
        """
        # Log in as student taking the exam.
        self.client.login_user(self.student_taking_exam)

        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
        )

        # POST an exam attempt.
        attempt_data = {
            'exam_id': proctored_exam.id,
            'external_id': proctored_exam.external_id,
            'start_clock': False,
        }

        response = self.client.post(
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )

        # Verify exam attempt was created correctly.
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertGreater(response_data['exam_attempt_id'], 0)

        old_attempt_id = response_data['exam_attempt_id']

        # Make sure the exam has not started.
        attempt = get_exam_attempt_by_id(old_attempt_id)
        self.assertIsNone(attempt['started_at'])

        # Log in the staff user.
        self.client.login_user(self.user)

        # Transition the exam attempt into the state defined by the action argument.
        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.attempt', args=[old_attempt_id]),
            json.dumps({
                'action': action,
                'user_id': self.student_taking_exam.id,
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 403)
        self.assertRaises(ProctoredExamPermissionDenied)

        # Make sure the exam attempt is in the ready_to_resume state.
        attempt = get_exam_attempt_by_id(old_attempt_id)
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.created)

    def test_resume_exam_attempt(self):
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
        )

        # POST an exam attempt.
        attempt_data = {
            'exam_id': proctored_exam.id,
            'external_id': proctored_exam.external_id,
            'start_clock': True,
        }
        response = self.client.post(
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )
        response_data = json.loads(response.content.decode('utf-8'))
        old_attempt_id = response_data['exam_attempt_id']

        # Transition the exam attempt into the error state.
        self.client.put(
            reverse('edx_proctoring:proctored_exam.attempt', args=[old_attempt_id]),
            json.dumps({
                'action': 'error',
            }),
            content_type='application/json'
        )

        # POST a new exam attempt - this should fail because the attempt isn't ready to resume yet
        response = self.client.post(
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )
        self.assertEqual(response.status_code, 400)

        # Transition the exam attempt into the ready_to_resume state.
        self.client.put(
            reverse('edx_proctoring:proctored_exam.attempt', args=[old_attempt_id]),
            json.dumps({
                'action': 'mark_ready_to_resume',
            }),
            content_type='application/json'
        )

        # POST a new exam attempt, which should pass this time
        response = self.client.post(
            reverse('edx_proctoring:proctored_exam.attempt.collection'),
            attempt_data
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))

        # GET both created attempts
        url = reverse('edx_proctoring:proctored_exam.attempts.course', kwargs={'course_id': proctored_exam.course_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(len(response_data['proctored_exam_attempts']), 2)
        # assert that the older attempt has transitioned to the 'resumed' status
        self.assertEqual(
            response_data['proctored_exam_attempts'][1]['status'],
            ProctoredExamStudentAttemptStatus.resumed
        )


class TestExamAllowanceView(LoggedInTestCase):
    """
    Tests for the ExamAllowanceView
    """
    def setUp(self):
        super().setUp()
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
            reverse('edx_proctoring:proctored_exam.allowance'),
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
            reverse('edx_proctoring:proctored_exam.allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.allowance'),
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
            reverse('edx_proctoring:proctored_exam.allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        allowance_data.pop('value')

        response = self.client.delete(
            reverse('edx_proctoring:proctored_exam.allowance'),
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
            reverse('edx_proctoring:proctored_exam.allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 403)
        response_data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            reverse('edx_proctoring:proctored_exam.allowance', kwargs={'course_id': proctored_exam.course_id})
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        # update the Instructor Mock service to return the course staff to False
        # which will return in the Forbidden request.
        set_runtime_service('instructor', MockInstructorService(is_user_course_staff=False))
        response = self.client.get(
            reverse('edx_proctoring:proctored_exam.allowance', kwargs={'course_id': proctored_exam.course_id})
        )

        self.assertEqual(response.status_code, 403)
        response_data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.allowance'),
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
            reverse('edx_proctoring:proctored_exam.allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            reverse('edx_proctoring:proctored_exam.allowance', kwargs={'course_id': proctored_exam.course_id})
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        # now make the exam inactive
        proctored_exam.is_active = False
        proctored_exam.save()

        response = self.client.get(
            reverse('edx_proctoring:proctored_exam.allowance', kwargs={'course_id': proctored_exam.course_id})
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
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
            reverse('edx_proctoring:proctored_exam.allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        allowance_data.pop('value')

        # now make the exam inactive
        proctored_exam.is_active = False
        proctored_exam.save()

        response = self.client.delete(
            reverse('edx_proctoring:proctored_exam.allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)


class TestActiveExamsForUserView(LoggedInTestCase):
    """
    Tests for the ActiveExamsForUserView
    """
    def setUp(self):
        super().setUp()
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
            reverse('edx_proctoring:proctored_exam.active_exams_for_user'),
            exams_query_data
        )
        self.assertEqual(response.status_code, 200)


@ddt.ddt
class TestInstructorDashboard(LoggedInTestCase):
    """
    Tests for launching the instructor dashboard
    """
    def setUp(self):
        super().setUp()
        profile = Profile()
        profile.name = 'boo radley'
        profile.user = self.user
        profile.save()
        self.user.is_staff = True
        self.user.save()
        self.second_user = User(username='tester2', email='tester2@test.com')
        self.second_user.save()
        self.client.login_user(self.user)
        self.course_id = 'a/b/c'

        set_runtime_service('instructor', MockInstructorService(is_user_course_staff=True))

    def test_launch_for_course(self):
        ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True,
            is_proctored=True,
        )

        expected_url = '/instructor/%s/' % self.course_id
        response = self.client.get(
            reverse('edx_proctoring:instructor_dashboard_course',
                    kwargs={'course_id': self.course_id})
        )
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    def test_launch_for_exam(self):
        proctored_exam = ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True,
            is_proctored=True,
        )
        exam_id = proctored_exam.id

        expected_url = '/instructor/%s/?exam=%s' % (self.course_id, proctored_exam.external_id)
        dashboard_url = reverse('edx_proctoring:instructor_dashboard_exam',
                                kwargs={'course_id': self.course_id, 'exam_id': exam_id})
        response = self.client.get(dashboard_url)
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)
        # try with an attempt
        attempt_frag = 'attempt=abcde'
        expected_url += '&%s' % attempt_frag
        dashboard_url += '?%s' % attempt_frag
        response = self.client.get(dashboard_url)
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    def test_error_with_multiple_backends(self):
        ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True,
            is_proctored=True,
            backend='test',
        )
        ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='test_content2',
            exam_name='Test Exam',
            external_id='123aXqe4',
            time_limit_mins=90,
            is_active=True,
            is_proctored=True,
            backend='null',
        )
        response = self.client.get(
            reverse('edx_proctoring:instructor_dashboard_course',
                    kwargs={'course_id': self.course_id})
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Multiple backends for course', response.data)

    def test_error_with_no_exams(self):
        response = self.client.get(
            reverse('edx_proctoring:instructor_dashboard_course',
                    kwargs={'course_id': self.course_id})
        )
        self.assertEqual(response.status_code, 404)

        # test the case of no PROCTORED exams
        ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='test_content',
            exam_name='Timed Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True,
            is_proctored=False,
            backend='mock',
        )
        response = self.client.get(
            reverse('edx_proctoring:instructor_dashboard_course',
                    kwargs={'course_id': self.course_id})
        )
        self.assertEqual(response.status_code, 404)

    def test_error_with_no_dashboard(self):
        ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True,
            is_proctored=True,
            backend='mock',
        )
        response = self.client.get(
            reverse('edx_proctoring:instructor_dashboard_course',
                    kwargs={'course_id': self.course_id})
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual('No instructor dashboard for Mock Backend', response.data)

    def test_launch_for_configuration_dashboard(self):
        proctored_exam = ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True,
            is_proctored=True,
        )
        exam_id = proctored_exam.id

        expected_url = '/instructor/%s/?exam=%s&config=true' % (self.course_id, proctored_exam.external_id)
        dashboard_url = reverse('edx_proctoring:instructor_dashboard_exam',
                                kwargs={'course_id': self.course_id, 'exam_id': exam_id})
        response = self.client.get(dashboard_url, {'config': 'true'})
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    @ddt.data(
        (True, True),
        (True, False),
        (False, True),
        (False, False)
    )
    @ddt.unpack
    def test_multiple_exams_returns_correct_dashboard(self, exam_1_is_proctored, exam_2_is_proctored):
        ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True,
            is_proctored=exam_1_is_proctored,
            backend='test',
        )
        ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='test_content2',
            exam_name='Test Exam',
            external_id='123aXqe4',
            time_limit_mins=90,
            is_active=True,
            is_proctored=exam_2_is_proctored,
            backend='test',
        )

        expected_url = '/instructor/%s/' % self.course_id
        response = self.client.get(
            reverse('edx_proctoring:instructor_dashboard_course',
                    kwargs={'course_id': self.course_id})
        )
        if not exam_1_is_proctored and not exam_2_is_proctored:
            self.assertEqual(response.status_code, 404)
            self.assertEqual(
                u'No proctored exams in course {}'.format(self.course_id),
                response.data
            )
        else:
            self.assertRedirects(response, expected_url, fetch_redirect_response=False)


class TestBackendUserDeletion(LoggedInTestCase):
    """
    Tests for deleting user data from backends
    """
    def setUp(self):
        super().setUp()
        self.user.is_staff = True
        self.user.save()
        self.second_user = User(username='tester2', email='tester2@test.com')
        self.second_user.save()
        self.client.login_user(self.user)

    def test_can_delete_user(self):
        deletion_url = reverse('edx_proctoring:backend_user_deletion_api', kwargs={'user_id': self.second_user.id})

        response = self.client.post(deletion_url)
        assert response.status_code == 200
        data = response.json()
        # if there is no user data, then no deletion happens
        assert data == {}

        for i, backend in enumerate(('test', 'null', 'test', None)):
            proctored_exam = ProctoredExam.objects.create(
                course_id='a/b/c',
                content_id='test_content%s' % i,
                exam_name='Test Exam',
                external_id='123aXqe3',
                is_proctored=True,
                is_active=True,
                time_limit_mins=90,
                backend=backend,
            )
            create_exam_attempt(proctored_exam.id, self.second_user.id, bool(backend))

        response = self.client.post(deletion_url)
        assert response.status_code == 200
        data = response.json()
        # if there is an attempt, we'll try to delete from the backend
        assert data == {'test': True}
        test_backend = get_backend_provider(name='test')
        assert test_backend.last_retire_user is not None

        # running a second time will return a false status
        response = self.client.post(deletion_url)
        assert response.status_code == 500
        data = response.json()
        assert len(data) == 1
        assert data == {'test': False}

    def test_no_access(self):
        self.client.login_user(self.second_user)
        deletion_url = reverse('edx_proctoring:backend_user_deletion_api', kwargs={'user_id': self.user.id})

        response = self.client.post(deletion_url)
        assert response.status_code == 403


class TestUserRetirement(LoggedInTestCase):
    """
    Tests for deleting user PII for proctoring
    """
    def setUp(self):
        super().setUp()
        self.user.is_staff = True
        self.user.save()
        self.user_to_retire = User(username='tester2', email='tester2@test.com')
        self.user_to_retire.save()
        self.client.login_user(self.user)
        self.deletion_url = reverse('edx_proctoring:user_retirement_api', kwargs={'user_id': self.user_to_retire.id})

    def _create_proctored_exam(self):
        """ Create a mock proctored exam with common values """
        return ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            is_proctored=True,
            is_active=True,
            time_limit_mins=90,
            backend='test'
        )

    def test_retire_no_access(self):
        """ A user without retirement permissions should not be able to retire other users """
        self.client.login_user(self.user_to_retire)
        deletion_url = reverse('edx_proctoring:user_retirement_api', kwargs={'user_id': self.user.id})

        response = self.client.post(deletion_url)
        assert response.status_code == 403

    def test_retire_user_no_data(self):
        """
        Attempting to retire an unknown user or user with no proctored attempts
        returns 204 but does not carry out a retirment
        """
        response = self.client.post(self.deletion_url)

        assert response.status_code == 204

    def test_retire_user_exam_attempt(self):
        """ Retiring a user should obfuscate PII for exam attempts and return a 204 status """
        # Create an exam attempt
        proctored_exam = self._create_proctored_exam()
        ProctoredExamStudentAttempt.objects.create(
            proctored_exam=proctored_exam,
            user=self.user_to_retire,
            student_name='me',
            last_poll_ipaddr='127.0.0.1'
        )

        # Run the retirement command
        deletion_url = reverse('edx_proctoring:user_retirement_api', kwargs={'user_id': self.user_to_retire.id})
        response = self.client.post(deletion_url)
        assert response.status_code == 204

        retired_attempt = ProctoredExamStudentAttempt.objects.filter(user_id=self.user_to_retire.id).first()
        assert retired_attempt.student_name == ''
        assert retired_attempt.last_poll_ipaddr is None

    def test_retire_user_exam_attempt_history(self):
        """ Retiring a user should obfuscate PII for exam attempt history and return a 204 status """
        # Create and archive an exam attempt so it appears in the history table
        proctored_exam = self._create_proctored_exam()
        ProctoredExamStudentAttemptHistory.objects.create(
            proctored_exam=proctored_exam,
            user=self.user_to_retire,
            student_name='me',
            last_poll_ipaddr='127.0.0.1'
        )

        # Run the retirement command
        response = self.client.post(self.deletion_url)
        assert response.status_code == 204

        retired_attempt_history = ProctoredExamStudentAttemptHistory \
            .objects.filter(user_id=self.user_to_retire.id).first()
        assert retired_attempt_history.student_name == ''
        assert retired_attempt_history.last_poll_ipaddr is None

    def test_retire_user_allowances(self):
        """ Retiring a user should delete their allowances and return a 204 """
        proctored_exam = self._create_proctored_exam()
        add_allowance_for_user(proctored_exam.id, self.user_to_retire.id, 'a_key', 30)

        # Run the retirement command
        response = self.client.post(self.deletion_url)
        assert response.status_code == 204

        retired_allowance = ProctoredExamStudentAllowance \
            .objects.filter(user=self.user_to_retire.id).first()
        assert retired_allowance.value == ''

    def test_retire_user_allowances_history(self):
        """ Retiring a user should delete their allowances and return a 204 """
        proctored_exam = self._create_proctored_exam()
        add_allowance_for_user(proctored_exam.id, self.user_to_retire.id, 'a_key', 30)
        add_allowance_for_user(proctored_exam.id, self.user_to_retire.id, 'a_key', 60)

        # Run the retirement command
        response = self.client.post(self.deletion_url)
        assert response.status_code == 204

        retired_allowance_history = ProctoredExamStudentAllowanceHistory \
            .objects.filter(user=self.user_to_retire.id).first()
        assert retired_allowance_history.value == ''
