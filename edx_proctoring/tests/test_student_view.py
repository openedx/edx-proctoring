# coding=utf-8
# pylint: disable=too-many-lines, invalid-name

"""
All tests for the api.py
"""

import itertools
from datetime import datetime, timedelta

import ddt
import pytz
from freezegun import freeze_time
from mock import MagicMock, patch

from edx_proctoring.api import (
    add_allowance_for_user,
    get_exam_attempt,
    get_exam_by_id,
    get_student_view,
    update_attempt_status,
    update_exam
)
from edx_proctoring.models import ProctoredExam, ProctoredExamStudentAllowance, ProctoredExamStudentAttempt
from edx_proctoring.runtime import set_runtime_service
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus
from edx_proctoring.tests import mock_perm

from .test_services import MockCreditServiceNone, MockCreditServiceWithCourseEndDate
from .utils import ProctoredExamTestCase


@patch('django.urls.reverse', MagicMock)
@ddt.ddt
class ProctoredExamStudentViewTests(ProctoredExamTestCase):
    """
    All tests for the student view
    """

    def setUp(self):
        """
        Build out test harnessing
        """
        super(ProctoredExamStudentViewTests, self).setUp()

        # Messages for get_student_view
        self.start_an_exam_msg = 'This exam is proctored'
        self.exam_expired_msg = 'The due date for this exam has passed'
        self.timed_exam_msg = u'{exam_name} is a Timed Exam'
        self.timed_exam_submitted = 'You have submitted your timed exam.'
        self.timed_exam_expired = 'The time allotted for this exam has expired.'
        self.timed_exam_submitted_expired = 'The time allotted for this exam has expired. Your exam has been submitted'
        self.submitted_timed_exam_msg_with_due_date = 'After the due date has passed,'
        self.exam_time_expired_msg = 'You did not complete the exam in the allotted time'
        self.exam_time_error_msg = 'A technical error has occurred with your proctored exam'
        self.chose_proctored_exam_msg = 'Set up and start your proctored exam'
        self.proctored_exam_optout_msg = 'Take this exam without proctoring'
        self.proctored_exam_completed_msg = 'Are you sure you want to end your proctored exam'
        self.proctored_exam_submitted_msg = 'You have submitted this proctored exam for review'
        self.take_exam_without_proctoring_msg = 'Take this exam without proctoring'
        self.ready_to_start_msg = 'Important'
        self.wrong_browser_msg = 'The content of this exam can only be viewed'
        self.footer_msg = 'About Proctored Exams'
        self.timed_footer_msg = 'Can I request additional time to complete my exam?'
        self.wait_deadline_msg = "The result will be visible after"
        self.inactive_account_msg = "You have not activated your account"

    def _render_exam(self, content_id, context_overrides=None):
        """
        Renders a test exam.
        """
        exam = get_exam_by_id(content_id)
        context = {
            'is_proctored': True,
            'allow_proctoring_opt_out': True,
            'display_name': self.exam_name,
            'default_time_limit_mins': 90,
            'is_practice_exam': False,
            'credit_state': {
                'enrollment_mode': 'verified',
                'credit_requirement_status': [],
            },
            'verification_status': 'approved',
            'verification_url': '/reverify',
        }
        if context_overrides:
            context.update(context_overrides)
        return get_student_view(
            user_id=self.user_id,
            course_id=exam['course_id'],
            content_id=exam['content_id'],
            context=context,
        )

    def render_proctored_exam(self, context_overrides=None):
        """
        Renders a test proctored exam.
        """
        exam_context_overrides = {
            'is_proctored': True,
            'allow_proctoring_opt_out': True,
            'is_practice_exam': False,
            'credit_state': {
                'enrollment_mode': 'verified',
                'credit_requirement_status': [],
            },
            'verification_status': 'approved',
            'verification_url': '/reverify',
        }
        if context_overrides:
            exam_context_overrides.update(context_overrides)
        return self._render_exam(
            self.proctored_exam_id,
            context_overrides=exam_context_overrides
        )

    def render_practice_exam(self, context_overrides=None):
        """
        Renders a test practice exam.
        """
        exam_context_overrides = {
            'is_proctored': True,
            'is_practice_exam': True,
        }
        if context_overrides:
            exam_context_overrides.update(context_overrides)
        return self._render_exam(
            self.practice_exam_id,
            context_overrides=exam_context_overrides
        )

    def render_onboarding_exam(self):
        """
        Renders a test practice exam.
        """
        return self._render_exam(self.onboarding_exam_id)

    def test_get_student_view(self):
        """
        Test for get_student_view prompting the user to take the exam
        as a timed exam or a proctored exam.
        """
        rendered_response = self.render_proctored_exam()
        self.assertIn(
            'data-exam-id="{proctored_exam_id}"'.format(proctored_exam_id=self.proctored_exam_id),
            rendered_response
        )
        self.assertIn(self.start_an_exam_msg.format(exam_name=self.exam_name), rendered_response)

        # try practice exam variant
        rendered_response = self.render_practice_exam()
        self.assertIn(
            'sequence proctored-exam entrance',
            rendered_response
        )

    def test_get_honor_view_with_practice_exam(self):
        """
        Test for get_student_view prompting when the student is enrolled in non-verified
        track for a practice exam, this should return not None, meaning
        student will see proctored content
        """
        rendered_response = self.render_practice_exam({
            'credit_state': {
                'enrollment_mode': 'honor',
            },
        })
        self.assertIsNotNone(rendered_response)

    @ddt.data(
        (None, 'Make sure you are on a computer with a webcam, and that you have valid photo identification'),
        ('pending', 'Your verification is pending'),
        ('must_reverify', 'Your verification attempt failed'),
        ('expired', 'Your verification has expired'),
    )
    @ddt.unpack
    def test_verification_status(self, verification_status, expected_message):
        """
        This test asserts that the correct id verification message is shown
        to the user when they choose to take a proctored exam.
        """
        self._create_unstarted_exam_attempt()
        rendered_response = self.render_proctored_exam({
            'verification_status': verification_status,
        })
        self.assertIn(expected_message, rendered_response)

    def test_proctored_only_entrance(self):
        """
        This test verifies that learners are not given the option to take
        an exam without proctoring if allow_proctoring_opt_out is false.
        """
        rendered_response = self.render_proctored_exam({
            'allow_proctoring_opt_out': False,
        })
        self.assertNotIn(self.take_exam_without_proctoring_msg, rendered_response)

    @ddt.data(
        'pending',
        'failed',
    )
    def test_proctored_only_with_prereqs(self, status):
        """
        This test verifies that learners are not given the option to take
        an exam without proctoring when they have prerequisites and when
        the setting allow_proctoring_opt_out is false.
        """
        rendered_response = self.render_proctored_exam({
            'allow_proctoring_opt_out': False,
            'credit_state': {
                'enrollment_mode': 'verified',
                'credit_requirement_status': [
                    {
                        'namespace': 'proctored_exam',
                        'name': 'foo',
                        'display_name': 'Mock Requirement',
                        'status': status,
                        'order': 0
                    }
                ]
            },
        })
        self.assertNotIn(self.take_exam_without_proctoring_msg, rendered_response)

    @ddt.data(
        ('reverification', None, 'The following prerequisites are in a <strong>pending</strong> state', True),
        ('reverification', 'pending', 'The following prerequisites are in a <strong>pending</strong> state', True),
        ('reverification', 'failed', 'You did not satisfy the following prerequisites', True),
        ('reverification', 'satisfied', 'To be eligible for credit', False),
        ('reverification', 'declined', None, False),
        ('proctored_exam', None, 'The following prerequisites are in a <strong>pending</strong> state', True),
        ('proctored_exam', 'pending', 'The following prerequisites are in a <strong>pending</strong> state', True),
        ('proctored_exam', 'failed', 'You did not satisfy the following prerequisites', True),
        ('proctored_exam', 'satisfied', 'To be eligible for credit', False),
        ('proctored_exam', 'declined', None, False),
        ('grade', 'failed', 'To be eligible for credit', False),
        # this is nonsense, but let's double check it
        ('grade', 'declined', 'To be eligible for credit', False),
    )
    @ddt.unpack
    def test_prereq_scenarios(self, namespace, req_status, expected_content, should_see_prereq):
        """
        This test asserts that proctoring will not be displayed under the following
        conditions:

        - Verified student has not completed all 'reverification' requirements
        """

        # user hasn't attempted reverifications
        rendered_response = self.render_proctored_exam({
            'credit_state': {
                'enrollment_mode': 'verified',
                'credit_requirement_status': [
                    {
                        'namespace': namespace,
                        'name': 'foo',
                        'display_name': 'Foo Requirement',
                        'status': req_status,
                        'order': 0
                    }
                ]
            },
        })

        if expected_content:
            self.assertIn(expected_content, rendered_response)
        else:
            self.assertIsNone(rendered_response)

        if req_status == 'declined' and not expected_content:
            # also we should have auto-declined if a pre-requisite was declined
            attempt = get_exam_attempt(self.proctored_exam_id, self.user_id)
            self.assertIsNotNone(attempt)
            self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.declined)

        if should_see_prereq:
            self.assertIn('Foo Requirement', rendered_response)

    def test_student_view_non_student(self):
        """
        Make sure that if we ask for a student view if we are not in a student role,
        then we don't see any proctoring views
        """

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id,
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90
            },
            user_role='staff'
        )
        self.assertIsNone(rendered_response)

    def test_wrong_exam_combo(self):
        """
        Verify that we get a None back when rendering a view
        for a practice, non-proctored exam. This is unsupported.
        """

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id='foo',
            content_id='bar',
            context={
                'is_proctored': False,
                'is_practice_exam': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90,
                'hide_after_due': False,
            },
            user_role='student'
        )
        self.assertIsNone(rendered_response)

    def test_proctored_exam_passed_end_date(self):
        """
        Verify that we get a None back on a proctored exam
        if the course end date is passed
        """
        credit_state = MockCreditServiceWithCourseEndDate().get_credit_state(self.user_id, 'foo', True)

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id='foo',
            content_id='bar',
            context={
                'is_proctored': True,
                'is_practice_exam': False,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90,
                'due_date': None,
                'hide_after_due': False,
                'credit_state': credit_state,
            },
            user_role='student'
        )
        self.assertIsNone(rendered_response)

    def test_practice_exam_passed_end_date(self):
        """
        Verify that we get a None back on a practice exam
        if the course end date is passed
        """
        credit_state = MockCreditServiceWithCourseEndDate().get_credit_state(self.user_id, 'foo', True)

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id='foo',
            content_id='bar',
            context={
                'is_proctored': True,
                'is_practice_exam': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90,
                'due_date': None,
                'hide_after_due': False,
                'credit_state': credit_state,
            },
            user_role='student'
        )
        self.assertIsNone(rendered_response)

    def test_get_disabled_student_view(self):
        """
        Assert that a disabled proctored exam will not override the
        student_view
        """
        self.assertIsNone(
            get_student_view(
                user_id=self.user_id,
                course_id=self.course_id,
                content_id=self.disabled_content_id,
                context={
                    'is_proctored': True,
                    'display_name': self.exam_name,
                    'default_time_limit_mins': 90
                }
            )
        )

    def test_student_response_without_credit_state(self):
        """
        Test that response is not None for users who are not enrolled.
        """
        set_runtime_service('credit', MockCreditServiceNone())
        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id,
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90
            },
            user_role='student'
        )
        self.assertIsNotNone(rendered_response)

    @ddt.data(False, True)
    def test_get_studentview_unstarted_exam(self, allow_proctoring_opt_out):
        """
        Test for get_student_view proctored exam which has not started yet.
        """

        self._create_unstarted_exam_attempt()

        # Verify that the option to skip proctoring is shown if allowed
        rendered_response = self.render_proctored_exam({
            'allow_proctoring_opt_out': allow_proctoring_opt_out,
        })
        self.assertIn(self.chose_proctored_exam_msg, rendered_response)
        if allow_proctoring_opt_out:
            self.assertIn(self.proctored_exam_optout_msg, rendered_response)
        else:
            self.assertNotIn(self.proctored_exam_optout_msg, rendered_response)

        # Now make sure content remains the same if the status transitions
        # to 'download_software_clicked'.
        update_attempt_status(
            self.proctored_exam_id,
            self.user_id,
            ProctoredExamStudentAttemptStatus.download_software_clicked
        )
        rendered_response = self.render_proctored_exam()
        self.assertIn(self.chose_proctored_exam_msg, rendered_response)
        self.assertIn(self.proctored_exam_optout_msg, rendered_response)

    def test_get_studentview_unstarted_practice_exam(self):
        """
        Test for get_student_view Practice exam which has not started yet.
        """
        self._create_unstarted_exam_attempt(is_practice=True)
        rendered_response = self.render_practice_exam()
        self.assertIn(self.chose_proctored_exam_msg, rendered_response)
        self.assertNotIn(self.proctored_exam_optout_msg, rendered_response)

    def test_declined_attempt(self):
        """
        Make sure that a declined attempt does not show proctoring
        """
        attempt_obj = self._create_unstarted_exam_attempt()
        attempt_obj.status = ProctoredExamStudentAttemptStatus.declined
        attempt_obj.save()

        rendered_response = self.render_proctored_exam()
        self.assertIsNone(rendered_response)

    def test_get_studentview_ready(self):
        """
        Assert that we get the right content
        when the exam is ready to be started
        """
        exam_attempt = self._create_started_exam_attempt()
        exam_attempt.status = ProctoredExamStudentAttemptStatus.ready_to_start
        exam_attempt.save()

        rendered_response = self.render_proctored_exam()
        self.assertIn(self.ready_to_start_msg, rendered_response)

    def test_get_studentview_started_exam(self):
        """
        Test for get_student_view proctored exam which has started.
        """
        self._create_started_exam_attempt()
        rendered_response = self.render_proctored_exam()
        self.assertIsNone(rendered_response)

    @patch('edx_proctoring.api.get_backend_provider')
    def test_get_studentview_started_from_wrong_browser(self, mocked_get_backend):
        """
        Test for get_student_view proctored exam as viewed from an
        insecure browser.
        """
        self._create_started_exam_attempt()
        mocked_get_backend.return_value.should_block_access_to_exam_material.return_value = True
        rendered_response = self.render_proctored_exam()
        self.assertIn(self.wrong_browser_msg, rendered_response)

    def test_get_studentview_started_practice_exam(self):
        """
        Test for get_student_view practice proctored exam which has started.
        """
        self._create_started_practice_exam_attempt()
        rendered_response = self.render_practice_exam()
        self.assertIsNone(rendered_response)

    @patch('edx_proctoring.api.get_backend_provider')
    def test_get_studentview_practice_from_wrong_browser(self, mocked_get_backend):
        """
        Test for get_student_view practice proctored exam as viewed
        from an insecure browser.
        """
        self._create_started_practice_exam_attempt()
        mocked_get_backend.return_value.should_block_access_to_exam_material.return_value = True
        # Need to make sure our mock doesn't behave like a different
        # type of backend before we reach to code under test
        mocked_get_backend.return_value.supports_onboarding = False
        rendered_response = self.render_practice_exam()
        self.assertIn(self.wrong_browser_msg, rendered_response)

    def test_get_studentview_started_timed_exam(self):
        """
        Test for get_student_view timed exam which has started.
        """
        self._create_started_exam_attempt(is_proctored=False)

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id_timed,
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90
            }
        )
        self.assertIsNone(rendered_response)

    @ddt.data(True, False)
    def test_get_studentview_long_limit(self, under_exception):
        """
        Test for hide_extra_time_footer on exams with > 20 hours time limit
        """
        exam_id = self._create_exam_with_due_time(is_proctored=False, )
        if under_exception:
            update_exam(exam_id, time_limit_mins=((20 * 60)))  # exactly 20 hours
        else:
            update_exam(exam_id, time_limit_mins=((20 * 60) + 1))  # 1 minute greater than 20 hours
        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id_for_exam_with_due_date,
            context={
                'is_proctored': False,
                'display_name': self.exam_name,
            }
        )
        if under_exception:
            self.assertIn(self.timed_footer_msg, rendered_response)
        else:
            self.assertNotIn(self.timed_footer_msg, rendered_response)

    @ddt.data(
        (datetime.now(pytz.UTC) + timedelta(days=1), False),
        (datetime.now(pytz.UTC) - timedelta(days=1), False),
        (datetime.now(pytz.UTC) - timedelta(days=1), True),
    )
    @ddt.unpack
    def test_get_studentview_submitted_timed_exam_with_past_due_date(self, due_date, hide_after_due):
        """
        Test for get_student_view timed exam with the due date.
        """

        # exam is created with due datetime which has already passed
        exam_id = self._create_exam_with_due_time(is_proctored=False, due_date=due_date)
        if hide_after_due:
            update_exam(exam_id, hide_after_due=hide_after_due)

        # now create the timed_exam attempt in the submitted state
        self._create_exam_attempt(exam_id, status='submitted')

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id_for_exam_with_due_date,
            context={
                'is_proctored': False,
                'display_name': self.exam_name,
                'default_time_limit_mins': 10,
                'due_date': due_date,
            }
        )
        if datetime.now(pytz.UTC) < due_date:
            self.assertIn(self.timed_exam_submitted, rendered_response)
            self.assertIn(self.submitted_timed_exam_msg_with_due_date, rendered_response)
        elif hide_after_due:
            self.assertIn(self.timed_exam_submitted, rendered_response)
            self.assertNotIn(self.submitted_timed_exam_msg_with_due_date, rendered_response)
        else:
            self.assertIsNone(rendered_response)

    @ddt.data(
        (False, 'submitted', True, 1),
        (True, 'verified', False, 1),
        (False, 'submitted', True, 0),
        (True, 'verified', False, 0),
    )
    @ddt.unpack
    def test_get_studentview_submitted_timed_exam_with_grace_period(self, is_proctored, status, is_timed, graceperiod):
        """
        Test the student view for a submitted exam, after the
        due date, when grace period is in effect.

        Scenario: Given an exam with past due
        When a user submission exists for that exam
        Then get the user view with an active grace period
        Then user will not be able to see exam content
        And a banner will be visible
        If the grace period is past due
        For timed exam, user will not see any banner
        And user will be able to see exam contents
        And For proctored exam, view exam button will be visible
        """
        due_date = datetime.now(pytz.UTC) - timedelta(days=1)
        context = {
            'is_proctored': is_proctored,
            'display_name': self.exam_name,
            'default_time_limit_mins': 10,
            'due_date': due_date,
            'grace_period': timedelta(days=2)
        }
        exam_id = self._create_exam_with_due_time(
            is_proctored=is_proctored, due_date=due_date
        )
        self._create_exam_attempt(exam_id, status=status)
        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id_for_exam_with_due_date,
            context=context
        )
        self.assertIn(self.wait_deadline_msg, rendered_response)

        # This pop is required as the student view updates the
        # context dict that was passed in the arguments
        context.pop('wait_deadline')

        context['grace_period'] = timedelta(days=graceperiod)
        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id_for_exam_with_due_date,
            context=context
        )
        if is_timed:
            self.assertIsNone(rendered_response)
        else:
            self.assertNotIn(self.wait_deadline_msg, rendered_response)

    def test_get_studentview_acknowledged_proctored_exam_with_grace_period(self):
        """
        Verify the student view for an acknowledge proctored exam with an active
        grace period.

        Given a proctored exam with a past due date and an inactive grace period
        And a verified user submission exists for that exam
        When user navigates to the exam
        Then the wait deadline part is not shown
        If the attempt is acknowledged to view the exam result
        Then visiting the page again will not show any banner
        When an active grace period is applied
        Then navigating to the exam will not exam content
        And the wait deadline will be shown
        """
        due_date = datetime.now(pytz.UTC) - timedelta(days=1)
        context = {
            'is_proctored': True,
            'display_name': self.exam_name,
            'default_time_limit_mins': 10,
            'due_date': due_date,
            'grace_period': timedelta(days=0)
        }
        exam_id = self._create_exam_with_due_time(
            is_proctored=True, due_date=due_date
        )
        attempt = self._create_exam_attempt(exam_id, status='verified')
        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id_for_exam_with_due_date,
            context=context
        )
        self.assertNotIn(self.wait_deadline_msg, rendered_response)
        attempt.is_status_acknowledged = True
        attempt.save()
        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id_for_exam_with_due_date,
            context=context
        )
        self.assertIsNone(rendered_response)
        context['grace_period'] = timedelta(days=2)
        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id_for_exam_with_due_date,
            context=context
        )
        self.assertIn(self.wait_deadline_msg, rendered_response)

    def test_proctored_exam_attempt_with_past_due_datetime(self):
        """
        Test for get_student_view for proctored exam with past due datetime
        """

        due_date = datetime.now(pytz.UTC) + timedelta(days=1)

        # exam is created with due datetime which has already passed
        self._create_exam_with_due_time(due_date=due_date)

        # due_date is exactly after 24 hours, if student arrives after 2 days
        # then he can not attempt the proctored exam
        reset_time = due_date + timedelta(days=2)
        with freeze_time(reset_time):
            rendered_response = get_student_view(
                user_id=self.user_id,
                course_id=self.course_id,
                content_id=self.content_id_for_exam_with_due_date,
                context={
                    'is_proctored': True,
                    'display_name': self.exam_name,
                    'default_time_limit_mins': self.default_time_limit,
                    'due_date': due_date,
                }
            )
            self.assertIn(self.exam_expired_msg, rendered_response)

            # call the view again, because the first call set the exam attempt to 'expired'
            # this second call will render the view based on the state
            rendered_response = get_student_view(
                user_id=self.user_id,
                course_id=self.course_id,
                content_id=self.content_id_for_exam_with_due_date,
                context={
                    'is_proctored': True,
                    'is_practice_exam': True,
                    'display_name': self.exam_name,
                    'default_time_limit_mins': self.default_time_limit,
                    'due_date': due_date,
                }
            )
            self.assertIn(self.exam_expired_msg, rendered_response)

    def test_timed_exam_attempt_with_past_due_datetime(self):
        """
        Test for get_student_view for timed exam with past due datetime
        """

        due_date = datetime.now(pytz.UTC) + timedelta(days=1)

        # exam is created with due datetime which has already passed
        self._create_exam_with_due_time(
            due_date=due_date,
            is_proctored=False
        )

        # due_date is exactly after 24 hours, if student arrives after 2 days
        # then he can not attempt the proctored exam
        reset_time = due_date + timedelta(days=2)
        with freeze_time(reset_time):
            rendered_response = get_student_view(
                user_id=self.user_id,
                course_id=self.course_id,
                content_id=self.content_id_for_exam_with_due_date,
                context={
                    'is_proctored': False,
                    'display_name': self.exam_name,
                    'default_time_limit_mins': self.default_time_limit,
                    'due_date': due_date,
                }
            )
            self.assertIn(self.exam_expired_msg, rendered_response)

            # call the view again, because the first call set the exam attempt to 'expired'
            # this second call will render the view based on the state
            rendered_response = get_student_view(
                user_id=self.user_id,
                course_id=self.course_id,
                content_id=self.content_id_for_exam_with_due_date,
                context={
                    'is_proctored': True,
                    'is_practice_exam': True,
                    'display_name': self.exam_name,
                    'default_time_limit_mins': self.default_time_limit,
                    'due_date': due_date,
                }
            )
            self.assertIn(self.exam_expired_msg, rendered_response)

    @patch.dict('django.conf.settings.PROCTORING_SETTINGS', {'ALLOW_TIMED_OUT_STATE': True})
    def test_get_studentview_timedout(self):
        """
        Verifies that if we call get_studentview when the timer has expired
        it will automatically state transition into timed_out
        """

        self._create_started_exam_attempt()

        reset_time = datetime.now(pytz.UTC) + timedelta(days=1)
        with freeze_time(reset_time):
            with self.assertRaises(NotImplementedError):
                self.render_proctored_exam()

    def test_get_studentview_submitted_status(self):
        """
        Test for get_student_view proctored exam which has been submitted.
        """
        exam_attempt = self._create_started_exam_attempt()
        exam_attempt.status = ProctoredExamStudentAttemptStatus.submitted
        exam_attempt.save()

        rendered_response = self.render_proctored_exam()
        self.assertIn(self.proctored_exam_submitted_msg, rendered_response)

        # now make sure if this status transitions to 'second_review_required'
        # the student will still see a 'submitted' message
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            exam_attempt.user_id,
            ProctoredExamStudentAttemptStatus.second_review_required
        )
        rendered_response = self.render_proctored_exam()
        self.assertIn(self.proctored_exam_submitted_msg, rendered_response)

    def test_get_studentview_submitted_status_with_duedate(self):
        """
        Test for get_student_view proctored exam which has been submitted
        And due date has passed
        """
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=30,
            is_proctored=True,
            is_active=True,
            due_date=datetime.now(pytz.UTC) + timedelta(minutes=40)
        )

        exam_attempt = ProctoredExamStudentAttempt.objects.create(
            proctored_exam=proctored_exam,
            user=self.user,
            allowed_time_limit_mins=30,
            taking_as_proctored=True,
            external_id=proctored_exam.external_id,
            status=ProctoredExamStudentAttemptStatus.submitted,
        )

        # due date is after 10 minutes
        reset_time = datetime.now(pytz.UTC) + timedelta(minutes=20)
        with freeze_time(reset_time):
            rendered_response = get_student_view(
                user_id=self.user.id,
                course_id='a/b/c',
                content_id='test_content',
                context={
                    'is_proctored': True,
                    'display_name': 'Test Exam',
                    'default_time_limit_mins': 30
                }
            )
            self.assertIn(self.proctored_exam_submitted_msg, rendered_response)
            exam_attempt.is_status_acknowledged = True
            exam_attempt.save()

            rendered_response = get_student_view(
                user_id=self.user.id,
                course_id='a/b/c',
                content_id='test_content',
                context={
                    'is_proctored': True,
                    'display_name': 'Test Exam',
                    'default_time_limit_mins': 30
                }
            )
            self.assertIsNotNone(rendered_response)

    @ddt.data(
        *itertools.product(
            (
                ProctoredExamStudentAttemptStatus.created,
                ProctoredExamStudentAttemptStatus.download_software_clicked,
                ProctoredExamStudentAttemptStatus.ready_to_start,
                ProctoredExamStudentAttemptStatus.started,
                ProctoredExamStudentAttemptStatus.ready_to_submit,
                ProctoredExamStudentAttemptStatus.declined,
                ProctoredExamStudentAttemptStatus.timed_out,
                ProctoredExamStudentAttemptStatus.submitted,
            ),
            (
                True,
                False,
            )
        )
    )
    @ddt.unpack
    def test_get_student_view_with_attempt_status_and_past_duedate(self, attempt_status, is_proctored):
        """
        Test for get_student_view on proctored or timed exams which have student attempt,
        And due date has passed
        """
        due_date = datetime.now(pytz.UTC) + timedelta(minutes=40)
        # due date is 10 minutes before testing time
        reset_time = datetime.now(pytz.UTC) + timedelta(minutes=50)

        created_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=30,
            is_proctored=is_proctored,
            is_active=True,
            due_date=due_date,
            hide_after_due=True
        )

        exam_attempt = ProctoredExamStudentAttempt.objects.create(
            proctored_exam=created_exam,
            user=self.user,
            allowed_time_limit_mins=30,
            taking_as_proctored=is_proctored,
            external_id=created_exam.external_id,
            status=attempt_status
        )

        if attempt_status == ProctoredExamStudentAttemptStatus.submitted:
            exam_attempt.started_at = datetime.now(pytz.UTC)
            exam_attempt.completed_at = reset_time
            exam_attempt.save()

        with freeze_time(reset_time):
            if attempt_status == ProctoredExamStudentAttemptStatus.timed_out:
                with self.assertRaises(NotImplementedError):
                    get_student_view(
                        user_id=self.user.id,
                        course_id='a/b/c',
                        content_id='test_content',
                        context={
                            'is_proctored': is_proctored,
                            'display_name': 'Test Exam',
                            'default_time_limit_mins': 30,
                            'due_date': due_date,
                        }
                    )
                return

            rendered_response = get_student_view(
                user_id=self.user.id,
                course_id='a/b/c',
                content_id='test_content',
                context={
                    'is_proctored': is_proctored,
                    'display_name': 'Test Exam',
                    'default_time_limit_mins': 30,
                    'due_date': due_date
                }
            )

            if attempt_status == ProctoredExamStudentAttemptStatus.submitted:
                expected_message = self.timed_exam_submitted_expired
                if is_proctored:
                    expected_message = self.proctored_exam_submitted_msg
                self.assertIn(expected_message, rendered_response)
            elif attempt_status == ProctoredExamStudentAttemptStatus.declined:
                self.assertIsNone(rendered_response)
            else:
                self.assertIn(self.exam_expired_msg, rendered_response)

    def test_get_no_perm_view(self):
        """
        Test for get_student_view prompting when the student does not have permission
        to view proctored exams, this should return None
        (For edx-proctoring tests, only authenticated students have the permission)
        """
        with mock_perm('edx_proctoring.can_take_proctored_exam'):
            rendered_response = self.render_proctored_exam()
        self.assertIsNone(rendered_response)

    def test_get_studentview_started_onboarding(self):
        """
        Test fallthrough page case for onboarding exams
        """
        exam_attempt = self._create_onboarding_attempt()
        exam_attempt.status = ProctoredExamStudentAttemptStatus.started
        exam_attempt.save()
        rendered_response = self.render_onboarding_exam()
        self.assertEqual(rendered_response, None)

    def test_get_studentview_new_onboarding(self):
        """
        Test entrance page case for onboarding exams
        """
        rendered_response = self.render_onboarding_exam()
        self.assertIn('Proctoring onboarding exam', rendered_response)

    def test_get_onboarding_no_perm(self):
        """
        Test that onboarding exams are gated by the same permission as proctored exams
        """
        with mock_perm('edx_proctoring.can_take_proctored_exam'):
            rendered_response = self.render_onboarding_exam()
        self.assertIsNone(rendered_response)

    @ddt.data(
        (ProctoredExamStudentAttemptStatus.created,
         'Set up and start your proctored exam'),
        (ProctoredExamStudentAttemptStatus.download_software_clicked,
         'Set up and start your proctored exam'),
        (ProctoredExamStudentAttemptStatus.ready_to_start,
         'Proctored Exam Rules'),
        (ProctoredExamStudentAttemptStatus.error,
         'There was a problem with your onboarding session'),
        (ProctoredExamStudentAttemptStatus.submitted,
         'You have submitted this onboarding exam'),
        (ProctoredExamStudentAttemptStatus.second_review_required,
         'You have submitted this onboarding exam'),
        (ProctoredExamStudentAttemptStatus.ready_to_submit,
         'and submit your proctoring session to complete onboarding'),
        (ProctoredExamStudentAttemptStatus.verified,
         'Your onboarding profile was reviewed successfully'),
        (ProctoredExamStudentAttemptStatus.rejected,
         'Your onboarding session was reviewed, but did not pass all requirements'),
    )
    @ddt.unpack
    def test_get_studentview_created_status_onboarding(self, status, expected_message):
        """
        Test for get_student_view practice exam which has been created.
        """
        exam_attempt = self._create_onboarding_attempt()
        exam_attempt.status = status
        exam_attempt.save()
        rendered_response = self.render_onboarding_exam()
        self.assertIn(expected_message, rendered_response)

    @ddt.data(
        (ProctoredExamStudentAttemptStatus.created,
         'Set up and start your proctored exam'),
        (ProctoredExamStudentAttemptStatus.download_software_clicked,
         'Set up and start your proctored exam'),
        (ProctoredExamStudentAttemptStatus.submitted,
         'You have submitted this practice proctored exam'),
        (ProctoredExamStudentAttemptStatus.error,
         'There was a problem with your practice proctoring session'),
    )
    @ddt.unpack
    def test_get_studentview_created_status_practiceexam(self, status, expected_message):
        """
        Test for get_student_view practice exam which has been created.
        """
        exam_attempt = self._create_started_practice_exam_attempt()
        exam_attempt.status = status
        exam_attempt.save()
        rendered_response = self.render_practice_exam()
        self.assertIn(expected_message, rendered_response)

    def test_get_studentview_ready_to_start_status_practiceexam(self):
        """
        Test for get_student_view practice exam which is ready to start.
        """
        exam_attempt = self._create_started_practice_exam_attempt()
        exam_attempt.status = ProctoredExamStudentAttemptStatus.ready_to_start
        exam_attempt.save()
        rendered_response = self.render_practice_exam()
        self.assertIn(self.ready_to_start_msg, rendered_response)

    def test_get_studentview_complete_status_practiceexam(self):
        """
        Test for get_student_view practice exam when it is complete/ready to submit.
        """
        exam_attempt = self._create_started_practice_exam_attempt()
        exam_attempt.status = ProctoredExamStudentAttemptStatus.ready_to_submit
        exam_attempt.save()
        rendered_response = self.render_practice_exam()
        self.assertIn('Are you sure you want to end your proctored exam', rendered_response)

    @ddt.data(
        (
            ProctoredExamStudentAttemptStatus.rejected,
            'Your proctoring session was reviewed, but did not pass all requirements'
        ),
        (
            ProctoredExamStudentAttemptStatus.verified,
            'Your proctoring session was reviewed successfully.'
        ),
        (
            ProctoredExamStudentAttemptStatus.ready_to_submit,
            'Are you sure you want to end your proctored exam'
        ),
    )
    @ddt.unpack
    def test_get_studentview_status_message(self, status, expected_message):
        """
        Test for get_student_view proctored exam messages for each state
        """
        exam_attempt = self._create_started_exam_attempt()
        exam_attempt.status = status
        exam_attempt.save()
        rendered_response = self.render_proctored_exam()
        self.assertIn(expected_message, rendered_response)

    @patch.dict('django.conf.settings.PROCTORING_SETTINGS', {'ALLOW_TIMED_OUT_STATE': True})
    def test_get_studentview_expired(self):
        """
        Test for get_student_view proctored exam which has expired. Since we don't have a template
        for that view rendering, it will throw a NotImplementedError
        """

        self._create_started_exam_attempt(started_at=datetime.now(pytz.UTC).replace(year=2010))

        with self.assertRaises(NotImplementedError):
            self.render_proctored_exam()

    def test_get_studentview_erroneous_exam(self):
        """
        Test for get_student_view proctored exam which has exam status error.
        """
        ProctoredExamStudentAttempt.objects.create(
            proctored_exam_id=self.proctored_exam_id,
            user_id=self.user_id,
            external_id=self.external_id,
            started_at=datetime.now(pytz.UTC),
            allowed_time_limit_mins=10,
            status='error'
        )
        rendered_response = self.render_proctored_exam()
        self.assertIn(self.exam_time_error_msg, rendered_response)

    def test_get_studentview_unstarted_timed_exam(self):
        """
        Test for get_student_view Timed exam which is not proctored and has not started yet.
        """
        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id="abc",
            content_id=self.content_id,
            context={
                'is_proctored': False,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90,
                'hide_after_due': False,
            }
        )
        self.assertNotIn(
            'data-exam-id="{proctored_exam_id}"'.format(proctored_exam_id=self.proctored_exam_id),
            rendered_response
        )
        self.assertIn(self.timed_exam_msg.format(exam_name=self.exam_name), rendered_response)
        self.assertIn('1 hour and 30 minutes', rendered_response)
        self.assertNotIn(self.start_an_exam_msg.format(exam_name=self.exam_name), rendered_response)

    def test_get_studentview_unstarted_timed_exam_with_allowance(self):
        """
        Test for get_student_view Timed exam which is not proctored and has not started yet.
        But user has an allowance
        """

        allowed_extra_time = 10
        add_allowance_for_user(
            self.timed_exam_id,
            self.user.username,
            ProctoredExamStudentAllowance.ADDITIONAL_TIME_GRANTED,
            str(allowed_extra_time)
        )

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id_timed,
            context={}
        )
        self.assertNotIn(
            'data-exam-id="{proctored_exam_id}"'.format(proctored_exam_id=self.proctored_exam_id),
            rendered_response
        )
        self.assertIn(self.timed_exam_msg.format(exam_name=self.exam_name), rendered_response)
        self.assertIn('31 minutes', rendered_response)
        self.assertNotIn(self.start_an_exam_msg.format(exam_name=self.exam_name), rendered_response)

    @ddt.data(
        (ProctoredExamStudentAttemptStatus.ready_to_submit, 'Are you sure that you want to submit your timed exam?'),
        (ProctoredExamStudentAttemptStatus.submitted, 'You have submitted your timed exam'),
    )
    @ddt.unpack
    def test_get_studentview_completed_timed_exam(self, status, expected_content):
        """
        Test for get_student_view timed exam which has completed.
        """
        exam_attempt = self._create_started_exam_attempt(is_proctored=False)
        exam_attempt.status = status
        if status == 'submitted':
            exam_attempt.completed_at = datetime.now(pytz.UTC)

        exam_attempt.save()

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id_timed,
            context={
                'display_name': self.exam_name,
            }
        )
        self.assertIn(expected_content, rendered_response)

    def test_expired_exam(self):
        """
        Test that an expired exam shows a difference message when the exam is expired just recently
        """
        # create exam with completed_at equal to current time and started_at equal to allowed_time_limit_mins ago
        attempt = self._create_started_exam_attempt(is_proctored=False)
        attempt.status = "submitted"
        attempt.started_at = attempt.started_at - timedelta(minutes=attempt.allowed_time_limit_mins)
        attempt.completed_at = attempt.started_at + timedelta(minutes=attempt.allowed_time_limit_mins)
        attempt.save()

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id_timed,
            context={
                'display_name': self.exam_name,
            }
        )

        self.assertIn(self.timed_exam_expired, rendered_response)

        # update start and completed time such that completed_time is allowed_time_limit_mins ago than the current time
        attempt.started_at = attempt.started_at - timedelta(minutes=attempt.allowed_time_limit_mins)
        attempt.completed_at = attempt.completed_at - timedelta(minutes=attempt.allowed_time_limit_mins)
        attempt.save()

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id_timed,
            context={
                'display_name': self.exam_name,
            }
        )

        self.assertIn(self.timed_exam_submitted, rendered_response)

    @ddt.data(
        ProctoredExamStudentAttemptStatus.eligible,
        ProctoredExamStudentAttemptStatus.created,
        ProctoredExamStudentAttemptStatus.download_software_clicked,
        ProctoredExamStudentAttemptStatus.submitted,
        ProctoredExamStudentAttemptStatus.verified,
        ProctoredExamStudentAttemptStatus.rejected,
    )
    def test_footer_present(self, status):
        """
        Make sure the footer content is visible in the rendered output
        """

        if status != ProctoredExamStudentAttemptStatus.eligible:
            exam_attempt = self._create_started_exam_attempt()
            exam_attempt.status = status
            exam_attempt.save()

        rendered_response = self.render_proctored_exam()
        self.assertIsNotNone(rendered_response)
        if status == ProctoredExamStudentAttemptStatus.submitted:

            reset_time = datetime.now(pytz.UTC) + timedelta(minutes=2)
            with freeze_time(reset_time):
                rendered_response = self.render_proctored_exam()
                self.assertIn(self.footer_msg, rendered_response)
        else:
            self.assertIn(self.footer_msg, rendered_response)

    @ddt.data(
        *ProctoredExamStudentAttemptStatus.onboarding_errors
    )
    def test_onboarding_error_pages(self, onboarding_status):
        """
        Test that onboarding errors return a particular error page
        """
        exam_attempt = self._create_started_exam_attempt()
        exam_attempt.status = onboarding_status
        exam_attempt.save()
        rendered_response = self.render_proctored_exam()
        assert onboarding_status in rendered_response

    @ddt.data(
        render_onboarding_exam,
        render_practice_exam,
        render_proctored_exam,
    )
    def test_inactive_account_interstitial(self, render_exam):
        """
        Test that the correct interstitial is shown for an inactive account
        """
        self.user.is_active = False
        self.user.save()

        rendered_response = render_exam(self)
        self.assertIn(self.inactive_account_msg, rendered_response)
