"""
Tests for the reset_attempts management command
"""
from tempfile import NamedTemporaryFile
from unittest.mock import patch

import ddt

from django.core.management import call_command

from edx_proctoring.api import create_exam
from edx_proctoring.models import ProctoredExamStudentAttempt
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus
from edx_proctoring.tests.test_utils.utils import LoggedInTestCase


@ddt.ddt
class ResetAttemptsTests(LoggedInTestCase):
    """
    Coverage of the reset_attempts.py file
    """

    def setUp(self):
        """
        Build up test data
        """
        super().setUp()
        self.exam_id = create_exam(
            course_id='a/b/c',
            content_id='bar',
            exam_name='Test Exam',
            time_limit_mins=90
        )

        self.num_attempts = 10

        user_list = self.create_batch_users(self.num_attempts)
        for user in user_list:
            ProctoredExamStudentAttempt.objects.create(
                proctored_exam_id=self.exam_id,
                user_id=user.id,
                external_id='foo',
                status=ProctoredExamStudentAttemptStatus.created,
                allowed_time_limit_mins=10,
                taking_as_proctored=True,
                is_sample_attempt=False
            )

    @ddt.data(
        5,
        7,
        10,
    )
    def test_run_command(self, num_to_delete):
        """
        Run the management command
        """
        ids = list(ProctoredExamStudentAttempt.objects.all().values_list('id', flat=True))[:num_to_delete]

        with NamedTemporaryFile() as file:
            with open(file.name, 'w') as writing_file:
                for num in ids:
                    writing_file.write(str(num) + '\n')

            call_command(
                'reset_attempts',
                batch_size=2,
                sleep_time=0,
                file_path=file.name,
            )

        attempts = ProctoredExamStudentAttempt.objects.all()
        self.assertEqual(len(attempts), self.num_attempts - num_to_delete)

    @patch('edx_proctoring.api.get_backend_provider')
    def test_run_command_notifies_provider(self, mock_get_backend):
        """
        Registered proctored attempts are removed on the provider (best-effort) before the
        local bulk delete, so the provider is not left with orphaned attempts.
        """
        backend = mock_get_backend.return_value
        ids = list(ProctoredExamStudentAttempt.objects.all().values_list('id', flat=True))

        with NamedTemporaryFile() as file:
            with open(file.name, 'w') as writing_file:
                for num in ids:
                    writing_file.write(str(num) + '\n')

            call_command(
                'reset_attempts',
                batch_size=2,
                sleep_time=0,
                file_path=file.name,
            )

        # one provider removal per attempt, and everything is deleted locally
        self.assertEqual(backend.remove_exam_attempt.call_count, len(ids))
        self.assertFalse(ProctoredExamStudentAttempt.objects.exists())

    @patch('edx_proctoring.api.get_backend_provider')
    def test_run_command_stops_calling_failing_backend(self, mock_get_backend):
        """
        If the provider errors out (e.g. it is unreachable), the command stops calling it
        for the rest of the run -- so it does not pay a request timeout per attempt -- while
        still deleting every attempt locally.
        """
        mock_get_backend.return_value.remove_exam_attempt.side_effect = ConnectionError('provider down')
        ids = list(ProctoredExamStudentAttempt.objects.all().values_list('id', flat=True))

        with NamedTemporaryFile() as file:
            with open(file.name, 'w') as writing_file:
                for num in ids:
                    writing_file.write(str(num) + '\n')

            call_command(
                'reset_attempts',
                batch_size=2,
                sleep_time=0,
                file_path=file.name,
            )

        # the provider is called once, then skipped for the rest of the run ...
        self.assertEqual(mock_get_backend.return_value.remove_exam_attempt.call_count, 1)
        # ... but every attempt is still deleted locally
        self.assertFalse(ProctoredExamStudentAttempt.objects.exists())
