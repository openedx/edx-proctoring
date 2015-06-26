"""
All tests for the models.py
"""
from datetime import datetime
import pytz
from edx_proctoring.api import create_exam, update_exam, get_exam_by_id, get_exam_by_content_id, \
    add_allowance_for_user, remove_allowance_for_user, start_exam_attempt, stop_exam_attempt
from edx_proctoring.exceptions import ProctoredExamAlreadyExists, ProctoredExamNotFoundException, \
    StudentExamAttemptAlreadyExistsException
from edx_proctoring.models import ProctoredExam, ProctoredExamStudentAllowance, ProctoredExamStudentAttempt

from .utils import (
    LoggedInTestCase
)


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
        self.exam_name = 'Test Exam'
        self.user_id = 1
        self.key = 'Test Key'
        self.value = 'Test Value'
        self.external_id = 'test_external_id'

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

    def _create_student_exam_attempt_entry(self):
        """
        Creates the ProctoredExamStudentAttempt object.
        """

        proctored_exam_id = self._create_proctored_exam()
        return ProctoredExamStudentAttempt.objects.create(
            proctored_exam_id=proctored_exam_id,
            user_id=self.user_id,
            external_id=self.external_id,
            started_at=datetime.now(pytz.UTC)
        )

    def _add_allowance_for_user(self):
        proctored_exam_id = self._create_proctored_exam()
        return ProctoredExamStudentAllowance.objects.create(
            proctored_exam_id=proctored_exam_id, user_id=self.user_id, key=self.key, value=self.value
        )

    def test_create_exam(self):
        """
        Test to create a proctored exam.
        """
        proctored_exam = self._create_proctored_exam()
        self.assertIsNotNone(proctored_exam)

    def test_create_already_existing_exam_throws_exception(self):
        """
        Test to create a proctored exam that has already exist in the
        database and will throw an exception ProctoredExamAlreadyExist.
        """
        ProctoredExam.objects.create(
            course_id='test_course',
            content_id='test_content_id',
            external_id='test_external_id',
            exam_name='Test Exam',
            time_limit_mins=21,
            is_proctored=True,
            is_active=True
        )
        with self.assertRaises(ProctoredExamAlreadyExists):
            self._create_proctored_exam()

    def test_update_proctored_exam(self):
        """
        test update the existing proctored exam
        """
        proctored_exam_id = self._create_proctored_exam()
        updated_proctored_exam_id = update_exam(
            proctored_exam_id, exam_name='Updated Exam Name', time_limit_mins=30,
            is_proctored=True, external_id='external_id', is_active=True
        )

        # only those fields were updated, whose
        # values are passed.
        self.assertEqual(proctored_exam_id, updated_proctored_exam_id)

        update_proctored_exam = ProctoredExam.objects.get(id=updated_proctored_exam_id)

        self.assertEqual(update_proctored_exam.exam_name, 'Updated Exam Name')
        self.assertEqual(update_proctored_exam.time_limit_mins, 30)
        self.assertEqual(update_proctored_exam.course_id, 'test_course')
        self.assertEqual(update_proctored_exam.content_id, 'test_content_id')

    def test_update_non_existing_proctored_exam(self):
        """
        test to update the non-existing proctored exam
        which will throw the exception
        """
        with self.assertRaises(ProctoredExamNotFoundException):
            update_exam(1, exam_name='Updated Exam Name', time_limit_mins=30)

    def test_get_proctored_exam(self):
        """
        test to get the exam by the exam_id and
        then compare their values.
        """
        proctored_exam_id = self._create_proctored_exam()
        proctored_exam = get_exam_by_id(proctored_exam_id)
        self.assertEqual(proctored_exam['course_id'], self.course_id)
        self.assertEqual(proctored_exam['content_id'], self.content_id)
        self.assertEqual(proctored_exam['exam_name'], self.exam_name)

        proctored_exam = get_exam_by_content_id(self.course_id, self.content_id)
        self.assertEqual(proctored_exam['course_id'], self.course_id)
        self.assertEqual(proctored_exam['content_id'], self.content_id)
        self.assertEqual(proctored_exam['exam_name'], self.exam_name)

    def test_get_invalid_proctored_exam(self):
        """
        test to get the exam by the invalid exam_id which will
        raises exception
        """

        with self.assertRaises(ProctoredExamNotFoundException):
            get_exam_by_id(1)

        with self.assertRaises(ProctoredExamNotFoundException):
            get_exam_by_content_id('teasd', 'tewasda')

    def test_add_allowance_for_user(self):
        proctored_exam_id = self._create_proctored_exam()
        add_allowance_for_user(proctored_exam_id, self.user_id, self.key, self.value)

        student_allowance = ProctoredExamStudentAllowance.get_allowance_for_user(
            proctored_exam_id, self.user_id, self.key
        )
        self.assertIsNotNone(student_allowance)

    def test_allowance_for_user_already_exists(self):
        student_allowance = self._add_allowance_for_user()
        add_allowance_for_user(student_allowance.proctored_exam.id, self.user_id, self.key, 'new_value')

        student_allowance = ProctoredExamStudentAllowance.get_allowance_for_user(
            student_allowance.proctored_exam.id, self.user_id, self.key
        )
        self.assertIsNotNone(student_allowance)
        self.assertEqual(student_allowance.value, 'new_value')

    def test_get_allowance_for_user_does_not_exist(self):
        proctored_exam_id = self._create_proctored_exam()

        student_allowance = ProctoredExamStudentAllowance.get_allowance_for_user(
            proctored_exam_id, self.user_id, self.key
        )
        self.assertIsNone(student_allowance)

    def test_remove_allowance_for_user(self):
        student_allowance = self._add_allowance_for_user()
        self.assertEqual(len(ProctoredExamStudentAllowance.objects.filter()), 1)
        remove_allowance_for_user(student_allowance.proctored_exam.id, self.user_id, self.key)
        self.assertEqual(len(ProctoredExamStudentAllowance.objects.filter()), 0)

    def test_student_exam_attempt_entry_already_exists(self):
        proctored_exam_id = self._create_proctored_exam()
        start_exam_attempt(proctored_exam_id, self.user_id, self.external_id)
        self.assertIsNotNone(start_exam_attempt)

    def test_create_student_exam_attempt_entry(self):
        proctored_exam_student_attempt = self._create_student_exam_attempt_entry()
        with self.assertRaises(StudentExamAttemptAlreadyExistsException):
            start_exam_attempt(proctored_exam_student_attempt.proctored_exam, self.user_id, self.external_id)

    def test_stop_exam_attempt(self):
        proctored_exam_student_attempt = self._create_student_exam_attempt_entry()
        self.assertIsNone(proctored_exam_student_attempt.completed_at)
        proctored_exam_student_attempt_id = stop_exam_attempt(
            proctored_exam_student_attempt.proctored_exam, self.user_id
        )
        self.assertEqual(proctored_exam_student_attempt.id, proctored_exam_student_attempt_id)

    def test_stop_invalid_exam_attempt_raises_exception(self):
        proctored_exam = self._create_proctored_exam()
        with self.assertRaises(StudentExamAttemptAlreadyExistsException):
            stop_exam_attempt(proctored_exam, self.user_id)
