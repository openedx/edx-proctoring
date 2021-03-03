"""
Tests for signals.py
"""

from unittest.mock import patch

from httmock import HTTMock

from django.db.models.signals import pre_delete

from edx_proctoring.models import ProctoredExam, ProctoredExamStudentAttempt
from edx_proctoring.signals import on_attempt_changed

from .utils import ProctoredExamTestCase


class SignalTests(ProctoredExamTestCase):
    """
    Tests for signals.py
    """
    def setUp(self):
        super().setUp()
        self.backend_name = 'software_secure'
        self.proctored_exam = ProctoredExam.objects.create(
          course_id='x/y/z', content_id=self.content_id, exam_name=self.exam_name,
          time_limit_mins=self.default_time_limit, external_id=self.external_id,
          backend=self.backend_name
        )

        pre_delete.connect(on_attempt_changed, sender=ProctoredExamStudentAttempt)

    def tearDown(self):
        super().tearDown()
        pre_delete.disconnect()

    @patch('logging.Logger.error')
    def test_backend_fails_to_delete_attempt(self, logger_mock):
        attempt = ProctoredExamStudentAttempt.objects.create(
            proctored_exam=self.proctored_exam, user=self.user, attempt_code='12345',
            external_id='abcde'
        )

        # If there is no response from the backend, assert that it is logged correctly
        with HTTMock(None):
            attempt.delete_exam_attempt()
            log_format_string = ('Failed to remove attempt_id=%s from backend=%s')
            logger_mock.assert_any_call(log_format_string, 1, self.backend_name)
