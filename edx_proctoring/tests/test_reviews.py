"""
Review callback tests
"""
from __future__ import absolute_import

import json

import ddt
from mock import patch

from django.urls import reverse

from edx_proctoring import constants
from edx_proctoring.api import create_exam, create_exam_attempt, get_exam_attempt_by_id, remove_exam_attempt
from edx_proctoring.backends.tests.test_review_payload import create_test_review_payload
from edx_proctoring.exceptions import (ProctoredExamBadReviewStatus, ProctoredExamReviewAlreadyExists)
from edx_proctoring.models import (ProctoredExamSoftwareSecureComment, ProctoredExamSoftwareSecureReview,
                                   ProctoredExamSoftwareSecureReviewHistory, ProctoredExamStudentAttemptHistory,
                                   ProctoredExamStudentAttemptStatus)
from edx_proctoring.runtime import get_runtime_service, set_runtime_service
from edx_proctoring.tests.test_services import (MockCertificateService, MockCreditService, MockGradesService,
                                                MockInstructorService)
from edx_proctoring.views import ProctoredExamReviewCallback

from .utils import LoggedInTestCase


@ddt.ddt
class ReviewTests(LoggedInTestCase):
    """
    Tests for reviews
    """
    def setUp(self):
        super(ReviewTests, self).setUp()
        self.exam_id = create_exam(
            course_id='foo/bar/baz',
            content_id='content',
            exam_name='Sample Exam',
            time_limit_mins=10,
            is_proctored=True,
            backend='test'
        )

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

    def tearDown(self):
        super(ReviewTests, self).tearDown()
        set_runtime_service('credit', None)
        set_runtime_service('grades', None)
        set_runtime_service('certificates', None)

    def get_review_payload(self, status='pass', comments=None, **kwargs):
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
        if comments:
            review['comments'].extend(comments)
        return review

    @ddt.data(
        ('Bogus', None, None),
        ('Clean', 'pass', 'satisfied'),
        ('Rules Violation', 'pass', 'satisfied'),
        ('Suspicious', 'fail', 'failed'),
        ('Not Reviewed', 'fail', 'failed'),
    )
    @ddt.unpack
    @patch('edx_proctoring.constants.REQUIRE_FAILURE_SECOND_REVIEWS', False)
    def test_review_callback(self, psi_review_status, review_status, credit_requirement_status):
        """
        Simulates callbacks from SoftwareSecure with various statuses
        """
        test_payload = json.loads(create_test_review_payload(
            attempt_code=self.attempt['attempt_code'],
            external_id=self.attempt['external_id'],
            review_status=psi_review_status
        ))
        # test_payload = self.get_review_payload(review_status)
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
            self.assertFalse(review.video_url)

            self.assertIsNotNone(review.raw_data)
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

    @ddt.data(
        ('bad', 400),
        (None, 200),
    )
    @ddt.unpack
    def test_post_review(self, external_id, status):
        review = self.get_review_payload()
        if not external_id:
            external_id = self.attempt['external_id']
        response = self.client.post(
            reverse('edx_proctoring.proctored_exam.attempt.callback',
                    kwargs={'external_id': external_id}),
            json.dumps(review),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status)

    @patch('edx_proctoring.constants.REQUIRE_FAILURE_SECOND_REVIEWS', False)
    def test_review_on_archived_attempt(self):
        """
        Make sure we can process a review report for
        an attempt which has been archived
        """
        test_payload = self.get_review_payload('Clean')

        # now delete the attempt, which puts it into the archive table
        remove_exam_attempt(self.attempt_id, requesting_user=self.user)

        # now process the report
        ProctoredExamReviewCallback().make_review(self.attempt, test_payload)

        # make sure that what we have in the Database matches what we expect
        review = ProctoredExamSoftwareSecureReview.get_review_by_attempt_code(self.attempt['attempt_code'])

        self.assertIsNotNone(review)
        self.assertEqual(review.review_status, 'Clean')
        self.assertFalse(review.video_url)

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
        test_payload = self.get_review_payload('ok')

        ProctoredExamReviewCallback().make_review(self.attempt, test_payload)

        # now call again
        with self.assertRaises(ProctoredExamReviewAlreadyExists):
            ProctoredExamReviewCallback().make_review(self.attempt, test_payload)

    @patch('edx_proctoring.constants.ALLOW_REVIEW_UPDATES', True)
    def test_allow_review_resubmission(self):
        """
        Tests that an resubmission is allowed
        """
        test_payload = self.get_review_payload('Clean')

        ProctoredExamReviewCallback().make_review(self.attempt, test_payload)

        # make sure history table is empty
        records = ProctoredExamSoftwareSecureReviewHistory.objects.filter(attempt_code=self.attempt['attempt_code'])
        self.assertEqual(len(records), 0)

        # now call again, this will not throw exception
        test_payload['status'] = 'Suspicious'
        ProctoredExamReviewCallback().make_review(self.attempt, test_payload)

        # make sure that what we have in the Database matches what we expect
        review = ProctoredExamSoftwareSecureReview.get_review_by_attempt_code(self.attempt['attempt_code'])

        self.assertIsNotNone(review)
        self.assertEqual(review.review_status, 'Suspicious')
        self.assertFalse(review.video_url)

        self.assertIsNotNone(review.raw_data)

        # make sure history table is no longer empty
        records = ProctoredExamSoftwareSecureReviewHistory.objects.filter(attempt_code=self.attempt['attempt_code'])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].review_status, 'Clean')

        # now try to delete the record and make sure it was archived

        review.delete()

        records = ProctoredExamSoftwareSecureReviewHistory.objects.filter(attempt_code=self.attempt['attempt_code'])
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].review_status, 'Clean')
        self.assertEqual(records[1].review_status, 'Suspicious')

    @patch('edx_proctoring.constants.REQUIRE_FAILURE_SECOND_REVIEWS', True)
    def test_failure_submission(self):
        """
        Tests that a submission of a failed test and make sure that we
        don't automatically update the status to failure
        """
        test_payload = self.get_review_payload('Suspicious')
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
        self.assertEqual(review.review_status, 'Suspicious')

    @patch('edx_proctoring.constants.REQUIRE_FAILURE_SECOND_REVIEWS', True)
    def test_failure_submission_rejected(self):
        """
        Tests that a submission of a failed test and make sure that we
        don't automatically update the status to failure
        """
        test_payload = self.get_review_payload('Suspicious')
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
        self.assertEqual(review.review_status, 'Suspicious')

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

        # now delete the attempt, which puts it into the archive table
        remove_exam_attempt(self.attempt_id, requesting_user=self.user)

        review = ProctoredExamSoftwareSecureReview.objects.get(attempt_code=self.attempt['attempt_code'])

        # look at the attempt again, since it moved into Archived state
        # then it should still remain unchanged
        archived_attempt = ProctoredExamStudentAttemptHistory.objects.filter(
            attempt_code=self.attempt['attempt_code']
        ).latest('created')

        self.assertEqual(archived_attempt.status, attempt['status'])
        self.assertEqual(review.review_status, 'pass')
