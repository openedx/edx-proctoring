"""
Base implementation of a REST backend, following the API documented in
docs/backends.rst
"""
import logging
import time
import uuid
import pkg_resources
from edx_proctoring.backends.backend import ProctoringBackendProvider
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus
from edx_rest_api_client.client import OAuthAPIClient

import jwt

log = logging.getLogger(__name__)


class BaseRestProctoringProvider(ProctoringBackendProvider):
    """
    Base class for official REST API proctoring service.
    Subclasses must override base_url and may override the other url
    properties
    """
    base_url = None
    token_expiration_time = 60
    needs_oauth = True

    @property
    def exam_attempt_url(self):
        "Returns exam attempt url"
        return self.base_url + u'/api/v1/exam/{exam_id}/attempt/{attempt_id}/'

    @property
    def create_exam_attempt_url(self):
        "Returns the create exam url"
        return self.base_url + u'/api/v1/exam/{exam_id}/attempt/'

    @property
    def create_exam_url(self):
        "Returns create exam url"
        return self.base_url + u'/api/v1/exam/'

    @property
    def exam_url(self):
        "Returns exam url"
        return self.base_url + u'/api/v1/exam/{exam_id}/'

    @property
    def config_url(self):
        "Returns proctor config url"
        return self.base_url + u'/api/v1/config/'

    @property
    def instructor_url(self):
        "Returns the instructor dashboard url"
        return self.base_url + u'/api/v1/instructor/{client_id}/?jwt={jwt}'

    def __init__(self, client_id=None, client_secret=None, **kwargs):
        """
        Initialize REST backend.
        client_id: provided by backend service
        client_secret: provided by backend service
        """
        ProctoringBackendProvider.__init__(self)
        self.client_id = client_id
        self.client_secret = client_secret
        self.default_rules = None
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
        log.debug('Requesting config from %s', url)
        response = self.session.get(url).json()
        return response

    def get_exam(self, exam):
        """
        Returns the exam metadata stored by the proctoring service
        """
        url = self.exam_url.format(exam_id=exam['id'])
        log.debug('Requesting exam from %s', url)
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
        log.debug('Creating exam attempt for %s at %s', exam['external_id'], url)
        response = self.session.post(url, json=payload)
        response = response.json()
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
        if self.default_rules and not exam.get('rules', None):
            # allows the platform to define a default configuration
            exam['rules'] = self.default_rules
        external_id = exam.get('external_id', None)
        if external_id:
            url = self.exam_url.format(exam_id=external_id)
        else:
            url = self.create_exam_url
        log.debug('Saving exam to %s', url)
        try:
            response = self.session.post(url, json=exam)
            data = response.json()
        except Exception:  # pylint: disable=broad-except
            log.exception('saving exam. %s', response.content)
            data = {}
        return data.get('id')

    def get_instructor_url(self, course_id, user, exam_id=None, attempt_id=None):
        """
        Return a URL to the instructor dashboard
        course_id: str
        user: dict of {id, full_name, email}
        exam_id: str optional exam external id
        attempt_id: str optional exam attempt external id
        """
        exp = time.time() + self.token_expiration_time
        token = {
            'course_id': course_id,
            'user': user,
            'iss': self.client_id,
            'jti': uuid.uuid4().hex,
            'exp': exp
        }
        if exam_id:
            token['exam_id'] = exam_id
            if attempt_id:
                token['attempt_id'] = attempt_id
        encoded = jwt.encode(token, self.client_secret)
        url = self.instructor_url.format(client_id=self.client_id, jwt=encoded)
        log.debug('Created instructor url for %s %s %s', course_id, exam_id, attempt_id)
        return url

    def _make_attempt_request(self, exam, attempt, method='POST', status=None, **payload):
        """
        Calls backend attempt API
        """
        if status:
            payload['status'] = status
        else:
            payload = None
        url = self.exam_attempt_url.format(exam_id=exam, attempt_id=attempt)
        log.debug('Making %s attempt request at %s', method, url)
        response = self.session.request(method, url, json=payload).json()
        return response
