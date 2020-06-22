"""
Implements a mock proctoring backend provider to be used for testing,
which doesn't require the setup and configuration of the Software Secure backend provider.
"""

import threading

from edx_proctoring.backends.backend import ProctoringBackendProvider
from edx_proctoring.callbacks import start_exam_callback


class MockProctoringBackendProvider(ProctoringBackendProvider):
    """
    Implementation of the ProctoringBackendProvider that bypasses proctoring setup.
    """
    verbose_name = u'Mock Backend'

    def __init__(self, *args, **kwargs):
        ProctoringBackendProvider.__init__(self)
        self.args = args
        self.kwargs = kwargs

    def register_exam_attempt(self, exam, context):
        """
        Called when the exam attempt has been created but not started

        Args
            exam (dict) - a dictionary containing information about the exam
               keys:
                 exam_name (str) - the name of the exam
                 course_id (str) - serialized course key of the course that the exam belongs to
                 id (str) - the id of the given exam
            context (dict) - a dictionary containing information about the current exam context
               keys:
                 attempt_code (str) - code that represents this current attempt
                 time_limit_mins (str) - time limit of exam in minutes
                 is_sample_attempt (bool) - True if this is a practice exam
                 callback_url (str) - url that we would like the external grader to call back to
                 full_name (str) - full name of the student taking the exam
                 review_policy (dict) - the policy for reviewing this exam
                 review_policy_exception (dict) - an exceptions that may exist for this review
                 email (str) - the email address of the student

        Returns
            string that corresponds to the backend record locator of the attempt
        """
        # Since the code expects this callback to be coming from the external software, we wait
        # to call it so that the attempt is created properly before the callback is called.
        timer = threading.Timer(1.0, start_exam_callback, args=(None, context['attempt_code']))
        timer.start()
        return context['attempt_code']

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
        return True

    def get_software_download_url(self):
        """
        Returns
            the URL that the user needs to go to in order to download
            the corresponding desktop software
        """
        return "mockurl"

    def on_review_callback(self, attempt, payload):
        """
        Called when the reviewing 3rd party service posts back the results

        Args
            payload (dict) -
                the payload from the external service - is service dependent

        Returns nothing

        Side Effects
            - updates review status
        """
        return None

    def on_exam_saved(self, exam):
        """
        Called after an exam is saved.
        """
        return None
