# coding=utf-8
"""
All tests for proctored exam emails.
"""

from __future__ import absolute_import

import ddt
from django.core import mail
from mock import patch

from edx_proctoring.api import (
    update_attempt_status,
)
from edx_proctoring.models import (
    ProctoredExamStudentAttemptStatus,
)
from edx_proctoring.runtime import set_runtime_service, get_runtime_service

from .test_services import (
    MockCreditService,
)
from .utils import (
    ProctoredExamTestCase,
)


@ddt.ddt
class ProctoredExamEmailTests(ProctoredExamTestCase):
    """
    All tests for proctored exam emails.
    """

    def setUp(self):
        """
        Build out test harnessing
        """
        super(ProctoredExamEmailTests, self).setUp()

        # Messages for get_student_view
        self.proctored_exam_email_subject = 'Proctoring Session Results Update'
        self.proctored_exam_email_body = 'the status of your proctoring session review'

    @ddt.data(
        ProctoredExamStudentAttemptStatus.submitted,
        ProctoredExamStudentAttemptStatus.verified,
        ProctoredExamStudentAttemptStatus.rejected
    )
    def test_send_email(self, status):
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
        self.assertEquals(len(mail.outbox), 1)
        self.assertIn(self.proctored_exam_email_subject, mail.outbox[0].subject)
        self.assertIn(self.proctored_exam_email_body, mail.outbox[0].body)
        self.assertIn(ProctoredExamStudentAttemptStatus.get_status_alias(status), mail.outbox[0].body)
        self.assertIn(credit_state['course_name'], mail.outbox[0].body)

    @ddt.data(
        ProctoredExamStudentAttemptStatus.second_review_required,
        ProctoredExamStudentAttemptStatus.error
    )
    def test_email_not_sent(self, status):
        """
        Assert than email is not sent on the following statuses of proctoring attempt
        """

        exam_attempt = self._create_started_exam_attempt()
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            status
        )
        self.assertEquals(len(mail.outbox), 0)

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
        self.assertEquals(len(mail.outbox), 1)
        self.assertIn(self.proctored_exam_email_subject, mail.outbox[0].subject)
        self.assertIn(course_name, mail.outbox[0].subject)
        self.assertIn(self.proctored_exam_email_body, mail.outbox[0].body)
        self.assertIn(
            ProctoredExamStudentAttemptStatus.get_status_alias(
                ProctoredExamStudentAttemptStatus.submitted
            ),
            mail.outbox[0].body
        )
        self.assertIn(credit_state['course_name'], mail.outbox[0].body)

    @ddt.data(
        ProctoredExamStudentAttemptStatus.eligible,
        ProctoredExamStudentAttemptStatus.created,
        ProctoredExamStudentAttemptStatus.download_software_clicked,
        ProctoredExamStudentAttemptStatus.ready_to_start,
        ProctoredExamStudentAttemptStatus.started,
        ProctoredExamStudentAttemptStatus.ready_to_submit,
        ProctoredExamStudentAttemptStatus.declined,
        ProctoredExamStudentAttemptStatus.timed_out,
        ProctoredExamStudentAttemptStatus.error
    )
    @patch.dict('django.conf.settings.PROCTORING_SETTINGS', {'ALLOW_TIMED_OUT_STATE': True})
    def test_not_send_email(self, status):
        """
        Assert that email is not sent on the following statuses of proctoring attempt.
        """

        exam_attempt = self._create_started_exam_attempt()
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            status
        )
        self.assertEquals(len(mail.outbox), 0)

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
        self.assertEquals(len(mail.outbox), 0)

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
        self.assertEquals(len(mail.outbox), 0)
