"""
Tests for the REST backend
"""
import json
from django.test import TestCase

from edx_proctoring.backends.rest import BaseRestProctoringProvider

import responses


class RESTBackendTests(TestCase):
    """
    Tests for the REST backend
    """
    def setUp(self):
        "setup tests"
        BaseRestProctoringProvider.base_url = 'http://rr.fake'
        self.provider = BaseRestProctoringProvider()
        responses.add(
            responses.POST,
            url=self.provider.base_url + '/oauth2/access_token',
            json={'access_token': 'abcd', 'expires_in': 600},
            status=200
        )

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
        exam = {
            'course_id': 'course123',
            'id': 'abcd',
            'name': 'my exam',
            'is_active': True,
            'is_proctored': True,
            'is_practice': False,
        }
        responses.add(
            responses.GET,
            url=self.provider.exam_url.format(exam_id='abcd'),
            json=exam
        )
        external_exam = self.provider.get_exam(exam)
        self.assertEqual(external_exam, exam)

    @responses.activate
    def test_on_exam_saved(self):
        exam = {
            'course_id': 'course123',
            'id': 1,
            'name': 'my exam',
            'is_active': True,
            'is_proctored': True,
            'is_practice': False,
        }
        responses.add(
            responses.POST,
            url=self.provider.create_exam_url,
            json={'id': 'abcdefg'}
        )
        external_id = self.provider.on_exam_saved(exam)
        self.assertEqual(external_id, 'abcdefg')

    @responses.activate
    def test_get_attempt(self):
        pass

    @responses.activate
    def test_register_exam_attempt(self):
        exam = {
            'course_id': 'course123',
            'id': 1,
            'external_id': 'abcdefg',
            'name': 'my exam',
            'is_active': True,
            'is_proctored': True,
            'is_practice': False,
        }
        context = {
            'attempt_code': '2',
            'obs_user_id': 'abcdefghij',
            'full_name': 'user name',
            'lms_host': 'http://lms.com'
        }
        responses.add(
            responses.POST,
            url=self.provider.create_exam_attempt_url.format(exam_id=exam['external_id']),
            json={'id': 2}
        )
        attempt_external_id = self.provider.register_exam_attempt(exam, context)
        request = json.loads(responses.calls[1].request.body)
        self.assertEqual(attempt_external_id, 2)
        self.assertEquals(request['status'], 'created')
        self.assertIn('lms_host', request)
        self.assertIn('full_name', request)

    @responses.activate
    def test_start_exam_attempt(self):
        exam = {
            'course_id': 'course123',
            'id': 1,
            'external_id': 'abcdefg',
            'name': 'my exam',
            'is_active': True,
            'is_proctored': True,
            'is_practice': False,
        }
        attempt_id = 2
        responses.add(
            responses.PATCH,
            url=self.provider.exam_attempt_url.format(exam_id=exam['external_id'], attempt_id=attempt_id),
            json={'id': 2, 'status': 'start'}
        )
        status = self.provider.start_exam_attempt(exam['external_id'], attempt_id)
        self.assertEqual(status, 'start')

    @responses.activate
    def test_stop_exam_attempt(self):
        exam = {
            'course_id': 'course123',
            'id': 1,
            'external_id': 'abcdefg',
            'name': 'my exam',
            'is_active': True,
            'is_proctored': True,
            'is_practice': False,
        }
        attempt_id = 2
        responses.add(
            responses.PATCH,
            url=self.provider.exam_attempt_url.format(exam_id=exam['external_id'], attempt_id=attempt_id),
            json={'id': 2, 'status': 'stop'}
        )
        status = self.provider.stop_exam_attempt(exam['external_id'], attempt_id)
        self.assertEqual(status, 'stop')

    @responses.activate
    def test_on_review_callback(self):
        pass
