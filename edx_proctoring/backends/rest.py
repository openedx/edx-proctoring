"""
Base implementation of a REST backend, following the API documented in
docs/backends.rst
"""
import time
import jwt
import pkg_resources
from django.conf import settings
from edx_proctoring.backends.backend import ProctoringBackendProvider
from requests import Session


class BaseRestProctoringProvider(ProctoringBackendProvider):
    """
    Base class for official REST API proctoring service.
    Subclasses must override base_url and may override the other url
    properties
    """
    base_url = None
    expiration_time = 86400 * 2

    @property
    def exam_attempt_url(self):
        "Returns exam attempt url"
        return self.base_url + '/v1/exam/{exam_id}/attempt/{attempt_id}/'

    @property
    def create_exam_url(self):
        "Returns create exam url"
        return self.base_url + '/v1/exam/'

    @property
    def exam_url(self):
        "Returns exam url"
        return self.base_url + '/v1/exam/{exam_id}/'

    @property
    def config_url(self):
        "Returns proctor config url"
        return self.base_url + '/v1/config/'

    def __init__(self, client_id=None, client_secret=None, **kwargs):
        """
        Initialize REST backend.
        client_id: provided by backend service
        client_secret: provided by backend service
        """
        ProctoringBackendProvider.__init__(self)
        self.client_id = client_id
        self.client_secret = client_secret
        for key, value in kwargs:
            setattr(self, key, value)
        self.session = Session()
        self.session.auth = (self.client_id, self.client_secret)

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
            attempt['attempt_code'],
            method='GET')
        return response

    def register_exam_attempt(self, exam, context):
        """
        Called when the exam attempt has been created but not started
        """
        attempt_id = context['attempt_code']
        response = self._make_attempt_request(
            exam['external_id'],
            attempt_id,
            status='created',
            **context)
        return response['id']

    def start_exam_attempt(self, exam, attempt):
        """
        Method that is responsible for communicating with the backend provider
        to establish a new proctored exam
        """
        response = self._make_attempt_request(exam, attempt, status='start', method='PATCH')
        return response.get('status')

    def stop_exam_attempt(self, exam, attempt):
        """
        Method that is responsible for communicating with the backend provider
        to finish a proctored exam
        """
        response = self._make_attempt_request(exam, attempt, status='stop', method='PATCH')
        return response.get('status')

    def on_review_callback(self, attempt, payload):
        """
        Called when the reviewing 3rd party service posts back the results
        """
        if self.is_valid_payload(attempt['attempt_code'], payload):
            return payload
        return False

    def on_review_saved(self, review):
        """
        Called when a review has been saved - either through API or via Django Admin panel
        in order to trigger any workflow.
        """
        raise NotImplementedError()

    def on_exam_saved(self, exam):
        """
        Called after an exam is saved.
        """
        url = self.create_exam_url
        response = self.session.post(url, json=exam).json()
        return response.get('id')

    def is_valid_payload(self, attempt_code, payload):
        """
        Returns whether the payload coming back from the provider is valid.
        """
        try:
            token = payload['token']
            jwt.decode(token, key=settings.SECRET_KEY, audience=attempt_code)
            return True
        except (KeyError, jwt.DecodeError):
            return False

    def _make_attempt_request(self, exam, attempt, method='POST', status=None, **payload):
        """
        Calls backend attempt API
        """
        if status:
            payload['status'] = status
            payload['callback_token'] = self._get_callback_token(attempt)
        else:
            payload = None
        url = self.exam_attempt_url.format(exam_id=exam, attempt_id=attempt)
        response = self.session.request(method, url, json=payload).json()
        return response

    def _get_callback_token(self, attempt_code):
        """
        Creates callback token
        """
        return self._get_token(settings.SECRET_KEY, audience=attempt_code)

    def _get_token(self, secret, audience=None, **kwargs):
        """
        Creates JWT token
        """
        iss = self.client_id
        now = time.time()
        exp = now + self.expiration_time

        payload = {
            'iss': iss,
            'exp': exp,
            'iat': now,
            'aud': audience
        }
        payload.update(kwargs)
        token = jwt.encode(payload, secret)
        return token