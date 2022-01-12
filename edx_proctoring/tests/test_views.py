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
from opaque_keys.edx.locator import BlockUsageLocator

from django.contrib.auth import get_user_model
from django.test.client import Client
from django.test.utils import override_settings
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from edx_proctoring.api import (
    _calculate_allowed_mins,
    add_allowance_for_user,
    create_exam,
    create_exam_attempt,
    get_backend_provider,
    get_exam_attempt_by_id,
    mark_exam_attempt_as_ready_to_resume,
    reset_practice_exam,
    update_attempt_status,
    update_exam
)
from edx_proctoring.backends.tests.test_backend import TestBackendProvider
from edx_proctoring.backends.tests.test_review_payload import create_test_review_payload
from edx_proctoring.backends.tests.test_software_secure import mock_response_content
from edx_proctoring.constants import TIME_MULTIPLIER
from edx_proctoring.exceptions import (
    BackendProviderOnboardingProfilesException,
    ProctoredExamIllegalStatusTransition,
    ProctoredExamPermissionDenied,
    StudentExamAttemptDoesNotExistsException
)
from edx_proctoring.models import (
    ProctoredExam,
    ProctoredExamStudentAllowance,
    ProctoredExamStudentAllowanceHistory,
    ProctoredExamStudentAttempt
)
from edx_proctoring.runtime import get_runtime_service, set_runtime_service
from edx_proctoring.serializers import ProctoredExamSerializer, ProctoredExamStudentAllowanceSerializer
from edx_proctoring.statuses import (
    InstructorDashboardOnboardingAttemptStatus,
    ProctoredExamStudentAttemptStatus,
    VerificientOnboardingProfileStatus
)
from edx_proctoring.tests import mock_perm
from edx_proctoring.urls import urlpatterns
from edx_proctoring.utils import obscured_user_id, resolve_exam_url_for_learning_mfe
from edx_proctoring.views import require_course_or_global_staff, require_staff
from mock_apps.models import Profile

from .test_services import (
    MockCertificateService,
    MockCreditService,
    MockEnrollment,
    MockEnrollmentsService,
    MockGradesService,
    MockInstructorService,
    MockLearningSequencesService,
    MockScheduleItemData
)
from .utils import LoggedInTestCase, ProctoredExamTestCase

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
        set_runtime_service('instructor', MockInstructorService())

    def test_no_anonymous_access(self):
        """
        Make sure we cannot access any API methods without being logged in
        """
        self.client = Client()  # use AnonymousUser on the API calls
        for urlpattern in urlpatterns:
            if hasattr(urlpattern, 'name') and 'anonymous.' not in urlpattern.name:
                name = f'edx_proctoring:{urlpattern.name}'
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
                            try:
                                # some require 2 args. Try first with course id regex match
                                response = self.client.get(reverse(name, args=["0/0/0", 0]))
                            except NoReverseMatch:
                                # next try with a user id or exam id regex match
                                response = self.client.get(reverse(name, args=["000", 0]))

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
        set_runtime_service('instructor', MockInstructorService())

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
        self.assertEqual(
            response_data['detail'],
            f'Attempted to update exam_id={exam_id}, but this exam does not exist.',
        )

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
        self.assertEqual(
            response_data['detail'],
            'Attempted to get exam_id=99999, but this exam does not exist.',
        )

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
        message = (
            f'Cannot find proctored exam in course_id=c/d/e with content_id={proctored_exam.content_id}'
        )
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


@ddt.ddt
class TestStudentOnboardingStatusView(ProctoredExamTestCase):
    """
    Tests for StudentOnboardingStatusView
    """
    def setUp(self):
        super().setUp()

        self.proctored_exam_id = self._create_proctored_exam()
        self.onboarding_exam_id = self._create_onboarding_exam()

        yesterday = timezone.now() - timezone.timedelta(days=1)
        self.course_scheduled_sections = {
            BlockUsageLocator.from_string(self.content_id_onboarding): MockScheduleItemData(yesterday),
            BlockUsageLocator.from_string(
                'block-v1:test+course+1+type@sequential+block@assignment'
            ): MockScheduleItemData(yesterday),
        }

        set_runtime_service('learning_sequences', MockLearningSequencesService(
            list(self.course_scheduled_sections.keys()),
            self.course_scheduled_sections,
        ))
        set_runtime_service('instructor', MockInstructorService(is_user_course_staff=False))
        self.other_user = User.objects.create(username='otheruser', password='test')
        self.onboarding_exam = ProctoredExam.objects.get(id=self.onboarding_exam_id)

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
        # Create the user's own attempt
        attempt_id = create_exam_attempt(self.onboarding_exam_id, self.user.id, True)
        update_attempt_status(attempt_id, ProctoredExamStudentAttemptStatus.submitted)
        # Create another user's attempt
        other_attempt_id = create_exam_attempt(self.onboarding_exam_id, self.other_user.id, True)
        update_attempt_status(other_attempt_id, ProctoredExamStudentAttemptStatus.verified)
        # Assert that the onboarding status returned is 'submitted'
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?course_id={self.onboarding_exam.course_id}'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['onboarding_status'], ProctoredExamStudentAttemptStatus.submitted)

    def test_unauthorized(self):
        """
        Test that non-staff cannot view other users' onboarding status
        """
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?username={self.other_user.username}&course_id={self.course_id}'
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
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?username={self.other_user.username}&course_id={self.course_id}'
        )
        self.assertEqual(response.status_code, 200)
        # Should also work for course staff
        set_runtime_service('instructor', MockInstructorService(is_user_course_staff=True))
        self.user.is_staff = False
        self.user.save()
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?username={self.other_user.username}&course_id={self.course_id}'
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

    @override_settings(LEARNING_MICROFRONTEND_URL='https://learningmfe')
    def test_onboarding_mfe_link(self):
        """
        Test that the request returns correct link to onboarding exam for learning mfe application.
        """
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?course_id={self.course_id}&is_learning_mfe=True'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(
            response_data['onboarding_link'],
            resolve_exam_url_for_learning_mfe(self.course_id, self.onboarding_exam.content_id)
        )

    def test_no_exam_attempts(self):
        """
        Test that the onboarding status is None if there are no exam attempts
        """
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?course_id={self.course_id}'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertIsNone(response_data['onboarding_status'])
        self.assertEqual(response_data['onboarding_link'], reverse(
            'jump_to',
            args=[self.course_id, self.onboarding_exam.content_id]
        ))

    def test_no_verified_attempts(self):
        """
        Test that if there are no verified attempts, the most recent status is returned
        """
        # Create first attempt
        attempt_id = create_exam_attempt(self.onboarding_exam_id, self.user_id, True)
        update_attempt_status(attempt_id, ProctoredExamStudentAttemptStatus.submitted)
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?course_id={self.course_id}'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['onboarding_status'], ProctoredExamStudentAttemptStatus.submitted)
        self.assertEqual(response_data['onboarding_link'], reverse(
            'jump_to',
            args=[self.course_id, self.onboarding_exam.content_id]
        ))
        # Create second attempt and assert that most recent attempt is returned
        create_exam_attempt(self.onboarding_exam_id, self.user_id, True)
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?course_id={self.course_id}'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['onboarding_status'], ProctoredExamStudentAttemptStatus.created)
        self.assertEqual(response_data['onboarding_link'], reverse(
            'jump_to',
            args=[self.course_id, self.onboarding_exam.content_id]
        ))

    def test_get_verified_attempt(self):
        """
        Test that if there is at least one verified attempt, the status returned is always verified
        """
        # Create first attempt
        attempt_id = create_exam_attempt(self.onboarding_exam_id, self.user_id, True)
        update_attempt_status(attempt_id, ProctoredExamStudentAttemptStatus.verified)
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?course_id={self.course_id}'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['onboarding_status'], ProctoredExamStudentAttemptStatus.verified)
        self.assertEqual(response_data['onboarding_link'], reverse(
            'jump_to',
            args=[self.course_id, self.onboarding_exam.content_id]
        ))
        # Create second attempt and assert that verified attempt is still returned
        create_exam_attempt(self.onboarding_exam_id, self.user_id, True)
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?course_id={self.course_id}'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['onboarding_status'], ProctoredExamStudentAttemptStatus.verified)
        self.assertEqual(response_data['onboarding_link'], reverse(
            'jump_to',
            args=[self.course_id, self.onboarding_exam.content_id]
        ))

    def test_verified_in_another_course(self):
        """
        Test that, if there are no verified onboarding attempts in the current course, but there is at least
        one verified attempt in another course, the status will return `other_course_approved` and
        it will also return an `expiration_date`
        """
        proctoring_backend = 'test'
        other_course_id = 'x/y/z'
        other_course_onboarding_exam = ProctoredExam.objects.create(
            course_id=other_course_id,
            content_id='block-v1:test+course+2+type@sequential+block@other_onboard',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True,
            is_proctored=True,
            is_practice_exam=True,
            backend=proctoring_backend
        )
        # Create a submitted attempt in the current course
        attempt_id = create_exam_attempt(self.onboarding_exam_id, self.user_id, True)
        update_attempt_status(attempt_id, ProctoredExamStudentAttemptStatus.submitted)
        # Create an attempt in the other course that has been verified
        attempt_id = create_exam_attempt(self.onboarding_exam_id, self.user_id, True)
        self._create_exam_attempt(
            other_course_onboarding_exam.id, ProctoredExamStudentAttemptStatus.verified, True
        )
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?course_id={self.course_id}'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['onboarding_status'], 'other_course_approved')
        self.assertEqual(response_data['onboarding_link'], reverse(
            'jump_to',
            args=[self.course_id, self.onboarding_exam.content_id]
        ))
        self.assertIsNotNone(response_data['expiration_date'])

    def test_verified_in_multiple_courses(self):
        """
        Test that, if there is both a verified onboarding attempt in the current course, and there is
        a verified attempt in another course, the status will return `verified`
        """
        proctoring_backend = 'test'
        other_course_id = 'x/y/z'
        other_course_onboarding_exam = ProctoredExam.objects.create(
            course_id=other_course_id,
            content_id='block-v1:test+course+2+type@sequential+block@onboard',
            exam_name='test_content',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True,
            is_proctored=True,
            is_practice_exam=True,
            backend=proctoring_backend
        )
        # Create a verified attempt in the current course
        attempt_id = create_exam_attempt(self.onboarding_exam_id, self.user_id, True)
        update_attempt_status(attempt_id, ProctoredExamStudentAttemptStatus.verified)
        # Create an attempt in the other course that has been verified
        self._create_exam_attempt(
            other_course_onboarding_exam.id, ProctoredExamStudentAttemptStatus.verified, True
        )
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?course_id={self.course_id}'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['onboarding_status'], 'verified')
        self.assertEqual(response_data['onboarding_link'], reverse(
            'jump_to',
            args=[self.course_id, self.onboarding_exam.content_id]
        ))

    def test_only_onboarding_exam(self):
        """
        Test that only onboarding exam attempts are evaluated when requesting onboarding status
        """
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + '?course_id=a/b/c'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        onboarding_link = reverse('jump_to', args=['a/b/c', self.onboarding_exam.content_id])
        self.assertEqual(response_data['onboarding_link'], onboarding_link)

    def test_requirements_url_backend_specific(self):
        """
        Test that proctoring backend's setting affects what support center link is put in
        """
        backend = get_backend_provider(name=self.onboarding_exam.backend)
        backend.help_center_article_url = 'https://example.com'
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + '?course_id=a/b/c'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['review_requirements_url'], backend.help_center_article_url)

    def test_ignore_history_table(self):
        """
        Test that deleted attempts are not evaluated when requesting onboarding status
        """
        self.user.is_staff = True
        self.user.save()
        # Verify the attempt and assert that the status returns correctly
        attempt_id = create_exam_attempt(self.onboarding_exam_id, self.user_id, True)
        update_attempt_status(attempt_id, ProctoredExamStudentAttemptStatus.verified)
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?course_id={self.course_id}'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['onboarding_status'], ProctoredExamStudentAttemptStatus.verified)
        # Delete the attempt
        self.client.delete(
            reverse('edx_proctoring:proctored_exam.attempt', args=[attempt_id])
        )
        # Assert that the status has been cleared and is no longer verified
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?course_id={self.course_id}'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertIsNone(response_data['onboarding_status'])

    def test_ineligible_for_onboarding_exam(self):
        """
        Test that the request returns a 404 error if the user cannot view the onboarding exam
        """
        course_sections = self.course_scheduled_sections
        accessible_sequences = list(self.course_scheduled_sections.keys())
        accessible_sequences.remove(BlockUsageLocator.from_string(self.onboarding_exam.content_id))
        set_runtime_service('learning_sequences', MockLearningSequencesService(
            accessible_sequences,
            course_sections,
        ))
        with mock_perm('edx_proctoring.can_take_proctored_exam'):
            response = self.client.get(
                reverse('edx_proctoring:user_onboarding.status')
                + f'?course_id={self.course_id}'
            )
        self.assertEqual(response.status_code, 404)
        response_data = json.loads(response.content.decode('utf-8'))
        message = 'There is no onboarding exam accessible to this user.'
        self.assertEqual(response_data['detail'], message)

    def test_multiple_hidden_onboarding_exams(self):
        """
        If there are multiple onboarding exams we should only link to an exam accessible to the user
        """
        accessible_onboarding_exam = ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='block-v1:test+course+1+type@sequential+block@onboard_visible',
            exam_name=self.exam_name,
            time_limit_mins=self.default_time_limit,
            is_practice_exam=True,
            is_proctored=True,
            backend='test',
            is_active=True,
        )
        inaccessible_onboarding_exam = ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='block-v1:test+course+1+type@sequential+block@onboard_hidden',
            exam_name=self.exam_name,
            time_limit_mins=self.default_time_limit,
            is_practice_exam=True,
            is_proctored=True,
            backend='test',
            is_active=True,
        )
        exam_schedule = MockScheduleItemData(timezone.now() - timedelta(days=1))
        course_sections = {
            BlockUsageLocator.from_string(self.onboarding_exam.content_id): exam_schedule,
            BlockUsageLocator.from_string(accessible_onboarding_exam.content_id): exam_schedule,
            BlockUsageLocator.from_string(inaccessible_onboarding_exam.content_id): exam_schedule,
        }
        set_runtime_service('learning_sequences', MockLearningSequencesService(
            [BlockUsageLocator.from_string(accessible_onboarding_exam.content_id)],  # sections user can see
            course_sections,                                                         # all scheduled sections
        ))
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?course_id={self.course_id}'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['onboarding_status'], None)
        self.assertEqual(response_data['onboarding_link'], reverse(
            'jump_to',
            args=[accessible_onboarding_exam.course_id, accessible_onboarding_exam.content_id]
        ))

    def test_no_accessible_onboarding(self):
        """
        Test that the request returns 404 if onboarding exams exist but none are accessible to the user
        """
        set_runtime_service('learning_sequences', MockLearningSequencesService(
            [],                              # sections user can see (none)
            self.course_scheduled_sections,  # all scheduled sections
        ))
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?course_id={self.course_id}'
        )
        self.assertEqual(response.status_code, 404)
        response_data = json.loads(response.content.decode('utf-8'))
        message = 'There is no onboarding exam accessible to this user.'
        self.assertEqual(response_data['detail'], message)

    def test_no_accessible_onboarding_no_schedule(self):
        """
        Test that the request returns 404 if onboarding exams exist but none are accessible to the user by
        virtue of there being no associated sequence schedule.
        """
        set_runtime_service('learning_sequences', MockLearningSequencesService(
            [],  # sections user can see (none)
            {},  # all scheduled sections
        ))
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?course_id={self.course_id}'
        )
        self.assertEqual(response.status_code, 404)
        response_data = json.loads(response.content.decode('utf-8'))
        message = 'There is no onboarding exam accessible to this user.'
        self.assertEqual(response_data['detail'], message)

    @ddt.data(None, timezone.now() + timezone.timedelta(days=3))
    def test_onboarding_not_yet_released(self, due_date):
        """
        If the onboarding section has not been released the release date is returned
        """
        tomorrow = timezone.now() + timezone.timedelta(days=1)
        self.course_scheduled_sections[
            BlockUsageLocator.from_string(self.onboarding_exam.content_id)
        ] = MockScheduleItemData(tomorrow, due_date=due_date)

        set_runtime_service('learning_sequences', MockLearningSequencesService(
            [],
            self.course_scheduled_sections,
        ))

        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?course_id={self.onboarding_exam.course_id}'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['onboarding_status'], None)
        self.assertEqual(response_data['onboarding_link'], None)
        self.assertEqual(response_data['onboarding_release_date'], tomorrow.isoformat())

    def test_onboarding_past_due(self):
        """
        If the onboarding section is past due, the release date and a flag indicating that onboarding
        is past due are returned.
        """
        two_days_ago = timezone.now() - timezone.timedelta(days=2)
        yesterday = timezone.now() - timezone.timedelta(days=1)
        self.course_scheduled_sections[
            BlockUsageLocator.from_string(self.onboarding_exam.content_id)
        ] = MockScheduleItemData(two_days_ago, due_date=yesterday)

        set_runtime_service('learning_sequences', MockLearningSequencesService(
            [],
            self.course_scheduled_sections,
        ))

        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?course_id={self.onboarding_exam.course_id}'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['onboarding_past_due'], True)
        self.assertEqual(response_data['onboarding_status'], None)
        self.assertEqual(response_data['onboarding_link'], None)
        self.assertEqual(response_data['onboarding_release_date'], two_days_ago.isoformat())

    def test_multiple_onboarding_exams_all_past_due(self):
        """
        If there are multiple past due onboarding exams, then the release date of the most
        recently created onboarding exam and a flag indicating that onboarding is past due
        are returned.
        """
        onboarding_exam_2 = ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='block-v1:test+course+1+type@sequential+block@onboard_2',
            exam_name=self.exam_name,
            time_limit_mins=self.default_time_limit,
            is_practice_exam=True,
            is_proctored=True,
            backend='test',
            is_active=True,
        )
        three_days_ago = timezone.now() - timezone.timedelta(days=3)
        onboarding_exam_1_schedule = MockScheduleItemData(
            timezone.now() - timezone.timedelta(days=2),
            timezone.now() - timezone.timedelta(days=1)
        )
        onboarding_exam_2_schedule = MockScheduleItemData(
            three_days_ago,
            timezone.now() - timezone.timedelta(days=1)
        )
        course_sections = {
            BlockUsageLocator.from_string(self.onboarding_exam.content_id): onboarding_exam_1_schedule,
            BlockUsageLocator.from_string(onboarding_exam_2.content_id): onboarding_exam_2_schedule,
        }
        set_runtime_service('learning_sequences', MockLearningSequencesService(
            [],               # sections user can see
            course_sections,  # all scheduled sections
        ))
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?course_id={self.course_id}'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['onboarding_past_due'], True)
        self.assertEqual(response_data['onboarding_status'], None)
        self.assertEqual(response_data['onboarding_link'], None)
        self.assertEqual(response_data['onboarding_release_date'], three_days_ago.isoformat())

    def test_multiple_onboarding_exams_all_to_be_released(self):
        """
        If there are multiple onboarding exams to be released, then the release date of the most
        recently created onboarding exam is returned.
        """
        onboarding_exam_2 = ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='block-v1:test+course+1+type@sequential+block@onboard_2',
            exam_name=self.exam_name,
            time_limit_mins=self.default_time_limit,
            is_practice_exam=True,
            is_proctored=True,
            backend='test',
            is_active=True,
        )
        three_days_in_future = timezone.now() + timezone.timedelta(days=3)
        onboarding_exam_1_schedule = MockScheduleItemData(timezone.now() + timezone.timedelta(days=2))
        onboarding_exam_2_schedule = MockScheduleItemData(three_days_in_future)
        course_sections = {
            BlockUsageLocator.from_string(self.onboarding_exam.content_id): onboarding_exam_1_schedule,
            BlockUsageLocator.from_string(onboarding_exam_2.content_id): onboarding_exam_2_schedule,
        }
        set_runtime_service('learning_sequences', MockLearningSequencesService(
            [],               # sections user can see
            course_sections,  # all scheduled sections
        ))
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?course_id={self.course_id}'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['onboarding_past_due'], False)
        self.assertEqual(response_data['onboarding_status'], None)
        self.assertEqual(response_data['onboarding_link'], None)
        self.assertEqual(response_data['onboarding_release_date'], three_days_in_future.isoformat())

    def test_multiple_onboarding_exams_mixed_favor_currently_available(self):
        """
        If there are multiple onboarding exams, and some are to be released, some are past due,
        and some are currently available, then the to be currently available exam(s) is/are favored,
        and the release date of and link to the most recently created onboarding exam
        is returned.
        """
        onboarding_exam_2 = ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='block-v1:test+course+1+type@sequential+block@onboard_2',
            exam_name=self.exam_name,
            time_limit_mins=self.default_time_limit,
            is_practice_exam=True,
            is_proctored=True,
            backend='test',
            is_active=True,
        )
        onboarding_exam_3 = ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='block-v1:test+course+1+type@sequential+block@onboard_3',
            exam_name=self.exam_name,
            time_limit_mins=self.default_time_limit,
            is_practice_exam=True,
            is_proctored=True,
            backend='test',
            is_active=True,
        )
        tomorrow = timezone.now() + timezone.timedelta(days=1)
        onboarding_exam_1_schedule = MockScheduleItemData(
            timezone.now() - timezone.timedelta(days=2),
            timezone.now() - timezone.timedelta(days=1),
        )
        onboarding_exam_2_schedule = MockScheduleItemData(timezone.now() + timezone.timedelta(days=1))
        onboarding_exam_3_schedule = MockScheduleItemData(tomorrow)
        course_sections = {
            BlockUsageLocator.from_string(self.onboarding_exam.content_id): onboarding_exam_1_schedule,
            BlockUsageLocator.from_string(onboarding_exam_2.content_id): onboarding_exam_2_schedule,
            BlockUsageLocator.from_string(onboarding_exam_3.content_id): onboarding_exam_3_schedule,
        }
        set_runtime_service('learning_sequences', MockLearningSequencesService(
            [BlockUsageLocator.from_string(onboarding_exam_3.content_id)],  # sections user can see
            course_sections,                                                # all scheduled sections
        ))
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?course_id={self.course_id}'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['onboarding_past_due'], False)
        self.assertEqual(response_data['onboarding_status'], None)
        self.assertEqual(response_data['onboarding_link'], reverse(
            'jump_to',
            args=[onboarding_exam_3.course_id, onboarding_exam_3.content_id]
        ))
        self.assertEqual(response_data['onboarding_release_date'], tomorrow.isoformat())

    @patch('edx_proctoring.api.constants.ONBOARDING_PROFILE_API', True)
    @patch('logging.Logger.warning')
    @patch.object(TestBackendProvider, 'get_onboarding_profile_info')
    @ddt.data(
        (VerificientOnboardingProfileStatus.no_profile, None),
        (VerificientOnboardingProfileStatus.other_course_approved,
         InstructorDashboardOnboardingAttemptStatus.other_course_approved),
        (VerificientOnboardingProfileStatus.approved, ProctoredExamStudentAttemptStatus.verified),
        (VerificientOnboardingProfileStatus.rejected, ProctoredExamStudentAttemptStatus.rejected),
        (VerificientOnboardingProfileStatus.pending, ProctoredExamStudentAttemptStatus.submitted),
        (VerificientOnboardingProfileStatus.expired, ProctoredExamStudentAttemptStatus.expired)
    )
    @ddt.unpack
    def test_onboarding_with_api_endpoint(self, api_status, attempt_status, mocked_onboarding_api,
                                          mock_logger):
        set_runtime_service('grades', MockGradesService(rejected_exam_overrides_grade=False))

        if attempt_status:
            attempt_id = create_exam_attempt(self.onboarding_exam_id, self.user_id, True)
            update_attempt_status(attempt_id, attempt_status)

        mocked_onboarding_api.return_value = {
            'user_id': '123abc',
            'status': api_status,
            'expiration_date': '2051-05-21'
        }

        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?course_id={self.onboarding_exam.course_id}'
        )

        mocked_onboarding_api.assert_called_with(
            self.onboarding_exam.course_id,
            user_id=obscured_user_id(self.user_id, self.onboarding_exam.backend)
        )

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['onboarding_status'], attempt_status)
        self.assertEqual(response_data['expiration_date'], '2051-05-21')
        mock_logger.assert_not_called()

    @patch('edx_proctoring.api.constants.ONBOARDING_PROFILE_API', True)
    @patch('logging.Logger.error')
    @patch.object(TestBackendProvider, 'get_onboarding_profile_info')
    def test_onboarding_with_differing_data(self, mocked_onboarding_api, mock_logger):
        attempt_id = create_exam_attempt(self.onboarding_exam_id, self.user_id, True)
        update_attempt_status(attempt_id, ProctoredExamStudentAttemptStatus.submitted)

        mocked_onboarding_api.return_value = {
            'user_id': self.user_id,
            'status': VerificientOnboardingProfileStatus.approved,
            'expiration_date': '2051-05-21'
        }

        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?course_id={self.onboarding_exam.course_id}'
        )

        mocked_onboarding_api.assert_called_with(
            self.onboarding_exam.course_id,
            user_id=obscured_user_id(self.user_id, self.onboarding_exam.backend)
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['onboarding_status'], 'verified')
        self.assertEqual(response_data['expiration_date'], '2051-05-21')
        mock_logger.assert_called()

    @patch('edx_proctoring.api.constants.ONBOARDING_PROFILE_API', True)
    @patch.object(TestBackendProvider, 'get_onboarding_profile_info')
    def test_onboarding_with_api_404(self, mocked_onboarding_api):
        attempt_id = create_exam_attempt(self.onboarding_exam_id, self.user_id, True)
        update_attempt_status(attempt_id, ProctoredExamStudentAttemptStatus.submitted)

        mocked_onboarding_api.return_value = None

        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?course_id={self.onboarding_exam.course_id}'
        )
        self.assertEqual(response.status_code, 404)

    @patch('edx_proctoring.api.constants.ONBOARDING_PROFILE_API', True)
    @patch('logging.Logger.warning')
    @patch.object(TestBackendProvider, 'get_onboarding_profile_info')
    def test_onboarding_with_api_failure(self, mocked_onboarding_api, mock_logger):
        attempt_id = create_exam_attempt(self.onboarding_exam_id, self.user_id, True)
        update_attempt_status(attempt_id, ProctoredExamStudentAttemptStatus.submitted)

        mocked_onboarding_api.side_effect = BackendProviderOnboardingProfilesException('some error', 403)

        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?course_id={self.onboarding_exam.course_id}'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['onboarding_status'], 'submitted')
        self.assertEqual(response_data['expiration_date'], None)
        mock_logger.assert_called()

    def test_multiple_onboarding_exams_mixed_favor_to_be_released(self):
        """
        If there are multiple onboarding exams, and some are to be released and some are past due, the
        to be released exam(s) is/are favored, and the release date of the most recently created onboarding exam
        is returned.
        """
        onboarding_exam_2 = ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='block-v1:test+course+1+type@sequential+block@onboard_2',
            exam_name=self.exam_name,
            time_limit_mins=self.default_time_limit,
            is_practice_exam=True,
            is_proctored=True,
            backend='test',
            is_active=True,
        )
        tomorrow = timezone.now() + timezone.timedelta(days=1)
        onboarding_exam_1_schedule = MockScheduleItemData(
            timezone.now() - timezone.timedelta(days=2),
            timezone.now() - timezone.timedelta(days=1),
        )
        onboarding_exam_2_schedule = MockScheduleItemData(tomorrow)
        course_sections = {
            BlockUsageLocator.from_string(self.onboarding_exam.content_id): onboarding_exam_1_schedule,
            BlockUsageLocator.from_string(onboarding_exam_2.content_id): onboarding_exam_2_schedule,
        }
        set_runtime_service('learning_sequences', MockLearningSequencesService(
            [],               # sections user can see
            course_sections,  # all scheduled sections
        ))
        response = self.client.get(
            reverse('edx_proctoring:user_onboarding.status')
            + f'?course_id={self.course_id}'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['onboarding_past_due'], False)
        self.assertEqual(response_data['onboarding_status'], None)
        self.assertEqual(response_data['onboarding_link'], None)
        self.assertEqual(response_data['onboarding_release_date'], tomorrow.isoformat())


@ddt.ddt
class TestStudentOnboardingStatusByCourseView(ProctoredExamTestCase):
    """Tests for StudentOnboardingStatusByCourseView"""
    def setUp(self):
        super().setUp()
        self.user.is_staff = True
        self.user.save()

        self.proctored_exam_id = self._create_proctored_exam()
        self.onboarding_exam_id = self._create_onboarding_exam()

        # add some more users
        self.learner_1 = User(username='user1', email='learner_1@test.com')
        self.learner_1.save()
        self.learner_2 = User(username='user2', email='learner_2@test.com')
        self.learner_2.save()

        self.enrollment_modes = ['verified', 'masters', 'executive-education']
        enrollments = [
            {
                'user': self.user,
                'mode': self.enrollment_modes[0],
            },
            {
                'user': self.learner_1,
                'mode': self.enrollment_modes[1],
            },
            {
                'user': self.learner_2,
                'mode': self.enrollment_modes[2],
            },
        ]
        set_runtime_service('enrollments', MockEnrollmentsService(enrollments))
        set_runtime_service('certificates', MockCertificateService())
        set_runtime_service('grades', MockGradesService())

        self.onboarding_exam = ProctoredExam.objects.get(id=self.onboarding_exam_id)

    def test_no_onboarding_exams(self):
        self.onboarding_exam.delete()
        response = self.client.get(reverse(
                'edx_proctoring:user_onboarding.status.course',
                kwargs={'course_id': 'a/b/c'}
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_backend_does_not_support_onboarding(self):
        test_backend = get_backend_provider(name='test')
        previous_value = test_backend.supports_onboarding
        test_backend.supports_onboarding = False
        response = self.client.get(reverse(
                'edx_proctoring:user_onboarding.status.course',
                kwargs={'course_id': 'a/b/c'}
            )
        )
        self.assertEqual(response.status_code, 404)
        test_backend.supports_onboarding = previous_value

    def test_multiple_onboarding_exams(self):
        onboarding_exam_2_id = create_exam(
            course_id=self.course_id,
            content_id='test_content_2',
            exam_name=self.exam_name,
            time_limit_mins=self.default_time_limit,
            is_practice_exam=True,
            is_proctored=True,
            backend='test',
        )

        create_exam_attempt(self.onboarding_exam.id, self.user.id, True)
        onboarding_attempt_2_id = create_exam_attempt(onboarding_exam_2_id, self.user.id, True)

        update_attempt_status(onboarding_attempt_2_id, ProctoredExamStudentAttemptStatus.submitted)
        # get serialized onboarding_attempt because modified time has changed
        serialized_onboarding_attempt = get_exam_attempt_by_id(onboarding_attempt_2_id)

        response = self.client.get(reverse(
                'edx_proctoring:user_onboarding.status.course',
                kwargs={'course_id': self.course_id}
            )
        )
        response_data = json.loads(response.content.decode('utf-8'))

        expected_data = {
            'results': [
                {
                    'username': self.user.username,
                    'enrollment_mode': self.enrollment_modes[0],
                    'status': InstructorDashboardOnboardingAttemptStatus.submitted,
                    'modified': serialized_onboarding_attempt['modified'] if serialized_onboarding_attempt else None,
                },
                {
                    'username': self.learner_1.username,
                    'enrollment_mode': self.enrollment_modes[1],
                    'status': InstructorDashboardOnboardingAttemptStatus.not_started,
                    'modified': None,
                },
                {
                    'username': self.learner_2.username,
                    'enrollment_mode': self.enrollment_modes[2],
                    'status': InstructorDashboardOnboardingAttemptStatus.not_started,
                    'modified': None,
                }
            ],
            'count': 3,
            'previous': None,
            'next': None,
            'num_pages': 1,
            'use_onboarding_profile_api': False,
        }

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_data, expected_data)

    @patch('edx_proctoring.views.ATTEMPTS_PER_PAGE', 1)
    def test_basic_pagination(self):
        create_exam_attempt(self.onboarding_exam.id, self.user_id, True)
        create_exam_attempt(self.onboarding_exam.id, self.learner_1.id, True)
        create_exam_attempt(self.onboarding_exam.id, self.learner_2.id, True)

        response = self.client.get(reverse(
                'edx_proctoring:user_onboarding.status.course',
                kwargs={'course_id': self.onboarding_exam.course_id}
            ),
            {
                'page': 2,
            }
        )
        response_data = json.loads(response.content.decode('utf-8'))

        base_url = reverse('edx_proctoring:user_onboarding.status.course',
                           kwargs={'course_id': self.onboarding_exam.course_id}
                           )

        self.assertEqual(response_data['count'], 3)
        self.assertEqual(response_data['previous'], base_url + '?page=1')
        self.assertEqual(response_data['next'], base_url + '?page=3')
        self.assertEqual(response_data['num_pages'], 3)

    @patch('edx_proctoring.views.ATTEMPTS_PER_PAGE', 1)
    def test_pagination_maintains_query_params(self):
        create_exam_attempt(self.onboarding_exam.id, self.user.id, True)
        create_exam_attempt(self.onboarding_exam.id, self.learner_1.id, True)
        create_exam_attempt(self.onboarding_exam.id, self.learner_2.id, True)

        response = self.client.get(reverse(
                'edx_proctoring:user_onboarding.status.course',
                kwargs={'course_id': self.onboarding_exam.course_id}
            ),
            {
                'page': 2,
                'statuses': InstructorDashboardOnboardingAttemptStatus.setup_started,
                'text_search': 'test.com',
            }
        )
        response_data = json.loads(response.content.decode('utf-8'))

        self.assertEqual(response_data['count'], 3)
        self.assertEqual(response_data['num_pages'], 3)

        base_url = reverse('edx_proctoring:user_onboarding.status.course',
                           kwargs={'course_id': self.onboarding_exam.course_id}
                           )
        previous_url = response_data['previous']
        next_url = response_data['next']
        text_search_string = 'text_search=test.com'
        status_filters_string = f'statuses={InstructorDashboardOnboardingAttemptStatus.setup_started}'

        self.assertIn(base_url, previous_url)
        self.assertIn('page=1', previous_url)
        self.assertIn(text_search_string, previous_url)
        self.assertIn(status_filters_string, previous_url)

        self.assertIn(base_url, next_url)
        self.assertIn('page=3', next_url)
        self.assertIn(text_search_string, next_url)
        self.assertIn(status_filters_string, next_url)

    def test_one_status_filter(self):
        first_attempt_id = create_exam_attempt(self.onboarding_exam.id, self.user.id, True)
        second_attempt_id = create_exam_attempt(self.onboarding_exam.id, self.learner_1.id, True)
        update_attempt_status(
            second_attempt_id,
            ProctoredExamStudentAttemptStatus.download_software_clicked
        )

        # get serialized onboarding_attempt to get modified time
        first_serialized_onboarding_attempt = get_exam_attempt_by_id(first_attempt_id)
        second_serialized_onboarding_attempt = get_exam_attempt_by_id(second_attempt_id)

        response = self.client.get(reverse(
                'edx_proctoring:user_onboarding.status.course',
                kwargs={'course_id': self.onboarding_exam.course_id}
            ),
            {
                'statuses': InstructorDashboardOnboardingAttemptStatus.setup_started
            }
        )

        response_data = json.loads(response.content.decode('utf-8'))
        expected_data = {
            'results': [
                {
                    'username': self.user.username,
                    'enrollment_mode': self.enrollment_modes[0],
                    'status': InstructorDashboardOnboardingAttemptStatus.setup_started,
                    'modified': (first_serialized_onboarding_attempt['modified']
                                 if first_serialized_onboarding_attempt else None
                                 )
                },
                {
                    'username': self.learner_1.username,
                    'enrollment_mode': self.enrollment_modes[1],
                    'status': InstructorDashboardOnboardingAttemptStatus.setup_started,
                    'modified': (second_serialized_onboarding_attempt['modified']
                                 if second_serialized_onboarding_attempt else None
                                 )
                },
            ],
            'count': 2,
            'previous': None,
            'next': None,
            'num_pages': 1,
            'use_onboarding_profile_api': False,
        }

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_data, expected_data)

    def test_multiple_status_filters(self):
        first_attempt_id = create_exam_attempt(self.onboarding_exam.id, self.user.id, True)
        second_attempt_id = create_exam_attempt(self.onboarding_exam.id, self.learner_1.id, True)

        update_attempt_status(second_attempt_id, ProctoredExamStudentAttemptStatus.verified)

        # get serialized onboarding_attempt to get modified time
        first_serialized_onboarding_attempt = get_exam_attempt_by_id(first_attempt_id)
        second_serialized_onboarding_attempt = get_exam_attempt_by_id(second_attempt_id)

        response = self.client.get(reverse(
                'edx_proctoring:user_onboarding.status.course',
                kwargs={'course_id': self.onboarding_exam.course_id}
            ),
            {
                'statuses': ','.join([
                    InstructorDashboardOnboardingAttemptStatus.setup_started,
                    InstructorDashboardOnboardingAttemptStatus.verified
                ])
            }
        )

        response_data = json.loads(response.content.decode('utf-8'))
        expected_data = {
            'results': [
                {
                    'username': self.user.username,
                    'enrollment_mode': self.enrollment_modes[0],
                    'status': InstructorDashboardOnboardingAttemptStatus.setup_started,
                    'modified': (first_serialized_onboarding_attempt['modified']
                                 if first_serialized_onboarding_attempt else None
                                 )
                },
                {
                    'username': self.learner_1.username,
                    'enrollment_mode': self.enrollment_modes[1],
                    'status': InstructorDashboardOnboardingAttemptStatus.verified,
                    'modified': (second_serialized_onboarding_attempt['modified']
                                 if second_serialized_onboarding_attempt else None
                                 )
                },
            ],
            'count': 2,
            'previous': None,
            'next': None,
            'num_pages': 1,
            'use_onboarding_profile_api': False,
        }

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_data, expected_data)

    @ddt.data(
        (None, InstructorDashboardOnboardingAttemptStatus.not_started),
        (ProctoredExamStudentAttemptStatus.created, InstructorDashboardOnboardingAttemptStatus.setup_started),
        (ProctoredExamStudentAttemptStatus.download_software_clicked,
            InstructorDashboardOnboardingAttemptStatus.setup_started),
        (ProctoredExamStudentAttemptStatus.ready_to_start, InstructorDashboardOnboardingAttemptStatus.setup_started),
        (ProctoredExamStudentAttemptStatus.started, InstructorDashboardOnboardingAttemptStatus.onboarding_started),
        (ProctoredExamStudentAttemptStatus.ready_to_submit,
            InstructorDashboardOnboardingAttemptStatus.onboarding_started),
        (ProctoredExamStudentAttemptStatus.submitted, InstructorDashboardOnboardingAttemptStatus.submitted),
        (ProctoredExamStudentAttemptStatus.rejected, InstructorDashboardOnboardingAttemptStatus.rejected),
        (ProctoredExamStudentAttemptStatus.verified, InstructorDashboardOnboardingAttemptStatus.verified),
        (ProctoredExamStudentAttemptStatus.error, InstructorDashboardOnboardingAttemptStatus.error),
    )
    @ddt.unpack
    def test_returns_correct_onboarding_status(self, attempt_status, expected_onboarding_status):
        serialized_onboarding_attempt = None

        if attempt_status:
            onboarding_attempt_id = create_exam_attempt(self.onboarding_exam.id, self.user.id, True)
            update_attempt_status(onboarding_attempt_id, attempt_status)

            # get serialized onboarding_attempt because modified time has changed
            serialized_onboarding_attempt = get_exam_attempt_by_id(onboarding_attempt_id)

        response = self.client.get(reverse(
                'edx_proctoring:user_onboarding.status.course',
                kwargs={'course_id': self.onboarding_exam.course_id}
            )
        )
        response_data = json.loads(response.content.decode('utf-8'))

        expected_data = {
            'results': [
                {
                    'username': self.user.username,
                    'enrollment_mode': self.enrollment_modes[0],
                    'status': expected_onboarding_status,
                    'modified': serialized_onboarding_attempt['modified'] if serialized_onboarding_attempt else None,
                },
                {
                    'username': self.learner_1.username,
                    'enrollment_mode': self.enrollment_modes[1],
                    'status': InstructorDashboardOnboardingAttemptStatus.not_started,
                    'modified': None,
                },
                {
                    'username': self.learner_2.username,
                    'enrollment_mode': self.enrollment_modes[2],
                    'status': InstructorDashboardOnboardingAttemptStatus.not_started,
                    'modified': None,
                },
            ],
            'count': 3,
            'previous': None,
            'next': None,
            'num_pages': 1,
            'use_onboarding_profile_api': False,
        }

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_data, expected_data)

    @ddt.data(
        (
            [ProctoredExamStudentAttemptStatus.error, ProctoredExamStudentAttemptStatus.submitted],
            InstructorDashboardOnboardingAttemptStatus.submitted
        ),
        (
            [ProctoredExamStudentAttemptStatus.verified, ProctoredExamStudentAttemptStatus.rejected],
            InstructorDashboardOnboardingAttemptStatus.verified
        )
    )
    @ddt.unpack
    def test_returns_correct_attempt(self, attempt_statuses, expected_onboarding_status):
        """
        Test that it always returns verified if a verified attempt exists. Else, returns the most
        recent attempt.
        """
        for status in attempt_statuses:
            onboarding_attempt_id = create_exam_attempt(self.onboarding_exam.id, self.user.id, True)
            update_attempt_status(onboarding_attempt_id, status)

        response = self.client.get(reverse(
                'edx_proctoring:user_onboarding.status.course',
                kwargs={'course_id': self.onboarding_exam.course_id}
            )
        )
        response_data = json.loads(response.content.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_data['results'][0]['status'], expected_onboarding_status)

    @ddt.data(True, False)
    def test_multiple_exam_attempts(self, should_reset_attempt_be_most_recent_modified):
        attempt_id = create_exam_attempt(self.onboarding_exam.id, self.user.id, True)

        # create a second exam attempt by resetting the onboarding attempt
        set_runtime_service('grades', MockGradesService(rejected_exam_overrides_grade=False))
        update_attempt_status(attempt_id, ProctoredExamStudentAttemptStatus.rejected)
        second_exam_attempt_id = reset_practice_exam(self.onboarding_exam.id, self.user.id, self.user)

        # get serialized onboarding_attempt to get modified time
        serialized_onboarding_attempt = get_exam_attempt_by_id(second_exam_attempt_id)

        if should_reset_attempt_be_most_recent_modified:
            # if we want the reset attempt to have the most recent modified date, we should resave the attempt
            # a reset attempt having a more recent modified date is an edge case
            attempt = ProctoredExamStudentAttempt.objects.get(id=attempt_id)
            attempt.save()

        response = self.client.get(reverse(
                'edx_proctoring:user_onboarding.status.course',
                kwargs={'course_id': self.onboarding_exam.course_id}
            )
        )

        response_data = json.loads(response.content.decode('utf-8'))
        expected_data = {
            'results': [
                {
                    'username': self.user.username,
                    'enrollment_mode': self.enrollment_modes[0],
                    'status': InstructorDashboardOnboardingAttemptStatus.setup_started,
                    'modified': serialized_onboarding_attempt['modified'] if serialized_onboarding_attempt else None,
                },
                {
                    'username': self.learner_1.username,
                    'enrollment_mode': self.enrollment_modes[1],
                    'status': InstructorDashboardOnboardingAttemptStatus.not_started,
                    'modified': None,
                },
                {
                    'username': self.learner_2.username,
                    'enrollment_mode': self.enrollment_modes[2],
                    'status': InstructorDashboardOnboardingAttemptStatus.not_started,
                    'modified': None,
                },
            ],
            'count': 3,
            'previous': None,
            'next': None,
            'num_pages': 1,
            'use_onboarding_profile_api': False,
        }

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_data, expected_data)

    def test_no_enrollments(self):
        set_runtime_service('enrollments', MockEnrollmentsService([]))

        response = self.client.get(reverse(
                    'edx_proctoring:user_onboarding.status.course',
                    kwargs={'course_id': self.onboarding_exam.course_id}
                )
            )
        response_data = json.loads(response.content.decode('utf-8'))

        expected_data = {
            'results': [],
            'count': 0,
            'previous': None,
            'next': None,
            'num_pages': 1,
            'use_onboarding_profile_api': False,
        }

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_data, expected_data)

    def test_other_course_verified(self):
        # Setup other course and its onboarding exam
        other_course_id = 'e/f/g'
        other_course_onboarding_content_id = 'block-v1:test+course+2+type@sequential+block@other_onboard'
        other_onboarding_exam_name = 'other_test_onboarding_exam_name'
        other_onboarding_exam_id = create_exam(
            course_id=other_course_id,
            content_id=other_course_onboarding_content_id,
            exam_name=other_onboarding_exam_name,
            time_limit_mins=self.default_time_limit,
            is_practice_exam=True,
            is_proctored=True,
            backend='test',
        )

        # Setup Learner 1's attempts on the other course.
        onboarding_attempt_1 = create_exam_attempt(
            other_onboarding_exam_id,
            self.learner_1.id,
            True,
        )
        update_attempt_status(onboarding_attempt_1, ProctoredExamStudentAttemptStatus.verified)
        # get serialized onboarding_attempt to get modified time
        serialized_onboarding_attempt_1 = get_exam_attempt_by_id(onboarding_attempt_1)

        # Setup Learner 2's attempt in current course and verified attempt in another course
        onboarding_attempt_2_course = create_exam_attempt(
            self.onboarding_exam_id,
            self.learner_2.id,
            True,
        )
        onboarding_attempt_2_other_course = create_exam_attempt(
            other_onboarding_exam_id,
            self.learner_2.id,
            True,
        )
        update_attempt_status(onboarding_attempt_2_course, ProctoredExamStudentAttemptStatus.download_software_clicked)
        update_attempt_status(onboarding_attempt_2_other_course, ProctoredExamStudentAttemptStatus.verified)

        # Setup Learner with verified attempt in both current course and another course
        onboarding_attempt_course = create_exam_attempt(
            self.onboarding_exam_id,
            self.user.id,
            True,
        )
        onboarding_attempt_other_course = create_exam_attempt(
            other_onboarding_exam_id,
            self.user.id,
            True,
        )
        update_attempt_status(onboarding_attempt_course, ProctoredExamStudentAttemptStatus.verified)
        update_attempt_status(onboarding_attempt_other_course, ProctoredExamStudentAttemptStatus.verified)
        serialized_onboarding_attempt_course = get_exam_attempt_by_id(onboarding_attempt_course)

        # get serialized onboarding_attempt to get modified time
        serialized_onboarding_attempt_2 = get_exam_attempt_by_id(onboarding_attempt_2_other_course)

        response = self.client.get(reverse(
                'edx_proctoring:user_onboarding.status.course',
                kwargs={'course_id': self.onboarding_exam.course_id}
            )
        )
        self.assertEqual(response.status_code, 200)

        response_data = json.loads(response.content.decode('utf-8'))
        expected_data = {
            'results': [
                {
                    'username': self.user.username,
                    'enrollment_mode': self.enrollment_modes[0],
                    'status': InstructorDashboardOnboardingAttemptStatus.verified,
                    'modified': serialized_onboarding_attempt_course.get('modified')
                },
                {
                    'username': self.learner_1.username,
                    'enrollment_mode': self.enrollment_modes[1],
                    'status': InstructorDashboardOnboardingAttemptStatus.other_course_approved,
                    'modified': serialized_onboarding_attempt_1.get('modified'),
                },
                {
                    'username': self.learner_2.username,
                    'enrollment_mode': self.enrollment_modes[2],
                    'status': InstructorDashboardOnboardingAttemptStatus.other_course_approved,
                    'modified': serialized_onboarding_attempt_2.get('modified'),
                },
            ],
            'count': 3,
            'previous': None,
            'next': None,
            'num_pages': 1,
            'use_onboarding_profile_api': False,
        }
        self.assertEqual(response_data, expected_data)

    def test_onboarding_reset_failed_past_due(self):
        # TODO: remove as part of MST-745
        onboarding_attempt_id = create_exam_attempt(
            self.onboarding_exam.id,
            self.user.id,
            True,
        )

        # Update the exam attempt to rejected to allow onboarding exam to be reset.
        update_attempt_status(onboarding_attempt_id, ProctoredExamStudentAttemptStatus.rejected)

        # Update the exam to have a due date in the past.
        self.onboarding_exam.due_date = datetime.now(pytz.UTC) - timedelta(minutes=10)
        self.onboarding_exam.save()

        # Reset the practice exam.
        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.attempt', args=[onboarding_attempt_id]),
            json.dumps({
                'action': 'reset_attempt',
            }),
            content_type='application/json'
        )

        # Get serialized onboarding_attempt to get modified time.
        serialized_onboarding_attempt = get_exam_attempt_by_id(onboarding_attempt_id)

        response = self.client.get(reverse(
                'edx_proctoring:user_onboarding.status.course',
                kwargs={'course_id': self.onboarding_exam.course_id}
            )
        )
        self.assertEqual(response.status_code, 200)

        response_data = json.loads(response.content.decode('utf-8'))
        expected_data = {
            'results': [
                {
                    'username': self.user.username,
                    'enrollment_mode': self.enrollment_modes[0],
                    'status': InstructorDashboardOnboardingAttemptStatus.onboarding_reset_past_due,
                    'modified': serialized_onboarding_attempt.get('modified')
                },
                {
                    'username': self.learner_1.username,
                    'enrollment_mode': self.enrollment_modes[1],
                    'status': InstructorDashboardOnboardingAttemptStatus.not_started,
                    'modified': None,
                },
                {
                    'username': self.learner_2.username,
                    'enrollment_mode': self.enrollment_modes[2],
                    'status': InstructorDashboardOnboardingAttemptStatus.not_started,
                    'modified': None,
                },
            ],
            'count': 3,
            'previous': None,
            'next': None,
            'num_pages': 1,
            'use_onboarding_profile_api': False,
        }
        self.assertEqual(response_data, expected_data)

    def test_not_staff_or_course_staff(self):
        self.user.is_staff = False
        self.user.save()
        set_runtime_service('instructor', MockInstructorService(is_user_course_staff=False))

        response = self.client.get(reverse(
                'edx_proctoring:user_onboarding.status.course',
                kwargs={'course_id': self.onboarding_exam.course_id}
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_course_staff_only_allowed(self):
        self.user.is_staff = False
        self.user.save()
        response = self.client.get(reverse(
                'edx_proctoring:user_onboarding.status.course',
                kwargs={'course_id': self.onboarding_exam.course_id}
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_staff_only_allowed(self):
        set_runtime_service('instructor', MockInstructorService(is_user_course_staff=False))
        response = self.client.get(reverse(
                'edx_proctoring:user_onboarding.status.course',
                kwargs={'course_id': self.onboarding_exam.course_id}
            )
        )
        self.assertEqual(response.status_code, 200)

    @patch('logging.Logger.error')
    @patch('edx_proctoring.views.waffle.switch_is_active')
    @patch.object(TestBackendProvider, 'get_onboarding_profile_info')
    @ddt.data(
        (VerificientOnboardingProfileStatus.no_profile, InstructorDashboardOnboardingAttemptStatus.not_started),
        (VerificientOnboardingProfileStatus.other_course_approved,
         InstructorDashboardOnboardingAttemptStatus.other_course_approved),
        (VerificientOnboardingProfileStatus.approved, ProctoredExamStudentAttemptStatus.verified),
        (VerificientOnboardingProfileStatus.rejected, ProctoredExamStudentAttemptStatus.rejected),
        (VerificientOnboardingProfileStatus.pending, ProctoredExamStudentAttemptStatus.submitted),
        (VerificientOnboardingProfileStatus.expired, ProctoredExamStudentAttemptStatus.expired)
    )
    @ddt.unpack
    def test_instructor_onboarding_with_api_endpoint(self, api_status, attempt_status, mocked_onboarding_api,
                                                     mocked_switch_is_active, mock_logger):
        mocked_switch_is_active.return_value = True

        mocked_onboarding_api.return_value = {
            'results': [
                {
                    'user_id': obscured_user_id(self.user.id, self.onboarding_exam.backend),
                    'status': api_status,
                    'expiration_date': '2051-05-21'
                },
            ]
        }

        response = self.client.get(
            reverse(
                'edx_proctoring:user_onboarding.status.course',
                kwargs={'course_id': self.onboarding_exam.course_id},
            )
        )

        mocked_onboarding_api.assert_called()

        expected_data = {
            'results': [
                {
                    'username': self.user.username,
                    'enrollment_mode': self.enrollment_modes[0],
                    'status': attempt_status,
                    'modified': None,
                },
                {
                    'username': self.learner_1.username,
                    'enrollment_mode': self.enrollment_modes[1],
                    'status': InstructorDashboardOnboardingAttemptStatus.not_started,
                    'modified': None,
                },
                {
                    'username': self.learner_2.username,
                    'enrollment_mode': self.enrollment_modes[2],
                    'status': InstructorDashboardOnboardingAttemptStatus.not_started,
                    'modified': None,
                }
            ],
            'count': 3,
            'previous': None,
            'next': None,
            'num_pages': 1,
            'use_onboarding_profile_api': True,
        }

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data, expected_data)
        mock_logger.assert_not_called()

    @patch('logging.Logger.error')
    @patch('edx_proctoring.views.waffle.switch_is_active')
    @patch.object(TestBackendProvider, 'get_onboarding_profile_info')
    def test_instructor_onboarding_with_403_api_response(self, mocked_onboarding_api,
                                                         mocked_switch_is_active, mock_logger):
        """
        Test that internal logic is used if proctoring backend api endpoint returns non 200 response.
        """
        mocked_switch_is_active.return_value = True

        mocked_onboarding_api.side_effect = BackendProviderOnboardingProfilesException('some error', 403)

        response = self.client.get(
            reverse(
                'edx_proctoring:user_onboarding.status.course',
                kwargs={'course_id': self.onboarding_exam.course_id},
            )
        )

        mocked_onboarding_api.assert_called()

        self.assertEqual(response.status_code, 503)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(
            response_data,
            {'detail': 'The onboarding service is temporarily unavailable. Please try again later.'}
        )
        mock_logger.assert_called()

    @patch('logging.Logger.error')
    @patch('edx_proctoring.views.waffle.switch_is_active')
    @patch.object(TestBackendProvider, 'get_onboarding_profile_info')
    def test_instructor_onboarding_filter_by_user(self, mocked_onboarding_api, mocked_switch_is_active, mock_logger):
        mocked_switch_is_active.return_value = True

        mocked_onboarding_api.return_value = {
            'results': [
                {
                    'user_id': obscured_user_id(self.user.id, self.onboarding_exam.backend),
                    'status': VerificientOnboardingProfileStatus.approved,
                    'expiration_date': '2051-05-21'
                },
            ]
        }

        mock_enrollments = [MockEnrollment(self.user, self.enrollment_modes[0])]

        # create onboarding attempt to check that modified time is accurate
        onboarding_attempt_id = create_exam_attempt(
            self.onboarding_exam.id,
            self.user.id,
            True,
        )
        update_attempt_status(onboarding_attempt_id, ProctoredExamStudentAttemptStatus.verified)
        serialized_onboarding_attempt = get_exam_attempt_by_id(onboarding_attempt_id)

        with patch(
                'edx_proctoring.tests.test_services.MockEnrollmentsService.get_enrollments_can_take_proctored_exams',
                return_value=mock_enrollments
        ):
            response = self.client.get(
                reverse(
                    'edx_proctoring:user_onboarding.status.course',
                    kwargs={'course_id': self.onboarding_exam.course_id},
                ),
                {'text_search': self.user.username}
            )

        mocked_onboarding_api.assert_called()

        expected_data = {
            'results': [
                {
                    'username': self.user.username,
                    'enrollment_mode': self.enrollment_modes[0],
                    'status': ProctoredExamStudentAttemptStatus.verified,
                    'modified': serialized_onboarding_attempt['modified'],
                },
            ],
            'count': 1,
            'previous': None,
            'next': None,
            'num_pages': 1,
            'use_onboarding_profile_api': True,
        }

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data, expected_data)
        mock_logger.assert_not_called()

    @patch('edx_proctoring.views.waffle.switch_is_active')
    @patch.object(TestBackendProvider, 'get_onboarding_profile_info')
    def test_instructor_onboarding_filter_by_status(self, mocked_onboarding_api, mocked_switch_is_active):
        mocked_switch_is_active.return_value = True
        mocked_onboarding_api.return_value = {
            'results': [
                {
                    'user_id': obscured_user_id(self.user.id, self.onboarding_exam.backend),
                    'status': VerificientOnboardingProfileStatus.approved,
                    'expiration_date': '2051-05-21'
                },
                {
                    'user_id': obscured_user_id(self.learner_1.id, self.onboarding_exam.backend),
                    'status': VerificientOnboardingProfileStatus.pending,
                    'expiration_date': '2051-05-21'
                },
            ]
        }

        response = self.client.get(
            reverse(
                'edx_proctoring:user_onboarding.status.course',
                kwargs={'course_id': self.onboarding_exam.course_id},
            ),
            {'statuses': 'verified,submitted'}
        )

        expected_data = {
            'results': [
                {
                    'username': self.user.username,
                    'enrollment_mode': self.enrollment_modes[0],
                    'status': ProctoredExamStudentAttemptStatus.verified,
                    'modified': None,
                },
                {
                    'username': self.learner_1.username,
                    'enrollment_mode': self.enrollment_modes[1],
                    'status': ProctoredExamStudentAttemptStatus.submitted,
                    'modified': None,
                },
            ],
            'count': 2,
            'previous': None,
            'next': None,
            'num_pages': 1,
            'use_onboarding_profile_api': True,
        }

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data, expected_data)

    @patch('edx_proctoring.views.waffle.switch_is_active')
    @patch.object(TestBackendProvider, 'get_onboarding_profile_info')
    def test_instructor_onboarding_filter_by_status_no_profile(self, mocked_onboarding_api, mocked_switch_is_active):

        mocked_switch_is_active.return_value = True
        mocked_onboarding_api.return_value = {
            'results': [
                {
                    'user_id': obscured_user_id(self.user.id, self.onboarding_exam.backend),
                    'status': VerificientOnboardingProfileStatus.no_profile,
                    'expiration_date': '2051-05-21'
                },
            ],
        }

        response = self.client.get(
            reverse(
                'edx_proctoring:user_onboarding.status.course',
                kwargs={'course_id': self.onboarding_exam.course_id},
            ),
            {'statuses': 'not_started'}
        )

        expected_data = {
            'results': [
                {
                    'username': self.user.username,
                    'enrollment_mode': self.enrollment_modes[0],
                    'status': InstructorDashboardOnboardingAttemptStatus.not_started,
                    'modified': None,
                },
                {
                    'username': self.learner_1.username,
                    'enrollment_mode': self.enrollment_modes[1],
                    'status': InstructorDashboardOnboardingAttemptStatus.not_started,
                    'modified': None,
                },
                {
                    'username': self.learner_2.username,
                    'enrollment_mode': self.enrollment_modes[2],
                    'status': InstructorDashboardOnboardingAttemptStatus.not_started,
                    'modified': None,
                },
            ],
            'count': 3,
            'previous': None,
            'next': None,
            'num_pages': 1,
            'use_onboarding_profile_api': True,
        }

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data, expected_data)


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
        update_attempt_status(attempt['id'], ProctoredExamStudentAttemptStatus.started)
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

    def test_get_status_of_exam_attempt(self):
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
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.started)

        response = self.client.get(
            reverse('edx_proctoring:proctored_exam.attempt.collection')
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))
        self.assertIn('attempt_status', data)
        self.assertEqual(data['attempt_status'], ProctoredExamStudentAttemptStatus.started)

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
        self.assertFalse(attempt['is_resumable'])

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
        update_attempt_status(attempt['id'], ProctoredExamStudentAttemptStatus.download_software_clicked)

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
        self.assertFalse(response_data['is_resumable'])
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
            # Also make sure the attempt is now resumable
            self.assertTrue(attempt.is_resumable)

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
            proctored_exam.id, self.user.id,
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
            attempt_id,
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
            'Cannot create new exam attempt for exam_id=1 and user_id=1 in course_id=a/b/c '
            'because it already exists!'
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

        is_attempt_resumable = False
        if expected_status == ProctoredExamStudentAttemptStatus.error:
            is_attempt_resumable = True
        self.assertEqual(attempt['is_resumable'], is_attempt_resumable)

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
            old_attempt_id, ProctoredExamStudentAttemptStatus.rejected
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
        url = reverse(
            'edx_proctoring:proctored_exam.attempts.grouped.course',
            kwargs={'course_id': proctored_exam.course_id},
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(len(response_data['proctored_exam_attempts']), 1)

        attempt = response_data['proctored_exam_attempts'][0]
        self.assertEqual(attempt['proctored_exam']['id'], proctored_exam.id)
        self.assertEqual(attempt['user']['id'], self.user.id)

        url = f'{url}?page=9999'
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
        url = reverse(
            'edx_proctoring:proctored_exam.attempts.grouped.course',
            kwargs={'course_id': proctored_exam.course_id},
        )

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
                'edx_proctoring:proctored_exam.attempts.grouped.search',
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
                'edx_proctoring:proctored_exam.attempts.grouped.search',
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
            user = User.objects.create(username=f'student{i}', email=f'student{i}@test.com')
            ProctoredExamStudentAttempt.create_exam_attempt(
                proctored_exam.id, user.id,
                f'test_attempt_code{i}', True, False, f'test_external_id{i}'
            )

        self.client.login_user(self.user)
        response = self.client.get(
            reverse(
                'edx_proctoring:proctored_exam.attempts.grouped.course',
                kwargs={'course_id': proctored_exam.course_id},
            )
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))

        self.assertEqual(len(response_data['proctored_exam_attempts']), 25)
        self.assertTrue(response_data['pagination_info']['has_next'])
        self.assertEqual(response_data['pagination_info']['total_pages'], 4)
        self.assertEqual(response_data['pagination_info']['current_page'], 1)

    def test_get_grouped_exam_attempts(self):
        """
        Test to ensure that if there are multiple attempts on the same exam, they are grouped by user
        """
        course_id = 'a/b/c'

        exam_id_1 = create_exam(
            course_id=course_id,
            content_id='content',
            exam_name='Sample Exam',
            time_limit_mins=10,
            is_proctored=True
        )

        exam_id_2 = create_exam(
            course_id=course_id,
            content_id='content2',
            exam_name='Sample Exam',
            time_limit_mins=10,
            is_proctored=True
        )
        # create two attempts each for exam 1
        attempt_1 = create_exam_attempt(exam_id_1, self.user.id, taking_as_proctored=True)
        update_attempt_status(attempt_1, ProctoredExamStudentAttemptStatus.error)
        mark_exam_attempt_as_ready_to_resume(attempt_1)
        attempt_2 = create_exam_attempt(exam_id_1, self.user.id, taking_as_proctored=True)

        attempt_3 = create_exam_attempt(exam_id_1, self.second_user.id, taking_as_proctored=True)
        update_attempt_status(attempt_3, ProctoredExamStudentAttemptStatus.error)
        mark_exam_attempt_as_ready_to_resume(attempt_3)
        attempt_4 = create_exam_attempt(exam_id_1, self.second_user.id, taking_as_proctored=True)

        # create one attempt each for exam 2
        attempt_5 = create_exam_attempt(exam_id_2, self.user.id, taking_as_proctored=True)
        attempt_6 = create_exam_attempt(exam_id_2, self.second_user.id, taking_as_proctored=True)

        # check that endpoint returns only four attempts, unique to user and exam
        url = reverse(
            'edx_proctoring:proctored_exam.attempts.grouped.course',
            kwargs={'course_id': course_id},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(len(response_data['proctored_exam_attempts']), 4)

        # check that each attempt returned is structured as expected
        # order of attempts should be sorted by most recently created
        first_attempt = response_data['proctored_exam_attempts'][0]
        self.assertEqual(first_attempt['user']['id'], self.second_user.id)
        self.assertEqual(len(first_attempt['all_attempts']), 1)
        self.assertEqual(first_attempt['all_attempts'][0]['id'], attempt_6)

        second_attempt = response_data['proctored_exam_attempts'][1]
        self.assertEqual(second_attempt['user']['id'], self.user.id)
        self.assertEqual(len(second_attempt['all_attempts']), 1)
        self.assertEqual(second_attempt['all_attempts'][0]['id'], attempt_5)

        third_attempt = response_data['proctored_exam_attempts'][2]
        self.assertEqual(third_attempt['user']['id'], self.second_user.id)
        self.assertEqual(third_attempt['id'], attempt_4)
        self.assertEqual(len(third_attempt['all_attempts']), 2)
        self.assertEqual(third_attempt['all_attempts'][0]['id'], attempt_4)
        self.assertEqual(third_attempt['all_attempts'][1]['id'], attempt_3)

        fourth_attempt = response_data['proctored_exam_attempts'][3]
        self.assertEqual(fourth_attempt['user']['id'], self.user.id)
        self.assertEqual(fourth_attempt['id'], attempt_2)
        self.assertEqual(len(fourth_attempt['all_attempts']), 2)
        self.assertEqual(fourth_attempt['all_attempts'][0]['id'], attempt_2)
        self.assertEqual(fourth_attempt['all_attempts'][1]['id'], attempt_1)

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
        self.assertEqual(response_data['detail'], 'Attempted to update attempt_id=0 but it does not exist.')

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

    def test_review_callback_non_proctored_exam(self):
        """
        Simulates a callback from the proctoring service with the
        review data but the matched attempt had the exam not proctored
        """
        exam_id = create_exam(
            course_id='foo/bar/baz',
            content_id='content',
            exam_name='Sample Exam',
            time_limit_mins=10,
            is_proctored=True
        )

        # be sure to use the mocked out exam provider handlers
        with HTTMock(mock_response_content):
            attempt_id = create_exam_attempt(
                exam_id,
                self.user.id,
                taking_as_proctored=True
            )

        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertIsNotNone(attempt['external_id'])

        update_exam(exam_id, is_proctored=False)

        test_payload = create_test_review_payload(
            attempt_code=attempt['attempt_code'],
            external_id=attempt['external_id'],
        )
        response = self.client.post(
            reverse(
                'edx_proctoring:proctored_exam.attempt.callback',
                args=[attempt['external_id']]
            ),
            data=test_payload,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 412)
        self.assertEqual(response.data, 'Exam no longer proctored')

    def test_review_callback_get(self):
        """
        We don't support any http METHOD other than GET
        """

        response = self.client.get(
            reverse('edx_proctoring:anonymous.proctoring_review_callback'),
        )

        self.assertEqual(response.status_code, 405)

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

    def test_attempt_review_status_callback_non_reviewable(self):
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
        self.assertEqual(response.status_code, 404)

    @override_settings(PROCTORED_EXAM_VIEWABLE_PAST_DUE=True)
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

    @override_settings(PROCTORED_EXAM_VIEWABLE_PAST_DUE=True)
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

    @override_settings(PROCTORED_EXAM_VIEWABLE_PAST_DUE=True)
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
        self.assertTrue(attempt['is_resumable'])

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
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.error)
        self.assertTrue(attempt['ready_to_resume'])
        self.assertFalse(attempt['is_resumable'])

    @ddt.data(
        (True, True),
        (True, False),
        (False, True)
    )
    @ddt.unpack
    def test_mark_ready_to_resume_attempt_for_other_as_staff(self, is_staff, is_course_staff):
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

        if not is_course_staff:
            set_runtime_service('instructor', MockInstructorService(is_user_course_staff=False))
        if not is_staff:
            self.user.is_staff = False
            self.user.save()

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
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.error)
        self.assertTrue(attempt['ready_to_resume'])

    @ddt.data(
        (True, True),
        (True, False),
        (False, True)
    )
    @ddt.unpack
    def test_mark_ready_to_resume_attempt_for_other_as_staff_no_user_id(self, is_staff, is_course_staff):
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

        if not is_course_staff:
            set_runtime_service('instructor', MockInstructorService(is_user_course_staff=False))
        if not is_staff:
            self.user.is_staff = False
            self.user.save()

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

    def test_is_user_course_or_global_staff_called_correct_args(self):
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

        response_data = json.loads(response.content.decode('utf-8'))
        attempt_id = response_data['exam_attempt_id']

        # Transition the exam attempt into the error state.
        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.attempt', args=[attempt_id]),
            json.dumps({
                'action': 'error',
            }),
            content_type='application/json'
        )

        # Log in the staff user.
        self.client.login_user(self.student_taking_exam)

        # Transition the exam attempt into the ready_to_resume state. This is not
        # a valid state transition, but that's okay because we're not testing that.
        with patch('edx_proctoring.views.is_user_course_or_global_staff') as is_staff_mock:
            response = self.client.put(
                reverse('edx_proctoring:proctored_exam.attempt', args=[attempt_id]),
                json.dumps({
                    'action': 'mark_ready_to_resume',
                    'user_id': self.student_taking_exam.id,
                }),
                content_type='application/json'
            )
            is_staff_mock.assert_called_once()

            # We can't assert that is_user_course_or_global_staff is called with self.user because
            # Django lazily loads request.user, so it's a SimpleLazyObject.
            (_, course_id) = is_staff_mock.call_args.args
            assert course_id == proctored_exam.course_id

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

        # Make sure the exam attempt is in the original state.
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
        url = reverse(
            'edx_proctoring:proctored_exam.attempts.grouped.course',
            kwargs={'course_id': proctored_exam.course_id},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(len(response_data['proctored_exam_attempts'][0]['all_attempts']), 2)
        # assert that the older attempt has transitioned to the resumed
        self.assertTrue(
            response_data['proctored_exam_attempts'][0]['all_attempts'][1]['resumed'],
        )
        # Make sure the resumed attempt is no longer resumable again
        self.assertFalse(
            response_data['proctored_exam_attempts'][0]['all_attempts'][1]['is_resumable']
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
        self.assertEqual(response_data['detail'], "Cannot find user against invalid_user")

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
            'allowance_value "invalid_value" should be non-negative integer value.'
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


@ddt.ddt
class ExamBulkAllowanceView(LoggedInTestCase):
    """

    Tests for the ExamBulkAllowanceView
    """
    def setUp(self):
        super().setUp()
        self.user.is_staff = True
        self.user.save()
        self.client.login_user(self.user)
        self.course_id = 'a/b/c'
        self.student_taking_exam = User()
        self.student_taking_exam.save()

        set_runtime_service('instructor', MockInstructorService(is_user_course_staff=True))

    @ddt.data(
        (
            'additional_time_granted',
            '30'
        ),
        (
            TIME_MULTIPLIER,
            '1.5'
        ),
        (
            'review_policy_exception',
            'notes'
        ),
        (
            'review_policy_exception',
            25
        )
    )
    @ddt.unpack
    def test_add_bulk_time_allowances(self, allowance_type, value):
        """
        Add bulk time allowance for multiple users and exams
        """
        # Create an exam.
        user_list = self.create_batch_users(3)
        user_id_list = [user.email for user in user_list]
        exam1 = ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='test_content',
            exam_name='Test Exam',
            time_limit_mins=90,
            is_active=True
            )
        exam2 = ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='test_content2',
            exam_name='Test Exam2',
            time_limit_mins=90,
            is_active=True
            )
        exam_list = [exam1.id, exam2.id]

        allowance_data = {
            'course_id': self.course_id,
            'exam_ids': ','.join(str(exam) for exam in exam_list),
            'user_ids': ','.join(str(user) for user in user_id_list),
            'allowance_type': allowance_type,
            'value': value
        }
        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.bulk_allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

    @ddt.data((True, 200), (False, 403))
    @ddt.unpack
    def test_add_bulk_allowance_non_global_staff_user(  # pylint: disable=invalid-name
        self, is_user_course_staff, expected_status_code,
    ):
        """
        Test to add bulk allowance with a non global staff user. Course staff should be able
        to add allowances, while non staff will receive a forbidden response.
        """
        self.user.is_staff = False
        self.user.save()
        set_runtime_service('instructor', MockInstructorService(is_user_course_staff=is_user_course_staff))
        # Create exams.
        user_list = self.create_batch_users(3)
        user_id_list = [user.email for user in user_list]
        exam1 = ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='test_content',
            exam_name='Test Exam',
            time_limit_mins=90,
            is_active=True
            )
        exam2 = ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='test_content2',
            exam_name='Test Exam2',
            time_limit_mins=90,
            is_active=True
            )
        exam_list = [exam1.id, exam2.id]

        allowance_data = {
            'course_id': self.course_id,
            'exam_ids': ','.join(str(exam) for exam in exam_list),
            'user_ids': ','.join(str(user) for user in user_id_list),
            'allowance_type': 'additional_time_granted',
            'value': '30'
        }
        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.bulk_allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, expected_status_code)
        if not is_user_course_staff:
            response_data = json.loads(response.content.decode('utf-8'))
            self.assertEqual(response_data['detail'], 'Must be a Staff User to Perform this request.')

    @ddt.data(
        (
            'additional_time_granted',
            '30'
        ),
        (
            TIME_MULTIPLIER,
            '1.5'
        ),
        (
            'review_policy_exception',
            'notes'
        ),
        (
            'review_policy_exception',
            25
        )
    )
    @ddt.unpack
    def test_add_bulk_allowance_invalid_user(self, allowance_type, value):  # pylint: disable=invalid-name
        """
        Test to add bulk allowance with an invalid user in the list
        """
        # Create exams.
        user_list = self.create_batch_users(3)
        user_id_list = [user.email for user in user_list]
        user_id_list.append('invalid_user')
        exam1 = ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='test_content',
            exam_name='Test Exam',
            time_limit_mins=90,
            is_active=True
            )
        exam2 = ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='test_content2',
            exam_name='Test Exam2',
            time_limit_mins=90,
            is_active=True
            )
        exam_list = [exam1.id, exam2.id]

        allowance_data = {
            'course_id': self.course_id,
            'exam_ids': ','.join(str(exam) for exam in exam_list),
            # Add additonal whitesapce for invalid users
            'user_ids': ','.join(str(user) for user in user_id_list) + ',,   ,  ,w',
            'allowance_type': allowance_type,
            'value': value
        }
        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.bulk_allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 207)

    @ddt.data(
        (
            'additional_time_granted',
            '30'
        ),
        (
            TIME_MULTIPLIER,
            '1.5'
        ),
        (
            'review_policy_exception',
            'notes'
        ),
        (
            'review_policy_exception',
            25
        )
    )
    @ddt.unpack
    def test_add_bulk_allowance_invalid_exam(self, allowance_type, value):  # pylint: disable=invalid-name
        """
        Test to add bulk allowance with an invalid exam in the list
        """
        # Create exams.
        user_list = self.create_batch_users(3)
        user_id_list = [user.email for user in user_list]
        exam1 = ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='test_content',
            exam_name='Test Exam',
            time_limit_mins=90,
            is_active=True
            )
        exam2 = ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='test_content2',
            exam_name='Test Exam2',
            time_limit_mins=90,
            is_active=True
            )
        exam_list = [exam1.id, exam2.id, -99]

        allowance_data = {
            'course_id': self.course_id,
            # Test added whitesapce in the exam id input
            'exam_ids': ','.join(str(exam) for exam in exam_list) + ',2  3, 22,',
            'user_ids': ','.join(str(user) for user in user_id_list),
            'allowance_type': allowance_type,
            'value': value
        }
        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.bulk_allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 207)

    @ddt.data(
        (
            'additional_time_granted',
            '-30'
        ),
        (
            TIME_MULTIPLIER,
            '-1.5'
        ),
        (
            TIME_MULTIPLIER,
            'invalid_value'
        )
    )
    @ddt.unpack
    def test_add_bulk_allowance_invalid_allowance_value(self, allowance_type, value):  # pylint: disable=invalid-name
        """
        Test to add bulk allowance with invalid allowance value
        """
        # Create exams.
        user_list = self.create_batch_users(3)
        user_id_list = [user.email for user in user_list]
        exam1 = ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='test_content',
            exam_name='Test Exam',
            time_limit_mins=90,
            is_active=True
            )
        exam2 = ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='test_content2',
            exam_name='Test Exam2',
            time_limit_mins=90,
            is_active=True
            )
        exam_list = [exam1.id, exam2.id]

        allowance_data = {
            'course_id': self.course_id,
            'exam_ids': ','.join(str(exam) for exam in exam_list),
            'user_ids': ','.join(str(user) for user in user_id_list),
            'allowance_type': allowance_type,
            'value': value
        }
        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.bulk_allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['detail'], 'Enter a valid positive value number')
        self.assertEqual(response_data['field'], 'allowance_value')

    def test_add_bulk_allowance_all_invalid_data(self):  # pylint: disable=invalid-name
        """
        Test to add bulk allowance with invalid exams and users
        """
        # Create exams.
        user_id_list = ['invalid', 'invalid2', 'invalid3']
        exam_list = [-99, -98]

        allowance_data = {
            'course_id': self.course_id,
            'exam_ids': ','.join(str(exam) for exam in exam_list),
            'user_ids': ','.join(str(user) for user in user_id_list),
            'allowance_type': 'additional_time_granted',
            'value': '30'
        }
        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.bulk_allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_add_bulk_allowance_no_users(self):  # pylint: disable=invalid-name
        """
        Test to add bulk allowance with no users
        """
        # Create exams.
        exam1 = ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='test_content',
            exam_name='Test Exam',
            time_limit_mins=90,
            is_active=True
            )
        exam2 = ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='test_content2',
            exam_name='Test Exam2',
            time_limit_mins=90,
            is_active=True
            )
        exam_list = [exam1.id, exam2.id]

        allowance_data = {
            'course_id': self.course_id,
            'exam_ids': ','.join(str(exam) for exam in exam_list),
            'user_ids': ' ',
            'allowance_type': 'additional_time_granted',
            'value': '30'
        }
        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.bulk_allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_add_bulk_allowance_no_exams(self):  # pylint: disable=invalid-name
        """
        Test to add bulk allowance with no exams
        """
        # Create exams.
        user_list = self.create_batch_users(3)
        user_id_list = [user.email for user in user_list]

        allowance_data = {
            'course_id': self.course_id,
            'exam_ids': ' ',
            'user_ids': ','.join(str(user) for user in user_id_list),
            'allowance_type': 'additional_time_granted',
            'value': '30'
        }
        response = self.client.put(
            reverse('edx_proctoring:proctored_exam.bulk_allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)


class GroupedExamAllowancesByStudent(LoggedInTestCase):
    """
    Tests for the GroupedExamAllowancesByStudent
    """
    def setUp(self):
        super().setUp()
        self.user.is_staff = True
        self.user.save()
        self.client.login_user(self.user)
        self.student_taking_exam = User()
        self.student_taking_exam.save()

        set_runtime_service('instructor', MockInstructorService(is_user_course_staff=True))

    def test_get_grouped_allowances(self):
        """
        Test to get the exam allowances of a course
        """
        # Create an exam.
        user_list = self.create_batch_users(3)
        user_id_list = [user.email for user in user_list]
        exam1 = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            time_limit_mins=90,
            is_active=True
            )
        exam_list = [exam1.id]

        allowance_data = {
            'exam_ids': ','.join(str(exam) for exam in exam_list),
            'user_ids': ','.join(str(user) for user in user_id_list),
            'allowance_type': 'additional_time_granted',
            'value': '30'
        }
        self.client.put(
            reverse('edx_proctoring:proctored_exam.bulk_allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        url = reverse(
            'edx_proctoring:proctored_exam.allowance.grouped.course',
            kwargs={'course_id': exam1.course_id}
        )

        # Create expected dictionary by getting each users allowance seperately
        first_user = user_list[0].id
        first_user_allowance = ProctoredExamStudentAllowance.get_allowance_for_user(exam1.id, first_user,
                                                                                    'additional_time_granted')
        first_serialized_allowance = ProctoredExamStudentAllowanceSerializer(first_user_allowance).data
        second_user = user_list[1].id
        second_user_allowance = ProctoredExamStudentAllowance.get_allowance_for_user(exam1.id, second_user,
                                                                                     'additional_time_granted')
        second_serialized_allowance = ProctoredExamStudentAllowanceSerializer(second_user_allowance).data
        third_user = user_list[2].id
        third_user_allowance = ProctoredExamStudentAllowance.get_allowance_for_user(exam1.id, third_user,
                                                                                    'additional_time_granted')
        third_serialized_allowance = ProctoredExamStudentAllowanceSerializer(third_user_allowance).data
        expected_response = {
                                user_list[0].username: [first_serialized_allowance],
                                user_list[1].username: [second_serialized_allowance],
                                user_list[2].username: [third_serialized_allowance]}
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertDictEqual(expected_response, response_data)

    def test_get_grouped_allowances_non_staff(self):
        """
        Test to get the exam allowances of a course when not a staff member
        """
        # Create an exam.
        user_list = self.create_batch_users(3)
        user_id_list = [user.email for user in user_list]
        exam1 = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            time_limit_mins=90,
            is_active=True
            )
        exam2 = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content2',
            exam_name='Test Exam2',
            time_limit_mins=90,
            is_active=True
            )
        exam_list = [exam1.id, exam2.id]

        allowance_data = {
            'exam_ids': ','.join(str(exam) for exam in exam_list),
            'user_ids': ','.join(str(user) for user in user_id_list),
            'allowance_type': 'additional_time_granted',
            'value': '30'
        }
        self.client.put(
            reverse('edx_proctoring:proctored_exam.bulk_allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        self.user.is_staff = False
        self.user.save()
        set_runtime_service('instructor', MockInstructorService(is_user_course_staff=False))
        url = reverse(
            'edx_proctoring:proctored_exam.allowance.grouped.course',
            kwargs={'course_id': exam1.course_id}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(response_data['detail'], 'Must be a Staff User to Perform this request.')

    def test_get_grouped_allowances_course_no_allowances(self):
        """
        Test to get the exam allowances of a course with no allowances
        """
        url = reverse(
            'edx_proctoring:proctored_exam.allowance.grouped.course',
            kwargs={'course_id': 'a/c/d'}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(len(response_data), 0)

    def test_get_grouped_allowances_non_global_staff(self):
        """
        Test to get the exam allowances of a course when a member is course staff,
        but not global
        """
        # Create an exam.
        user_list = self.create_batch_users(3)
        user_id_list = [user.email for user in user_list]
        exam1 = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            time_limit_mins=90,
            is_active=True
            )
        exam2 = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content2',
            exam_name='Test Exam2',
            time_limit_mins=90,
            is_active=True
            )
        exam_list = [exam1.id, exam2.id]

        allowance_data = {
            'exam_ids': ','.join(str(exam) for exam in exam_list),
            'user_ids': ','.join(str(user) for user in user_id_list),
            'allowance_type': 'additional_time_granted',
            'value': '30'
        }
        self.client.put(
            reverse('edx_proctoring:proctored_exam.bulk_allowance'),
            json.dumps(allowance_data),
            content_type='application/json'
        )
        set_runtime_service('instructor', MockInstructorService(is_user_course_staff=False))
        url = reverse(
            'edx_proctoring:proctored_exam.allowance.grouped.course',
            kwargs={'course_id': exam1.course_id}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertEqual(len(response_data), 3)


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

        set_runtime_service('credit', MockCreditService())
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

        expected_url = f'/instructor/{self.course_id}/'
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

        expected_url = f'/instructor/{self.course_id}/?exam={proctored_exam.external_id}'
        dashboard_url = reverse('edx_proctoring:instructor_dashboard_exam',
                                kwargs={'course_id': self.course_id, 'exam_id': exam_id})
        response = self.client.get(dashboard_url)
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)
        # try with an attempt
        attempt_frag = 'attempt=abcde'
        expected_url += f'&{attempt_frag}'
        dashboard_url += f'?{attempt_frag}'
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

        expected_url = f'/instructor/{self.course_id}/?exam={proctored_exam.external_id}&config=true'
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

        expected_url = f'/instructor/{self.course_id}/'
        response = self.client.get(
            reverse('edx_proctoring:instructor_dashboard_course',
                    kwargs={'course_id': self.course_id})
        )
        if not exam_1_is_proctored and not exam_2_is_proctored:
            self.assertEqual(response.status_code, 404)
            self.assertEqual(
                f'No proctored exams in course {self.course_id}',
                response.data
            )
        else:
            self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    @patch('edx_proctoring.views.waffle.switch_is_active')
    @ddt.data(
        (True, False),
        (True, True),
        (False, False),
        (False, True),
    )
    @ddt.unpack
    def test_psi_instructor_dashboard_url(self, include_attempt_id, is_switch_active, mock_switch):
        """
        Test that instructor dashboard redirects correctly for psi software secure backend
        """
        mock_switch.return_value = is_switch_active
        # set up exam
        exam = ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True,
            is_proctored=True,
            backend='software_secure',
        )

        # create exam attempt
        with HTTMock(mock_response_content):
            attempt_id = create_exam_attempt(exam.id, self.second_user.id, True)

        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertIsNotNone(attempt['external_id'])

        # create review for attempt
        test_payload = create_test_review_payload(
            attempt_code=attempt['attempt_code'],
            external_id=attempt['external_id'].upper(),
            review_status='Clean'
        )
        response = self.client.post(
            reverse('edx_proctoring:anonymous.proctoring_review_callback'),
            data=test_payload,
            content_type='foo'
        )
        self.assertEqual(response.status_code, 200)

        # call dashboard exam url with attempt id
        dashboard_url = reverse('edx_proctoring:instructor_dashboard_exam',
                                kwargs={'course_id': self.course_id, 'exam_id': exam.id})
        query_params = {'attempt': attempt['external_id']} if include_attempt_id else {}
        response = self.client.get(dashboard_url, query_params)
        if not (include_attempt_id and is_switch_active):
            self.assertEqual(response.status_code, 404)
        else:
            video_url = json.loads(test_payload)['videoReviewLink']
            expected_url = video_url.replace('DirectLink-Generic', 'DirectLink-HTML5')
            self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    @patch('edx_proctoring.views.waffle.switch_is_active')
    def test_psi_instructor_dashboard_url_deleted_attempt(self, mock_switch):
        """
        Test that instructor dashboard redirects correctly for psi software secure backend when an attempt is deleted
        """
        mock_switch.return_value = True
        # set up exam
        exam = ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True,
            is_proctored=True,
            backend='software_secure',
        )

        # create exam attempt
        with HTTMock(mock_response_content):
            attempt_id = create_exam_attempt(exam.id, self.second_user.id, True)

        attempt = get_exam_attempt_by_id(attempt_id)
        external_id = attempt['external_id']

        # remove the attempt
        response = self.client.delete(
            reverse('edx_proctoring:proctored_exam.attempt', args=[attempt_id])
        )
        self.assertEqual(response.status_code, 200)

        # call dashboard exam url with attempt id
        dashboard_url = reverse('edx_proctoring:instructor_dashboard_exam',
                                kwargs={'course_id': self.course_id, 'exam_id': exam.id})
        response = self.client.get(dashboard_url, {'attempt': external_id})

        self.assertEqual(response.status_code, 404)

    @patch('edx_proctoring.views.waffle.switch_is_active')
    def test_psi_instructor_dashboard_url_no_review(self, mock_switch):
        """
        Test that instructor dashboard redirects correctly for psi software secure backend when there
        is no review for an attempt
        """
        mock_switch.return_value = True
        # set up exam
        exam = ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True,
            is_proctored=True,
            backend='software_secure',
        )

        # create exam attempt
        with HTTMock(mock_response_content):
            attempt_id = create_exam_attempt(exam.id, self.second_user.id, True)

        attempt = get_exam_attempt_by_id(attempt_id)
        external_id = attempt['external_id']

        # call dashboard exam url with attempt id
        dashboard_url = reverse('edx_proctoring:instructor_dashboard_exam',
                                kwargs={'course_id': self.course_id, 'exam_id': exam.id})
        response = self.client.get(dashboard_url, {'attempt': external_id})

        self.assertEqual(response.status_code, 404)

    @patch('edx_proctoring.backends.software_secure.decode_and_decrypt')
    @patch('edx_proctoring.views.waffle.switch_is_active')
    def test_psi_instructor_dashboard_url_decoding_error(self, mock_switch, mock_decode):
        """
        Test that the instructor dashboard returns a 404 if there was an error decoding the video url
        """
        mock_switch.return_value = True
        mock_decode.side_effect = Exception()
        # set up exam
        exam = ProctoredExam.objects.create(
            course_id=self.course_id,
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True,
            is_proctored=True,
            backend='software_secure',
        )

        # create exam attempt
        with HTTMock(mock_response_content):
            attempt_id = create_exam_attempt(exam.id, self.second_user.id, True)

        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertIsNotNone(attempt['external_id'])

        # create review for attempt
        test_payload = create_test_review_payload(
            attempt_code=attempt['attempt_code'],
            external_id=attempt['external_id'].upper(),
            review_status='Clean'
        )
        response = self.client.post(
            reverse('edx_proctoring:anonymous.proctoring_review_callback'),
            data=test_payload,
            content_type='foo'
        )
        self.assertEqual(response.status_code, 200)

        # call dashboard exam url with attempt id
        dashboard_url = reverse('edx_proctoring:instructor_dashboard_exam',
                                kwargs={'course_id': self.course_id, 'exam_id': exam.id})
        query_params = {'attempt': attempt['external_id']}
        response = self.client.get(dashboard_url, query_params)

        self.assertEqual(response.status_code, 404)


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
                content_id=f'test_content{i}',
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


@ddt.ddt
class TestResetAttemptsView(LoggedInTestCase):
    """
    Tests for resetting all active attempts for a given user and exam
    """
    def setUp(self):
        super().setUp()
        set_runtime_service('credit', MockCreditService())
        set_runtime_service('instructor', MockInstructorService())
        self.user.is_staff = True
        self.user.save()
        self.client.login_user(self.user)

        self.exam_id = create_exam(
            course_id='foo/bar/baz',
            content_id='content',
            exam_name='Sample Exam',
            time_limit_mins=10,
            is_proctored=True
        )

    def _create_attempts(self, last_status):
        """
        Set up for multiple active attempts
        """
        first_attempt_id = create_exam_attempt(
            self.exam_id,
            self.user.id,
            True
        )
        ready_first = ProctoredExamStudentAttempt.objects.get(id=first_attempt_id)
        ready_first.status = ProctoredExamStudentAttemptStatus.error
        ready_first.resumed = True
        ready_first.save()
        second_attempt_id = create_exam_attempt(
            self.exam_id,
            self.user.id,
            True
        )
        ready_second = ProctoredExamStudentAttempt.objects.get(id=second_attempt_id)
        ready_second.status = ProctoredExamStudentAttemptStatus.error
        ready_second.resumed = True
        ready_second.save()
        third_attempt_id = create_exam_attempt(
            self.exam_id,
            self.user.id,
            True
        )
        third_attempt = ProctoredExamStudentAttempt.objects.get(id=third_attempt_id)
        third_attempt.status = last_status
        third_attempt.save()

        attempts = ProctoredExamStudentAttempt.objects.filter(user_id=self.user.id, proctored_exam_id=self.exam_id)
        assert len(attempts) == 3

    def test_404_with_no_attempts(self):
        """
        Test that endpoint responds with a 404 when there are no attempts
        """
        response = self.client.delete(
            reverse('edx_proctoring:proctored_exam.attempts.reset',
                    kwargs={'exam_id': self.exam_id, 'user_id': self.user.id})
        )
        assert response.status_code == 404

    def test_404_with_no_user_id(self):
        """
        Test that endpoint responds with a 404 when given user id and exam id have no attempts
        """
        self._create_attempts('verified')
        response = self.client.delete(
            reverse('edx_proctoring:proctored_exam.attempts.reset',
                    kwargs={'exam_id': self.exam_id, 'user_id': 111111})
        )
        assert response.status_code == 404

    def test_deletes_all_attempts(self):
        """
        Test that all attempts are deleted
        """
        self._create_attempts('verified')

        self.client.delete(
            reverse('edx_proctoring:proctored_exam.attempts.reset',
                    kwargs={'exam_id': self.exam_id, 'user_id': self.user.id})
        )
        attempts = ProctoredExamStudentAttempt.objects.filter(user_id=self.user.id, proctored_exam_id=self.exam_id)
        assert len(attempts) == 0

    def test_course_staff_can_delete(self):
        """
        Tests that course staff can delete attempts
        """

        attempt_data = {
            'exam_id': self.exam_id,
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
        # and also user is a course staff
        self.user.is_staff = False
        self.user.save()
        set_runtime_service('instructor', MockInstructorService(is_user_course_staff=True))

        response = self.client.delete(
            reverse('edx_proctoring:proctored_exam.attempts.reset',
                    kwargs={'exam_id': self.exam_id, 'user_id': self.user.id})
        )

        self.assertEqual(response.status_code, 200)
