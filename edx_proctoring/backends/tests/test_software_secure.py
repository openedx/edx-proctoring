"""
Tests for the software_secure module
"""

import json
import ddt
from string import Template  # pylint: disable=deprecated-module
from mock import patch
from httmock import all_requests, HTTMock

from django.test import TestCase
from django.contrib.auth.models import User
from edx_proctoring.runtime import set_runtime_service, get_runtime_service

from edx_proctoring.backends import get_backend_provider
from edx_proctoring.exceptions import BackendProvideCannotRegisterAttempt

from edx_proctoring.api import (
    get_exam_attempt_by_id,
    create_exam,
    create_exam_attempt,
    remove_exam_attempt,
)
from edx_proctoring.exceptions import (
    StudentExamAttemptDoesNotExistsException,
    ProctoredExamSuspiciousLookup,
    ProctoredExamReviewAlreadyExists,
    ProctoredExamBadReviewStatus
)
from edx_proctoring. models import (
    ProctoredExamSoftwareSecureReview,
    ProctoredExamSoftwareSecureComment,
    ProctoredExamStudentAttemptStatus,
)
from edx_proctoring.backends.tests.test_review_payload import TEST_REVIEW_PAYLOAD

from edx_proctoring.tests.test_services import MockCreditService


@all_requests
def mock_response_content(url, request):  # pylint: disable=unused-argument
    """
    Mock HTTP response from SoftwareSecure
    """
    return {
        'status_code': 200,
        'content': json.dumps({
            'ssiRecordLocator': 'foobar'
        })
    }


@all_requests
def mock_response_error(url, request):  # pylint: disable=unused-argument
    """
    Mock HTTP response from SoftwareSecure
    """
    return {
        'status_code': 404,
        'content': 'Page not found'
    }


@patch(
    'django.conf.settings.PROCTORING_BACKEND_PROVIDER',
    {
        "class": "edx_proctoring.backends.software_secure.SoftwareSecureBackendProvider",
        "options": {
            "secret_key_id": "foo",
            "secret_key": "4B230FA45A6EC5AE8FDE2AFFACFABAA16D8A3D0B",
            "crypto_key": "123456789123456712345678",
            "exam_register_endpoint": "http://test",
            "organization": "edx",
            "exam_sponsor": "edX LMS",
            "software_download_url": "http://example.com"
        }
    }
)
@ddt.ddt
class SoftwareSecureTests(TestCase):
    """
    All tests for the SoftwareSecureBackendProvider
    """

    def setUp(self):
        """
        Initialize
        """
        super(SoftwareSecureTests, self).setUp()
        self.user = User(username='foo', email='foo@bar.com')
        self.user.save()

        set_runtime_service('credit', MockCreditService())

    def tearDown(self):
        """
        When tests are done
        """
        set_runtime_service('credit', None)

    def test_provider_instance(self):
        """
        Makes sure the instance of the proctoring module can be created
        """

        provider = get_backend_provider()
        self.assertIsNotNone(provider)

    def test_get_software_download_url(self):
        """
        Makes sure we get the expected download url
        """

        provider = get_backend_provider()
        self.assertEqual(provider.get_software_download_url(), 'http://example.com')

    def test_register_attempt(self):
        """
        Makes sure we can register an attempt
        """

        exam_id = create_exam(
            course_id='foo/bar/baz',
            content_id='content',
            exam_name='Sample Exam',
            time_limit_mins=10,
            is_proctored=True
        )

        with HTTMock(mock_response_content):
            attempt_id = create_exam_attempt(exam_id, self.user.id, taking_as_proctored=True)
            self.assertIsNotNone(attempt_id)

            attempt = get_exam_attempt_by_id(attempt_id)
            self.assertEqual(attempt['external_id'], 'foobar')
            self.assertIsNone(attempt['started_at'])

    def test_single_name_attempt(self):
        """
        Tests to make sure we can parse a fullname which does not have any spaces in it
        """

        def mock_profile_service(user_id):  # pylint: disable=unused-argument
            """
            Mocked out Profile callback endpoint
            """
            return {'name': 'Bono'}

        set_runtime_service('profile', mock_profile_service)

        exam_id = create_exam(
            course_id='foo/bar/baz',
            content_id='content',
            exam_name='Sample Exam',
            time_limit_mins=10,
            is_proctored=True
        )

        with HTTMock(mock_response_content):
            attempt_id = create_exam_attempt(exam_id, self.user.id, taking_as_proctored=True)
            self.assertIsNotNone(attempt_id)

    def test_failing_register_attempt(self):
        """
        Makes sure we can register an attempt
        """

        exam_id = create_exam(
            course_id='foo/bar/baz',
            content_id='content',
            exam_name='Sample Exam',
            time_limit_mins=10,
            is_proctored=True
        )

        # now try a failing request
        with HTTMock(mock_response_error):
            with self.assertRaises(BackendProvideCannotRegisterAttempt):
                create_exam_attempt(exam_id, self.user.id, taking_as_proctored=True)

    def test_payload_construction(self):
        """
        Calls directly into the SoftwareSecure payload construction
        """

        provider = get_backend_provider()
        body = provider._body_string({  # pylint: disable=protected-access
            'foo': False,
            'none': None,
        })
        self.assertIn('false', body)
        self.assertIn('null', body)

        body = provider._body_string({  # pylint: disable=protected-access
            'foo': ['first', {'here': 'yes'}]
        })
        self.assertIn('first', body)
        self.assertIn('here', body)
        self.assertIn('yes', body)

    def test_start_proctored_exam(self):
        """
        Test that SoftwareSecure's implementation returns None, because there is no
        work that needs to happen right now
        """

        provider = get_backend_provider()
        self.assertIsNone(provider.start_exam_attempt(None, None))

    def test_stop_proctored_exam(self):
        """
        Test that SoftwareSecure's implementation returns None, because there is no
        work that needs to happen right now
        """

        provider = get_backend_provider()
        self.assertIsNone(provider.stop_exam_attempt(None, None))

    @ddt.data(
        ('Clean', 'satisfied'),
        ('Suspicious', 'satisfied'),
        ('Rules Violation', 'failed'),
        ('Not Reviewed', 'failed'),
    )
    @ddt.unpack
    def test_review_callback(self, review_status, credit_requirement_status):
        """
        Simulates callbacks from SoftwareSecure with various statuses
        """

        provider = get_backend_provider()

        exam_id = create_exam(
            course_id='foo/bar/baz',
            content_id='content',
            exam_name='Sample Exam',
            time_limit_mins=10,
            is_proctored=True
        )

        # be sure to use the mocked out SoftwareSecure handlers
        with HTTMock(mock_response_content):
            attempt_id = create_exam_attempt(
                exam_id,
                self.user.id,
                taking_as_proctored=True
            )

        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertIsNotNone(attempt['external_id'])

        test_payload = Template(TEST_REVIEW_PAYLOAD).substitute(
            attempt_code=attempt['attempt_code'],
            external_id=attempt['external_id']
        )
        test_payload = test_payload.replace('Clean', review_status)

        provider.on_review_callback(json.loads(test_payload))

        # make sure that what we have in the Database matches what we expect
        review = ProctoredExamSoftwareSecureReview.get_review_by_attempt_code(attempt['attempt_code'])

        self.assertIsNotNone(review)
        self.assertEqual(review.review_status, review_status)
        self.assertEqual(
            review.video_url,
            'http://www.remoteproctor.com/AdminSite/Account/Reviewer/DirectLink-Generic.aspx?ID=foo'
        )
        self.assertIsNotNone(review.raw_data)

        # now check the comments that were stored
        comments = ProctoredExamSoftwareSecureComment.objects.filter(review_id=review.id)

        self.assertEqual(len(comments), 6)

        # check that we got credit requirement set appropriately

        credit_service = get_runtime_service('credit')
        credit_status = credit_service.get_credit_state(self.user.id, 'foo/bar/baz')

        self.assertEqual(
            credit_status['credit_requirement_status'][0]['status'],
            credit_requirement_status
        )

    def test_review_bad_code(self):
        """
        Asserts raising of an exception if we get a report for
        an attempt code which does not exist
        """

        provider = get_backend_provider()
        test_payload = Template(TEST_REVIEW_PAYLOAD).substitute(
            attempt_code='not-here',
            external_id='also-not-here'
        )

        with self.assertRaises(StudentExamAttemptDoesNotExistsException):
            provider.on_review_callback(json.loads(test_payload))

    def test_review_status_code(self):
        """
        Asserts raising of an exception if we get a report
        with a reviewStatus which is unexpected
        """

        provider = get_backend_provider()
        test_payload = Template(TEST_REVIEW_PAYLOAD).substitute(
            attempt_code='not-here',
            external_id='also-not-here'
        )
        test_payload = test_payload.replace('Clean', 'Unexpected')

        with self.assertRaises(ProctoredExamBadReviewStatus):
            provider.on_review_callback(json.loads(test_payload))

    def test_review_mistmatched_tokens(self):
        """
        Asserts raising of an exception if we get a report for
        an attempt code which has a external_id which does not
        match the report
        """

        provider = get_backend_provider()

        exam_id = create_exam(
            course_id='foo/bar/baz',
            content_id='content',
            exam_name='Sample Exam',
            time_limit_mins=10,
            is_proctored=True
        )

        # be sure to use the mocked out SoftwareSecure handlers
        with HTTMock(mock_response_content):
            attempt_id = create_exam_attempt(
                exam_id,
                self.user.id,
                taking_as_proctored=True
            )

        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertIsNotNone(attempt['external_id'])

        test_payload = Template(TEST_REVIEW_PAYLOAD).substitute(
            attempt_code=attempt['attempt_code'],
            external_id='bogus'
        )

        with self.assertRaises(ProctoredExamSuspiciousLookup):
            provider.on_review_callback(json.loads(test_payload))

    @patch.dict('django.conf.settings.PROCTORING_SETTINGS', {'ALLOW_CALLBACK_SIMULATION': True})
    def test_allow_simulated_callbacks(self):
        """
        Verify that the configuration switch to
        not do confirmation of external_id/ssiRecordLocators
        """

        provider = get_backend_provider()

        exam_id = create_exam(
            course_id='foo/bar/baz',
            content_id='content',
            exam_name='Sample Exam',
            time_limit_mins=10,
            is_proctored=True
        )

        # be sure to use the mocked out SoftwareSecure handlers
        with HTTMock(mock_response_content):
            attempt_id = create_exam_attempt(
                exam_id,
                self.user.id,
                taking_as_proctored=True
            )

        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertIsNotNone(attempt['external_id'])

        test_payload = Template(TEST_REVIEW_PAYLOAD).substitute(
            attempt_code=attempt['attempt_code'],
            external_id='bogus'
        )

        # this should not raise an exception since we have
        # the ALLOW_CALLBACK_SIMULATION override
        provider.on_review_callback(json.loads(test_payload))

        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.verified)

    def test_review_on_archived_attempt(self):
        """
        Make sure we can process a review report for
        an attempt which has been archived
        """

        provider = get_backend_provider()

        exam_id = create_exam(
            course_id='foo/bar/baz',
            content_id='content',
            exam_name='Sample Exam',
            time_limit_mins=10,
            is_proctored=True
        )

        # be sure to use the mocked out SoftwareSecure handlers
        with HTTMock(mock_response_content):
            attempt_id = create_exam_attempt(
                exam_id,
                self.user.id,
                taking_as_proctored=True
            )

        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertIsNotNone(attempt['external_id'])

        test_payload = Template(TEST_REVIEW_PAYLOAD).substitute(
            attempt_code=attempt['attempt_code'],
            external_id=attempt['external_id']
        )

        # now delete the attempt, which puts it into the archive table
        remove_exam_attempt(attempt_id)

        # now process the report
        provider.on_review_callback(json.loads(test_payload))

        # make sure that what we have in the Database matches what we expect
        review = ProctoredExamSoftwareSecureReview.get_review_by_attempt_code(attempt['attempt_code'])

        self.assertIsNotNone(review)
        self.assertEqual(review.review_status, 'Clean')
        self.assertEqual(
            review.video_url,
            'http://www.remoteproctor.com/AdminSite/Account/Reviewer/DirectLink-Generic.aspx?ID=foo'
        )
        self.assertIsNotNone(review.raw_data)

        # now check the comments that were stored
        comments = ProctoredExamSoftwareSecureComment.objects.filter(review_id=review.id)

        self.assertEqual(len(comments), 6)

    def test_review_resubmission(self):
        """
        Tests that an exception is raised if a review report is resubmitted for the same
        attempt
        """

        provider = get_backend_provider()

        exam_id = create_exam(
            course_id='foo/bar/baz',
            content_id='content',
            exam_name='Sample Exam',
            time_limit_mins=10,
            is_proctored=True
        )

        # be sure to use the mocked out SoftwareSecure handlers
        with HTTMock(mock_response_content):
            attempt_id = create_exam_attempt(
                exam_id,
                self.user.id,
                taking_as_proctored=True
            )

        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertIsNotNone(attempt['external_id'])

        test_payload = Template(TEST_REVIEW_PAYLOAD).substitute(
            attempt_code=attempt['attempt_code'],
            external_id=attempt['external_id']
        )

        provider.on_review_callback(json.loads(test_payload))

        # now call again
        with self.assertRaises(ProctoredExamReviewAlreadyExists):
            provider.on_review_callback(json.loads(test_payload))
