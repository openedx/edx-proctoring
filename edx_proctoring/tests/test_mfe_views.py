"""
Tests for the MFE proctored exam views.
"""
import json

import ddt
from mock import patch

from django.conf import settings
from django.test.utils import override_settings
from django.urls import reverse

from edx_proctoring.exceptions import BackendProviderNotConfigured, ProctoredExamNotFoundException
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus

from .utils import ProctoredExamTestCase


@override_settings(LEARNING_MICROFRONTEND_URL='https//learningmfe')
@ddt.ddt
class ProctoredExamAttemptsMFEViewTests(ProctoredExamTestCase):
    """
    Tests for the ProctoredExamView called from MFE application.
    """
    def setUp(self):
        """
        Initialize
        """
        super().setUp()
        self.timed_exam_id = self._create_timed_exam()
        self.proctored_exam_id = self._create_proctored_exam()
        self.url = reverse(
            'edx_proctoring:proctored_exam.exam_attempts',
            kwargs={
                'course_id': self.course_id,
                'content_id': self.content_id
            }
        ) + '?is_learning_mfe=true'
        self.expected_exam_url = '{}/course/{}/{}'.format(
            settings.LEARNING_MICROFRONTEND_URL, self.course_id, self.content_id
        )

    def assertHasExamData(self, response_data, has_attempt, content_id=None):
        """ Ensure expected exam data is present. """
        exam_data = response_data['exam']
        assert 'exam' in response_data
        assert 'attempt' in exam_data
        if has_attempt:
            assert exam_data['attempt']
        else:
            assert not exam_data['attempt']
        self.assertEqual(exam_data['course_id'], self.course_id)
        self.assertEqual(exam_data['content_id'], self.content_id if not content_id else content_id)
        self.assertEqual(exam_data['time_limit_mins'], self.default_time_limit)

    def test_get_started_proctored_exam_attempts_data(self):
        """
        Tests the get proctored exam attempts data by course id and usage key endpoint for started exam.
        """
        self._create_started_exam_attempt(is_proctored=True)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        exam_data = response_data['exam']
        assert 'active_attempt' in response_data and response_data['active_attempt']
        self.assertHasExamData(response_data, has_attempt=True)
        self.assertEqual(exam_data['attempt']['exam_url_path'], self.expected_exam_url)

    def test_get_started_timed_exam_attempts_data(self):
        """
        Tests the get timed exam attempts data by course id and usage key endpoint for started exam.
        """
        self._create_started_exam_attempt(is_proctored=False)

        url = reverse(
            'edx_proctoring:proctored_exam.exam_attempts',
            kwargs={
                'course_id': self.course_id,
                'content_id': self.content_id_timed
            }
        ) + '?is_learning_mfe=true'

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        exam_data = response_data['exam']
        expected_exam_url = '{}/course/{}/{}'.format(
            settings.LEARNING_MICROFRONTEND_URL, self.course_id, self.content_id_timed
        )
        assert 'active_attempt' in response_data and response_data['active_attempt']
        self.assertHasExamData(response_data, has_attempt=True, content_id=self.content_id_timed)
        self.assertEqual(exam_data['attempt']['exam_url_path'], expected_exam_url)

    def test_no_attempts_data_before_exam_starts(self):
        """
        Test we get exam data before exam is started. Ensure no attempts data returned.
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        assert 'active_attempt' in response_data and not response_data['active_attempt']
        self.assertHasExamData(response_data, has_attempt=False)

    def test_get_exam_attempts_data_after_exam_is_submitted(self):
        """
        Tests the Get Exam attempts data contains exam.attempt with submitted status after exam ends.
        """
        self._create_exam_attempt(self.proctored_exam_id, status=ProctoredExamStudentAttemptStatus.submitted)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        exam_data = response_data['exam']
        assert 'active_attempt' in response_data and not response_data['active_attempt']
        self.assertHasExamData(response_data, has_attempt=True)
        self.assertEqual(exam_data['attempt']['exam_url_path'], self.expected_exam_url)
        self.assertEqual(exam_data['attempt']['attempt_status'], ProctoredExamStudentAttemptStatus.submitted)

    def test_no_exam_data_returned_for_non_exam_sequence(self):
        """
        Test empty exam data is returned for content_id of non-exam sequence item.
        """
        url = reverse(
            'edx_proctoring:proctored_exam.exam_attempts',
            kwargs={
                'course_id': self.course_id,
                'content_id': 'block-v1:test+course+1+type@sequential+block@unit'
            }
        ) + '?is_learning_mfe=true'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        exam_data = response_data['exam']
        assert 'active_attempt' in response_data
        assert not response_data['active_attempt']
        assert not exam_data


class ProctoredSettingsViewTests(ProctoredExamTestCase):
    """
    Tests for the ProctoredSettingsView.
    """

    def setUp(self):
        """
        Initialize.
        """
        super().setUp()
        self.proctored_exam_id = self._create_proctored_exam()
        self.timed_exam_id = self._create_timed_exam()

    def get_url(self, exam_id):
        """
        Returns ProctoredSettingsView url for exam_id.
        """
        return reverse(
            'edx_proctoring:proctored_exam.proctoring_settings',
            kwargs={
                'exam_id': exam_id,
            }
        )

    def test_get_proctoring_settings_for_proctored_exam(self):
        """
        Tests the get proctoring settings for proctored exam.
        """
        url = self.get_url(self.proctored_exam_id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        assert 'link_urls' in response_data and response_data['link_urls']
        assert 'exam_proctoring_backend' in response_data

    def test_get_proctoring_settings_for_timed_exam(self):
        """
        Tests the get proctoring settings for timed exam.
        """
        url = self.get_url(self.timed_exam_id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        assert 'link_urls' in response_data and response_data['link_urls']
        assert 'exam_proctoring_backend' in response_data and not response_data['exam_proctoring_backend']

    def test_get_proctoring_settings_for_non_existing_exam(self):
        """
        Test to get the proctoring settings for non-existing exam_id raises exception.
        """
        exam_id = 9999
        url = self.get_url(exam_id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        self.assertRaises(ProctoredExamNotFoundException)

    def test_get_proctoring_settings_for_exam_with_not_configured_backend(self):
        """
        Test to get the proctoring settings for the exam with not configured backend raises an exception.
        """
        url = self.get_url(self.proctored_exam_id)
        with patch('edx_proctoring.api.get_backend_provider', side_effect=NotImplementedError()):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 500)
        self.assertRaises(BackendProviderNotConfigured)
