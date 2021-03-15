# coding=utf-8
"""
All tests for proctored exam emails.
"""

from copy import deepcopy
from itertools import product

import ddt
from mock import MagicMock, patch
from opaque_keys import InvalidKeyError

from django.conf import settings
from django.core import mail
from django.core.exceptions import ObjectDoesNotExist

from edx_proctoring.api import update_attempt_status
from edx_proctoring.constants import SITE_NAME
from edx_proctoring.runtime import get_runtime_service, set_runtime_service
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus

from .test_services import MockCertificateService, MockCreditService, MockGradesService, MockInstructorService
from .utils import ProctoredExamTestCase


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
        super().setUp()
        self.proctored_exam_id = self._create_proctored_exam()
        self.timed_exam_id = self._create_timed_exam()
        set_runtime_service('grades', MockGradesService())
        set_runtime_service('certificates', MockCertificateService())
        set_runtime_service('instructor', MockInstructorService())

    def tearDown(self):
        """
        When tests are done
        """
        super().tearDown()
        set_runtime_service('grades', None)
        set_runtime_service('certificates', None)
        set_runtime_service('instructor', None)

    @ddt.data(
        [
            ProctoredExamStudentAttemptStatus.submitted,
            'Proctoring Review In Progress',
            'was submitted successfully',
        ],
        [
            ProctoredExamStudentAttemptStatus.verified,
            'Proctoring Results',
            'was reviewed and you met all proctoring requirements',
        ],
        [
            ProctoredExamStudentAttemptStatus.rejected,
            'Proctoring Results',
            'the course team has identified one or more violations',
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
            exam_attempt.id,
            status
        )
        self.assertEqual(len(mail.outbox), 1)

        # Verify the subject
        actual_subject = self._normalize_whitespace(mail.outbox[0].subject)
        self.assertIn(expected_subject, actual_subject)
        self.assertIn(self.exam_name, actual_subject)

        # Verify the body
        actual_body = self._normalize_whitespace(mail.outbox[0].body)
        self.assertIn('Hello tester,', actual_body)
        self.assertIn('Your proctored exam "Test Exam"', actual_body)
        self.assertIn(credit_state['course_name'], actual_body)
        self.assertIn(expected_message_string, actual_body)

    @ddt.data(
        ProctoredExamStudentAttemptStatus.verified,
        ProctoredExamStudentAttemptStatus.rejected
    )
    def test_escalation_email_included(self, status):
        """
        Test that verified and rejected emails include a proctoring escalation email if given.
        """
        instructor_service = get_runtime_service('instructor')
        mock_escalation_email = 'escalation@test.com'
        instructor_service.mock_proctoring_escalation_email(mock_escalation_email)

        exam_attempt = self._create_started_exam_attempt()
        update_attempt_status(exam_attempt.id, status)

        actual_body = self._normalize_whitespace(mail.outbox[0].body)
        self.assertIn(mock_escalation_email, actual_body)
        self.assertNotIn('support/contact_us', actual_body)

    @ddt.data(
        ProctoredExamStudentAttemptStatus.verified,
        ProctoredExamStudentAttemptStatus.rejected
    )
    def test_escalation_email_not_included(self, status):
        """
        Test that verified and rejected emails link to support if an escalation email is
        not given.
        """
        set_runtime_service('instructor', None)

        exam_attempt = self._create_started_exam_attempt()
        update_attempt_status(exam_attempt.id, status)

        actual_body = self._normalize_whitespace(mail.outbox[0].body)
        self.assertIn('support/contact_us', actual_body)

    @ddt.data(InvalidKeyError('foo', 'bar'), ObjectDoesNotExist)
    def test_proctoring_escalation_email_exceptions(self, error):
        """
        Test that when an error is raised when trying to retrieve a proctoring escalation
        email, it sets `proctoring_escalation_email` to None and link to support is used instead
        """
        instructor_service = get_runtime_service('instructor')
        instructor_service.mock_proctoring_escalation_email_error(error)

        exam_attempt = self._create_started_exam_attempt()
        update_attempt_status(
            exam_attempt.id,
            ProctoredExamStudentAttemptStatus.verified
        )

        actual_body = self._normalize_whitespace(mail.outbox[0].body)
        self.assertIn('support/contact_us', actual_body)

    @ddt.data(
        [
            ProctoredExamStudentAttemptStatus.submitted,
            'proctoring_attempt_submitted_email.html',
        ],
        [
            ProctoredExamStudentAttemptStatus.verified,
            'proctoring_attempt_satisfactory_email.html',
        ],
        [
            ProctoredExamStudentAttemptStatus.rejected,
            'proctoring_attempt_unsatisfactory_email.html',
        ]
    )
    @ddt.unpack
    @patch('edx_proctoring.api.loader.select_template')
    def test_email_template_select(self, status, template_name, select_template_mock):
        """
        Assert that we search for the correct email templates, including any backend specific overriding templates
        and the base template.
        """
        exam_attempt = self._create_started_exam_attempt()
        update_attempt_status(
            exam_attempt.id,
            status
        )

        expected_args = [
            'emails/proctoring/{backend}/{template_name}'.format(
                backend=exam_attempt.proctored_exam.backend, template_name=template_name),
            'emails/{template_name}'.format(template_name=template_name)
        ]
        select_template_mock.assert_called_once_with(expected_args)

    def test_send_email_unicode(self):
        """
        Assert that email can be sent with a unicode course name.
        """

        course_name = u'अआईउऊऋऌ अआईउऊऋऌ'
        set_runtime_service('credit', MockCreditService(course_name=course_name))

        exam_attempt = self._create_started_exam_attempt()
        credit_state = get_runtime_service('credit').get_credit_state(self.user_id, self.course_id)
        update_attempt_status(
            exam_attempt.id,
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
    def test_email_not_sent(self, to_status):
        """
        Assert that an email is not sent for the following attempt status codes.
        """
        exam_attempt = self._create_exam_attempt(self.proctored_exam_id)
        update_attempt_status(
            exam_attempt.id,
            to_status
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
            exam_attempt.id,
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
            exam_attempt.id,
            status
        )
        self.assertEqual(len(mail.outbox), 0)

    @ddt.data(
        *product(
            [ProctoredExamStudentAttemptStatus.verified, ProctoredExamStudentAttemptStatus.rejected],
            [True, False]
        )
    )
    @ddt.unpack
    def test_correct_edx_support_url(self, status, override_email):
        """
        Test that the correct edX support URL is used in emails. The email should use either the backend specific
        contact URL, if one is specified, or fall back to the edX contact us support page.
        """
        contact_url = 'http://{site_name}/support/contact_us'.format(site_name=SITE_NAME)
        backend_settings = settings.PROCTORING_BACKENDS

        if override_email:
            contact_url = 'www.example.com'
            backend_settings = deepcopy(backend_settings)
            backend_settings['test'] = {
                'LINK_URLS': {
                    'contact': contact_url,
                }
            }

        with self.settings(PROCTORING_BACKENDS=backend_settings):
            exam_attempt = self._create_started_exam_attempt()
            update_attempt_status(
                exam_attempt.id,
                status
            )

            # Verify the edX support URL
            actual_body = self._normalize_whitespace(mail.outbox[0].body)
            self.assertIn(u'<a href="{contact_url}"> '
                          u'{contact_url} </a>'.format(contact_url=contact_url),
                          actual_body)
