"""
Tests for handlers.py
"""
from unittest.mock import patch

import ddt
from httmock import HTTMock

from django.db.models.signals import pre_delete, pre_save

from edx_proctoring.api import update_attempt_status
from edx_proctoring.models import ProctoredExam, ProctoredExamStudentAttempt
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus
from edx_proctoring.tests.test_services import MockInstructorService

from .utils import ProctoredExamTestCase


@ddt.ddt
class SignalTests(ProctoredExamTestCase):
    """
    Tests for handlers.py
    """
    def setUp(self):
        super().setUp()
        self.backend_name = 'software_secure'
        self.proctored_exam = ProctoredExam.objects.create(
            course_id='x/y/z', content_id=self.content_id, exam_name=self.exam_name,
            time_limit_mins=self.default_time_limit, external_id=self.external_id,
            backend=self.backend_name
        )
        self.attempt = ProctoredExamStudentAttempt.objects.create(
            proctored_exam=self.proctored_exam, user=self.user, attempt_code='12345',
            external_id='abcde'
        )

    def tearDown(self):
        super().tearDown()
        pre_delete.disconnect()
        pre_save.disconnect()

    @patch('logging.Logger.error')
    def test_backend_fails_to_delete_attempt(self, logger_mock):
        # If there is no response from the backend, assert that it is logged correctly
        with HTTMock(None):
            self.attempt.delete_exam_attempt()
            log_format_string = ('Failed to remove attempt_id=%s from backend=%s')
            logger_mock.assert_any_call(log_format_string, 1, self.backend_name)

    @ddt.data(None, MockInstructorService())
    @patch('edx_proctoring.handlers.get_runtime_service')
    @patch('edx_proctoring.tests.test_services.MockInstructorService.complete_student_attempt')
    def test_pre_save_complete_student_attempt(
            self, runtime_return, mock_complete_student_attempt, mock_get_runtime_service
    ):
        """
        Ensures the complete_student_attempt function will not be called if the instructor service
        is not found.
        """
        mock_get_runtime_service.return_value = runtime_return
        update_attempt_status(self.attempt.id, ProctoredExamStudentAttemptStatus.submitted)
        if runtime_return:
            mock_complete_student_attempt.assert_called_once_with(self.user.username, self.content_id)
        else:
            mock_complete_student_attempt.assert_not_called()
