# coding=utf-8
# pylint: disable=too-many-lines, invalid-name, protected-access
"""
Tests for the software_secure module
"""

import json

import ddt
from httmock import HTTMock, all_requests
from mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from edx_proctoring import constants
from edx_proctoring.api import add_allowance_for_user, create_exam, create_exam_attempt, get_exam_attempt_by_id
from edx_proctoring.backends import get_backend_provider
from edx_proctoring.backends.software_secure import SOFTWARE_SECURE_INVALID_CHARS, SoftwareSecureBackendProvider
from edx_proctoring.backends.tests.test_review_payload import create_test_review_payload
from edx_proctoring.exceptions import BackendProviderCannotRegisterAttempt
from edx_proctoring.models import ProctoredExamReviewPolicy, ProctoredExamStudentAllowance
from edx_proctoring.runtime import set_runtime_service
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus
from edx_proctoring.tests.test_services import (
    MockCertificateService,
    MockCreditService,
    MockCreditServiceNone,
    MockGradesService,
    MockInstructorService
)

User = get_user_model()


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
        'content': 'Page not found',
    }


# Save the real implementation for use in mocks.
software_secure_get_payload = SoftwareSecureBackendProvider._get_payload


@patch(
    'django.conf.settings.PROCTORING_BACKENDS',
    {
        "software_secure": {
            "secret_key_id": "foo",
            "secret_key": "4B230FA45A6EC5AE8FDE2AFFACFABAA16D8A3D0B",
            "crypto_key": "123456789123456712345678",
            "exam_register_endpoint": "http://test",
            "organization": "edx",
            "exam_sponsor": "edX LMS",
            "software_download_url": "http://example.com",
            "send_email": True,
            "help_center_url": "https://example.com",
            "video_review_aes_key": "B886E02F19C77EC734B1B132BEECD91E"
        },
        "DEFAULT": "software_secure",
        "test": {},
    }
)
@patch('django.urls.reverse', MagicMock)
@ddt.ddt
class SoftwareSecureTests(TestCase):
    """
    All tests for the SoftwareSecureBackendProvider
    """

    def setUp(self):
        """
        Initialize
        """
        super().setUp()
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
        super().tearDown()
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

    def test_get_proctoring_config(self):
        """
        Makes sure proctoring config is returned
        """

        provider = get_backend_provider()
        config = provider.get_proctoring_config()
        self.assertIsNotNone(config)
        self.assertEqual(config['name'], provider.verbose_name)
        self.assertEqual(config['download_url'], 'http://example.com')

    def test_get_video_review_aes_key(self):
        """
        Make sure we get expected aes key
        """

        provider = get_backend_provider()
        self.assertEqual(provider.get_video_review_aes_key(), 'B886E02F19C77EC734B1B132BEECD91E')

    def test_register_attempt(self):
        """
        Makes sure we can register an attempt
        """

        exam_id = create_exam(
            course_id='foo/bar/baz',
            content_id='content',
            exam_name='Sample Exam',
            time_limit_mins=10,
            is_proctored=True,
            backend='software_secure',
        )

        with HTTMock(mock_response_content):
            attempt_id = create_exam_attempt(exam_id, self.user.id, taking_as_proctored=True)
            self.assertIsNotNone(attempt_id)

            attempt = get_exam_attempt_by_id(attempt_id)
            self.assertEqual(attempt['external_id'], 'foobar')
            self.assertIsNone(attempt['started_at'])

    @patch.dict('django.conf.settings.PROCTORING_SETTINGS', {'ALLOW_CALLBACK_SIMULATION': True})
    @patch('edx_proctoring.constants.REQUIRE_FAILURE_SECOND_REVIEWS', False)
    def test_allow_simulated_callbacks(self):
        """
        Verify that the configuration switch to
        not do confirmation of external_id/ssiRecordLocators
        """
        exam_id = create_exam(
            course_id='foo/bar/baz',
            content_id='content',
            exam_name='Sample Exam',
            time_limit_mins=10,
            is_proctored=True,
            backend='software_secure',
        )

        # this should not raise an exception since we have
        # the ALLOW_CALLBACK_SIMULATION override
        with HTTMock(mock_response_content):
            attempt_id = create_exam_attempt(exam_id, self.user.id, taking_as_proctored=True)
            self.assertIsNotNone(attempt_id)
            attempt = get_exam_attempt_by_id(attempt_id)
            test_payload = create_test_review_payload(
                attempt_code=attempt['attempt_code'],
                external_id='bogus'
            )
            response = self.client.post(
                reverse('edx_proctoring:anonymous.proctoring_review_callback'),
                data=test_payload,
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 200)
        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.verified)

    def test_missing_attempt_code(self):
        """
        Test that bad attept codes return errors
        """
        exam_id = create_exam(
            course_id='foo/bar/baz',
            content_id='content',
            exam_name='Sample Exam',
            time_limit_mins=10,
            is_proctored=True,
            backend='software_secure',
        )

        with HTTMock(mock_response_content):
            attempt_id = create_exam_attempt(exam_id, self.user.id, taking_as_proctored=True)
            self.assertIsNotNone(attempt_id)
            test_payload = create_test_review_payload(
                attempt_code='bag code',
                external_id='bogus'
            )
            response = self.client.post(
                reverse('edx_proctoring:anonymous.proctoring_review_callback'),
                data=test_payload,
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 400)
        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.created)

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

        test_self = self        # So that we can access test methods in nested function.

        def assert_get_payload_mock(self, exam, context):
            """
            Add a mock shim so we can assert that the _get_payload has been called with the right
            review policy
            """
            assert_get_payload_mock.called = True

            test_self.assertIn('review_policy', context)
            test_self.assertEqual(policy.review_policy, context['review_policy'])

            # call into real implementation
            # pylint: disable=too-many-function-args
            result = software_secure_get_payload(self, exam, context)

            # assert that this is in the 'reviewerNotes' field that is passed to SoftwareSecure
            expected = context['review_policy']
            if review_policy_exception:
                expected = f'{expected}; {review_policy_exception}'

            test_self.assertEqual(result['reviewerNotes'], expected)
            return result

        with HTTMock(mock_response_content):
            # patch the _get_payload method on the backend provider
            # so that we can assert that we are called with the review policy
            # as well as asserting that _get_payload includes that review policy
            # that was passed in
            with patch.object(SoftwareSecureBackendProvider, '_get_payload', assert_get_payload_mock):
                assert_get_payload_mock.called = False
                attempt_id = create_exam_attempt(
                    exam_id,
                    self.user.id,
                    taking_as_proctored=True
                )
                self.assertGreater(attempt_id, 0)

                # make sure we recorded the policy id at the time this was created
                attempt = get_exam_attempt_by_id(attempt_id)
                self.assertEqual(attempt['review_policy_id'], policy.id)
                self.assertTrue(assert_get_payload_mock.called)

    def test_attempt_with_no_review_policy(self):
        """
        Create an unstarted proctoring attempt with no review policy associated with it.
        """

        test_self = self        # So that we can access test methods in nested function.

        def assert_get_payload_mock_no_policy(self, exam, context):
            """
            Add a mock shim so we can assert that the _get_payload has been called with the right
            review policy
            """
            assert_get_payload_mock_no_policy.called = True

            test_self.assertNotIn('review_policy', context)

            # call into real implementation
            # pylint: disable=too-many-function-args
            result = software_secure_get_payload(self, exam, context)

            # assert that we use the default that is defined in system configuration
            test_self.assertEqual(result['reviewerNotes'], constants.DEFAULT_SOFTWARE_SECURE_REVIEW_POLICY)

            # the check that if a colon was passed in for the exam name, then the colon was changed to
            # a dash. This is because SoftwareSecure cannot handle a colon in the exam name
            for illegal_char in SOFTWARE_SECURE_INVALID_CHARS:
                if illegal_char in exam['exam_name']:
                    test_self.assertNotIn(illegal_char, result['examName'])
                    test_self.assertIn('_', result['examName'])

            return result

        for illegal_char in SOFTWARE_SECURE_INVALID_CHARS:
            exam_id = create_exam(
                course_id='foo/bar/baz',
                content_id=f'content with {illegal_char}',
                exam_name=f'Sample Exam with {illegal_char} character',
                time_limit_mins=10,
                is_proctored=True,
                backend='software_secure',
            )

            with HTTMock(mock_response_content):
                # patch the _get_payload method on the backend provider
                # so that we can assert that we are called with the review policy
                # undefined and that we use the system default
                with patch.object(SoftwareSecureBackendProvider, '_get_payload', assert_get_payload_mock_no_policy):
                    assert_get_payload_mock_no_policy.called = False
                    attempt_id = create_exam_attempt(
                        exam_id,
                        self.user.id,
                        taking_as_proctored=True
                    )
                    self.assertGreater(attempt_id, 0)

                    # make sure we recorded that there is no review policy
                    attempt = get_exam_attempt_by_id(attempt_id)
                    self.assertIsNone(attempt['review_policy_id'])
                    self.assertTrue(assert_get_payload_mock_no_policy.called)

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
            except UnicodeEncodeError:      # pragma: no cover (only run if test fails)
                return False

        test_self = self        # So that we can access test methods in nested function.

        def assert_get_payload_mock_unicode_characters(self, exam, context):
            """
            Add a mock so we can assert that the _get_payload call removes unicode characters.
            """
            assert_get_payload_mock_unicode_characters.called = True

            # call into real implementation
            # pylint: disable=too-many-function-args
            result = software_secure_get_payload(self, exam, context)
            test_self.assertTrue(is_ascii(result['examName']))
            test_self.assertGreater(len(result['examName']), 0)
            return result

        with HTTMock(mock_response_content):

            exam_id = create_exam(
                course_id='foo/bar/baz',
                content_id='content with unicode characters',
                exam_name='Klüft skräms inför på fédéral électoral große',
                time_limit_mins=10,
                is_proctored=True,
                backend='software_secure',
            )

            # patch the _get_payload method on the backend provider
            with patch.object(SoftwareSecureBackendProvider, '_get_payload',
                              assert_get_payload_mock_unicode_characters):
                assert_get_payload_mock_unicode_characters.called = False
                attempt_id = create_exam_attempt(
                    exam_id,
                    self.user.id,
                    taking_as_proctored=True
                )
                self.assertGreater(attempt_id, 0)
                self.assertTrue(assert_get_payload_mock_unicode_characters.called)

            # now try with an eastern language (Chinese)
            exam_id = create_exam(
                course_id='foo/bar/baz',
                content_id='content with chinese characters',
                exam_name='到处群魔乱舞',
                time_limit_mins=10,
                is_proctored=True,
                backend='software_secure',
            )

            # patch the _get_payload method on the backend provider
            with patch.object(SoftwareSecureBackendProvider, '_get_payload',
                              assert_get_payload_mock_unicode_characters):
                assert_get_payload_mock_unicode_characters.called = False
                attempt_id = create_exam_attempt(
                    exam_id,
                    self.user.id,
                    taking_as_proctored=True
                )
                self.assertGreater(attempt_id, 0)
                self.assertTrue(assert_get_payload_mock_unicode_characters.called)

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
            is_proctored=True,
            backend='software_secure',
        )

        with HTTMock(mock_response_content):
            attempt_id = create_exam_attempt(exam_id, self.user.id, taking_as_proctored=True)
            self.assertIsNotNone(attempt_id)

    def test_full_name_without_credit_service(self):
        """
        Tests to make sure split doesn't raises AttributeError if credit service is down.
        """

        set_runtime_service('credit', MockCreditServiceNone())

        exam_id = create_exam(
            course_id='foo/bar/baz',
            content_id='content',
            exam_name='Sample Exam',
            time_limit_mins=10,
            is_proctored=True,
            backend='software_secure',
        )

        with HTTMock(mock_response_content):
            attempt_id = create_exam_attempt(exam_id, self.user.id, taking_as_proctored=True)
            self.assertIsNotNone(attempt_id)

    def test_unicode_attempt(self):
        """
        Tests to make sure we can handle an attempt when a user's fullname has unicode characters in it
        """

        set_runtime_service('credit', MockCreditService(profile_fullname='अआईउऊऋऌ अआईउऊऋऌ'))

        exam_id = create_exam(
            course_id='foo/bar/baz',
            content_id='content',
            exam_name='Sample Exam',
            time_limit_mins=10,
            is_proctored=True,
            backend='software_secure',
        )

        with HTTMock(mock_response_content):
            attempt_id = create_exam_attempt(exam_id, self.user.id, taking_as_proctored=True)
            self.assertIsNotNone(attempt_id)

        # try unicode exam name, also
        exam_id = create_exam(
            course_id='foo/bar/baz',
            content_id='content_unicode_name',
            exam_name='अआईउऊऋऌ अआईउऊऋऌ',
            time_limit_mins=10,
            is_proctored=True,
            backend='software_secure',
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
            is_proctored=True,
            backend='software_secure',
        )

        # now try a failing request
        with HTTMock(mock_response_error):
            with self.assertRaises(BackendProviderCannotRegisterAttempt):
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
        self.assertIn(b'false', body)
        self.assertIn(b'null', body)

        body = provider._body_string({  # pylint: disable=protected-access
            'foo': ['first', {'here': 'yes'}]
        })
        self.assertIn(b'first', body)
        self.assertIn(b'here', body)
        self.assertIn(b'yes', body)

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

    def test_mark_erroneous_proctored_exam(self):
        """
        Test that SoftwareSecure's implementation returns None, because there is no
        work that needs to happen right now
        """

        provider = get_backend_provider()
        self.assertIsNone(provider.mark_erroneous_exam_attempt(None, None))

    @ddt.data(
        ['boop-be-boop-bop-bop', False],
        [False, True],
    )
    @ddt.unpack
    @patch('edx_proctoring.backends.software_secure.get_current_request')
    def test_should_block_access_to_exam_material(
            self,
            cookie_present,
            resultant_boolean,
            mocked_get_current_request
    ):
        """
        Test that conditions applied for blocking user from accessing
        course content are correct
        """
        provider = get_backend_provider()
        mocked_get_current_request.return_value.get_signed_cookie.return_value = cookie_present
        assert bool(provider.should_block_access_to_exam_material()) == resultant_boolean

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

        (first_name, last_name) = provider._split_fullname('अआईउऊऋऌ अआईउऊऋऌ')
        self.assertEqual(first_name, 'अआईउऊऋऌ')
        self.assertEqual(last_name, 'अआईउऊऋऌ')
