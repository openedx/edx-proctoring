"""
Review callback tests
"""

import codecs
import json

import ddt
import mock
from crum import set_current_request
from mock import call, patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.urls import reverse

from edx_proctoring import constants
from edx_proctoring.api import create_exam, create_exam_attempt, get_exam_attempt_by_id, remove_exam_attempt
from edx_proctoring.backends import get_backend_provider
from edx_proctoring.backends.software_secure import SoftwareSecureBackendProvider
from edx_proctoring.backends.tests.test_review_payload import create_test_review_payload
from edx_proctoring.exceptions import ProctoredExamBadReviewStatus, ProctoredExamReviewAlreadyExists
from edx_proctoring.models import (
    ProctoredExamSoftwareSecureComment,
    ProctoredExamSoftwareSecureReview,
    ProctoredExamSoftwareSecureReviewHistory
)
from edx_proctoring.runtime import get_runtime_service, set_runtime_service
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus, ReviewStatus, SoftwareSecureReviewStatus
from edx_proctoring.tests.test_services import (
    MockCertificateService,
    MockCreditService,
    MockGradesService,
    MockInstructorService
)
from edx_proctoring.utils import decode_and_decrypt, locate_attempt_by_attempt_code
from edx_proctoring.views import ProctoredExamReviewCallback, is_user_course_or_global_staff

from .utils import LoggedInTestCase

User = get_user_model()


@ddt.ddt
class ReviewTests(LoggedInTestCase):
    """
    Tests for reviews
    """
    def setUp(self):
        super().setUp()
        self.dummy_request = RequestFactory().get('/')
        self.exam_creation_params = {
            'course_id': 'foo/bar/baz',
            'content_id': 'content',
            'exam_name': 'Sample Exam',
            'time_limit_mins': 10,
            'is_proctored': True,
            'backend': 'test'
        }
        self.exam_id = create_exam(**self.exam_creation_params)

        self.attempt_id = create_exam_attempt(
            self.exam_id,
            self.user.id,
            taking_as_proctored=True
        )

        self.attempt = get_exam_attempt_by_id(self.attempt_id)
        set_runtime_service('credit', MockCreditService())
        set_runtime_service('instructor', MockInstructorService())
        set_runtime_service('grades', MockGradesService())
        set_runtime_service('certificates', MockCertificateService())
        set_current_request(self.dummy_request)

    def tearDown(self):
        super().tearDown()
        set_runtime_service('credit', None)
        set_runtime_service('grades', None)
        set_runtime_service('certificates', None)

    def get_review_payload(self, status=ReviewStatus.passed, **kwargs):
        """
        Returns a standard review payload
        """
        review = {
            'status': status,
            'comments': [
                {
                    "comment": "Browsing other websites",
                    "duration": 88,
                    "stop": 88,
                    "start": 12,
                    "status": "suspicious"
                },
                {
                    "comment": "Browsing local computer",
                    "duration": 88,
                    "stop": 88,
                    "start": 15,
                    "status": "Rules Violation"
                },
                {
                    "comment": "Student never entered the exam.",
                    "duration": 88,
                    "stop": 88,
                    "start": 87,
                    "status": "Clean"
                }
            ]
        }
        review.update(kwargs)
        return review

    @ddt.data(
        ('Bogus', None, None),
        ('Clean', 'Clean', 'satisfied'),
        ('Rules Violation', 'Rules Violation', 'satisfied'),
        ('Suspicious', 'Suspicious', 'failed'),
        ('Not Reviewed', 'Not Reviewed', 'failed'),
    )
    @ddt.unpack
    @patch('edx_proctoring.constants.REQUIRE_FAILURE_SECOND_REVIEWS', False)
    def test_psi_review_callback(self, psi_review_status, review_status, credit_requirement_status):
        """
        Simulates callbacks from SoftwareSecure with various statuses
        """
        test_payload = json.loads(create_test_review_payload(
            attempt_code=self.attempt['attempt_code'],
            external_id=self.attempt['external_id'],
            review_status=psi_review_status
        ))

        self.attempt['proctored_exam']['backend'] = 'software_secure'
        if review_status is None:
            with self.assertRaises(ProctoredExamBadReviewStatus):
                ProctoredExamReviewCallback().make_review(self.attempt, test_payload)
        else:
            ProctoredExamReviewCallback().make_review(self.attempt, test_payload)
            # make sure that what we have in the Database matches what we expect
            review = ProctoredExamSoftwareSecureReview.get_review_by_attempt_code(self.attempt['attempt_code'])

            self.assertIsNotNone(review)
            self.assertEqual(review.review_status, review_status)
            self.assertTrue(review.encrypted_video_url)

            self.assertIsNotNone(review.raw_data)
            self.assertIsNone(json.loads(review.raw_data).get('videoReviewLink'))
            self.assertIsNone(review.reviewed_by)

            # now check the comments that were stored
            comments = ProctoredExamSoftwareSecureComment.objects.filter(review_id=review.id)

            self.assertEqual(len(comments), 6)

            # check that we got credit requirement set appropriately

            credit_service = get_runtime_service('credit')
            credit_status = credit_service.get_credit_state(self.user.id, 'foo/bar/baz')

            self.assertEqual(
                credit_status['credit_requirement_status'][0]['status'],
                credit_requirement_status
            )

            instructor_service = get_runtime_service('instructor')
            notifications = instructor_service.notifications
            if psi_review_status == SoftwareSecureReviewStatus.suspicious:
                # check to see whether the zendesk ticket was created
                self.assertEqual(len(notifications), 1)
                exam = self.attempt['proctored_exam']
                review_url = 'http://testserver/edx_proctoring/v1/instructor/foo/bar/baz/1?attempt=testexternalid'
                self.assertEqual(notifications,
                                 [(exam['course_id'],
                                   exam['exam_name'],
                                   self.attempt['user']['username'],
                                   review.review_status,
                                   review_url)])
            else:
                self.assertEqual(len(notifications), 0)

    def test_psi_video_url(self):
        """
        Test that review callback from PSI produces encrypted video link
        """

        test_payload = json.loads(create_test_review_payload(
            attempt_code=self.attempt['attempt_code'],
            external_id=self.attempt['external_id'],
            review_status='Clean'
        ))

        video_url = test_payload['videoReviewLink']

        self.attempt['proctored_exam']['backend'] = 'software_secure'

        ProctoredExamReviewCallback().make_review(self.attempt, test_payload)
        review = ProctoredExamSoftwareSecureReview.get_review_by_attempt_code(self.attempt['attempt_code'])
        aes_key_str = get_backend_provider(name='software_secure').get_video_review_aes_key()
        aes_key = codecs.decode(aes_key_str, "hex")
        decoded_video_url = decode_and_decrypt(review.encrypted_video_url, aes_key)

        self.assertEqual(decoded_video_url.decode("utf-8"), video_url)

    def test_psi_video_url_no_key(self):
        """
        Test that review callback from PSI does not produce encrypted video url if now encryption key is provided
        """

        with patch.object(SoftwareSecureBackendProvider, 'get_video_review_aes_key') as key_mock:
            key_mock.return_value = None

            test_payload = json.loads(create_test_review_payload(
                attempt_code=self.attempt['attempt_code'],
                external_id=self.attempt['external_id'],
                review_status='Clean'
            ))

            self.attempt['proctored_exam']['backend'] = 'software_secure'

            ProctoredExamReviewCallback().make_review(self.attempt, test_payload)
            review = ProctoredExamSoftwareSecureReview.get_review_by_attempt_code(self.attempt['attempt_code'])
            self.assertFalse(review.encrypted_video_url)

    def test_bad_review_status(self):
        """
        Tests that an exception is raised if the review has an invalid status
        """
        test_payload = self.get_review_payload('bogus')

        with self.assertRaises(ProctoredExamBadReviewStatus):
            ProctoredExamReviewCallback().make_review(self.attempt, test_payload)

    @ddt.data(
        ('bad', 400),
        (None, 200),
    )
    @ddt.unpack
    def test_post_review(self, external_id, status):
        self.user.is_staff = True
        self.user.save()
        review = self.get_review_payload()
        if not external_id:
            external_id = self.attempt['external_id']
        response = self.client.post(
            reverse('edx_proctoring:proctored_exam.attempt.callback',
                    kwargs={'external_id': external_id}),
            json.dumps(review),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status)

    def test_post_review_auth(self):
        review = json.dumps(self.get_review_payload())
        external_id = self.attempt['external_id']
        url = reverse('edx_proctoring:proctored_exam.attempt.callback',
                      kwargs={'external_id': external_id})
        response = self.client.post(
            url,
            review,
            content_type='application/json'
        )
        assert response.status_code == 403
        # staff users can review
        self.user.is_staff = True
        self.user.save()
        response = self.client.post(
            url,
            review,
            content_type='application/json'
        )
        assert response.status_code == 200
        # user in the review group
        group_name = f"{self.attempt['proctored_exam']['backend']}_review"
        self.user.groups.get_or_create(name=group_name)
        self.user.is_staff = False
        self.user.save()
        response = self.client.post(
            url,
            review,
            content_type='application/json'
        )
        assert response.status_code == 200

    @patch('edx_proctoring.constants.REQUIRE_FAILURE_SECOND_REVIEWS', False)
    def test_review_on_archived_attempt(self):
        """
        Make sure we can process a review report for
        an attempt which has been archived
        """
        test_payload = self.get_review_payload(ReviewStatus.passed)

        # now delete the attempt, which puts it into the archive table
        remove_exam_attempt(self.attempt_id, requesting_user=self.user)

        # now process the report
        ProctoredExamReviewCallback().make_review(self.attempt, test_payload)

        # make sure that what we have in the Database matches what we expect
        review = ProctoredExamSoftwareSecureReview.get_review_by_attempt_code(self.attempt['attempt_code'])

        self.assertIsNotNone(review)
        self.assertEqual(review.review_status, SoftwareSecureReviewStatus.clean)

        self.assertIsNotNone(review.raw_data)

        # now check the comments that were stored
        comments = ProctoredExamSoftwareSecureComment.objects.filter(review_id=review.id)

        self.assertEqual(len(comments), 3)

    @patch('edx_proctoring.constants.ALLOW_REVIEW_UPDATES', False)
    @patch('edx_proctoring.constants.REQUIRE_FAILURE_SECOND_REVIEWS', False)
    def test_disallow_review_resubmission(self):
        """
        Tests that an exception is raised if a review report is resubmitted for the same
        attempt
        """
        test_payload = self.get_review_payload(ReviewStatus.passed)

        ProctoredExamReviewCallback().make_review(self.attempt, test_payload)

        # now call again
        with self.assertRaises(ProctoredExamReviewAlreadyExists):
            ProctoredExamReviewCallback().make_review(self.attempt, test_payload)

    @patch('edx_proctoring.constants.ALLOW_REVIEW_UPDATES', True)
    def test_allow_review_resubmission(self):
        """
        Tests that an resubmission is allowed
        """
        test_payload = self.get_review_payload(ReviewStatus.passed)

        ProctoredExamReviewCallback().make_review(self.attempt, test_payload)

        # make sure history table is empty
        records = ProctoredExamSoftwareSecureReviewHistory.objects.filter(attempt_code=self.attempt['attempt_code'])
        self.assertEqual(len(records), 0)

        # now call again, this will not throw exception
        test_payload['status'] = ReviewStatus.suspicious
        ProctoredExamReviewCallback().make_review(self.attempt, test_payload)

        # make sure that what we have in the Database matches what we expect
        review = ProctoredExamSoftwareSecureReview.get_review_by_attempt_code(self.attempt['attempt_code'])

        self.assertIsNotNone(review)
        self.assertEqual(review.review_status, SoftwareSecureReviewStatus.suspicious)

        self.assertIsNotNone(review.raw_data)

        # make sure history table is no longer empty
        records = ProctoredExamSoftwareSecureReviewHistory.objects.filter(attempt_code=self.attempt['attempt_code'])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].review_status, 'Clean')

        # now try to delete the record and make sure it was archived

        review.delete()

        records = ProctoredExamSoftwareSecureReviewHistory.objects.filter(attempt_code=self.attempt['attempt_code'])
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].review_status, SoftwareSecureReviewStatus.clean)
        self.assertEqual(records[1].review_status, SoftwareSecureReviewStatus.suspicious)

    @patch('edx_proctoring.constants.REQUIRE_FAILURE_SECOND_REVIEWS', True)
    def test_failure_submission_rejected(self):
        """
        Tests that a submission of a failed test and make sure that we
        don't automatically update the status to failure
        """
        test_payload = self.get_review_payload(ReviewStatus.suspicious)
        allow_rejects = not constants.REQUIRE_FAILURE_SECOND_REVIEWS
        # submit a Suspicious review payload
        ProctoredExamReviewCallback().make_review(self.attempt, test_payload)

        # now look at the attempt and make sure it did not
        # transition to failure on the callback,
        # as we'll need a manual confirmation via Django Admin pages
        attempt = get_exam_attempt_by_id(self.attempt_id)
        self.assertNotEqual(attempt['status'], ProctoredExamStudentAttemptStatus.rejected)

        review = ProctoredExamSoftwareSecureReview.objects.get(attempt_code=self.attempt['attempt_code'])

        attempt = get_exam_attempt_by_id(self.attempt_id)

        # if we don't allow rejects to be stored in attempt status
        # then we should expect a 'second_review_required' status
        expected_status = (
            ProctoredExamStudentAttemptStatus.rejected if allow_rejects else
            ProctoredExamStudentAttemptStatus.second_review_required
        )
        self.assertEqual(attempt['status'], expected_status)
        self.assertEqual(review.review_status, SoftwareSecureReviewStatus.suspicious)

    def test_failure_not_reviewed(self):
        """
        Tests that a review which comes back as "not reviewed"
        transitions to an error state
        """
        test_payload = self.get_review_payload(ReviewStatus.not_reviewed)
        ProctoredExamReviewCallback().make_review(self.attempt, test_payload)

        attempt = get_exam_attempt_by_id(self.attempt_id)
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.error)

    def test_update_archived_attempt(self):
        """
        Test calling the interface point with an attempt_code that was archived
        """
        test_payload = self.get_review_payload()

        # now process the report
        ProctoredExamReviewCallback().make_review(self.attempt, test_payload)

        # now look at the attempt and make sure it did not
        # transition to failure on the callback,
        # as we'll need a manual confirmation via Django Admin pages
        attempt = get_exam_attempt_by_id(self.attempt_id)
        self.assertEqual(attempt['status'], 'verified')

        attempt, is_archived = locate_attempt_by_attempt_code(self.attempt['attempt_code'])
        self.assertFalse(is_archived)
        self.assertEqual(attempt.status, 'verified')

        # now delete the attempt, which puts it into the archive table
        remove_exam_attempt(self.attempt_id, requesting_user=self.user)
        attempt, is_archived = locate_attempt_by_attempt_code(self.attempt['attempt_code'])
        self.assertTrue(is_archived)
        self.assertEqual(attempt.status, 'verified')

        review = ProctoredExamSoftwareSecureReview.objects.get(attempt_code=self.attempt['attempt_code'])
        self.assertEqual(review.review_status, SoftwareSecureReviewStatus.clean)

        # now we'll make another review for the archived attempt. It should NOT update the status
        test_payload = self.get_review_payload(ReviewStatus.suspicious)
        self.attempt['is_archived'] = True
        ProctoredExamReviewCallback().make_review(self.attempt, test_payload)
        attempt, is_archived = locate_attempt_by_attempt_code(self.attempt['attempt_code'])
        self.assertTrue(is_archived)
        self.assertEqual(attempt.status, 'verified')

    def test_clean_status(self):
        """
        Test that defining `passing_statuses` on the backend works
        """
        test_backend = get_backend_provider(name='test')
        with patch.object(test_backend, 'passing_statuses', [SoftwareSecureReviewStatus.clean], create=True):
            test_payload = self.get_review_payload(status=ReviewStatus.violation)
            ProctoredExamReviewCallback().make_review(self.attempt, test_payload)

            attempt = get_exam_attempt_by_id(self.attempt_id)
            self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.second_review_required)

    def test_onboarding_attempts_no_second_review_necessary(self):
        """
        Test that onboarding exams do not require a manual pass of review before they land in rejected
        """
        exam_creation_params = self.exam_creation_params.copy()
        exam_creation_params.update({
            'is_practice_exam': True,
            'content_id': 'onboarding_content',
        })
        onboarding_exam_id = create_exam(**exam_creation_params)
        onboarding_attempt_id = create_exam_attempt(
            onboarding_exam_id,
            self.user.id,
            taking_as_proctored=True,
        )
        onboarding_attempt = get_exam_attempt_by_id(onboarding_attempt_id)
        test_payload = self.get_review_payload(ReviewStatus.suspicious)
        ProctoredExamReviewCallback().make_review(onboarding_attempt, test_payload)

        onboarding_attempt = get_exam_attempt_by_id(onboarding_attempt_id)
        assert onboarding_attempt['status'] != ProctoredExamStudentAttemptStatus.second_review_required

    def test_status_reviewed_by_field(self):
        """
        Test that `reviewed_by` field of Review model is correctly assigned to None or to a User object.
        """
        # no reviewed_by field
        test_payload = self.get_review_payload(ReviewStatus.suspicious)
        # submit a Suspicious review payload
        ProctoredExamReviewCallback().make_review(self.attempt, test_payload)

        review = ProctoredExamSoftwareSecureReview.objects.get(attempt_code=self.attempt['attempt_code'])
        self.assertIsNone(review.reviewed_by)

        # reviewed_by field with no corresponding User object
        reviewed_by_email = 'testy@example.com'
        test_payload['reviewed_by'] = reviewed_by_email

        # submit a Suspicious review payload
        ProctoredExamReviewCallback().make_review(self.attempt, test_payload)
        review = ProctoredExamSoftwareSecureReview.objects.get(attempt_code=self.attempt['attempt_code'])
        self.assertIsNone(review.reviewed_by)

        # reviewed_by field with corresponding User object
        user = User.objects.create(
            email=reviewed_by_email,
            username='TestyMcTesterson'
        )
        # submit a Suspicious review payload
        ProctoredExamReviewCallback().make_review(self.attempt, test_payload)
        review = ProctoredExamSoftwareSecureReview.objects.get(attempt_code=self.attempt['attempt_code'])
        self.assertEqual(review.reviewed_by, user)

    def test_is_user_course_or_global_staff(self):
        """
        Test that is_user_course_or_global_staff function correctly returns whether
        a user is either global staff or course staff.
        """
        user = User.objects.create(
            email='testy@example.com',
            username='TestyMcTesterson'
        )
        course_id = self.attempt['proctored_exam']['course_id']

        # course_staff = true, is_staff = false
        # by default, user.is_staff is false and instructor_service.is_course_staff returns true
        self.assertTrue(is_user_course_or_global_staff(user, course_id))

        # course_staff = true, is_staff = true
        user.is_staff = True
        self.assertTrue(is_user_course_or_global_staff(user, course_id))

        # mock instructor service must be configured to treat users as not course staff.
        set_runtime_service('instructor', MockInstructorService(is_user_course_staff=False))

        # course_staff = false, is_staff = true
        self.assertTrue(is_user_course_or_global_staff(user, course_id))

        # course_staff = false, is_staff = false
        user.is_staff = False
        self.assertFalse(is_user_course_or_global_staff(user, course_id))

    @patch('logging.Logger.warning')
    def test_reviewed_by_is_course_or_global_staff(self, logger_mock):
        """
        Test that a "reviewed_by" field of a review that corresponds to a user
        that is not a course staff or global staff causes a warning to be logged.
        Test that no warning is logged if a user is course staff or global staff.
        """
        test_payload = self.get_review_payload()
        reviewed_by_email = 'testy@example.com'
        test_payload['reviewed_by'] = reviewed_by_email

        # reviewed_by field with corresponding User object
        user = User.objects.create(
            email=reviewed_by_email,
            username='TestyMcTesterson'
        )

        log_format_string = (
            'user=%(user)s does not have the required permissions '
            'to submit a review for attempt_code=%(attempt_code)s.'
        )

        log_format_dictionary = {
            'user': user,
            'attempt_code': self.attempt['attempt_code'],
        }

        with patch('edx_proctoring.views.is_user_course_or_global_staff', return_value=False):
            ProctoredExamReviewCallback().make_review(self.attempt, test_payload)

            # using assert_any_call instead of assert_called_with due to logging in analytics emit_event function
            logger_mock.assert_any_call(log_format_string, log_format_dictionary)

        logger_mock.reset_mock()

        with patch('edx_proctoring.views.is_user_course_or_global_staff', return_value=True):
            ProctoredExamReviewCallback().make_review(self.attempt, test_payload)

            # the mock API doesn't have a "assert_not_called_with" method
            # pylint: disable=wrong-assert-type
            self.assertFalse(
                call(log_format_string, log_format_dictionary) in logger_mock.call_args_list
            )

    def test_review_update_attempt_active_field(self):
        """
        Make sure we update the is_active_attempt field when an attempt is archived
        """
        test_payload = self.get_review_payload(ReviewStatus.passed)
        ProctoredExamReviewCallback().make_review(self.attempt, test_payload)

        review = ProctoredExamSoftwareSecureReview.get_review_by_attempt_code(self.attempt['attempt_code'])
        self.assertTrue(review.is_attempt_active)

        # now delete the attempt, which puts it into the archive table
        with mock.patch('edx_proctoring.api.update_attempt_status') as mock_update_status:
            remove_exam_attempt(self.attempt_id, requesting_user=self.user)

        # check that the field has been updated
        review = ProctoredExamSoftwareSecureReview.get_review_by_attempt_code(self.attempt['attempt_code'])
        self.assertFalse(review.is_attempt_active)

        # check that update_attempt_status has not been called, as the attempt has been archived
        mock_update_status.assert_not_called()
