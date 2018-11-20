# coding=utf-8
"""
All tests for proctored exam emails.
"""

from __future__ import absolute_import

import ddt
from django.core import mail
from mock import MagicMock, patch

from edx_proctoring.api import (
    update_attempt_status,
)
from edx_proctoring.runtime import set_runtime_service, get_runtime_service
from edx_proctoring.statuses import (
    ProctoredExamStudentAttemptStatus,
)

from .test_services import (
    MockCreditService,
    MockGradesService,
    MockCertificateService
)
from .utils import (
    ProctoredExamTestCase,
)


@patch('django.urls.reverse', MagicMock)
@ddt.ddt
class ProctoredExamEmailTests(ProctoredExamTestCase):
    """
    All tests for proctored exam emails.
    """

    def setUp(self):
        """
        Initialize
        """
        super(ProctoredExamEmailTests, self).setUp()

        set_runtime_service('grades', MockGradesService())
        set_runtime_service('certificates', MockCertificateService())

    def tearDown(self):
        """
        When tests are done
        """
        super(ProctoredExamEmailTests, self).tearDown()
        set_runtime_service('grades', None)
        set_runtime_service('certificates', None)

    @ddt.data(
        [
            ProctoredExamStudentAttemptStatus.submitted,
            'Proctoring Review In Progress',
            'was submitted successfully',
        ],
        [
            ProctoredExamStudentAttemptStatus.verified,
            'Proctoring Results',
            'was reviewed and you met all exam requirements',
        ],
        [
            ProctoredExamStudentAttemptStatus.rejected,
            'Proctoring Results',
            'the team found one or more violations',
        ]
    )
    @ddt.unpack
    def test_send_email(self, status, expected_subject, expected_message_string):
        """
        Assert that email is sent on the following statuses of proctoring attempt.
        """

        exam_attempt = self._create_started_exam_attempt()
        credit_state = get_runtime_service('credit').get_credit_state(self.user_id, self.course_id)
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            status
        )
        self.assertEqual(len(mail.outbox), 1)

        # Verify the subject
        actual_subject = self._normalize_whitespace(mail.outbox[0].subject)
        self.assertIn(expected_subject, actual_subject)
        self.assertIn(self.exam_name, actual_subject)

        # Verify the body
        actual_body = self._normalize_whitespace(mail.outbox[0].body)
        self.assertIn('Hi tester,', actual_body)
        self.assertIn('Your proctored exam "Test Exam"', actual_body)
        self.assertIn(credit_state['course_name'], actual_body)
        self.assertIn(expected_message_string, actual_body)

    def test_send_email_unicode(self):
        """
        Assert that email can be sent with a unicode course name.
        """

        course_name = u'अआईउऊऋऌ अआईउऊऋऌ'
        set_runtime_service('credit', MockCreditService(course_name=course_name))

        exam_attempt = self._create_started_exam_attempt()
        credit_state = get_runtime_service('credit').get_credit_state(self.user_id, self.course_id)
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            ProctoredExamStudentAttemptStatus.submitted
        )
        self.assertEqual(len(mail.outbox), 1)

        # Verify the subject
        actual_subject = self._normalize_whitespace(mail.outbox[0].subject)
        self.assertIn('Proctoring Review In Progress', actual_subject)
        self.assertIn(course_name, actual_subject)

        # Verify the body
        actual_body = self._normalize_whitespace(mail.outbox[0].body)
        self.assertIn('was submitted successfully', actual_body)
        self.assertIn(credit_state['course_name'], actual_body)

    @ddt.data(
        ProctoredExamStudentAttemptStatus.eligible,
        ProctoredExamStudentAttemptStatus.created,
        ProctoredExamStudentAttemptStatus.download_software_clicked,
        ProctoredExamStudentAttemptStatus.ready_to_start,
        ProctoredExamStudentAttemptStatus.started,
        ProctoredExamStudentAttemptStatus.ready_to_submit,
        ProctoredExamStudentAttemptStatus.declined,
        ProctoredExamStudentAttemptStatus.timed_out,
        ProctoredExamStudentAttemptStatus.second_review_required,
        ProctoredExamStudentAttemptStatus.error,
    )
    @patch.dict('django.conf.settings.PROCTORING_SETTINGS', {'ALLOW_TIMED_OUT_STATE': True})
    def test_email_not_sent(self, status):
        """
        Assert that an email is not sent for the following attempt status codes.
        """

        exam_attempt = self._create_started_exam_attempt()
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            status
        )
        self.assertEqual(len(mail.outbox), 0)

    @ddt.data(
        ProctoredExamStudentAttemptStatus.submitted,
        ProctoredExamStudentAttemptStatus.verified,
        ProctoredExamStudentAttemptStatus.rejected
    )
    def test_not_send_email_sample_exam(self, status):
        """
        Assert that email is not sent when there is practice/sample exam
        """

        exam_attempt = self._create_started_exam_attempt(is_sample_attempt=True)
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            status
        )
        self.assertEqual(len(mail.outbox), 0)

    @ddt.data(
        ProctoredExamStudentAttemptStatus.submitted,
        ProctoredExamStudentAttemptStatus.verified,
        ProctoredExamStudentAttemptStatus.rejected
    )
    def test_not_send_email_timed_exam(self, status):
        """
        Assert that email is not sent when exam is timed/not-proctoring
        """

        exam_attempt = self._create_started_exam_attempt(is_proctored=False)
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            status
        )
        self.assertEqual(len(mail.outbox), 0)
