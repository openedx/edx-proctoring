"""
Base implementation of a REST backend, following the API documented in
docs/backends.rst
"""

import logging
import time
import uuid
import warnings
from urllib.parse import urlencode, urlparse  # pylint: disable=import-error, wrong-import-order

import jwt
from edx_rest_api_client.client import OAuthAPIClient
from webpack_loader.exceptions import BaseWebpackLoaderException, WebpackBundleLookupError
from webpack_loader.utils import get_files

from django.conf import settings

from edx_proctoring.backends.backend import ProctoringBackendProvider
from edx_proctoring.exceptions import (
    BackendProviderCannotRegisterAttempt,
    BackendProviderCannotRetireUser,
    BackendProviderOnboardingException,
    BackendProviderOnboardingProfilesException,
    BackendProviderSentNoAttemptID
)
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus, SoftwareSecureReviewStatus

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
    has_dashboard = True
    supports_onboarding = True
    passing_statuses = (SoftwareSecureReviewStatus.clean,)

    @property
    def exam_attempt_url(self):
        "Returns exam attempt url"
        return self.base_url + '/api/v1/exam/{exam_id}/attempt/{attempt_id}/'

    @property
    def create_exam_attempt_url(self):
        "Returns the create exam url"
        return self.base_url + '/api/v1/exam/{exam_id}/attempt/'

    @property
    def create_exam_url(self):
        "Returns create exam url"
        return self.base_url + '/api/v1/exam/'

    @property
    def exam_url(self):
        "Returns exam url"
        return self.base_url + '/api/v1/exam/{exam_id}/'

    @property
    def config_url(self):
        "Returns proctor config url"
        return self.base_url + '/api/v1/config/'

    @property
    def instructor_url(self):
        "Returns the instructor dashboard url"
        return self.base_url + '/api/v1/instructor/{client_id}/?jwt={jwt}'

    @property
    def user_info_url(self):
        "Returns the user info url"
        return self.base_url + '/api/v1/user/{user_id}/'

    @property
    def onboarding_statuses_url(self):
        "Returns the onboarding statuses url"
        return self.base_url + '/api/v1/courses/{course_id}/onboarding_statuses'

    @property
    def proctoring_instructions(self):
        "Returns the (optional) proctoring instructions"
        return []

    def __init__(self, client_id=None, client_secret=None, **kwargs):
        """
        Initialize REST backend.
        client_id: provided by backend service
        client_secret: provided by backend service
        """
        self.default_rules = None
        super().__init__(**kwargs)
        self.client_id = client_id
        self.client_secret = client_secret
        self.session = OAuthAPIClient(self.base_url, self.client_id, self.client_secret)

    def get_javascript(self):
        """
        Returns the url of the javascript bundle into which the provider's JS will be loaded
        """
        # use the defined npm_module name, or else the python package name
        package = getattr(self, 'npm_module', self.__class__.__module__.split('.', maxsplit=1)[0])
        js_url = ''
        try:
            bundle_chunks = get_files(package, config="WORKERS")
            # still necessary to check, since webpack_loader can be
            # configured to ignore all matching packages
            if bundle_chunks:
                js_url = bundle_chunks[0]["url"]

        except WebpackBundleLookupError:
            warnings.warn(
                f'Could not find webpack bundle for proctoring backend {package}.'
                ' Check whether webpack is configured to build such a bundle'
            )
        except BaseWebpackLoaderException:
            warnings.warn(
                f'Could not find webpack bundle for proctoring backend {package}.'
            )
        except IOError as err:
            warnings.warn(
                f'Webpack stats file corresponding to WebWorkers not found: {str(err)}'
            )

        # if the Javascript URL is not an absolute URL (i.e. doesn't have a scheme), prepend
        # the LMS Root URL to it, if it is defined, to make it an absolute URL
        if not urlparse(js_url).scheme:
            if hasattr(settings, 'LMS_ROOT_URL'):
                js_url = settings.LMS_ROOT_URL + js_url

        return js_url

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
        log.debug('Requesting config from %r', url)
        response = self.session.get(url, headers=self._get_language_headers()).json()
        return response

    def get_exam(self, exam):
        """
        Returns the exam metadata stored by the proctoring service
        """
        url = self.exam_url.format(exam_id=exam['id'])
        log.debug('Requesting exam from %r', url)
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
        # If the class has instructions defined, use them.
        # Otherwise, the instructions should be returned by this
        # API request. Subclasses should wrap each instruction with gettext
        response['instructions'] = self.proctoring_instructions or response.get('instructions', [])
        return response

    def register_exam_attempt(self, exam, context):
        """
        Called when the exam attempt has been created but not started
        """
        url = self.create_exam_attempt_url.format(exam_id=exam['external_id'])
        payload = context
        payload['status'] = 'created'
        # attempt code isn't needed in this API
        payload.pop('attempt_code', False)
        log.debug(
            'Creating exam attempt for exam_id=%(exam_id)i (external_id=%(external_id)s) at %(url)s',
            {'exam_id': exam['id'], 'external_id': exam['external_id'], 'url': url}
        )
        response = self.session.post(url, json=payload)
        if response.status_code != 200:
            raise BackendProviderCannotRegisterAttempt(response.content, response.status_code)
        status_code = response.status_code
        response = response.json()
        log.debug(response)
        onboarding_status = response.get('status', None)
        if onboarding_status in ProctoredExamStudentAttemptStatus.onboarding_errors:
            raise BackendProviderOnboardingException(onboarding_status)
        attempt_id = response.get('id', None)
        if not attempt_id:
            raise BackendProviderSentNoAttemptID(response, status_code)
        return attempt_id

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

    def remove_exam_attempt(self, exam, attempt):
        """
        Removes the exam attempt on the backend provider's server
        """
        response = self._make_attempt_request(
            exam,
            attempt,
            method='DELETE')
        return response.get('status', None) == 'deleted'

    def mark_erroneous_exam_attempt(self, exam, attempt):
        """
        Method that is responsible for communicating with the backend provider
        to mark an unfinished exam to be in error
        """
        response = self._make_attempt_request(
            exam,
            attempt,
            status=ProctoredExamStudentAttemptStatus.error,
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
        log.info(
            'Saving exam_id=%(exam_id)i to %(url)s',
            {'exam_id': exam['id'], 'url': url}
        )
        response = None
        try:
            response = self.session.post(url, json=exam)
            data = response.json()
        except Exception as exc:  # pylint: disable=broad-except
            if response:
                # pylint: disable=no-member
                if hasattr(exc, 'response') and exc.response is not None:
                    content = exc.response.content
                else:
                    content = response.content
            else:
                content = None
            log.exception(
                'Failed to save exam_id=%(exam_id)i to %(url)s. Response: %(content)s',
                {'exam_id': exam['id'], 'url': url, 'content': content}
            )
            data = {}
        return data.get('id')

    def get_instructor_url(
        self, course_id, user, exam_id=None, attempt_id=None,
        show_configuration_dashboard=False, encrypted_video_review_url=None
    ):
        """
        Return a URL to the instructor dashboard
        course_id: str
        user: dict of {id, full_name, email} for the instructor or reviewer
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
            if show_configuration_dashboard:
                token['config'] = True
            if attempt_id:
                token['attempt_id'] = attempt_id
        encoded = jwt.encode(token, self.client_secret)
        url = self.instructor_url.format(client_id=self.client_id, jwt=encoded)

        log.debug(
            ('Created instructor url for course_id=%(course_id)s exam_id=%(exam_id)i '
             'attempt_id=%(attempt_id)s'),
            {'course_id': course_id, 'exam_id': exam_id, 'attempt_id': attempt_id}
        )
        return url

    def retire_user(self, user_id):
        url = self.user_info_url.format(user_id=user_id)
        try:
            response = self.session.delete(url)
            data = response.json()
            assert data in (True, False)
        except Exception as exc:  # pylint: disable=broad-except
            # pylint: disable=no-member
            if hasattr(exc, 'response') and exc.response is not None:
                content = exc.response.content
            else:
                content = response.content
            raise BackendProviderCannotRetireUser(content) from exc
        return data

    def get_onboarding_profile_info(self, course_id, **kwargs):
        url = self.onboarding_statuses_url.format(course_id=course_id)
        if kwargs:
            query_string = urlencode(kwargs)
            url += '?' + query_string

        response = self.session.get(url)

        if response.status_code != 200:
            raise BackendProviderOnboardingProfilesException(response.content, response.status_code)
        data = response.json()
        return data

    def _get_language_headers(self):
        """
        Returns a dictionary of the Accept-Language headers
        """
        # This import is here because developers writing backends which subclass this class
        # may want to import this module and use the other methods, without having to run in the context
        # of django settings, etc.
        from django.utils.translation import get_language  # pylint: disable=import-outside-toplevel

        current_lang = get_language()
        default_lang = settings.LANGUAGE_CODE
        lang_header = default_lang
        if current_lang and current_lang != default_lang:
            lang_header = f'{current_lang};{default_lang}'
        return {'Accept-Language': lang_header}

    def _make_attempt_request(self, exam, attempt, method='POST', status=None, **payload):
        """
        Calls backend attempt API
        """
        if not attempt:
            return {}
        if status:
            payload['status'] = status
        else:
            payload = None
        url = self.exam_attempt_url.format(exam_id=exam, attempt_id=attempt)
        headers = {}
        if method == 'GET':
            headers.update(self._get_language_headers())
        log.debug('Making %r attempt request at %r', method, url)
        response = self.session.request(method, url, json=payload, headers=headers)
        try:
            data = response.json()
        except ValueError:
            log.exception("Decoding attempt %r -> %r", attempt, response.content)
            data = {}
        return data
