from requests import Session
from edx_proctoring.backends.backend import ProctoringBackendProvider
from django.conf import settings
from django.core.urlresolvers import reverse


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
        return self.base_url + '/v1/exam/{exam_id}/attempt/{attempt_id}/'

    @property
    def exam_url(self):
        return self.base_url + '/v1/exam/{exam_id}/'

    @property
    def config_url(self):
        return self.base_url + '/v1/config/'

    def __init__(self, client_id=None, client_secret=None, **kwargs):
        self.client_id = client_id
        self.client_secret = client_secret
        for k, v in kwargs:
            setattr(self, k, v)
        self.session = Session()
        self.session.auth = (self.client_id, self.client_secret)

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

    def get_exam_instructions(self, attempt):
        exam = self.get_exam(attempt['proctored_exam'])
        return exam.get('instructions', {})

    def register_exam_attempt(self, exam, context):
        """
        Called when the exam attempt has been created but not started
        """
        attempt_id = context['attempt_code']
        callback_url = reverse('edx_proctoring.proctored_exam.attempt.callback', args=[attempt_id])
        user_id = context['user_id']
        response = self._make_attempt_request(
                                            exam['id'],
                                            attempt_id,
                                            'created',
                                            callback_url=callback_url,
                                            user_id=user_id)
        return response['id']

    def start_exam_attempt(self, exam, attempt):
        """
        Method that is responsible for communicating with the backend provider
        to establish a new proctored exam
        """
        response = self._make_attempt_request(exam['id'], attempt, 'start', method='PATCH')
        return response['status']

    def stop_exam_attempt(self, exam, attempt):
        """
        Method that is responsible for communicating with the backend provider
        to establish a new proctored exam
        """
        response = self._make_attempt_request(exam['id'], attempt, 'stop', method='PATCH')
        return response['status']

    def on_review_callback(self, attempt, payload):
        """
        Called when the reviewing 3rd party service posts back the results
        """
        jwt.decode(payload['token'], audience=attempt['attempt_code'], key=settings.SECRET_KEY)

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
        url = self.exam_url.format(exam_id=exam['id'])
        response = self.session.post(url, json=exam).json()
        return response

    def _make_attempt_request(self, exam, attempt, status, method='POST', **payload):
        payload['status'] = status
        payload['callback_token'] = self._get_callback_token(attempt)
        url = self.exam_attempt_url.format(exam_id=exam, attempt_id=attempt)
        response = self.session.request(method, url, json=payload).json()
        return response

    def _get_callback_token(self, attempt_code):
        return self._get_token(settings.SECRET_KEY, audience=attempt_code)

    def _get_token(self, secret, audience=None, **kwargs):
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

