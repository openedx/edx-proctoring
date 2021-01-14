"""
Tests for the set_is_attempt_active management command
"""

from django.core.management import call_command

from edx_proctoring.api import create_exam, create_exam_attempt, get_exam_attempt_by_id, remove_exam_attempt
from edx_proctoring.models import ProctoredExamSoftwareSecureReview, ProctoredExamSoftwareSecureReviewHistory
from edx_proctoring.runtime import set_runtime_service
from edx_proctoring.tests.test_services import MockCertificateService, MockCreditService, MockGradesService
from edx_proctoring.tests.utils import LoggedInTestCase


class SetAttemptActiveFieldTests(LoggedInTestCase):
    """
    Coverage of the set_attempt_status.py file
    """

    def setUp(self):
        """
        Build up test data
        """
        super().setUp()
        set_runtime_service('credit', MockCreditService())
        set_runtime_service('grades', MockGradesService())
        set_runtime_service('certificates', MockCertificateService())
        self.exam_id = create_exam(
            course_id='foo',
            content_id='bar',
            exam_name='Test Exam',
            time_limit_mins=90
        )

        self.attempt_id = create_exam_attempt(
            self.exam_id,
            self.user.id,
            taking_as_proctored=True
        )

        self.attempt = get_exam_attempt_by_id(self.attempt_id)

        ProctoredExamSoftwareSecureReview.objects.create(
            attempt_code=self.attempt['attempt_code'],
            exam_id=self.exam_id,
            student_id=self.user.id,
        )

    def test_run_command(self):
        """
        Run the management command
        """

        # check that review is there
        reviews = ProctoredExamSoftwareSecureReview.objects.all()
        self.assertEqual(len(reviews), 1)

        archive_reviews = ProctoredExamSoftwareSecureReviewHistory.objects.all()
        self.assertEqual(len(archive_reviews), 0)

        # archive attempt
        remove_exam_attempt(self.attempt_id, requesting_user=self.user)

        # check that field is false
        review = ProctoredExamSoftwareSecureReview.objects.get(attempt_code=self.attempt['attempt_code'])
        self.assertFalse(review.is_attempt_active)

        # change field back to true for testing
        review.is_attempt_active = True
        review.save()

        # expect there to be two archived reviews, one from removing the attempt, and one because we changed a field
        archive_reviews = ProctoredExamSoftwareSecureReviewHistory.objects.all()
        self.assertEqual(len(archive_reviews), 2)

        call_command(
            'set_is_attempt_active',
            batch_size=5,
            sleep_time=0
        )

        review = ProctoredExamSoftwareSecureReview.objects.get(attempt_code=self.attempt['attempt_code'])
        self.assertFalse(review.is_attempt_active)

        archive_reviews = ProctoredExamSoftwareSecureReviewHistory.objects.filter(is_attempt_active=False)
        self.assertEqual(len(archive_reviews), 2)
