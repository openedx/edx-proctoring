"""
Tests for the update_attempt_status_from_review management command
"""
from datetime import datetime, timedelta

import pytz

from django.core.management import call_command

from edx_proctoring.api import create_exam, create_exam_attempt, get_exam_attempt_by_id
from edx_proctoring.models import ProctoredExamSoftwareSecureReview
from edx_proctoring.runtime import set_runtime_service
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus, SoftwareSecureReviewStatus
from edx_proctoring.tests.test_services import MockCertificateService, MockCreditService, MockGradesService
from edx_proctoring.tests.utils import LoggedInTestCase


class SetAttemptActiveFieldTests(LoggedInTestCase):
    """
    Coverage of the update_attempt_status_from_review.py file
    """

    def setUp(self):
        """
        Build up test data
        """
        super().setUp()
        set_runtime_service('credit', MockCreditService())
        set_runtime_service('grades', MockGradesService())
        set_runtime_service('certificates', MockCertificateService())
        self.first_exam_id = create_exam(
            course_id='a/b/c',
            content_id='bar',
            exam_name='Test Exam 1',
            time_limit_mins=90
        )
        self.second_exam_id = create_exam(
            course_id='a/b/c',
            content_id='baz',
            exam_name='Test Exam 2',
            time_limit_mins=90
        )

        # create a first attempt and review
        self.first_attempt_id = create_exam_attempt(
            self.first_exam_id,
            self.user.id,
            taking_as_proctored=True
        )
        self.first_attempt = get_exam_attempt_by_id(self.first_attempt_id)
        self.first_attempt_review_object = ProctoredExamSoftwareSecureReview.objects.create(
            attempt_code=self.first_attempt['attempt_code'],
            exam_id=self.first_exam_id,
            student_id=self.user.id,
        )

        # create a second attempt and review
        self.second_attempt_id = create_exam_attempt(
            self.second_exam_id,
            self.user.id,
            taking_as_proctored=True
        )
        self.second_attempt = get_exam_attempt_by_id(self.second_attempt_id)
        self.second_attempt_review_object = ProctoredExamSoftwareSecureReview.objects.create(
            attempt_code=self.second_attempt['attempt_code'],
            exam_id=self.second_exam_id,
            student_id=self.user.id,
        )

        # update both reviews, and use update instead of save to avoid triggering a post_save signal
        ProctoredExamSoftwareSecureReview.objects.filter(id=self.first_attempt_review_object.id).update(
            review_status=SoftwareSecureReviewStatus.clean
        )
        ProctoredExamSoftwareSecureReview.objects.filter(id=self.second_attempt_review_object.id).update(
            review_status=SoftwareSecureReviewStatus.suspicious
        )

    def test_run_command(self):
        """
        Run the management command
        """
        # check status of attempts
        self.assertEqual(self.first_attempt['status'], ProctoredExamStudentAttemptStatus.created)
        self.assertEqual(self.second_attempt['status'], ProctoredExamStudentAttemptStatus.created)
        # check status of reviews
        first_review = ProctoredExamSoftwareSecureReview.objects.get(id=self.first_attempt_review_object.id)
        self.assertEqual(first_review.review_status, SoftwareSecureReviewStatus.clean)
        second_review = ProctoredExamSoftwareSecureReview.objects.get(id=self.second_attempt_review_object.id)
        self.assertEqual(second_review.review_status, SoftwareSecureReviewStatus.suspicious)

        start_time = datetime.now(pytz.UTC) - timedelta(minutes=60)
        end_time = datetime.now(pytz.UTC) + timedelta(minutes=60)

        # run command
        call_command(
            'update_attempt_status_from_review',
            batch_size=2,
            sleep_time=0,
            start_date_time=start_time.strftime('%Y-%m-%d %H:%M:%S'),
            end_date_time=end_time.strftime('%Y-%m-%d %H:%M:%S')
        )

        # check that attempt statuses has been updated
        updated_first_attempt = get_exam_attempt_by_id(self.first_attempt_id)
        self.assertEqual(updated_first_attempt['status'], ProctoredExamStudentAttemptStatus.verified)
        updated_second_attempt = get_exam_attempt_by_id(self.second_attempt_id)
        self.assertEqual(updated_second_attempt['status'], ProctoredExamStudentAttemptStatus.second_review_required)
