"""
Django management command to update the status of a ProctoredExamStudentAttempt
based on the status of its corresponding ProctoredExamSoftwareSecureReview
"""
import datetime
import logging
import time

from django.core.management.base import BaseCommand

from edx_proctoring.models import ProctoredExamSoftwareSecureReview

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django Management command to update is_attempt_active field on review models
    """

    def add_arguments(self, parser):
        parser.add_argument(
          '--start_date_time',
          action='store',
          dest='start_date_time',
          type=str,
          help='First date time for reviews that we want to consider. Should be formatted as 2020-12-02 00:00:00.'
        )
        parser.add_argument(
          '--end_date_time',
          action='store',
          dest='end_date_time',
          type=str,
          help='Last date time for reviews that we want to consider. Should be formatted as 2020-12-02 00:00:00.'
        )
        parser.add_argument(
            '--batch_size',
            action='store',
            dest='batch_size',
            type=int,
            default=300,
            help='Maximum number of attempt_codes to process. '
                 'This helps avoid overloading the database while updating large amount of data.'
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
        review_start_date = datetime.datetime.strptime(options['start_date_time'], '%Y-%m-%d %H:%M:%S')
        review_end_date = datetime.datetime.strptime(options['end_date_time'], '%Y-%m-%d %H:%M:%S')

        reviews_in_date_range = ProctoredExamSoftwareSecureReview.objects.filter(
          modified__range=[review_start_date, review_end_date]
        )
        review_count = 0

        for review in reviews_in_date_range:
            review_id = review.id
            attempt_code = review.attempt_code
            log.info(
                'Saving review_id=%i for corresponding attempt_code=%s',
                review_id,
                attempt_code
            )
            review.save()
            review_count += 1

            if review_count == batch_size:
                review_count = 0
                time.sleep(sleep_time)
