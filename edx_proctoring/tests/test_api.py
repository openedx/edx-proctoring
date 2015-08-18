# pylint: disable=too-many-lines

"""
All tests for the models.py
"""
import ddt
from datetime import datetime, timedelta
from mock import patch
import pytz
from freezegun import freeze_time

from edx_proctoring.api import (
    create_exam,
    update_exam,
    get_exam_by_id,
    get_exam_by_content_id,
    add_allowance_for_user,
    remove_allowance_for_user,
    start_exam_attempt,
    start_exam_attempt_by_code,
    stop_exam_attempt,
    get_active_exams_for_user,
    get_exam_attempt,
    create_exam_attempt,
    get_student_view,
    get_allowances_for_course,
    get_all_exams_for_course,
    get_exam_attempt_by_id,
    remove_exam_attempt,
    get_all_exam_attempts,
    get_filtered_exam_attempts,
    is_feature_enabled,
    mark_exam_attempt_timeout,
    mark_exam_attempt_as_ready,
    update_attempt_status,
    get_attempt_status_summary,
    update_exam_attempt
)
from edx_proctoring.exceptions import (
    ProctoredExamAlreadyExists,
    ProctoredExamNotFoundException,
    StudentExamAttemptAlreadyExistsException,
    StudentExamAttemptDoesNotExistsException,
    StudentExamAttemptedAlreadyStarted,
    UserNotFoundException,
    ProctoredExamIllegalStatusTransition,
    ProctoredExamPermissionDenied
)
from edx_proctoring.models import (
    ProctoredExam,
    ProctoredExamStudentAllowance,
    ProctoredExamStudentAttempt,
    ProctoredExamStudentAttemptStatus,
)

from .utils import (
    LoggedInTestCase,
)

from edx_proctoring.tests.test_services import (
    MockCreditService,
    MockInstructorService,
)
from edx_proctoring.runtime import set_runtime_service, get_runtime_service


@ddt.ddt
class ProctoredExamApiTests(LoggedInTestCase):
    """
    All tests for the models.py
    """

    def setUp(self):
        """
        Build out test harnessing
        """
        super(ProctoredExamApiTests, self).setUp()
        self.default_time_limit = 21
        self.course_id = 'test_course'
        self.content_id = 'test_content_id'
        self.content_id_timed = 'test_content_id_timed'
        self.content_id_practice = 'test_content_id_practice'
        self.disabled_content_id = 'test_disabled_content_id'
        self.exam_name = 'Test Exam'
        self.user_id = self.user.id
        self.key = 'Test Key'
        self.value = 'Test Value'
        self.external_id = 'test_external_id'
        self.proctored_exam_id = self._create_proctored_exam()
        self.timed_exam = self._create_timed_exam()
        self.practice_exam_id = self._create_practice_exam()
        self.disabled_exam_id = self._create_disabled_exam()

        # Messages for get_student_view
        self.start_an_exam_msg = 'Would you like to take "%s" as a proctored exam?'
        self.timed_exam_msg = '%s is a Timed Exam'
        self.exam_time_expired_msg = 'You did not complete the exam in the allotted time'
        self.exam_time_error_msg = 'There was a problem with your proctoring session'
        self.chose_proctored_exam_msg = 'You Have Chosen To Take a Proctored Exam'
        self.proctored_exam_completed_msg = 'Are you sure you want to end your proctored exam'
        self.proctored_exam_submitted_msg = 'You have submitted this proctored exam for review'
        self.proctored_exam_verified_msg = 'Your proctoring session was reviewed and passed all requirements'
        self.proctored_exam_rejected_msg = 'Your proctoring session was reviewed and did not pass requirements'
        self.timed_exam_completed_msg = 'This is the end of your timed exam'
        self.start_a_practice_exam_msg = 'Would you like to take "%s" as a practice proctored exam?'
        self.practice_exam_submitted_msg = 'You have submitted this practice proctored exam'
        self.ready_to_start_msg = 'Your Proctoring Installation and Set Up is Complete'
        self.practice_exam_failed_msg = 'There was a problem with your practice proctoring session'

        set_runtime_service('credit', MockCreditService())
        set_runtime_service('instructor', MockInstructorService())

    def _create_proctored_exam(self):
        """
        Calls the api's create_exam to create an exam object.
        """
        return create_exam(
            course_id=self.course_id,
            content_id=self.content_id,
            exam_name=self.exam_name,
            time_limit_mins=self.default_time_limit
        )

    def _create_timed_exam(self):
        """
        Calls the api's create_exam to create an exam object.
        """
        return create_exam(
            course_id=self.course_id,
            content_id=self.content_id_timed,
            exam_name=self.exam_name,
            time_limit_mins=self.default_time_limit,
            is_proctored=False
        )

    def _create_practice_exam(self):
        """
        Calls the api's create_exam to create a practice exam object.
        """
        return create_exam(
            course_id=self.course_id,
            content_id=self.content_id_practice,
            exam_name=self.exam_name,
            time_limit_mins=self.default_time_limit,
            is_practice_exam=True,
            is_proctored=False
        )

    def _create_disabled_exam(self):
        """
        Calls the api's create_exam to create an exam object.
        """
        return create_exam(
            course_id=self.course_id,
            content_id=self.disabled_content_id,
            exam_name=self.exam_name,
            time_limit_mins=self.default_time_limit,
            is_active=False
        )

    def _create_unstarted_exam_attempt(self, is_proctored=True):
        """
        Creates the ProctoredExamStudentAttempt object.
        """
        return ProctoredExamStudentAttempt.objects.create(
            proctored_exam_id=self.proctored_exam_id if is_proctored else self.timed_exam,
            user_id=self.user_id,
            external_id=self.external_id,
            allowed_time_limit_mins=10,
            status='created'
        )

    def _create_started_exam_attempt(self, started_at=None, is_proctored=True, is_sample_attempt=False):
        """
        Creates the ProctoredExamStudentAttempt object.
        """
        return ProctoredExamStudentAttempt.objects.create(
            proctored_exam_id=self.proctored_exam_id if is_proctored else self.timed_exam,
            user_id=self.user_id,
            external_id=self.external_id,
            started_at=started_at if started_at else datetime.now(pytz.UTC),
            status=ProctoredExamStudentAttemptStatus.started,
            allowed_time_limit_mins=10,
            is_sample_attempt=is_sample_attempt
        )

    def _create_started_practice_exam_attempt(self, started_at=None):  # pylint: disable=invalid-name
        """
        Creates the ProctoredExamStudentAttempt object.
        """
        return ProctoredExamStudentAttempt.objects.create(
            proctored_exam_id=self.practice_exam_id,
            user_id=self.user_id,
            external_id=self.external_id,
            started_at=started_at if started_at else datetime.now(pytz.UTC),
            is_sample_attempt=True,
            status=ProctoredExamStudentAttemptStatus.started,
            allowed_time_limit_mins=10
        )

    def _add_allowance_for_user(self):
        """
        creates allowance for user.
        """
        return ProctoredExamStudentAllowance.objects.create(
            proctored_exam_id=self.proctored_exam_id, user_id=self.user_id, key=self.key, value=self.value
        )

    def test_feature_enabled(self):
        """
        Checks the is_feature_enabled method
        """
        self.assertFalse(is_feature_enabled())

        with patch.dict('django.conf.settings.FEATURES', {'ENABLE_PROCTORED_EXAMS': False}):
            self.assertFalse(is_feature_enabled())

        with patch.dict('django.conf.settings.FEATURES', {'ENABLE_PROCTORED_EXAMS': True}):
            self.assertTrue(is_feature_enabled())

    def test_create_duplicate_exam(self):
        """
        Test to create a proctored exam that has already exist in the
        database and will throw an exception ProctoredExamAlreadyExists.
        """
        with self.assertRaises(ProctoredExamAlreadyExists):
            self._create_proctored_exam()

    def test_update_practice_exam(self):
        """
        test update the existing practice exam to increase the time limit.
        """
        updated_practice_exam_id = update_exam(
            self.practice_exam_id, time_limit_mins=31, is_practice_exam=True
        )

        # only those fields were updated, whose
        # values are passed.
        self.assertEqual(self.practice_exam_id, updated_practice_exam_id)

        update_practice_exam = ProctoredExam.objects.get(id=updated_practice_exam_id)

        self.assertEqual(update_practice_exam.time_limit_mins, 31)
        self.assertEqual(update_practice_exam.course_id, 'test_course')
        self.assertEqual(update_practice_exam.content_id, 'test_content_id_practice')

    def test_update_proctored_exam(self):
        """
        test update the existing proctored exam
        """
        updated_proctored_exam_id = update_exam(
            self.proctored_exam_id, exam_name='Updated Exam Name', time_limit_mins=30,
            is_proctored=True, external_id='external_id', is_active=True
        )

        # only those fields were updated, whose
        # values are passed.
        self.assertEqual(self.proctored_exam_id, updated_proctored_exam_id)

        update_proctored_exam = ProctoredExam.objects.get(id=updated_proctored_exam_id)

        self.assertEqual(update_proctored_exam.exam_name, 'Updated Exam Name')
        self.assertEqual(update_proctored_exam.time_limit_mins, 30)
        self.assertEqual(update_proctored_exam.course_id, 'test_course')
        self.assertEqual(update_proctored_exam.content_id, 'test_content_id')

    def test_update_non_existing_exam(self):
        """
        test to update the non-existing proctored exam
        which will throw the exception
        """
        with self.assertRaises(ProctoredExamNotFoundException):
            update_exam(0, exam_name='Updated Exam Name', time_limit_mins=30)

    def test_get_proctored_exam(self):
        """
        test to get the exam by the exam_id and
        then compare their values.
        """
        proctored_exam = get_exam_by_id(self.proctored_exam_id)
        self.assertEqual(proctored_exam['course_id'], self.course_id)
        self.assertEqual(proctored_exam['content_id'], self.content_id)
        self.assertEqual(proctored_exam['exam_name'], self.exam_name)

        proctored_exam = get_exam_by_content_id(self.course_id, self.content_id)
        self.assertEqual(proctored_exam['course_id'], self.course_id)
        self.assertEqual(proctored_exam['content_id'], self.content_id)
        self.assertEqual(proctored_exam['exam_name'], self.exam_name)

        exams = get_all_exams_for_course(self.course_id)
        self.assertEqual(len(exams), 4)

    def test_get_invalid_proctored_exam(self):
        """
        test to get the exam by the invalid exam_id which will
        raises exception
        """

        with self.assertRaises(ProctoredExamNotFoundException):
            get_exam_by_id(0)

        with self.assertRaises(ProctoredExamNotFoundException):
            get_exam_by_content_id('teasd', 'tewasda')

    def test_add_allowance_for_user(self):
        """
        Test to add allowance for user.
        """
        add_allowance_for_user(self.proctored_exam_id, self.user.username, self.key, self.value)

        student_allowance = ProctoredExamStudentAllowance.get_allowance_for_user(
            self.proctored_exam_id, self.user_id, self.key
        )
        self.assertIsNotNone(student_allowance)

    def test_add_invalid_allowance(self):
        """
        Test to add allowance for invalid user.
        """
        with self.assertRaises(UserNotFoundException):
            add_allowance_for_user(self.proctored_exam_id, 'invalid_user', self.key, self.value)

    def test_update_existing_allowance(self):
        """
        Test updation to the allowance that already exists.
        """
        student_allowance = self._add_allowance_for_user()
        add_allowance_for_user(student_allowance.proctored_exam.id, self.user.username, self.key, 'new_value')

        student_allowance = ProctoredExamStudentAllowance.get_allowance_for_user(
            student_allowance.proctored_exam.id, self.user_id, self.key
        )
        self.assertIsNotNone(student_allowance)
        self.assertEqual(student_allowance.value, 'new_value')

    def test_get_allowances_for_course(self):
        """
        Test to get all the allowances for a course.
        """
        allowance = self._add_allowance_for_user()
        course_allowances = get_allowances_for_course(self.course_id)
        self.assertEqual(len(course_allowances), 1)
        self.assertEqual(course_allowances[0]['proctored_exam']['course_id'], allowance.proctored_exam.course_id)

    def test_get_non_existing_allowance(self):
        """
        Test to get an allowance which does not exist.
        """
        student_allowance = ProctoredExamStudentAllowance.get_allowance_for_user(
            self.proctored_exam_id, self.user_id, self.key
        )
        self.assertIsNone(student_allowance)

    def test_remove_allowance_for_user(self):
        """
        Test to remove an allowance for user.
        """
        student_allowance = self._add_allowance_for_user()
        self.assertEqual(len(ProctoredExamStudentAllowance.objects.filter()), 1)
        remove_allowance_for_user(student_allowance.proctored_exam.id, self.user_id, self.key)
        self.assertEqual(len(ProctoredExamStudentAllowance.objects.filter()), 0)

    def test_create_an_exam_attempt(self):
        """
        Create an unstarted exam attempt.
        """
        attempt_id = create_exam_attempt(self.proctored_exam_id, self.user_id)
        self.assertGreater(attempt_id, 0)

    def test_attempt_with_allowance(self):
        """
        Create an unstarted exam attempt with additional time.
        """
        allowed_extra_time = 10
        add_allowance_for_user(
            self.proctored_exam_id,
            self.user.username,
            "Additional time (minutes)",
            str(allowed_extra_time)
        )
        attempt_id = create_exam_attempt(self.proctored_exam_id, self.user_id)
        self.assertGreater(attempt_id, 0)

        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertEqual(attempt['allowed_time_limit_mins'], self.default_time_limit + allowed_extra_time)

    def test_recreate_an_exam_attempt(self):
        """
        Start an exam attempt that has already been created.
        Raises StudentExamAttemptAlreadyExistsException
        """
        proctored_exam_student_attempt = self._create_unstarted_exam_attempt()
        with self.assertRaises(StudentExamAttemptAlreadyExistsException):
            create_exam_attempt(proctored_exam_student_attempt.proctored_exam.id, self.user_id)

    def test_recreate_a_practice_exam_attempt(self):  # pylint: disable=invalid-name
        """
        Taking the practice exam several times should not cause an exception.
        """
        practice_exam_student_attempt = self._create_started_practice_exam_attempt()
        new_attempt_id = create_exam_attempt(practice_exam_student_attempt.proctored_exam.id, self.user_id)
        self.assertGreater(practice_exam_student_attempt, new_attempt_id, "New attempt not created.")

    def test_get_exam_attempt(self):
        """
        Test to get the existing exam attempt.
        """
        self._create_unstarted_exam_attempt()
        exam_attempt = get_exam_attempt(self.proctored_exam_id, self.user_id)

        self.assertEqual(exam_attempt['proctored_exam']['id'], self.proctored_exam_id)
        self.assertEqual(exam_attempt['user']['id'], self.user_id)

    def test_start_uncreated_attempt(self):
        """
        Test to attempt starting an attempt which has not been created yet.
        should raise an exception.
        """
        with self.assertRaises(StudentExamAttemptDoesNotExistsException):
            start_exam_attempt(self.proctored_exam_id, self.user_id)

        with self.assertRaises(StudentExamAttemptDoesNotExistsException):
            start_exam_attempt_by_code('foobar')

    def test_start_a_created_attempt(self):
        """
        Test to attempt starting an attempt which has been created but not started.
        """
        self._create_unstarted_exam_attempt()
        start_exam_attempt(self.proctored_exam_id, self.user_id)

    def test_start_by_code(self):
        """
        Test to attempt starting an attempt which has been created but not started.
        """
        attempt = self._create_unstarted_exam_attempt()
        start_exam_attempt_by_code(attempt.attempt_code)

    def test_restart_a_started_attempt(self):
        """
        Test to attempt starting an attempt which has been created but not started.
        """
        self._create_unstarted_exam_attempt()
        start_exam_attempt(self.proctored_exam_id, self.user_id)
        with self.assertRaises(StudentExamAttemptedAlreadyStarted):
            start_exam_attempt(self.proctored_exam_id, self.user_id)

    def test_stop_exam_attempt(self):
        """
        Stop an exam attempt.
        """
        proctored_exam_student_attempt = self._create_unstarted_exam_attempt()
        self.assertIsNone(proctored_exam_student_attempt.completed_at)
        proctored_exam_attempt_id = stop_exam_attempt(
            proctored_exam_student_attempt.proctored_exam, self.user_id
        )
        self.assertEqual(proctored_exam_student_attempt.id, proctored_exam_attempt_id)

    def test_remove_exam_attempt(self):
        """
        Calling the api remove function removes the attempt.
        """
        with self.assertRaises(StudentExamAttemptDoesNotExistsException):
            remove_exam_attempt(9999)

        proctored_exam_student_attempt = self._create_unstarted_exam_attempt()
        remove_exam_attempt(proctored_exam_student_attempt.id)

        with self.assertRaises(StudentExamAttemptDoesNotExistsException):
            remove_exam_attempt(proctored_exam_student_attempt.id)

    def test_stop_a_non_started_exam(self):
        """
        Stop an exam attempt that had not started yet.
        """
        with self.assertRaises(StudentExamAttemptDoesNotExistsException):
            stop_exam_attempt(self.proctored_exam_id, self.user_id)

    def test_mark_exam_attempt_timeout(self):
        """
        Tests the mark exam as timed out
        """

        with self.assertRaises(StudentExamAttemptDoesNotExistsException):
            mark_exam_attempt_timeout(self.proctored_exam_id, self.user_id)

        proctored_exam_student_attempt = self._create_unstarted_exam_attempt()
        self.assertIsNone(proctored_exam_student_attempt.completed_at)
        proctored_exam_attempt_id = mark_exam_attempt_timeout(
            proctored_exam_student_attempt.proctored_exam.id, self.user_id
        )
        self.assertEqual(proctored_exam_student_attempt.id, proctored_exam_attempt_id)

    def test_mark_exam_attempt_as_ready(self):
        """
        Tests the mark exam as timed out
        """

        with self.assertRaises(StudentExamAttemptDoesNotExistsException):
            mark_exam_attempt_as_ready(self.proctored_exam_id, self.user_id)

        proctored_exam_student_attempt = self._create_unstarted_exam_attempt()
        self.assertIsNone(proctored_exam_student_attempt.completed_at)
        proctored_exam_attempt_id = mark_exam_attempt_as_ready(
            proctored_exam_student_attempt.proctored_exam, self.user_id
        )
        self.assertEqual(proctored_exam_student_attempt.id, proctored_exam_attempt_id)

    def test_get_active_exams_for_user(self):
        """
        Test to get the all the active
        exams for the user.
        """
        self._create_started_exam_attempt()
        exam_id = create_exam(
            course_id=self.course_id,
            content_id='test_content_2',
            exam_name='Final Test Exam',
            time_limit_mins=self.default_time_limit
        )
        create_exam_attempt(
            exam_id=exam_id,
            user_id=self.user_id
        )
        start_exam_attempt(
            exam_id=exam_id,
            user_id=self.user_id,
        )
        add_allowance_for_user(self.proctored_exam_id, self.user.username, self.key, self.value)
        add_allowance_for_user(self.proctored_exam_id, self.user.username, 'new_key', 'new_value')
        student_active_exams = get_active_exams_for_user(self.user_id, self.course_id)
        self.assertEqual(len(student_active_exams), 2)
        self.assertEqual(len(student_active_exams[0]['allowances']), 0)
        self.assertEqual(len(student_active_exams[1]['allowances']), 2)

    def test_get_filtered_exam_attempts(self):
        """
        Test to get all the exams filtered by the course_id
        and search type.
        """
        exam_attempt = self._create_started_exam_attempt()
        exam_id = create_exam(
            course_id=self.course_id,
            content_id='test_content_2',
            exam_name='Final Test Exam',
            time_limit_mins=self.default_time_limit
        )
        new_exam_attempt = create_exam_attempt(
            exam_id=exam_id,
            user_id=self.user_id
        )
        filtered_attempts = get_filtered_exam_attempts(self.course_id, self.user.username)
        self.assertEqual(len(filtered_attempts), 2)
        self.assertEqual(filtered_attempts[0]['id'], new_exam_attempt)
        self.assertEqual(filtered_attempts[1]['id'], exam_attempt.id)

    def test_get_all_exam_attempts(self):
        """
        Test to get all the exam attempts.
        """
        exam_attempt = self._create_started_exam_attempt()
        exam_id = create_exam(
            course_id=self.course_id,
            content_id='test_content_2',
            exam_name='Final Test Exam',
            time_limit_mins=self.default_time_limit
        )
        updated_exam_attempt_id = create_exam_attempt(
            exam_id=exam_id,
            user_id=self.user_id
        )
        all_exams = get_all_exam_attempts(self.course_id)
        self.assertEqual(len(all_exams), 2)
        self.assertEqual(all_exams[0]['id'], updated_exam_attempt_id)
        self.assertEqual(all_exams[1]['id'], exam_attempt.id)

    def test_get_student_view(self):
        """
        Test for get_student_view prompting the user to take the exam
        as a timed exam or a proctored exam.
        """
        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id,
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90
            }
        )
        self.assertIn('data-exam-id="%d"' % self.proctored_exam_id, rendered_response)
        self.assertIn(self.start_an_exam_msg % self.exam_name, rendered_response)

        # try practice exam variant
        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id + 'foo',
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90,
                'is_practice_exam': True,
            }
        )
        self.assertIn(self.start_a_practice_exam_msg % self.exam_name, rendered_response)

    def test_get_honor_view_with_practice_exam(self):  # pylint: disable=invalid-name
        """
        Test for get_student_view prompting when the student is enrolled in non-verified
        track for a practice exam, this should return not None, meaning
        student will see proctored content
        """
        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id_practice,
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90,
                'credit_state': {
                    'enrollment_mode': 'honor'
                },
                'is_practice_exam': True
            }
        )
        self.assertIsNotNone(rendered_response)

    def test_get_honor_view(self):
        """
        Test for get_student_view prompting when the student is enrolled in non-verified
        track, this should return None
        """
        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id,
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90,
                'credit_state': {
                    'enrollment_mode': 'honor'
                },
                'is_practice_exam': False
            }
        )
        self.assertIsNone(rendered_response)

    @ddt.data(
        ('reverification', None, True, True, False),
        ('reverification', 'failed', False, False, True),
        ('reverification', 'satisfied', True, True, False),
        ('grade', 'failed', True, False, False)
    )
    @ddt.unpack
    def test_prereq_scenarios(self, namespace, req_status, show_proctored,
                              pre_create_attempt, mark_as_declined):
        """
        This test asserts that proctoring will not be displayed under the following
        conditions:

        - Verified student has not completed all 'reverification' requirements
        """

        exam = get_exam_by_id(self.proctored_exam_id)

        if pre_create_attempt:
            create_exam_attempt(self.proctored_exam_id, self.user_id)

        # user hasn't attempted reverifications
        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=exam['course_id'],
            content_id=exam['content_id'],
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90,
                'is_practice_exam': False,
                'credit_state': {
                    'enrollment_mode': 'verified',
                    'credit_requirement_status': [
                        {
                            'namespace': namespace,
                            'status': req_status,
                        }
                    ]
                }
            }
        )
        if show_proctored:
            self.assertIsNotNone(rendered_response)
        else:
            self.assertIsNone(rendered_response)

        # also the user should have been marked as declined in certain
        # cases
        if mark_as_declined:
            attempt = get_exam_attempt(self.proctored_exam_id, self.user_id)
            self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.declined)

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

    def test_get_studentview_unstarted_exam(self):  # pylint: disable=invalid-name
        """
        Test for get_student_view proctored exam which has not started yet.
        """

        self._create_unstarted_exam_attempt()

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id,
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90
            }
        )
        self.assertIn(self.chose_proctored_exam_msg, rendered_response)

    def test_declined_attempt(self):
        """
        Make sure that a declined attempt does not show proctoring
        """
        attempt_obj = self._create_unstarted_exam_attempt()
        attempt_obj.status = ProctoredExamStudentAttemptStatus.declined
        attempt_obj.save()

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id,
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90
            }
        )
        self.assertIsNone(rendered_response)

    def test_get_studentview_ready(self):
        """
        Assert that we get the right content
        when the exam is ready to be started
        """
        exam_attempt = self._create_started_exam_attempt()
        exam_attempt.status = ProctoredExamStudentAttemptStatus.ready_to_start
        exam_attempt.save()

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id,
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90
            }
        )
        self.assertIn(self.ready_to_start_msg, rendered_response)

    def test_get_studentview_started_exam(self):  # pylint: disable=invalid-name
        """
        Test for get_student_view proctored exam which has started.
        """

        self._create_started_exam_attempt()

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id,
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90
            }
        )
        self.assertIsNone(rendered_response)

    @patch.dict('django.conf.settings.PROCTORING_SETTINGS', {'ALLOW_TIMED_OUT_STATE': True})
    def test_get_studentview_timedout(self):
        """
        Verifies that if we call get_studentview when the timer has expired
        it will automatically state transition into timed_out
        """

        attempt_obj = self._create_started_exam_attempt()

        reset_time = datetime.now(pytz.UTC) + timedelta(days=1)
        with freeze_time(reset_time):
            get_student_view(
                user_id=self.user_id,
                course_id=self.course_id,
                content_id=self.content_id,
                context={
                    'is_proctored': True,
                    'display_name': self.exam_name,
                    'default_time_limit_mins': 90
                }
            )

        attempt = get_exam_attempt_by_id(attempt_obj.id)
        self.assertEqual(attempt['status'], 'timed_out')

    def test_get_studentview_submitted_status(self):  # pylint: disable=invalid-name
        """
        Test for get_student_view proctored exam which has been submitted.
        """
        exam_attempt = self._create_started_exam_attempt()
        exam_attempt.status = ProctoredExamStudentAttemptStatus.submitted
        exam_attempt.save()

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id,
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90
            }
        )
        self.assertIn(self.proctored_exam_submitted_msg, rendered_response)

        # test the variant if we are a sample attempt
        exam_attempt.is_sample_attempt = True
        exam_attempt.save()

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id,
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90
            }
        )
        self.assertIn(self.practice_exam_submitted_msg, rendered_response)

    def test_get_studentview_rejected_status(self):  # pylint: disable=invalid-name
        """
        Test for get_student_view proctored exam which has been rejected.
        """
        exam_attempt = self._create_started_exam_attempt()
        exam_attempt.status = ProctoredExamStudentAttemptStatus.rejected
        exam_attempt.save()

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id,
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90
            }
        )
        self.assertIn(self.proctored_exam_rejected_msg, rendered_response)

    def test_get_studentview_verified_status(self):  # pylint: disable=invalid-name
        """
        Test for get_student_view proctored exam which has been verified.
        """
        exam_attempt = self._create_started_exam_attempt()
        exam_attempt.status = ProctoredExamStudentAttemptStatus.verified
        exam_attempt.save()

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id,
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90
            }
        )
        self.assertIn(self.proctored_exam_verified_msg, rendered_response)

    def test_get_studentview_completed_status(self):  # pylint: disable=invalid-name
        """
        Test for get_student_view proctored exam which has been completed.
        """
        exam_attempt = self._create_started_exam_attempt()
        exam_attempt.status = ProctoredExamStudentAttemptStatus.ready_to_submit
        exam_attempt.save()

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id,
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90
            }
        )
        self.assertIn(self.proctored_exam_completed_msg, rendered_response)

    @patch.dict('django.conf.settings.PROCTORING_SETTINGS', {'ALLOW_TIMED_OUT_STATE': True})
    def test_get_studentview_expired(self):
        """
        Test for get_student_view proctored exam which has expired.
        """

        self._create_started_exam_attempt(started_at=datetime.now(pytz.UTC).replace(year=2010))

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id,
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90
            }
        )

        self.assertIn(self.exam_time_expired_msg, rendered_response)

    def test_get_studentview_erroneous_exam(self):  # pylint: disable=invalid-name
        """
        Test for get_student_view proctored exam which has exam status error.
        """

        exam_attempt = ProctoredExamStudentAttempt.objects.create(
            proctored_exam_id=self.proctored_exam_id,
            user_id=self.user_id,
            external_id=self.external_id,
            started_at=datetime.now(pytz.UTC),
            allowed_time_limit_mins=10,
            status='error'
        )

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id,
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 10
            }
        )
        self.assertIn(self.exam_time_error_msg, rendered_response)

        # test the variant if we are a sample attempt
        exam_attempt.is_sample_attempt = True
        exam_attempt.save()

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id,
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90
            }
        )
        self.assertIn(self.practice_exam_failed_msg, rendered_response)

    def test_get_studentview_unstarted_timed_exam(self):  # pylint: disable=invalid-name
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
                'default_time_limit_mins': 90
            }
        )
        self.assertNotIn('data-exam-id="%d"' % self.proctored_exam_id, rendered_response)
        self.assertIn(self.timed_exam_msg % self.exam_name, rendered_response)
        self.assertNotIn(self.start_an_exam_msg % self.exam_name, rendered_response)

    def test_get_studentview_completed_timed_exam(self):  # pylint: disable=invalid-name
        """
        Test for get_student_view timed exam which has completed.
        """
        exam_attempt = self._create_started_exam_attempt(is_proctored=False)
        exam_attempt.status = ProctoredExamStudentAttemptStatus.ready_to_submit
        exam_attempt.save()

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id_timed,
            context={
                'is_proctored': False,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90
            }
        )
        self.assertIn(self.timed_exam_completed_msg, rendered_response)

    def test_submitted_credit_state(self):
        """
        Verify that putting an attempt into the submitted state will also mark
        the credit requirement as submitted
        """
        exam_attempt = self._create_started_exam_attempt()
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            ProctoredExamStudentAttemptStatus.submitted
        )

        credit_service = get_runtime_service('credit')
        credit_status = credit_service.get_credit_state(self.user.id, exam_attempt.proctored_exam.course_id)

        self.assertEqual(len(credit_status['credit_requirement_status']), 1)
        self.assertEqual(
            credit_status['credit_requirement_status'][0]['status'],
            'submitted'
        )

    def test_error_credit_state(self):
        """
        Verify that putting an attempt into the error state will also mark
        the credit requirement as failed
        """
        exam_attempt = self._create_started_exam_attempt()
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            ProctoredExamStudentAttemptStatus.error
        )

        credit_service = get_runtime_service('credit')
        credit_status = credit_service.get_credit_state(self.user.id, exam_attempt.proctored_exam.course_id)

        self.assertEqual(len(credit_status['credit_requirement_status']), 1)
        self.assertEqual(
            credit_status['credit_requirement_status'][0]['status'],
            'failed'
        )

    @ddt.data(
        (ProctoredExamStudentAttemptStatus.declined, ProctoredExamStudentAttemptStatus.eligible),
        (ProctoredExamStudentAttemptStatus.timed_out, ProctoredExamStudentAttemptStatus.created),
        (ProctoredExamStudentAttemptStatus.submitted, ProctoredExamStudentAttemptStatus.ready_to_start),
        (ProctoredExamStudentAttemptStatus.verified, ProctoredExamStudentAttemptStatus.started),
        (ProctoredExamStudentAttemptStatus.rejected, ProctoredExamStudentAttemptStatus.started),
        (ProctoredExamStudentAttemptStatus.not_reviewed, ProctoredExamStudentAttemptStatus.started),
        (ProctoredExamStudentAttemptStatus.error, ProctoredExamStudentAttemptStatus.started),
    )
    @ddt.unpack
    @patch.dict('django.conf.settings.PROCTORING_SETTINGS', {'ALLOW_TIMED_OUT_STATE': True})
    def test_illegal_status_transition(self, from_status, to_status):
        """
        Verify that we cannot reset backwards an attempt status
        once it is in a completed state
        """

        exam_attempt = self._create_started_exam_attempt()
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            from_status
        )

        with self.assertRaises(ProctoredExamIllegalStatusTransition):
            update_attempt_status(
                exam_attempt.proctored_exam_id,
                self.user.id,
                to_status
            )

    def test_alias_timed_out(self):
        """
        Verified that timed_out will automatically state transition
        to submitted
        """

        exam_attempt = self._create_started_exam_attempt()
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            ProctoredExamStudentAttemptStatus.timed_out
        )

        exam_attempt = get_exam_attempt_by_id(exam_attempt.id)

        self.assertEqual(
            exam_attempt['status'],
            ProctoredExamStudentAttemptStatus.submitted
        )

    def test_update_unexisting_attempt(self):
        """
        Tests updating an non-existing attempt
        """

        with self.assertRaises(StudentExamAttemptDoesNotExistsException):
            update_attempt_status(0, 0, ProctoredExamStudentAttemptStatus.timed_out)

        # also check the raise_if_not_found flag
        self.assertIsNone(
            update_attempt_status(
                0,
                0,
                ProctoredExamStudentAttemptStatus.timed_out,
                raise_if_not_found=False
            )
        )

    @ddt.data(
        (
            ProctoredExamStudentAttemptStatus.eligible, {
                'status': ProctoredExamStudentAttemptStatus.eligible,
                'short_description': 'Proctored Option Available',
                'suggested_icon': 'fa-lock',
                'in_completed_state': False
            }
        ),
        (
            ProctoredExamStudentAttemptStatus.declined, {
                'status': ProctoredExamStudentAttemptStatus.declined,
                'short_description': 'Taking As Open Exam',
                'suggested_icon': 'fa-unlock',
                'in_completed_state': False
            }
        ),
        (
            ProctoredExamStudentAttemptStatus.submitted, {
                'status': ProctoredExamStudentAttemptStatus.submitted,
                'short_description': 'Pending Session Review',
                'suggested_icon': 'fa-spinner fa-spin',
                'in_completed_state': True
            }
        ),
        (
            ProctoredExamStudentAttemptStatus.verified, {
                'status': ProctoredExamStudentAttemptStatus.verified,
                'short_description': 'Passed Proctoring',
                'suggested_icon': 'fa-check',
                'in_completed_state': True
            }
        ),
        (
            ProctoredExamStudentAttemptStatus.rejected, {
                'status': ProctoredExamStudentAttemptStatus.rejected,
                'short_description': 'Failed Proctoring',
                'suggested_icon': 'fa-exclamation-triangle',
                'in_completed_state': True
            }
        ),
        (
            ProctoredExamStudentAttemptStatus.error, {
                'status': ProctoredExamStudentAttemptStatus.error,
                'short_description': 'Failed Proctoring',
                'suggested_icon': 'fa-exclamation-triangle',
                'in_completed_state': True
            }
        ),
        (
            ProctoredExamStudentAttemptStatus.created, {
                'status': ProctoredExamStudentAttemptStatus.created,
                'short_description': 'Taking As Proctored Exam',
                'suggested_icon': 'fa-lock',
                'in_completed_state': False
            }
        ),
        (
            ProctoredExamStudentAttemptStatus.ready_to_start, {
                'status': ProctoredExamStudentAttemptStatus.ready_to_start,
                'short_description': 'Taking As Proctored Exam',
                'suggested_icon': 'fa-lock',
                'in_completed_state': False
            }
        ),
        (
            ProctoredExamStudentAttemptStatus.started, {
                'status': ProctoredExamStudentAttemptStatus.started,
                'short_description': 'Taking As Proctored Exam',
                'suggested_icon': 'fa-lock',
                'in_completed_state': False
            }
        ),
        (
            ProctoredExamStudentAttemptStatus.ready_to_submit, {
                'status': ProctoredExamStudentAttemptStatus.ready_to_submit,
                'short_description': 'Taking As Proctored Exam',
                'suggested_icon': 'fa-lock',
                'in_completed_state': False
            }
        )
    )
    @ddt.unpack
    def test_attempt_status_summary(self, status, expected):
        """
        Assert that we get the expected status summaries
        """

        exam_attempt = self._create_started_exam_attempt()
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            status
        )

        summary = get_attempt_status_summary(
            self.user.id,
            exam_attempt.proctored_exam.course_id,
            exam_attempt.proctored_exam.content_id
        )

        self.assertIn(summary, [expected])

    @ddt.data(
        (
            ProctoredExamStudentAttemptStatus.eligible, {
                'status': ProctoredExamStudentAttemptStatus.eligible,
                'short_description': 'Ungraded Practice Exam',
                'suggested_icon': 'fa-lock',
                'in_completed_state': False
            }
        ),
        (
            ProctoredExamStudentAttemptStatus.submitted, {
                'status': ProctoredExamStudentAttemptStatus.submitted,
                'short_description': 'Practice Exam Completed',
                'suggested_icon': 'fa-check',
                'in_completed_state': True
            }
        ),
        (
            ProctoredExamStudentAttemptStatus.error, {
                'status': ProctoredExamStudentAttemptStatus.error,
                'short_description': 'Practice Exam Failed',
                'suggested_icon': 'fa-exclamation-triangle',
                'in_completed_state': True
            }
        )
    )
    @ddt.unpack
    def test_practice_status_summary(self, status, expected):
        """
        Assert that we get the expected status summaries
        """

        exam_attempt = self._create_started_practice_exam_attempt()
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            status
        )

        summary = get_attempt_status_summary(
            self.user.id,
            exam_attempt.proctored_exam.course_id,
            exam_attempt.proctored_exam.content_id
        )

        self.assertIn(summary, [expected])

    @ddt.data(
        (
            ProctoredExamStudentAttemptStatus.eligible, {
                'status': ProctoredExamStudentAttemptStatus.eligible,
                'short_description': 'Ungraded Practice Exam',
                'suggested_icon': 'fa-lock',
                'in_completed_state': False
            }
        ),
        (
            ProctoredExamStudentAttemptStatus.submitted, {
                'status': ProctoredExamStudentAttemptStatus.submitted,
                'short_description': 'Practice Exam Completed',
                'suggested_icon': 'fa-check',
                'in_completed_state': True
            }
        ),
        (
            ProctoredExamStudentAttemptStatus.error, {
                'status': ProctoredExamStudentAttemptStatus.error,
                'short_description': 'Practice Exam Failed',
                'suggested_icon': 'fa-exclamation-triangle',
                'in_completed_state': True
            }
        )
    )
    @ddt.unpack
    def test_practice_status_honor(self, status, expected):
        """
        Assert that we get the expected status summaries
        """

        set_runtime_service('credit', MockCreditService(enrollment_mode='honor'))

        exam_attempt = self._create_started_practice_exam_attempt()

        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            status
        )

        summary = get_attempt_status_summary(
            self.user.id,
            exam_attempt.proctored_exam.course_id,
            exam_attempt.proctored_exam.content_id
        )

        self.assertIn(summary, [expected])

    def test_practice_no_attempt(self):
        """
        Assert that we get the expected status summaries
        """

        expected = {
            'status': ProctoredExamStudentAttemptStatus.eligible,
            'short_description': 'Ungraded Practice Exam',
            'suggested_icon': 'fa-lock',
            'in_completed_state': False
        }

        exam = get_exam_by_id(self.practice_exam_id)

        set_runtime_service('credit', MockCreditService(enrollment_mode='honor'))
        summary = get_attempt_status_summary(
            self.user.id,
            exam['course_id'],
            exam['content_id']
        )
        self.assertIn(summary, [expected])

        set_runtime_service('credit', MockCreditService())
        summary = get_attempt_status_summary(
            self.user.id,
            exam['course_id'],
            exam['content_id']
        )
        self.assertIn(summary, [expected])

    @ddt.data(
        'honor', 'staff'
    )
    def test_status_summary_honor(self, enrollment_mode):
        """
        Make sure status summary is None for a non-verified person
        """

        set_runtime_service('credit', MockCreditService(enrollment_mode=enrollment_mode))

        exam_attempt = self._create_started_exam_attempt()

        summary = get_attempt_status_summary(
            self.user.id,
            exam_attempt.proctored_exam.course_id,
            exam_attempt.proctored_exam.content_id
        )

        self.assertIsNone(summary)

    def test_status_summary_bad(self):
        """
        Make sure we get back a None when getting summary for content that does not
        exist
        """

        summary = get_attempt_status_summary(
            self.user.id,
            'foo',
            'foo'
        )

        self.assertIsNone(summary)

    def test_update_exam_attempt(self):
        """
        Make sure we restrict which fields we can update
        """

        exam_attempt = self._create_started_exam_attempt()

        with self.assertRaises(ProctoredExamPermissionDenied):
            update_exam_attempt(
                exam_attempt.id,
                last_poll_timestamp=datetime.utcnow(),
                last_poll_ipaddr='1.1.1.1',
                status='foo'
            )

        now = datetime.now(pytz.UTC)
        update_exam_attempt(
            exam_attempt.id,
            last_poll_timestamp=now,
            last_poll_ipaddr='1.1.1.1',
        )

        attempt = get_exam_attempt_by_id(exam_attempt.id)

        self.assertEquals(attempt['last_poll_timestamp'], now)
        self.assertEquals(attempt['last_poll_ipaddr'], '1.1.1.1')
