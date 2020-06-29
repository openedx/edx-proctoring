"""
Defines the abstract base class that all backends should derive from
"""

import abc

from edx_proctoring import constants


class ProctoringBackendProvider(metaclass=abc.ABCMeta):
    """
    The base abstract class for all proctoring service providers
    """
    verbose_name = u'Unknown'
    ping_interval = constants.DEFAULT_DESKTOP_APPLICATION_PING_INTERVAL_SECONDS
    tech_support_email = ''
    learner_notification_from_email = ''
    tech_support_phone = ''
    # whether this backend supports an instructor review/configuration dashboard
    has_dashboard = False
    # whether practice exams map to "onboarding" exams for this backend
    supports_onboarding = False

    @abc.abstractmethod
    def register_exam_attempt(self, exam, context):
        """
        Called when the exam attempt has been created but not started
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def start_exam_attempt(self, exam, attempt):
        """
        Method that is responsible for communicating with the backend provider
        to establish a new proctored exam
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def stop_exam_attempt(self, exam, attempt):
        """
        Method that is responsible for communicating with the backend provider
        to establish a new proctored exam
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def mark_erroneous_exam_attempt(self, exam, attempt):
        """
        Method that is responsible for communicating with the backend provider
        to establish a new proctored exam
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def remove_exam_attempt(self, exam, attempt):
        """
        Method that removes the exam attempt from the backend's system
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def get_software_download_url(self):
        """
        Returns the URL that the user needs to go to in order to download
        the corresponding desktop software
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def on_review_callback(self, attempt, payload):
        """
        Called when the reviewing 3rd party service posts back the results
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def on_exam_saved(self, exam):
        """
        Called after an exam is saved.
        """
        raise NotImplementedError()

    def get_javascript(self):
        """
        Returns the backend javascript to embed on each proctoring page
        """
        return ""

    def get_exam(self, exam):
        """
        Returns the backend's representation of the exam
        Args:
            dict: our exam object
        Returns:
            dict: backend exam object
        """
        return exam

    def get_attempt(self, attempt):
        """
        Returns the backend's representation of the exam attempt
        Args:
            dict: our exam attempt object
        Returns:
            dict: backend exam attempt object
        """
        return attempt

    # pylint: disable=unused-argument
    def get_instructor_url(self, course_id, user, exam_id=None, attempt_id=None, show_configuration_dashboard=False):
        """
        Returns the instructor dashboard url for reviews
        """
        return None

    # pylint: disable=unused-argument
    def retire_user(self, user_id):
        """
        Delete the stored user in the backend.
        Returns boolean status of deletion, or None if this would be a no-op
        """
        return None

    def should_block_access_to_exam_material(self):
        """
        Whether learner access to exam content should be blocked during the exam
        """
        return False
