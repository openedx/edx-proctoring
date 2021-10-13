"""
Tests for backend.py
"""

import time

from mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase

from edx_proctoring.backends import get_backend_provider
from edx_proctoring.backends.backend import ProctoringBackendProvider
from edx_proctoring.backends.mock import MockProctoringBackendProvider
from edx_proctoring.backends.null import NullBackendProvider
from edx_proctoring.exceptions import (
    BackendProviderCannotRetireUser,
    BackendProviderOnboardingException,
    BackendProviderSentNoAttemptID
)

# pragma pylint: disable=useless-super-delegation


class TestBackendProvider(ProctoringBackendProvider):
    """
    Implementation of the ProctoringBackendProvider that does nothing
    """
    last_exam = None
    has_dashboard = True
    supports_onboarding = True

    last_retire_user = None
    attempt_error = None
    last_attempt_remove = None
    no_attempt_id_error = None

    def register_exam_attempt(self, exam, context):
        """
        Called when the exam attempt has been created but not started
        """
        if self.attempt_error:
            raise BackendProviderOnboardingException(self.attempt_error)
        if self.no_attempt_id_error:
            raise BackendProviderSentNoAttemptID(self.no_attempt_id_error, http_status=200)
        return 'testexternalid'

    def start_exam_attempt(self, exam, attempt):
        """
        Method that is responsible for communicating with the backend provider
        to establish a new proctored exam
        """
        return None

    def stop_exam_attempt(self, exam, attempt):
        """
        Method that is responsible for communicating with the backend provider
        to establish a new proctored exam
        """
        return None

    def mark_erroneous_exam_attempt(self, exam, attempt):
        """
        Method that would be responsible for communicating with the
        backend provider to mark a proctored session as having
        encountered a technical error
        """
        return None

    def remove_exam_attempt(self, exam, attempt):
        self.last_attempt_remove = (exam, attempt)
        return True

    def get_software_download_url(self):
        """
        Returns the URL that the user needs to go to in order to download
        the corresponding desktop software
        """
        return None

    def on_review_callback(self, attempt, payload):
        """
        Called when the reviewing 3rd party service posts back the results
        """
        return payload

    def on_exam_saved(self, exam):
        self.last_exam = exam
        return exam.get('external_id', None) or 'externalid'

    # pylint: disable=unused-argument
    def get_instructor_url(
        self, course_id, user, exam_id=None, attempt_id=None,
        show_configuration_dashboard=False, encrypted_video_review_url=None
    ):
        "Return a fake instructor url"
        url = f'/instructor/{course_id}/'
        if exam_id:
            url += f'?exam={exam_id}'
            if attempt_id:
                url += f'&attempt={attempt_id}'

        if show_configuration_dashboard:
            url += '&config=true'

        return url

    def retire_user(self, user_id):
        if self.last_retire_user:
            raise BackendProviderCannotRetireUser(user_id)
        self.last_retire_user = user_id
        return True

    def get_proctoring_config(self):
        """
        Returns the faked metadata and configuration options for the proctoring service.
        """
        return {'name': self.verbose_name}


class PassthroughBackendProvider(ProctoringBackendProvider):
    """
    Implementation of the ProctoringBackendProvider that just calls the base class
    """

    def register_exam_attempt(self, exam, context):
        """
        Called when the exam attempt has been created but not started
        """
        return super().register_exam_attempt(
            exam,
            context
        )

    def start_exam_attempt(self, exam, attempt):
        """
        Method that is responsible for communicating with the backend provider
        to establish a new proctored exam
        """
        return super().start_exam_attempt(
            exam,
            attempt
        )

    def stop_exam_attempt(self, exam, attempt):
        """
        Method that is responsible for communicating with the backend provider
        to establish a new proctored exam
        """
        return super().stop_exam_attempt(
            exam,
            attempt
        )

    def mark_erroneous_exam_attempt(self, exam, attempt):
        """
        Method that would be responsible for communicating with the
        backend provider to mark a proctored session as having
        encountered a technical error
        """
        return super().mark_erroneous_exam_attempt(
            exam,
            attempt
        )

    def remove_exam_attempt(self, exam, attempt):
        return super().remove_exam_attempt(
            exam,
            attempt
        )

    def get_software_download_url(self):
        """
        Returns the URL that the user needs to go to in order to download
        the corresponding desktop software
        """
        return super().get_software_download_url()

    def on_review_callback(self, attempt, payload):
        """
        Called when the reviewing 3rd party service posts back the results
        """
        return super().on_review_callback(attempt, payload)

    def on_exam_saved(self, exam):
        return super().on_exam_saved(exam)

    def get_onboarding_profile_info(self, course_id, **kwargs):
        return super().get_onboarding_profile_info(course_id, **kwargs)

    def get_video_review_aes_key(self):
        return super().get_video_review_aes_key()


class TestBackends(TestCase):
    """
    Miscellaneous tests for backends.py
    """

    def test_raises_exception(self):
        """
        Makes sure the abstract base class raises NotImplementedError
        """

        provider = PassthroughBackendProvider()

        with self.assertRaises(NotImplementedError):
            provider.register_exam_attempt(None, None)

        with self.assertRaises(NotImplementedError):
            provider.start_exam_attempt(None, None)

        with self.assertRaises(NotImplementedError):
            provider.stop_exam_attempt(None, None)

        with self.assertRaises(NotImplementedError):
            provider.get_software_download_url()

        with self.assertRaises(NotImplementedError):
            provider.on_review_callback(None, None)

        with self.assertRaises(NotImplementedError):
            provider.mark_erroneous_exam_attempt(None, None)

        with self.assertRaises(NotImplementedError):
            provider.remove_exam_attempt(None, None)

        with self.assertRaises(NotImplementedError):
            provider.on_exam_saved(None)

        self.assertIsNone(provider.get_exam(None))

        self.assertIsNone(provider.get_onboarding_profile_info(course_id='test'))

        self.assertIsNone(provider.get_proctoring_config())

        self.assertIsNone(provider.get_video_review_aes_key())

    def test_null_provider(self):
        """
        Assert that the Null provider does nothing
        """

        provider = NullBackendProvider()

        self.assertIsNone(provider.register_exam_attempt(None, None))
        self.assertIsNone(provider.start_exam_attempt(None, None))
        self.assertIsNone(provider.stop_exam_attempt(None, None))
        self.assertIsNone(provider.mark_erroneous_exam_attempt(None, None))
        self.assertIsNone(provider.get_software_download_url())
        self.assertIsNone(provider.on_review_callback(None, None))
        self.assertIsNone(provider.on_exam_saved(None))

    def test_mock_provider(self):
        """
        Test that the mock backend provider does what we expect it to do.
        """
        provider = MockProctoringBackendProvider()
        attempt_code = "test_code"
        with patch('edx_proctoring.backends.mock.start_exam_callback') as exam_callback_mock:
            exam_callback_mock.return_value = '5'
            self.assertEqual(
                attempt_code,
                provider.register_exam_attempt(None, {'attempt_code': attempt_code})
            )
            # Wait for the thread to run.
            time.sleep(2)
            self.assertTrue(exam_callback_mock.called)

        self.assertEqual(
            "mockurl",
            provider.get_software_download_url()
        )
        self.assertIsNone(provider.start_exam_attempt(None, None))
        self.assertIsNone(provider.stop_exam_attempt(None, None))
        self.assertIsNone(provider.mark_erroneous_exam_attempt(None, None))
        self.assertIsNone(provider.on_review_callback(None, None))
        self.assertIsNone(provider.on_exam_saved(None))

    @patch('logging.Logger.exception')
    @patch('edx_proctoring.callbacks.get_exam_attempt_by_code')
    @patch('edx_proctoring.callbacks.update_attempt_status')
    def test_mock_provider_exception(self, _, get_attempt_mock, logger_mock):
        """
        Test that the mock backend provider logs exception
        """
        provider = MockProctoringBackendProvider()

        attempt_code = 'test_code'

        get_attempt_mock.return_value = {
            'status': 'submitted',
            'attempt_code': attempt_code,
            'id': 1,
            'proctored_exam': {'course_id': '', 'content_id': ''}
        }
        provider.register_exam_attempt(None, {'attempt_code': attempt_code})
        time.sleep(2)

        self.assertTrue(get_attempt_mock.called)

        log_format_string = ("BLOCKING ERROR: Can't find course info url for course_id=%s")
        logger_mock.assert_any_call(log_format_string, '')


class BackendChooserTests(TestCase):
    """
    Tests for backend configuration
    """

    def test_default_backend(self):
        """
        Test the default backend choice
        """
        backend = get_backend_provider()
        self.assertIsInstance(backend, TestBackendProvider)

    def test_get_different_backend(self):
        """
        Test that passing in a backend name returns the right backend
        """
        backend = get_backend_provider({'backend': 'null'})
        self.assertIsInstance(backend, NullBackendProvider)
        backend = get_backend_provider(name='test')
        self.assertIsInstance(backend, TestBackendProvider)

    def test_backend_choices(self):
        """
        Test that we have a list of choices
        """
        from django.apps import apps  # pylint: disable=import-outside-toplevel
        choices = list(apps.get_app_config('edx_proctoring').get_backend_choices())
        choices.sort()
        expected = [
            ('mock', 'Mock Backend'),
            ('null', 'Null Backend'),
            ('software_secure', 'RPNow'),
            ('test', 'Unknown'),
        ]
        self.assertEqual(choices, expected)

    def test_no_backend_for_timed_exams(self):
        """
        Timed exams should not return a backend, even if one has accidentally been set
        """
        exam = {
            'is_proctored': False,
            'backend': 'test'
        }
        backend = get_backend_provider(exam)
        self.assertIsNone(backend)

    def test_invalid_configurations(self):
        """
        Test that invalid backends throw the right exceptions
        """
        with self.assertRaises(NotImplementedError):
            get_backend_provider({'backend': 'foo'})
        with patch('django.conf.settings.PROCTORING_BACKENDS', {}):
            with self.assertRaises(ImproperlyConfigured):
                get_backend_provider()
        with patch('django.conf.settings.PROCTORING_BACKENDS', {'test': {}}):
            with self.assertRaises(ImproperlyConfigured):
                get_backend_provider({'backend': None})
