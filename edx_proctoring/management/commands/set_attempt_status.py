"""
Django management command to manually set the attempt status for a user in a proctored exam
"""

from django.core.management.base import BaseCommand, CommandError

from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus


class Command(BaseCommand):
    """
    Django Management command to force a background check of all possible notifications
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '-a',
            '--attempt',
            metavar='ATTEMPT_ID',
            dest='attempt_id',
            help='attempt_id to change',
        )
        parser.add_argument(
            '-t',
            '--to',
            metavar='TO_STATUS',
            dest='to_status',
            help='the status to set',
        )

    def handle(self, *args, **options):
        """
        Management command entry point, simply call into the signal firiing
        """
        # pylint: disable=import-outside-toplevel
        from edx_proctoring.api import update_attempt_status

        attempt_id = options['attempt_id']
        to_status = options['to_status']

        msg = (
            u'Running management command to update '
            u'attempt {attempt_id} status to {to_status}'.format(
                attempt_id=attempt_id,
                to_status=to_status
            )
        )
        self.stdout.write(msg)

        if not ProctoredExamStudentAttemptStatus.is_valid_status(to_status):
            raise CommandError(u'{to_status} is not a valid attempt status!'.format(to_status=to_status))

        update_attempt_status(attempt_id, to_status)

        self.stdout.write('Completed!')
