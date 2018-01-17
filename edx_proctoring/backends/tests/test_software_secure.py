# coding=utf-8
# pylint: disable=too-many-lines, invalid-name, protected-access
"""
Tests for the software_secure module
"""

from __future__ import absolute_import

import json
import ddt
from mock import MagicMock, patch
from httmock import all_requests, HTTMock

from django.test import TestCase
from django.contrib.auth.models import User
from edx_proctoring.runtime import set_runtime_service, get_runtime_service

from edx_proctoring.backends import get_backend_provider
from edx_proctoring.exceptions import BackendProvideCannotRegisterAttempt
from edx_proctoring import constants

from edx_proctoring.api import (
    get_exam_attempt_by_id,
    create_exam,
    create_exam_attempt,
    remove_exam_attempt,
    add_allowance_for_user

)
from edx_proctoring.exceptions import (
    StudentExamAttemptDoesNotExistsException,
    ProctoredExamSuspiciousLookup,
    ProctoredExamReviewAlreadyExists,
    ProctoredExamBadReviewStatus
)
from edx_proctoring.models import (
    ProctoredExamSoftwareSecureReview,
    ProctoredExamSoftwareSecureComment,
    ProctoredExamStudentAttemptStatus,
    ProctoredExamSoftwareSecureReviewHistory,
    ProctoredExamReviewPolicy,
    ProctoredExamStudentAttemptHistory,
    ProctoredExamStudentAllowance
)
from edx_proctoring.backends.tests.test_review_payload import create_test_review_payload
from edx_proctoring.tests.test_services import (
    MockCreditService,
    MockInstructorService,
    MockGradesService,
    MockCertificateService
)
from edx_proctoring.backends.software_secure import SOFTWARE_SECURE_INVALID_CHARS


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
            "software_download_url": "http://example.com",
            "send_email": True
        }
    }
)
@patch('django.core.urlresolvers.reverse', MagicMock)
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
        set_runtime_service('instructor', MockInstructorService())
        set_runtime_service('grades', MockGradesService())
        set_runtime_service('certificates', MockCertificateService())

    def tearDown(self):
        """
        When tests are done
        """
        super(SoftwareSecureTests, self).tearDown()
        set_runtime_service('credit', None)
        set_runtime_service('grades', None)
        set_runtime_service('certificates', None)

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

    @ddt.data(None, 'additional person allowed in room')
    def test_attempt_with_review_policy(self, review_policy_exception):
        """
        Create an unstarted proctoring attempt with a review policy associated with it.
        """

        exam_id = create_exam(
            course_id='foo/bar/baz',
            content_id='content',
            exam_name='Sample Exam',
            time_limit_mins=10,
            is_proctored=True
        )

        if review_policy_exception:
            add_allowance_for_user(
                exam_id,
                self.user.id,
                ProctoredExamStudentAllowance.REVIEW_POLICY_EXCEPTION,
                review_policy_exception
            )

        policy = ProctoredExamReviewPolicy.objects.create(
            set_by_user_id=self.user.id,
            proctored_exam_id=exam_id,
            review_policy='Foo Policy'
        )

        def assert_get_payload_mock(exam, context):
            """
            Add a mock shim so we can assert that the _get_payload has been called with the right
            review policy
            """
            self.assertIn('review_policy', context)
            self.assertEqual(policy.review_policy, context['review_policy'])

            # call into real implementation
            result = get_backend_provider(emphemeral=True)._get_payload(exam, context)

            # assert that this is in the 'reviewerNotes' field that is passed to SoftwareSecure
            expected = context['review_policy']
            if review_policy_exception:
                expected = '{base}; {exception}'.format(
                    base=expected,
                    exception=review_policy_exception
                )

            self.assertEqual(result['reviewerNotes'], expected)
            return result

        with HTTMock(mock_response_content):
            # patch the _get_payload method on the backend provider
            # so that we can assert that we are called with the review policy
            # as well as asserting that _get_payload includes that review policy
            # that was passed in
            with patch.object(get_backend_provider(), '_get_payload', assert_get_payload_mock):
                attempt_id = create_exam_attempt(
                    exam_id,
                    self.user.id,
                    taking_as_proctored=True
                )
                self.assertGreater(attempt_id, 0)

                # make sure we recorded the policy id at the time this was created
                attempt = get_exam_attempt_by_id(attempt_id)
                self.assertEqual(attempt['review_policy_id'], policy.id)

    def test_attempt_with_no_review_policy(self):
        """
        Create an unstarted proctoring attempt with no review policy associated with it.
        """

        def assert_get_payload_mock_no_policy(exam, context):
            """
            Add a mock shim so we can assert that the _get_payload has been called with the right
            review policy
            """
            self.assertNotIn('review_policy', context)

            # call into real implementation
            result = get_backend_provider(emphemeral=True)._get_payload(exam, context)

            # assert that we use the default that is defined in system configuration
            self.assertEqual(result['reviewerNotes'], constants.DEFAULT_SOFTWARE_SECURE_REVIEW_POLICY)

            # the check that if a colon was passed in for the exam name, then the colon was changed to
            # a dash. This is because SoftwareSecure cannot handle a colon in the exam name
            for illegal_char in SOFTWARE_SECURE_INVALID_CHARS:
                if illegal_char in exam['exam_name']:
                    self.assertNotIn(illegal_char, result['examName'])
                    self.assertIn('_', result['examName'])

            return result

        for illegal_char in SOFTWARE_SECURE_INVALID_CHARS:
            exam_id = create_exam(
                course_id='foo/bar/baz',
                content_id='content with {}'.format(illegal_char),
                exam_name='Sample Exam with {} character'.format(illegal_char),
                time_limit_mins=10,
                is_proctored=True
            )

            with HTTMock(mock_response_content):
                # patch the _get_payload method on the backend provider
                # so that we can assert that we are called with the review policy
                # undefined and that we use the system default
                with patch.object(get_backend_provider(), '_get_payload', assert_get_payload_mock_no_policy):
                    attempt_id = create_exam_attempt(
                        exam_id,
                        self.user.id,
                        taking_as_proctored=True
                    )
                    self.assertGreater(attempt_id, 0)

                    # make sure we recorded that there is no review policy
                    attempt = get_exam_attempt_by_id(attempt_id)
                    self.assertIsNone(attempt['review_policy_id'])

    def test_attempt_with_unicode_characters(self):
        """
        test that the unicode characters are removed from exam names before registering with
        software secure.
        """

        def is_ascii(value):
            """
            returns True if string is ascii and False otherwise.
            """

            try:
                value.encode('ascii')
                return True
            except UnicodeEncodeError:
                return False

        def assert_get_payload_mock_unicode_characters(exam, context):
            """
            Add a mock so we can assert that the _get_payload call removes unicode characters.
            """

            # call into real implementation
            result = get_backend_provider(emphemeral=True)._get_payload(exam, context)
            self.assertFalse(isinstance(result['examName'], unicode))
            self.assertTrue(is_ascii(result['examName']))
            self.assertGreater(len(result['examName']), 0)
            return result

        with HTTMock(mock_response_content):

            exam_id = create_exam(
                course_id='foo/bar/baz',
                content_id='content with unicode characters',
                exam_name=u'Klüft skräms inför på fédéral électoral große',
                time_limit_mins=10,
                is_proctored=True
            )

            # patch the _get_payload method on the backend provider
            with patch.object(get_backend_provider(), '_get_payload', assert_get_payload_mock_unicode_characters):
                attempt_id = create_exam_attempt(
                    exam_id,
                    self.user.id,
                    taking_as_proctored=True
                )
                self.assertGreater(attempt_id, 0)

            # now try with an eastern language (Chinese)
            exam_id = create_exam(
                course_id='foo/bar/baz',
                content_id='content with chinese characters',
                exam_name=u'到处群魔乱舞',
                time_limit_mins=10,
                is_proctored=True
            )

            # patch the _get_payload method on the backend provider
            with patch.object(get_backend_provider(), '_get_payload', assert_get_payload_mock_unicode_characters):
                attempt_id = create_exam_attempt(
                    exam_id,
                    self.user.id,
                    taking_as_proctored=True
                )
                self.assertGreater(attempt_id, 0)

    def test_single_name_attempt(self):
        """
        Tests to make sure we can parse a fullname which does not have any spaces in it
        """

        set_runtime_service('credit', MockCreditService())

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

    def test_unicode_attempt(self):
        """
        Tests to make sure we can handle an attempt when a user's fullname has unicode characters in it
        """

        set_runtime_service('credit', MockCreditService(profile_fullname=u'अआईउऊऋऌ अआईउऊऋऌ'))

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

        # try unicode exam name, also
        exam_id = create_exam(
            course_id='foo/bar/baz',
            content_id='content_unicode_name',
            exam_name=u'अआईउऊऋऌ अआईउऊऋऌ',
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
        ('Rules Violation', 'satisfied'),
        ('Suspicious', 'failed'),
        ('Not Reviewed', 'failed'),
    )
    @ddt.unpack
    @patch('edx_proctoring.constants.REQUIRE_FAILURE_SECOND_REVIEWS', False)
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

        test_payload = create_test_review_payload(
            attempt_code=attempt['attempt_code'],
            external_id=attempt['external_id']
        )
        test_payload = test_payload.replace('Clean', review_status)

        provider.on_review_callback(json.loads(test_payload))

        # make sure that what we have in the Database matches what we expect
        review = ProctoredExamSoftwareSecureReview.get_review_by_attempt_code(attempt['attempt_code'])

        self.assertIsNotNone(review)
        self.assertEqual(review.review_status, review_status)
        self.assertFalse(review.video_url)

        self.assertIsNotNone(review.raw_data)
        self.assertIsNone(review.reviewed_by)

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
        test_payload = create_test_review_payload(
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
        test_payload = create_test_review_payload(
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

        test_payload = create_test_review_payload(
            attempt_code=attempt['attempt_code'],
            external_id='bogus'
        )

        with self.assertRaises(ProctoredExamSuspiciousLookup):
            provider.on_review_callback(json.loads(test_payload))

    @patch.dict('django.conf.settings.PROCTORING_SETTINGS', {'ALLOW_CALLBACK_SIMULATION': True})
    @patch('edx_proctoring.constants.REQUIRE_FAILURE_SECOND_REVIEWS', False)
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

        test_payload = create_test_review_payload(
            attempt_code=attempt['attempt_code'],
            external_id='bogus'
        )

        # this should not raise an exception since we have
        # the ALLOW_CALLBACK_SIMULATION override
        provider.on_review_callback(json.loads(test_payload))

        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.verified)

    @patch('edx_proctoring.constants.REQUIRE_FAILURE_SECOND_REVIEWS', False)
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

        test_payload = create_test_review_payload(
            attempt_code=attempt['attempt_code'],
            external_id=attempt['external_id']
        )

        # now delete the attempt, which puts it into the archive table
        remove_exam_attempt(attempt_id, requesting_user=self.user)

        # now process the report
        provider.on_review_callback(json.loads(test_payload))

        # make sure that what we have in the Database matches what we expect
        review = ProctoredExamSoftwareSecureReview.get_review_by_attempt_code(attempt['attempt_code'])

        self.assertIsNotNone(review)
        self.assertEqual(review.review_status, 'Clean')
        self.assertFalse(review.video_url)

        self.assertIsNotNone(review.raw_data)

        # now check the comments that were stored
        comments = ProctoredExamSoftwareSecureComment.objects.filter(review_id=review.id)

        self.assertEqual(len(comments), 6)

    @patch('edx_proctoring.constants.ALLOW_REVIEW_UPDATES', False)
    @patch('edx_proctoring.constants.REQUIRE_FAILURE_SECOND_REVIEWS', False)
    def test_disallow_review_resubmission(self):
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

        test_payload = create_test_review_payload(
            attempt_code=attempt['attempt_code'],
            external_id=attempt['external_id']
        )

        provider.on_review_callback(json.loads(test_payload))

        # now call again
        with self.assertRaises(ProctoredExamReviewAlreadyExists):
            provider.on_review_callback(json.loads(test_payload))

    @patch('edx_proctoring.constants.ALLOW_REVIEW_UPDATES', True)
    def test_allow_review_resubmission(self):
        """
        Tests that an resubmission is allowed
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

        test_payload = create_test_review_payload(
            attempt_code=attempt['attempt_code'],
            external_id=attempt['external_id']
        )

        provider.on_review_callback(json.loads(test_payload))

        # make sure history table is empty
        records = ProctoredExamSoftwareSecureReviewHistory.objects.filter(attempt_code=attempt['attempt_code'])
        self.assertEqual(len(records), 0)

        # now call again, this will not throw exception
        test_payload = test_payload.replace('Clean', 'Suspicious')
        provider.on_review_callback(json.loads(test_payload))

        # make sure that what we have in the Database matches what we expect
        review = ProctoredExamSoftwareSecureReview.get_review_by_attempt_code(attempt['attempt_code'])

        self.assertIsNotNone(review)
        self.assertEqual(review.review_status, 'Suspicious')
        self.assertFalse(review.video_url)

        self.assertIsNotNone(review.raw_data)

        # make sure history table is no longer empty
        records = ProctoredExamSoftwareSecureReviewHistory.objects.filter(attempt_code=attempt['attempt_code'])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].review_status, 'Clean')

        # now try to delete the record and make sure it was archived

        review.delete()

        records = ProctoredExamSoftwareSecureReviewHistory.objects.filter(attempt_code=attempt['attempt_code'])
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].review_status, 'Clean')
        self.assertEqual(records[1].review_status, 'Suspicious')

    @ddt.data(False, True)
    def test_failure_submission(self, allow_rejects):
        """
        Tests that a submission of a failed test and make sure that we
        don't automatically update the status to failure
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

        test_payload = create_test_review_payload(
            attempt_code=attempt['attempt_code'],
            external_id=attempt['external_id']
        )
        test_payload = test_payload.replace('Clean', 'Suspicious')

        # submit a Suspicious review payload
        provider.on_review_callback(json.loads(test_payload))

        # now look at the attempt and make sure it did not
        # transition to failure on the callback,
        # as we'll need a manual confirmation via Django Admin pages
        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertNotEqual(attempt['status'], ProctoredExamStudentAttemptStatus.rejected)

        review = ProctoredExamSoftwareSecureReview.objects.get(attempt_code=attempt['attempt_code'])

        # now simulate a update via Django Admin table which will actually
        # push through the failure into our attempt status (as well as trigger)
        # other workflow
        provider.on_review_saved(review, allow_rejects=allow_rejects)

        attempt = get_exam_attempt_by_id(attempt_id)

        # if we don't allow rejects to be stored in attempt status
        # then we should expect a 'second_review_required' status
        expected_status = (
            ProctoredExamStudentAttemptStatus.rejected if allow_rejects else
            ProctoredExamStudentAttemptStatus.second_review_required
        )
        self.assertEqual(attempt['status'], expected_status)

    def test_update_archived_attempt(self):
        """
        Test calling the on_review_saved interface point with an attempt_code that was archived
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

        test_payload = create_test_review_payload(
            attempt_code=attempt['attempt_code'],
            external_id=attempt['external_id']
        )

        # now process the report
        provider.on_review_callback(json.loads(test_payload))

        # now look at the attempt and make sure it did not
        # transition to failure on the callback,
        # as we'll need a manual confirmation via Django Admin pages
        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertEqual(attempt['status'], attempt['status'])

        # now delete the attempt, which puts it into the archive table
        remove_exam_attempt(attempt_id, requesting_user=self.user)

        review = ProctoredExamSoftwareSecureReview.objects.get(attempt_code=attempt['attempt_code'])

        # now simulate a update via Django Admin table which will actually
        # push through the failure into our attempt status but
        # as this is an archived attempt, we don't do anything
        provider.on_review_saved(review, allow_rejects=True)

        # look at the attempt again, since it moved into Archived state
        # then it should still remain unchanged
        archived_attempt = ProctoredExamStudentAttemptHistory.objects.filter(
            attempt_code=attempt['attempt_code']
        ).latest('created')

        self.assertEqual(archived_attempt.status, attempt['status'])

    def test_on_review_saved_bad_code(self):
        """
        Simulate calling on_review_saved() with an attempt code that cannot be found
        """

        provider = get_backend_provider()

        review = ProctoredExamSoftwareSecureReview()
        review.attempt_code = 'foo'

        self.assertIsNone(provider.on_review_saved(review, allow_rejects=True))

    def test_split_fullname(self):
        """
        Make sure we are splitting up full names correctly
        """

        provider = get_backend_provider()

        (first_name, last_name) = provider._split_fullname('John Doe')
        self.assertEqual(first_name, 'John')
        self.assertEqual(last_name, 'Doe')

        (first_name, last_name) = provider._split_fullname('Johnny')
        self.assertEqual(first_name, 'Johnny')
        self.assertEqual(last_name, '')

        (first_name, last_name) = provider._split_fullname('Baron von Munchausen')
        self.assertEqual(first_name, 'Baron')
        self.assertEqual(last_name, 'von Munchausen')

        (first_name, last_name) = provider._split_fullname(u'अआईउऊऋऌ अआईउऊऋऌ')
        self.assertEqual(first_name, u'अआईउऊऋऌ')
        self.assertEqual(last_name, u'अआईउऊऋऌ')
