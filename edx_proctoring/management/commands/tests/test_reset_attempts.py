"""
Tests for the reset_attempts management command
"""

import ddt
from tempfile import NamedTemporaryFile

from django.core.management import call_command

from edx_proctoring.api import create_exam
from edx_proctoring.models import ProctoredExamStudentAttempt
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus
from edx_proctoring.tests.utils import LoggedInTestCase


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
                for id in ids:
                    writing_file.write(str(id) + '\n')

            call_command(
                'reset_attempts',
                batch_size=2,
                sleep_time=0,
                file_path=file.name,
            )

        attempts = ProctoredExamStudentAttempt.objects.all()
        self.assertEqual(len(attempts), self.num_attempts - num_to_delete)
