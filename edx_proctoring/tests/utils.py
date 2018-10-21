# coding=utf-8
# pylint: disable=invalid-name

"""
Subclasses Django test client to allow for easy login
"""

from __future__ import absolute_import

from datetime import datetime
from importlib import import_module
import pytz

from django.conf import settings
from django.contrib.auth import login
from django.http import HttpRequest
from django.test.client import Client
from django.test import TestCase
from django.contrib.auth.models import User

from edx_proctoring.api import (
    create_exam,
)
from edx_proctoring.models import (
    ProctoredExamStudentAttempt,
    ProctoredExamStudentAttemptStatus,
)

from edx_proctoring.tests.test_services import (
    MockCreditService,
    MockInstructorService,
)
from edx_proctoring.runtime import set_runtime_service
from eventtracking import tracker
from eventtracking.tracker import Tracker, TRACKERS


class TestClient(Client):
    """
    Allows for 'fake logins' of a user so we don't need to expose a 'login' HTTP endpoint
    """
    def login_user(self, user):
        """
        Login as specified user, does not depend on auth backend (hopefully)

        This is based on Client.login() with a small hack that does not
        require the call to authenticate()
        """
        if 'django.contrib.sessions' not in settings.INSTALLED_APPS:
            raise AssertionError("Unable to login without django.contrib.sessions in INSTALLED_APPS")
        user.backend = "django.contrib.auth.backends.ModelBackend"
        engine = import_module(settings.SESSION_ENGINE)

        # Create a fake request to store login details.
        request = HttpRequest()

        request.session = engine.SessionStore()
        login(request, user)

        # Set the cookie to represent the session.
        session_cookie = settings.SESSION_COOKIE_NAME
        self.cookies[session_cookie] = request.session.session_key
        cookie_data = {
            'max-age': None,
            'path': '/',
            'domain': settings.SESSION_COOKIE_DOMAIN,
            'secure': settings.SESSION_COOKIE_SECURE or None,
            'expires': None,
        }
        self.cookies[session_cookie].update(cookie_data)

        # Save the session values.
        request.session.save()


class LoggedInTestCase(TestCase):
    """
    All tests for the views.py
    """

    def setUp(self):
        """
        Setup for tests
        """
        super(LoggedInTestCase, self).setUp()
        self.client = TestClient()
        self.user = User(username='tester', email='tester@test.com')
        self.user.save()
        self.client.login_user(self.user)


class MockTracker(Tracker):
    """
    A mocked out tracker which implements the emit method
    """
    def emit(self, name=None, data=None):
        """
        Overload this method to do nothing
        """
        pass


class ProctoredExamTestCase(LoggedInTestCase):
    """
    All tests for the models.py
    """

    def setUp(self):
        """
        Build out test harnessing
        """
        super(ProctoredExamTestCase, self).setUp()
        self.default_time_limit = 21
        self.course_id = 'test_course'
        self.content_id_for_exam_with_due_date = 'test_content_due_date_id'
        self.content_id = 'test_content_id'
        self.content_id_timed = 'test_content_id_timed'
        self.content_id_practice = 'test_content_id_practice'
        self.disabled_content_id = 'test_disabled_content_id'
        self.exam_name = 'Test Exam'
        self.user_id = self.user.id
        self.key = 'additional_time_granted'
        self.value = '10'
        self.external_id = 'test_external_id'
        self.proctored_exam_id = self._create_proctored_exam()
        self.timed_exam_id = self._create_timed_exam()
        self.practice_exam_id = self._create_practice_exam()
        self.disabled_exam_id = self._create_disabled_exam()

        set_runtime_service('credit', MockCreditService())
        set_runtime_service('instructor', MockInstructorService(is_user_course_staff=True))

        tracker.register_tracker(MockTracker())

        self.prerequisites = [
            {
                'namespace': 'proctoring',
                'name': 'proc1',
                'order': 2,
                'status': 'satisfied',
            },
            {
                'namespace': 'reverification',
                'name': 'rever1',
                'order': 1,
                'status': 'satisfied',
            },
            {
                'namespace': 'grade',
                'name': 'grade1',
                'order': 0,
                'status': 'pending',
            },
            {
                'namespace': 'reverification',
                'name': 'rever2',
                'order': 3,
                'status': 'failed',
            },
            {
                'namespace': 'proctoring',
                'name': 'proc2',
                'order': 4,
                'status': 'pending',
            },
        ]

        self.declined_prerequisites = [
            {
                'namespace': 'proctoring',
                'name': 'proc1',
                'order': 2,
                'status': 'satisfied',
            },
            {
                'namespace': 'reverification',
                'name': 'rever1',
                'order': 1,
                'status': 'satisfied',
            },
            {
                'namespace': 'grade',
                'name': 'grade1',
                'order': 0,
                'status': 'pending',
            },
            {
                'namespace': 'reverification',
                'name': 'rever2',
                'order': 3,
                'status': 'declined',
            },
            {
                'namespace': 'proctoring',
                'name': 'proc2',
                'order': 4,
                'status': 'pending',
            },
        ]

    def tearDown(self):
        """
        Cleanup
        """
        super(ProctoredExamTestCase, self).tearDown()
        del TRACKERS['default']

    def _create_proctored_exam(self):
        """
        Calls the api's create_exam to create an exam object.
        """
        return create_exam(
            course_id=self.course_id,
            content_id=self.content_id,
            exam_name=self.exam_name,
            time_limit_mins=self.default_time_limit
        )

    def _create_exam_with_due_time(self, is_proctored=True, is_practice_exam=False, due_date=None):
        """
        Calls the api's create_exam to create an exam object.
        """
        return create_exam(
            course_id=self.course_id,
            content_id=self.content_id_for_exam_with_due_date,
            exam_name=self.exam_name,
            time_limit_mins=self.default_time_limit,
            is_proctored=is_proctored,
            is_practice_exam=is_practice_exam,
            due_date=due_date
        )

    def _create_timed_exam(self):
        """
        Calls the api's create_exam to create an exam object.
        """
        return create_exam(
            course_id=self.course_id,
            content_id=self.content_id_timed,
            exam_name=self.exam_name,
            time_limit_mins=self.default_time_limit,
            is_proctored=False
        )

    def _create_practice_exam(self):
        """
        Calls the api's create_exam to create a practice exam object.
        """
        return create_exam(
            course_id=self.course_id,
            content_id=self.content_id_practice,
            exam_name=self.exam_name,
            time_limit_mins=self.default_time_limit,
            is_practice_exam=True,
            is_proctored=True
        )

    def _create_disabled_exam(self):
        """
        Calls the api's create_exam to create an exam object.
        """
        return create_exam(
            course_id=self.course_id,
            is_proctored=False,
            content_id=self.disabled_content_id,
            exam_name=self.exam_name,
            time_limit_mins=self.default_time_limit,
            is_active=False
        )

    def _create_exam_attempt(self, exam_id, status='created'):
        """
        Creates the ProctoredExamStudentAttempt object.
        """

        attempt = ProctoredExamStudentAttempt(
            proctored_exam_id=exam_id,
            user_id=self.user_id,
            external_id=self.external_id,
            allowed_time_limit_mins=10,
            status=status
        )

        if status in (ProctoredExamStudentAttemptStatus.started,
                      ProctoredExamStudentAttemptStatus.ready_to_submit, ProctoredExamStudentAttemptStatus.submitted):
            attempt.started_at = datetime.now(pytz.UTC)

        if ProctoredExamStudentAttemptStatus.is_completed_status(status):
            attempt.completed_at = datetime.now(pytz.UTC)

        attempt.save()

        return attempt

    def _create_unstarted_exam_attempt(self, is_proctored=True, is_practice=False):
        """
        Creates the ProctoredExamStudentAttempt object.
        """
        if is_proctored:
            if is_practice:
                exam_id = self.practice_exam_id
            else:
                exam_id = self.proctored_exam_id
        else:
            exam_id = self.timed_exam_id

        return ProctoredExamStudentAttempt.objects.create(
            proctored_exam_id=exam_id,
            user_id=self.user_id,
            external_id=self.external_id,
            allowed_time_limit_mins=10,
            status='created'
        )

    def _create_started_exam_attempt(self, started_at=None, is_proctored=True, is_sample_attempt=False):
        """
        Creates the ProctoredExamStudentAttempt object.
        """
        return ProctoredExamStudentAttempt.objects.create(
            proctored_exam_id=self.proctored_exam_id if is_proctored else self.timed_exam_id,
            user_id=self.user_id,
            external_id=self.external_id,
            started_at=started_at if started_at else datetime.now(pytz.UTC),
            status=ProctoredExamStudentAttemptStatus.started,
            allowed_time_limit_mins=10,
            taking_as_proctored=is_proctored,
            is_sample_attempt=is_sample_attempt
        )

    def _create_started_practice_exam_attempt(self, started_at=None):
        """
        Creates the ProctoredExamStudentAttempt object.
        """
        return ProctoredExamStudentAttempt.objects.create(
            proctored_exam_id=self.practice_exam_id,
            taking_as_proctored=True,
            user_id=self.user_id,
            external_id=self.external_id,
            started_at=started_at if started_at else datetime.now(pytz.UTC),
            is_sample_attempt=True,
            status=ProctoredExamStudentAttemptStatus.started,
            allowed_time_limit_mins=10
        )

    @staticmethod
    def _normalize_whitespace(string):
        """
        Replaces newlines and multiple spaces with a single space.
        """
        return ' '.join(string.replace('\n', '').split())
