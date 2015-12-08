"""
Implementation of a backend provider, which does nothing
"""

from edx_proctoring.backends.backend import ProctoringBackendProvider


class NullBackendProvider(ProctoringBackendProvider):
    """
    Implementation of the ProctoringBackendProvider that does nothing
    """

    def register_exam_attempt(self, exam, context):
        """
        Called when the exam attempt has been created but not started
        """
        return None

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
