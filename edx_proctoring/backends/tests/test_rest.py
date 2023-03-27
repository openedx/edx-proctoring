"""
Tests for the REST backend
"""

import json

import ddt
import jwt
import responses
from mock import patch

from django.test import TestCase, override_settings
from django.utils import translation

from edx_proctoring.backends.rest import BaseRestProctoringProvider
from edx_proctoring.exceptions import (
    BackendProviderCannotRegisterAttempt,
    BackendProviderCannotRetireUser,
    BackendProviderOnboardingException,
    BackendProviderOnboardingProfilesException,
    BackendProviderSentNoAttemptID
)
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus


@ddt.ddt
class RESTBackendTests(TestCase):
    """
    Tests for the REST backend
    """
    def setUp(self):
        "setup tests"
        BaseRestProctoringProvider.base_url = 'http://rr.fake'
        self.provider = BaseRestProctoringProvider('client_id', 'client_secret')
        responses.add(
            responses.POST,
            url=self.provider.base_url + '/oauth2/access_token',
            json={'access_token': 'abcd', 'expires_in': 600},
            status=200
        )
        self.backend_exam = {
            'course_id': 'course123',
            'id': 1,
            'external_id': 'abcdefg',
            'name': 'my exam',
            'is_active': True,
            'is_proctored': True,
            'is_practice': False,
        }
        self.register_exam_context = {
            'attempt_code': '2',
            'obs_user_id': 'abcdefghij',
            'full_name': 'user name',
            'lms_host': 'http://lms.com'
        }

    @responses.activate
    def test_get_software_download_url(self):
        """
        Makes sure we get the expected download url
        """
        responses.add(
            responses.GET,
            url=self.provider.config_url,
            json={'download_url': 'http://example.com'},
            status=200,
            content_type='application/json',
        )
        self.assertEqual(self.provider.get_software_download_url(), 'http://example.com')

    @responses.activate
    def test_get_proctoring_config(self):
        responses.add(
            responses.GET,
            url=self.provider.config_url,
            json={'download_url': 'http://example.com', 'config': {'allow_test': 'Allow Testing'}},
            status=200,
            content_type='application/json',
        )
        config = self.provider.get_proctoring_config()
        self.assertEqual(config['config']['allow_test'], 'Allow Testing')

    @responses.activate
    def test_get_exam(self):
        responses.add(
            responses.GET,
            url=self.provider.exam_url.format(exam_id=self.backend_exam['id']),
            json=self.backend_exam
        )
        external_exam = self.provider.get_exam(self.backend_exam)
        self.assertEqual(external_exam, self.backend_exam)

    @responses.activate
    def test_get_attempt(self):
        attempt = {
            'id': 1,
            'external_id': 'abcd',
            'proctored_exam': self.backend_exam,
            'user': 1,
            'instructions': [],
        }
        responses.add(
            responses.GET,
            url=self.provider.exam_attempt_url.format(
                exam_id=self.backend_exam['external_id'], attempt_id=attempt['external_id']),
            json=attempt
        )
        external_attempt = self.provider.get_attempt(attempt)
        self.assertEqual(external_attempt, attempt)
        self.assertEqual(responses.calls[-1].request.headers['Accept-Language'], 'en-us')

    @responses.activate
    def test_get_attempt_i18n(self):
        attempt = {
            'id': 1,
            'external_id': 'abcd',
            'proctored_exam': self.backend_exam,
            'user': 1,
            'instructions': []
        }
        responses.add(
            responses.GET,
            url=self.provider.exam_attempt_url.format(
                exam_id=self.backend_exam['external_id'], attempt_id=attempt['external_id']),
            json=attempt
        )
        with translation.override('es'):
            external_attempt = self.provider.get_attempt(attempt)
        self.assertEqual(external_attempt, attempt)
        self.assertEqual(responses.calls[-1].request.headers['Accept-Language'], 'es;en-us')

    @responses.activate
    def test_on_exam_saved(self):
        responses.add(
            responses.POST,
            url=self.provider.create_exam_url,
            json={'id': 'abcdefg'}
        )
        self.backend_exam.pop('external_id')
        external_id = self.provider.on_exam_saved(self.backend_exam)
        self.assertEqual(external_id, 'abcdefg')

    @responses.activate
    def test_create_exam_with_defaults(self):
        provider = BaseRestProctoringProvider(default_rules={'allow_grok': True})
        responses.add(
            responses.POST,
            url=self.provider.create_exam_url,
            json={'id': 'abcdefg'}
        )
        self.backend_exam.pop('external_id')
        external_id = provider.on_exam_saved(self.backend_exam)
        request = json.loads(responses.calls[-1].request.body.decode('utf-8'))
        self.assertEqual(external_id, 'abcdefg')
        self.assertTrue(request['rules']['allow_grok'])

    @responses.activate
    def test_update_exam(self):
        responses.add(
            responses.POST,
            url=self.provider.exam_url.format(exam_id=self.backend_exam['external_id']),
            json={'id': 'abcdefg'}
        )
        external_id = self.provider.on_exam_saved(self.backend_exam)
        self.assertEqual(external_id, 'abcdefg')

    @responses.activate
    def test_failed_exam_save(self):
        responses.add(
            responses.POST,
            url=self.provider.exam_url.format(exam_id=self.backend_exam['external_id']),
            body='}{bad',
        )
        external_id = self.provider.on_exam_saved(self.backend_exam)
        self.assertEqual(external_id, None)

    @responses.activate
    def test_bad_exam_save(self):
        self.backend_exam['bad'] = object()
        external_id = self.provider.on_exam_saved(self.backend_exam)
        self.assertEqual(external_id, None)

    @responses.activate
    def test_register_exam_attempt(self):
        responses.add(
            responses.POST,
            url=self.provider.create_exam_attempt_url.format(exam_id=self.backend_exam['external_id']),
            json={'id': 2},
            status=200
        )
        attempt_external_id = self.provider.register_exam_attempt(self.backend_exam, self.register_exam_context)
        request = json.loads(responses.calls[-1].request.body.decode('utf-8'))
        self.assertEqual(attempt_external_id, 2)
        self.assertEqual(request['status'], 'created')
        self.assertIn('lms_host', request)
        self.assertIn('full_name', request)

    @responses.activate
    def test_register_exam_attempt_failure(self):
        responses.add(
            responses.POST,
            url=self.provider.create_exam_attempt_url.format(exam_id=self.backend_exam['external_id']),
            json={'error': 'something'},
            status=400
        )
        with self.assertRaises(BackendProviderCannotRegisterAttempt):
            self.provider.register_exam_attempt(self.backend_exam, self.register_exam_context)

    @ddt.data(
        *ProctoredExamStudentAttemptStatus.onboarding_errors
    )
    @responses.activate
    def test_attempt_failure_onboarding(self, failure_status):
        responses.add(
            responses.POST,
            url=self.provider.create_exam_attempt_url.format(exam_id=self.backend_exam['external_id']),
            json={'status': failure_status},
            status=200
        )
        with self.assertRaises(BackendProviderOnboardingException) as exc_manager:
            self.provider.register_exam_attempt(self.backend_exam, self.register_exam_context)
        exception = exc_manager.exception
        assert exception.status == failure_status

    @responses.activate
    def test_attempt_no_id_returned(self):
        responses.add(
            responses.POST,
            url=self.provider.create_exam_attempt_url.format(exam_id=self.backend_exam['external_id']),
            json={'error': 'something'},
            status=200
        )
        with self.assertRaises(BackendProviderSentNoAttemptID):
            self.provider.register_exam_attempt(self.backend_exam, self.register_exam_context)

    @ddt.data(
        ['start_exam_attempt', 'start'],
        ['stop_exam_attempt', 'stop'],
        ['mark_erroneous_exam_attempt', 'error'],
    )
    @ddt.unpack
    @responses.activate
    def test_update_exam_attempt_status(self, provider_method_name, corresponding_status):
        attempt_id = 2
        responses.add(
            responses.PATCH,
            url=self.provider.exam_attempt_url.format(exam_id=self.backend_exam['external_id'], attempt_id=attempt_id),
            json={'id': 2, 'status': corresponding_status}
        )
        status = getattr(self.provider, provider_method_name)(self.backend_exam['external_id'], attempt_id)
        self.assertEqual(status, corresponding_status)

    @responses.activate
    def test_malformed_json_in_response(self):
        attempt_id = 2
        responses.add(
            responses.PATCH,
            url=self.provider.exam_attempt_url.format(exam_id=self.backend_exam['external_id'], attempt_id=attempt_id),
            body='"]'
        )
        status = self.provider.mark_erroneous_exam_attempt(self.backend_exam['external_id'], attempt_id)
        # the important thing is that it didn't raise an exception for bad json
        self.assertEqual(status, None)

    @responses.activate
    def test_remove_attempt(self):
        attempt_id = 2
        responses.add(
            responses.DELETE,
            url=self.provider.exam_attempt_url.format(exam_id=self.backend_exam['external_id'], attempt_id=attempt_id),
            json={'status': "deleted"}
        )
        status = self.provider.remove_exam_attempt(self.backend_exam['external_id'], attempt_id)
        self.assertTrue(status)

    def test_remove_attempt_no_attempt(self):
        status = self.provider.remove_exam_attempt(self.backend_exam['external_id'], None)
        self.assertFalse(status)

    def test_on_review_callback(self):
        """
        on_review_callback should just return the payload
        """
        attempt = {
            'id': 1,
            'external_id': 'abcd',
            'user': 1
        }
        payload = {
            'status': 'verified',
            'comments': [
                {'comment': 'something happened', 'status': 'ok'}
            ]
        }
        new_payload = self.provider.on_review_callback(attempt, payload)
        self.assertEqual(payload, new_payload)

    def test_get_javascript(self):
        self.assertEqual(self.provider.get_javascript(), '')

    @patch('edx_proctoring.backends.rest.get_files')
    def test_get_javascript_bundle(self, get_files_mock):
        get_files_mock.return_value = [{'name': 'rest', 'url': '/there/it/is'}]
        javascript_url = self.provider.get_javascript()
        self.assertEqual(javascript_url, '/there/it/is')

        # test absolute URL
        get_files_mock.return_value = [{'name': 'rest', 'url': 'http://www.example.com/there/it/is'}]
        javascript_url = self.provider.get_javascript()
        self.assertEqual(javascript_url, 'http://www.example.com/there/it/is')

    @patch('edx_proctoring.backends.rest.get_files')
    def test_get_javascript_empty_return(self, get_files_mock):
        get_files_mock.return_value = []
        javascript_url = self.provider.get_javascript()
        self.assertEqual(javascript_url, '')

    @patch('webpack_loader.loader.WebpackLoader.get_assets')
    def test_get_javascript_swallows_errors(self, mock_get_assets):
        mock_get_assets.return_value = {'status': 'done', 'chunks': {}}
        javascript_url = self.provider.get_javascript()
        self.assertEqual(javascript_url, '')
        mock_get_assets.return_value = {'status': 'error', 'chunks': {}}
        javascript_url = self.provider.get_javascript()
        self.assertEqual(javascript_url, '')
        mock_get_assets.return_value = {'status': 'turtle', 'chunks': {}}
        javascript_url = self.provider.get_javascript()
        self.assertEqual(javascript_url, '')

    @patch('edx_proctoring.backends.rest.get_files')
    def test_get_javascript_returns_absolute_url(self, get_files_mock):
        get_files_mock.return_value = [{'name': 'rest', 'url': '/there/it/is'}]
        javascript_url = self.provider.get_javascript()

        # no LMS_ROOT_URL setting, so return original URL
        self.assertEqual(javascript_url, '/there/it/is')

        with override_settings(LMS_ROOT_URL='http://www.example.com'):
            javascript_url = self.provider.get_javascript()
            self.assertEqual(javascript_url, 'http://www.example.com/there/it/is')

    def test_instructor_url(self):
        user = {
            'id': 1,
            'full_name': 'Instructor',
            'email': 'instructor@example.com'
        }
        course_id = 'course+abc'
        base_url = self.provider.get_instructor_url(course_id, user)
        self.assertIn('?jwt=', base_url)
        # now try with an exam_id and an attempt_id.
        # the tokens will be different
        exam_id = 'abcd'
        attempt_id = 'defgh'
        exam_url = self.provider.get_instructor_url(course_id, user, exam_id=exam_id)
        self.assertNotEqual(exam_url, base_url)
        attempt_url = self.provider.get_instructor_url(course_id, user, exam_id='abcd', attempt_id=attempt_id)
        self.assertNotEqual(attempt_url, base_url)
        self.assertNotEqual(attempt_url, exam_url)
        # let's ensure that the last token contains all of the expected data
        token = attempt_url.split('jwt=')[1]
        decoded = jwt.decode(token,
                             issuer=self.provider.client_id,
                             key=self.provider.client_secret,
                             algorithms=['HS256'])
        self.assertEqual(decoded['user'], user)
        self.assertEqual(decoded['course_id'], course_id)
        self.assertEqual(decoded['exam_id'], exam_id)
        self.assertEqual(decoded['attempt_id'], attempt_id)

        # test that correct URL is returned for a request with parameter "show_configuration_dashboard=true"
        config_url = self.provider.get_instructor_url(
            course_id,
            user,
            exam_id=exam_id,
            show_configuration_dashboard=True,
        )
        token = config_url.split('jwt=')[1]
        decoded = jwt.decode(token,
                             issuer=self.provider.client_id,
                             key=self.provider.client_secret,
                             algorithms=['HS256'])
        self.assertTrue(decoded['config'])
        self.assertEqual(decoded['exam_id'], exam_id)

    @responses.activate
    def test_retire_user(self):
        user_id = 'abcdef5'
        responses.add(
            responses.DELETE,
            url=self.provider.user_info_url.format(user_id=user_id),
            json=True
        )
        result = self.provider.retire_user(user_id)
        assert result is True

    @responses.activate
    def test_retire_unknown_user(self):
        user_id = 'abcdef5'
        responses.add(
            responses.DELETE,
            url=self.provider.user_info_url.format(user_id=user_id),
            json=False
        )
        result = self.provider.retire_user(user_id)
        assert result is False

    @responses.activate
    def test_retire_error(self):
        user_id = 'abcdef5'
        responses.add(
            responses.DELETE,
            url=self.provider.user_info_url.format(user_id=user_id),
            body='"'
        )
        with self.assertRaises(BackendProviderCannotRetireUser):
            self.provider.retire_user(user_id)

    @responses.activate
    def test_get_onboarding_profile_for_user(self):
        user_id = 'abcdef5'
        course_id = 'course+abc'
        response_json = {'user_id': user_id, 'status': 'rejected', 'expiration_date': None}
        responses.add(
            responses.GET,
            url=self.provider.onboarding_statuses_url.format(course_id=course_id)+'?user_id='+user_id,
            json=response_json
        )
        result = self.provider.get_onboarding_profile_info(course_id=course_id, user_id=user_id)
        assert result == response_json

    @responses.activate
    def test_get_onboarding_profiles_for_course_with_query_params(self):
        course_id = 'course+abc'
        response_json = {
            "count": 3,
            "next": None,
            "previous": None,
            "num_pages": 1,
            "number": 1,
            "next_page_number": None,
            "prev_page_number": None,
            "items_per_page": 25,
            "results": [
                {
                    "user_id": "06c3",
                    "status": "approved-in-course",
                    "expiration_date": "2021-05-21"
                },
                {
                    "user_id": "a6cf",
                    "status": "approved-in-course",
                    "expiration_date": "2022-01-22"
                },
                {
                    "user_id": "fea7",
                    "status": "approved-in-course",
                    "expiration_date": "2022-03-22"
                }
            ]
        }
        responses.add(
            responses.GET,
            url=self.provider.onboarding_statuses_url.format(
                course_id=course_id
            ) + '?status=approved-in-course&page=1&page_size=3',
            json=response_json
        )
        result = self.provider.get_onboarding_profile_info(
            course_id=course_id, status='approved-in-course', page=1, page_size=3
        )
        assert result == response_json

    @responses.activate
    def test_get_onboarding_profiles_for_course_with_no_params(self):
        course_id = 'course+abc'
        response_json = {
            "count": 3,
            "next": None,
            "previous": None,
            "num_pages": 1,
            "number": 1,
            "next_page_number": None,
            "prev_page_number": None,
            "items_per_page": 25,
            "results": [
                {
                    "user_id": "06c3",
                    "status": "approved-in-course",
                    "expiration_date": "2021-05-21"
                }
            ]
        }
        responses.add(
            responses.GET,
            url=self.provider.onboarding_statuses_url.format(course_id=course_id),
            json=response_json
        )
        result = self.provider.get_onboarding_profile_info(course_id=course_id)
        assert result == response_json

    @responses.activate
    def test_get_onboarding_profiles_for_unknown_user_id(self):
        user_id = 'bad_user'
        course_id = 'course+abc'
        responses.add(
            responses.GET,
            url=self.provider.onboarding_statuses_url.format(course_id=course_id) + '?user_id=' + user_id,
            json={'error': 'something'},
            status=404
        )
        with self.assertRaises(BackendProviderOnboardingProfilesException):
            self.provider.get_onboarding_profile_info(course_id=course_id, user_id=user_id)
