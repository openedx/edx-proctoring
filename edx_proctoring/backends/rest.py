"""
Base implementation of a REST backend, following the API documented in
docs/backends.rst
"""
import pkg_resources
from edx_proctoring.backends.backend import ProctoringBackendProvider
from edx_proctoring.models import ProctoredExamStudentAttemptStatus
from edx_rest_api_client.client import OAuthAPIClient


class BaseRestProctoringProvider(ProctoringBackendProvider):
    """
    Base class for official REST API proctoring service.
    Subclasses must override base_url and may override the other url
    properties
    """
    base_url = None
    expiration_time = 86400 * 2
    needs_oauth = True

    @property
    def exam_attempt_url(self):
        "Returns exam attempt url"
        return self.base_url + u'/v1/exam/{exam_id}/attempt/{attempt_id}/'

    @property
    def create_exam_attempt_url(self):
        "Returns the create exam url"
        return self.base_url + u'/v1/exam/{exam_id}/attempt/'

    @property
    def create_exam_url(self):
        "Returns create exam url"
        return self.base_url + u'/v1/exam/'

    @property
    def exam_url(self):
        "Returns exam url"
        return self.base_url + u'/v1/exam/{exam_id}/'

    @property
    def config_url(self):
        "Returns proctor config url"
        return self.base_url + u'/v1/config/'

    def __init__(self, client_id=None, client_secret=None, **kwargs):
        """
        Initialize REST backend.
        client_id: provided by backend service
        client_secret: provided by backend service
        """
        ProctoringBackendProvider.__init__(self)
        self.client_id = client_id
        self.client_secret = client_secret
        self.default_config = None
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.session = OAuthAPIClient(self.base_url, self.client_id, self.client_secret)

    def get_javascript(self):
        """
        Returns the backend javascript to embed on each proctoring page
        """
        package = self.__class__.__module__.split('.')[0]
        return pkg_resources.resource_string(package, 'backend.js')

    def get_software_download_url(self):
        """
        Returns the URL that the user needs to go to in order to download
        the corresponding desktop software
        """
        return self.get_proctoring_config().get('download_url', None)

    def get_proctoring_config(self):
        """
        Returns the metadata and configuration options for the proctoring service
        """
        url = self.config_url
        response = self.session.get(url).json()
        return response

    def get_exam(self, exam):
        """
        Returns the exam metadata stored by the proctoring service
        """
        url = self.exam_url.format(exam_id=exam['id'])
        response = self.session.get(url).json()
        return response

    def get_attempt(self, attempt):
        """
        Returns the attempt object from the backend
        """
        response = self._make_attempt_request(
            attempt['proctored_exam']['external_id'],
            attempt['external_id'],
            method='GET')
        return response

    def register_exam_attempt(self, exam, context):
        """
        Called when the exam attempt has been created but not started
        """
        url = self.create_exam_attempt_url.format(exam_id=exam['external_id'])
        payload = context
        payload['status'] = 'created'
        response = self.session.post(url, json=payload).json()
        return response['id']

    def start_exam_attempt(self, exam, attempt):
        """
        Method that is responsible for communicating with the backend provider
        to establish a new proctored exam
        """
        response = self._make_attempt_request(
            exam,
            attempt,
            status=ProctoredExamStudentAttemptStatus.started,
            method='PATCH')
        return response.get('status')

    def stop_exam_attempt(self, exam, attempt):
        """
        Method that is responsible for communicating with the backend provider
        to finish a proctored exam
        """
        response = self._make_attempt_request(
            exam,
            attempt,
            status=ProctoredExamStudentAttemptStatus.submitted,
            method='PATCH')
        return response.get('status')

    def on_review_callback(self, attempt, payload):
        """
        Called when the reviewing 3rd party service posts back the results
        """
        # REST backends should convert the payload into the expected data structure
        return payload

    def on_exam_saved(self, exam):
        """
        Called after an exam is saved.
        """
        if 'config' not in exam and self.default_config:
            # allows the platform to define a default configuration
            exam['config'] = self.default_config
        external_id = exam.get('external_id', None)
        if external_id:
            url = self.exam_url.format(exam_id=external_id)
        else:
            url = self.create_exam_url
        response = self.session.post(url, json=exam).json()
        return response.get('id')

    def _make_attempt_request(self, exam, attempt, method='POST', status=None, **payload):
        """
        Calls backend attempt API
        """
        if status:
            payload['status'] = status
        else:
            payload = None
        url = self.exam_attempt_url.format(exam_id=exam, attempt_id=attempt)
        response = self.session.request(method, url, json=payload).json()
        return response
