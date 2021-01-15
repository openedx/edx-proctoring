"""
Django management command to update the is_attempt_active field on
ProctoredExamSoftwareSecureReview and ProctoredExamSoftwareSecureReviewHistory models
"""
import logging
import time

from django.core.management.base import BaseCommand

from edx_proctoring.models import (
    ProctoredExamSoftwareSecureReview,
    ProctoredExamSoftwareSecureReviewHistory,
    ProctoredExamStudentAttempt
)

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django Management command to update is_attempt_active field on review models
    """
    update_field_count = 0
    update_attempt_codes = []
    distinct_attempt_codes = set()

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch_size',
            action='store',
            dest='batch_size',
            type=int,
            default=300,
            help='Maximum number of attempt_codes to process. '
                 'This helps avoid locking the database while updating large amount of data.'
        )
        parser.add_argument(
            '--sleep_time',
            action='store',
            dest='sleep_time',
            type=int,
            default=10,
            help='Sleep time in seconds between update of batches'
        )

    def handle(self, *args, **options):
        """
        Management command entry point, simply call into the signal firing
        """

        batch_size = options['batch_size']
        sleep_time = options['sleep_time']

        log.info('Updating is_attempt_active field for current reviews.')
        for review in ProctoredExamSoftwareSecureReview.objects.filter(is_attempt_active=True):
            self.check_and_update(review, batch_size, sleep_time)

        log.info('Updating is_attempt_active field for archived reviews.')
        for archived_review in ProctoredExamSoftwareSecureReviewHistory.objects.filter(is_attempt_active=True):
            self.check_and_update(archived_review, batch_size, sleep_time, only_update_archives=True)

        if self.update_attempt_codes:
            log.info('Updating {} reviews'.format(len(self.update_attempt_codes)))
            self.bulk_update(self.update_attempt_codes, False)

    def check_and_update(self, review_object, size, sleep_time, only_update_archives=False):
        """
        Function to check if a review object should be updated, and updates accordingly
        """
        if review_object.attempt_code not in self.distinct_attempt_codes:
            if self.should_update(review_object):
                self.distinct_attempt_codes.add(review_object.attempt_code)
                self.update_attempt_codes.append(review_object.attempt_code)
                self.update_field_count += 1
                log.info('Adding review {} to be updated'.format(review_object.id))

            if self.update_field_count == size:
                log.info('Updating {} reviews'.format(size))
                self.bulk_update(self.update_attempt_codes, only_update_archives)
                self.update_field_count = 0
                self.update_attempt_codes = []
                time.sleep(sleep_time)

    def bulk_update(self, attempt_codes, only_update_archive):
        """
        Updates the is_attempt_active fields for all reviews who have an attempt code in attempt_codes
        """
        if not only_update_archive:
            reviews = ProctoredExamSoftwareSecureReview.objects.filter(attempt_code__in=attempt_codes)
            reviews.update(is_attempt_active=False)

        archived_reviews = ProctoredExamSoftwareSecureReviewHistory.objects.filter(attempt_code__in=attempt_codes)
        archived_reviews.update(is_attempt_active=False)

    def should_update(self, review_object):
        """
        Returns a boolean based on whether an attempt exists in the ProctoredExamStudentAttempt model
        """
        attempt_code = review_object.attempt_code
        try:
            ProctoredExamStudentAttempt.objects.get(attempt_code=attempt_code)
            return False
        except ProctoredExamStudentAttempt.DoesNotExist:
            return True
