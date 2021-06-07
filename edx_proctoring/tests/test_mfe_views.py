"""
Tests for the MFE proctored exam views.
"""
import json

import ddt
from mock import patch

from django.conf import settings
from django.test.utils import override_settings
from django.urls import reverse

from edx_proctoring.api import get_review_policy_by_exam_id
from edx_proctoring.exceptions import BackendProviderNotConfigured, ProctoredExamNotFoundException
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus

from .utils import ProctoredExamTestCase


@override_settings(LEARNING_MICROFRONTEND_URL='https//learningmfe', ACCOUNT_MICROFRONTEND_URL='https//localhost')
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
        self.practice_exam_id = self._create_practice_exam()
        self.onboarding_exam_id = self._create_onboarding_exam()
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

    def assertHasExamData(self, response_data, has_attempt,
                          has_verification_url=False, has_download_url=False, content_id=None):
        """ Ensure expected exam data is present. """
        exam_data = response_data['exam']
        assert 'exam' in response_data
        assert 'attempt' in exam_data
        if has_attempt:
            assert exam_data['attempt']
            if has_verification_url:
                assert exam_data['attempt']['verification_url']
            if has_download_url:
                assert 'software_download_url' in exam_data['attempt']
            else:
                assert 'software_download_url' not in exam_data['attempt']
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

        # if exam started the prerequisites are not checked
        assert 'prerequisite_status' not in exam_data
        assert 'active_attempt' in response_data and response_data['active_attempt']
        self.assertHasExamData(response_data, has_attempt=True)
        self.assertEqual(exam_data['attempt']['exam_url_path'], self.expected_exam_url)
        self.assertEqual(exam_data['type'], 'proctored')

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
        assert 'prerequisite_status' not in exam_data
        assert 'active_attempt' in response_data and response_data['active_attempt']
        self.assertHasExamData(response_data, has_attempt=True, content_id=self.content_id_timed)
        self.assertEqual(exam_data['attempt']['exam_url_path'], expected_exam_url)

    def test_no_attempts_data_before_exam_starts(self):
        """
        Test we get exam data before exam is started. Ensure no attempts data returned and prerequisites are checked.
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        exam_data = response_data['exam']
        assert 'active_attempt' in response_data and not response_data['active_attempt']
        assert 'prerequisite_status' in exam_data
        self.assertHasExamData(response_data, has_attempt=False)
        self.assertEqual(exam_data['type'], 'proctored')

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
        assert 'prerequisite_status' not in exam_data
        self.assertHasExamData(response_data, has_attempt=True)
        self.assertEqual(exam_data['attempt']['exam_url_path'], self.expected_exam_url)
        self.assertEqual(exam_data['attempt']['attempt_status'], ProctoredExamStudentAttemptStatus.submitted)
        self.assertEqual(exam_data['type'], 'proctored')

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

    @ddt.data(
        ('content_id', True),
        ('content_id_timed', False),
        ('content_id_onboarding', False),
        ('content_id_practice', False),
    )
    @ddt.unpack
    def test_prerequisites_are_not_checked_if_exam_is_not_proctored(self, content_id, should_check_prerequisites):
        """
        Tests that prerequisites are not checked for non proctored exams.
        """
        content_id = getattr(self, content_id)
        url = reverse(
            'edx_proctoring:proctored_exam.exam_attempts',
            kwargs={
                'course_id': self.course_id,
                'content_id': content_id
            }
        ) + '?is_learning_mfe=true'

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        exam_data = response_data['exam']
        self.assertEqual('prerequisite_status' in exam_data, should_check_prerequisites)

    @ddt.data(
        ProctoredExamStudentAttemptStatus.created,
        ProctoredExamStudentAttemptStatus.download_software_clicked,
        ProctoredExamStudentAttemptStatus.ready_to_start,
        ProctoredExamStudentAttemptStatus.started,
        ProctoredExamStudentAttemptStatus.ready_to_submit,
        ProctoredExamStudentAttemptStatus.declined,
        ProctoredExamStudentAttemptStatus.submitted,
        ProctoredExamStudentAttemptStatus.rejected,
        ProctoredExamStudentAttemptStatus.expired
    )
    def test_exam_data_contains_necessary_data_based_on_the_attempt_status(self, status):
        """
        Tests the GET exam attempts data contains software download url ONLY when attempt
        is in created or download_software_clicked status and contains verification
        url ONLY when attempt is in created status
        """
        self._create_exam_attempt(self.proctored_exam_id, status=status)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        has_download_url = status in (
            ProctoredExamStudentAttemptStatus.created,
            ProctoredExamStudentAttemptStatus.download_software_clicked
        )
        has_verification_url = status == ProctoredExamStudentAttemptStatus.created
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertHasExamData(
            response_data,
            has_attempt=True,
            has_download_url=has_download_url,
            has_verification_url=has_verification_url,
        )


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


class ProctoredExamReviewPolicyView(ProctoredExamTestCase):
    """
    Tests for the ProctoredExamReviewPolicyView.
    """

    def setUp(self):
        """
        Initialize.
        """
        super().setUp()
        self.proctored_exam_id = self._create_proctored_exam()
        self.review_policy_id = self._create_review_policy(self.proctored_exam_id)
        self.url = reverse(
            'edx_proctoring:proctored_exam.review_policy',
            kwargs={
                'exam_id': self.proctored_exam_id,
            }
        )

    def test_get_exam_review_policy_for_proctored_exam(self):
        """
        Tests the GET exam review policy endpoint for proctored exam with existing policy.
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        expected_review_policy = get_review_policy_by_exam_id(self.proctored_exam_id)
        assert 'review_policy' in response_data
        self.assertEqual(response_data['review_policy'], expected_review_policy['review_policy'])

    def test_get_exam_review_policy_for_proctored_exam_with_no_existing_review(self):
        """
        Tests the GET exam review policy endpoint for proctored exam which has no review policy configured.
        """
        with patch('edx_proctoring.models.ProctoredExamReviewPolicy.get_review_policy_for_exam', return_value=None):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        assert 'review_policy' in response_data
        self.assertIsNone(response_data['review_policy'])
