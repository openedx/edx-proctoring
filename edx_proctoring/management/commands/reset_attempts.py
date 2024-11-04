"""
Django management command to delete attempts. This command should only be used
to remove attempts that have not been started or completed, as it will not
reset problem state or grade overrides.
"""
import csv
import logging
import time

from django.core.management.base import BaseCommand

from edx_proctoring.models import ProctoredExamStudentAttempt

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django Management command to delete attempts.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '-p',
            '--file_path',
            metavar='file_path',
            dest='file_path',
            required=True,
            help='Path to file.'
        )
        parser.add_argument(
            '--batch_size',
            action='store',
            dest='batch_size',
            type=int,
            default=300,
            help='Maximum number of attempt_ids to process. '
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
        file_path = options['file_path']

        with open(file_path, 'r') as file:
            ids_to_delete = file.readlines()

        total_deleted = 0

        for i in range(0, len(ids_to_delete), batch_size):
            batch_to_delete = ids_to_delete[i:i + batch_size]

            delete_queryset = ProctoredExamStudentAttempt.objects.filter(
                id__in=batch_to_delete
            )
            deleted_count, _ = delete_queryset.delete()

            total_deleted += deleted_count

            log.info(f'{deleted_count} attempts deleted.')
            time.sleep(sleep_time)


        log.info(f'Job completed. {total_deleted} attempts deleted.')
