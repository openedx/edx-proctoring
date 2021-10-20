"""
Tests for the update_attempts_for_exam management command
"""

from mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command

from edx_proctoring.api import create_exam, create_exam_attempt, update_attempt_status
from edx_proctoring.models import ProctoredExamStudentAttempt
from edx_proctoring.runtime import set_runtime_service
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus
from edx_proctoring.tests.test_services import MockCertificateService, MockCreditService, MockGradesService
from edx_proctoring.tests.utils import LoggedInTestCase

User = get_user_model()


class TestUpdateAttemptsForExam(LoggedInTestCase):
    """
    Coverage of the update_attempts_for_exam.py file
    """

    def setUp(self):
        """
        Build up test data
        """
        super().setUp()
        set_runtime_service('credit', MockCreditService())
        set_runtime_service('grades', MockGradesService())
        set_runtime_service('certificates', MockCertificateService())

    def test_run_command(self):
        """
        Run the management command
        """
        exam_id = create_exam(
            course_id='a/b/c',
            content_id='bar',
            exam_name='Test Exam 1',
            time_limit_mins=90
        )

        # create three users and three exam attempts
        for i in range(3):
            other_user = User.objects.create(username='otheruser'+str(i), password='test')
            attempt_id = create_exam_attempt(exam_id, other_user.id, taking_as_proctored=True)
            update_attempt_status(attempt_id, ProctoredExamStudentAttemptStatus.verified)

        with patch.object(MockCreditService, 'set_credit_requirement_status') as mock_credit:
            call_command(
                'update_attempts_for_exam',
                batch_size=2,
                sleep_time=0,
                exam_id=exam_id
            )
            mock_credit.assert_called()

        # make sure status stays the same
        attempts = ProctoredExamStudentAttempt.objects.filter(status=ProctoredExamStudentAttemptStatus.verified)
        self.assertEqual(len(attempts), 3)
