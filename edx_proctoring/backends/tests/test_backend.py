"""
Tests for backend.py
"""

from __future__ import absolute_import

import time
from mock import patch

from django.test import TestCase

from edx_proctoring.backends.backend import ProctoringBackendProvider
from edx_proctoring.backends.null import NullBackendProvider
from edx_proctoring.backends.mock import MockProctoringBackendProvider

# pragma pylint: disable=useless-super-delegation


class TestBackendProvider(ProctoringBackendProvider):
    """
    Implementation of the ProctoringBackendProvider that does nothing
    """

    def register_exam_attempt(self, exam, context):
        """
        Called when the exam attempt has been created but not started
        """
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

    def get_software_download_url(self):
        """
        Returns the URL that the user needs to go to in order to download
        the corresponding desktop software
        """
        return None

    def on_review_callback(self, payload):
        """
        Called when the reviewing 3rd party service posts back the results
        """

    def on_review_saved(self, review):
        """
        called when a review has been save - either through API or via Django Admin panel
        in order to trigger any workflow
        """


class PassthroughBackendProvider(ProctoringBackendProvider):
    """
    Implementation of the ProctoringBackendProvider that just calls the base class
    """

    def register_exam_attempt(self, exam, context):
        """
        Called when the exam attempt has been created but not started
        """
        return super(PassthroughBackendProvider, self).register_exam_attempt(
            exam,
            context
        )

    def start_exam_attempt(self, exam, attempt):
        """
        Method that is responsible for communicating with the backend provider
        to establish a new proctored exam
        """
        return super(PassthroughBackendProvider, self).start_exam_attempt(
            exam,
            attempt
        )

    def stop_exam_attempt(self, exam, attempt):
        """
        Method that is responsible for communicating with the backend provider
        to establish a new proctored exam
        """
        return super(PassthroughBackendProvider, self).stop_exam_attempt(
            exam,
            attempt
        )

    def get_software_download_url(self):
        """
        Returns the URL that the user needs to go to in order to download
        the corresponding desktop software
        """
        return super(PassthroughBackendProvider, self).get_software_download_url()

    def on_review_callback(self, payload):
        """
        Called when the reviewing 3rd party service posts back the results
        """
        return super(PassthroughBackendProvider, self).on_review_callback(payload)

    def on_review_saved(self, review):
        """
        called when a review has been save - either through API or via Django Admin panel
        in order to trigger any workflow
        """
        return super(PassthroughBackendProvider, self).on_review_saved(review)


class TestBackends(TestCase):
    """
    Miscelaneous tests for backends.py
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
            provider.on_review_callback(None)

        with self.assertRaises(NotImplementedError):
            provider.on_review_saved(None)

    def test_null_provider(self):
        """
        Assert that the Null provider does nothing
        """

        provider = NullBackendProvider()

        self.assertIsNone(provider.register_exam_attempt(None, None))
        self.assertIsNone(provider.start_exam_attempt(None, None))
        self.assertIsNone(provider.stop_exam_attempt(None, None))
        self.assertIsNone(provider.get_software_download_url())
        self.assertIsNone(provider.on_review_callback(None))
        self.assertIsNone(provider.on_review_saved(None))

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
        self.assertIsNone(provider.on_review_callback(None))
        self.assertIsNone(provider.on_review_saved(None))
