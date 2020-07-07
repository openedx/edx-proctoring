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
            '-e',
            '--exam',
            metavar='EXAM_ID',
            dest='exam_id',
            help='exam_id to change',
        )
        parser.add_argument(
            '-u',
            '--user',
            metavar='USER',
            dest='user_id',
            help='user_id of user to affect',
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
        from edx_proctoring.api import (
            update_attempt_status,
            get_exam_by_id
        )

        exam_id = options['exam_id']
        user_id = options['user_id']
        to_status = options['to_status']

        msg = (
            u'Running management command to update user {user_id} '
            u'attempt status on exam_id {exam_id} to {to_status}'.format(
                user_id=user_id,
                exam_id=exam_id,
                to_status=to_status
            )
        )
        self.stdout.write(msg)

        if not ProctoredExamStudentAttemptStatus.is_valid_status(to_status):
            raise CommandError(u'{to_status} is not a valid attempt status!'.format(to_status=to_status))

        # get exam, this will throw exception if does not exist, so let it bomb out
        get_exam_by_id(exam_id)

        update_attempt_status(exam_id, user_id, to_status)

        self.stdout.write('Completed!')
