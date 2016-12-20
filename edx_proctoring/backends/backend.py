"""
Defines the abstract base class that all backends should derive from
"""

from __future__ import absolute_import

import abc


class ProctoringBackendProvider(object):
    """
    The base abstract class for all proctoring service providers
    """

    # don't allow instantiation of this class, it must be subclassed
    __metaclass__ = abc.ABCMeta

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
    def get_software_download_url(self):
        """
        Returns the URL that the user needs to go to in order to download
        the corresponding desktop software
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def on_review_callback(self, payload):
        """
        Called when the reviewing 3rd party service posts back the results
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def on_review_saved(self, review):
        """
        called when a review has been save - either through API or via Django Admin panel
        in order to trigger any workflow.
        """
        raise NotImplementedError()
