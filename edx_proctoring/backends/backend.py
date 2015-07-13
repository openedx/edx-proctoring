"""
Defines the abstract base class that all backends should derive from
"""

import abc


class ProctoringBackendProvider(object):
    """
    The base abstract class for all proctoring service providers
    """

    # don't allow instantiation of this class, it must be subclassed
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def register_exam_attempt(self, exam, time_limit_mins, attempt_code,
                              is_sample_attempt, callback_url):
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
