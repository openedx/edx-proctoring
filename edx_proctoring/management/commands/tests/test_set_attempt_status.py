"""
Tests for the set_attempt_status management command
"""

from __future__ import absolute_import

from datetime import datetime
from mock import MagicMock, patch
import pytz

from django.core.management import call_command

from edx_proctoring.tests.utils import LoggedInTestCase
from edx_proctoring.api import create_exam, get_exam_attempt

from edx_proctoring.models import ProctoredExamStudentAttempt
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus
from edx_proctoring.tests.test_services import (
    MockCreditService,
    MockGradesService,
    MockCertificateService
)
from edx_proctoring.runtime import set_runtime_service


@patch('django.urls.reverse', MagicMock)
class SetAttemptStatusTests(LoggedInTestCase):
    """
    Coverage of the set_attempt_status.py file
    """

    def setUp(self):
        """
        Build up test data
        """
        super(SetAttemptStatusTests, self).setUp()
        set_runtime_service('credit', MockCreditService())
        set_runtime_service('grades', MockGradesService())
        set_runtime_service('certificates', MockCertificateService())
        self.exam_id = create_exam(
            course_id='foo',
            content_id='bar',
            exam_name='Test Exam',
            time_limit_mins=90)

        ProctoredExamStudentAttempt.objects.create(
            proctored_exam_id=self.exam_id,
            user_id=self.user.id,
            external_id='foo',
            started_at=datetime.now(pytz.UTC),
            status=ProctoredExamStudentAttemptStatus.started,
            allowed_time_limit_mins=10,
            taking_as_proctored=True,
            is_sample_attempt=False)

    def test_run_comand(self):
        """
        Run the management command
        """

        call_command('set_attempt_status',
                     exam_id=self.exam_id,
                     user_id=self.user.id,
                     to_status=ProctoredExamStudentAttemptStatus.rejected)

        attempt = get_exam_attempt(self.exam_id, self.user.id)
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.rejected)

        call_command('set_attempt_status',
                     exam_id=self.exam_id,
                     user_id=self.user.id,
                     to_status=ProctoredExamStudentAttemptStatus.verified)

        attempt = get_exam_attempt(self.exam_id, self.user.id)
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.verified)

    def test_bad_status(self):
        """
        Try passing a bad status
        """

        with self.assertRaises(Exception):
            call_command('set_attempt_status',
                         exam_id=self.exam_id,
                         user_id=self.user.id,
                         to_status='bad')
