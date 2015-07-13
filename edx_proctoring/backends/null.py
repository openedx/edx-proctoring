"""
Implementation of a backend provider, which does nothing
"""

from edx_proctoring.backends.backend import ProctoringBackendProvider


class NullBackendProvider(ProctoringBackendProvider):
    """
    Implementation of the ProctoringBackendProvider that does nothing
    """

    def register_exam_attempt(self, exam, time_limit_mins, attempt_code,
                              is_sample_attempt, callback_url):
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
