"""
Tests for the set_attempt_status management command
"""

from datetime import datetime
import pytz

from edx_proctoring.tests.utils import LoggedInTestCase
from edx_proctoring.api import create_exam, get_exam_attempt
from edx_proctoring.management.commands import set_attempt_status

from edx_proctoring.models import ProctoredExamStudentAttemptStatus, ProctoredExamStudentAttempt
from edx_proctoring.tests.test_services import (
    MockCreditService,
)
from edx_proctoring.runtime import set_runtime_service


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
        self.exam_id = create_exam(
            course_id='foo',
            content_id='bar',
            exam_name='Test Exam',
            time_limit_mins=90
        )

        ProctoredExamStudentAttempt.objects.create(
            proctored_exam_id=self.exam_id,
            user_id=self.user.id,
            external_id='foo',
            started_at=datetime.now(pytz.UTC),
            status=ProctoredExamStudentAttemptStatus.started,
            allowed_time_limit_mins=10,
            taking_as_proctored=True,
            is_sample_attempt=False
        )

    def test_run_comand(self):
        """
        Run the management command
        """

        set_attempt_status.Command().handle(
            exam_id=self.exam_id,
            user_id=self.user.id,
            to_status=ProctoredExamStudentAttemptStatus.rejected
        )

        attempt = get_exam_attempt(self.exam_id, self.user.id)
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.rejected)

        set_attempt_status.Command().handle(
            exam_id=self.exam_id,
            user_id=self.user.id,
            to_status=ProctoredExamStudentAttemptStatus.verified
        )

        attempt = get_exam_attempt(self.exam_id, self.user.id)
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.verified)

    def test_bad_status(self):
        """
        Try passing a bad status
        """

        with self.assertRaises(Exception):
            set_attempt_status.Command().handle(
                exam_id=self.exam_id,
                user_id=self.user.id,
                to_status='bad'
            )
