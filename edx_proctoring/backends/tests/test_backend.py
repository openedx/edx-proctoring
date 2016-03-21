"""
Tests for backend.py
"""
from django.test import TestCase
from django.conf import settings

from edx_proctoring.backends.backend import ProctoringBackendProvider
from edx_proctoring.backends.null import NullBackendProvider
from edx_proctoring.exceptions import ProctoredExamSuspiciousLookup
from edx_proctoring.utils import locate_attempt_by_attempt_code


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
        external_id = payload['examMetaData']['ssiRecordLocator']
        attempt_code = payload['examMetaData']['examCode']

        attempt_obj = locate_attempt_by_attempt_code(attempt_code)
        match = (
            attempt_obj[0].external_id.lower() == external_id.lower() or
            settings.PROCTORING_SETTINGS.get('ALLOW_CALLBACK_SIMULATION', False)
        )
        if not match:
            err_msg = (
                'Found attempt_code {attempt_code}, but the recorded external_id did not '
                'match the ssiRecordLocator that had been recorded previously. Has {existing} '
                'but received {received}!'.format(
                    attempt_code=attempt_code,
                    existing=attempt_obj[0].external_id,
                    received=external_id
                )
            )
            raise ProctoredExamSuspiciousLookup(err_msg)

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
