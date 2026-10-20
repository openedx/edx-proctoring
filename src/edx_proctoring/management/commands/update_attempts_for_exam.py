"""
Django management command to re-trigger the status update of a ProctoredExamStudentAttempt
for a specific proctored exam.
"""

import logging
import time

from django.core.management.base import BaseCommand

from edx_proctoring.api import update_attempt_status
from edx_proctoring.models import ProctoredExamStudentAttempt

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django Management command to update is_attempt_active field on review models
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch_size',
            action='store',
            dest='batch_size',
            type=int,
            default=300,
            help='Maximum number of attempts to process. '
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

        parser.add_argument(
            '--exam_id',
            action='store',
            dest='exam_id',
            type=int,
            help='Exam ID to process attempts for.'
        )

    def handle(self, *args, **options):
        """
        Management command entry point, simply call into the signal firing
        """

        batch_size = options['batch_size']
        sleep_time = options['sleep_time']
        exam_id = options['exam_id']

        # get all attempts for specific exam id
        exam_attempts = ProctoredExamStudentAttempt.objects.filter(proctored_exam_id=exam_id)

        attempt_count = 0

        # for each of those attempts, get id and status
        for attempt in exam_attempts:
            current_status = attempt.status
            current_id = attempt.id

            log.info(
                'Triggering attempt status update for attempt_id=%(attempt_id)s with status=%(status)s',
                {'attempt_id': current_id, 'status': current_status}
            )
            # need to use update_attempt_status because this function will trigger grade + credit updates
            update_attempt_status(current_id, current_status)
            attempt_count += 1

            if attempt_count == batch_size:
                attempt_count = 0
                time.sleep(sleep_time)
