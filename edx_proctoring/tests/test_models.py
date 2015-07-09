"""
All tests for the models.py
"""
from edx_proctoring.models import ProctoredExam, ProctoredExamStudentAllowance, ProctoredExamStudentAllowanceHistory

from .utils import (
    LoggedInTestCase
)


class ProctoredExamModelTests(LoggedInTestCase):
    """
    All tests for the models.py
    """

    def setUp(self):
        """
        Build out test harnessing
        """
        super(ProctoredExamModelTests, self).setUp()

    def test_save_proctored_exam_student_allowance_history(self):  # pylint: disable=invalid-name
        """
        Test to Save and update the proctored Exam Student Allowance object.
        Upon first save, a new entry is _not_ created in the History table
        However, a new entry in the History table is created every time the Student Allowance entry is updated.
        """
        proctored_exam = ProctoredExam.objects.create(
            course_id='test_course',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )
        ProctoredExamStudentAllowance.objects.create(
            user_id=1,
            proctored_exam=proctored_exam,
            key='allowance_key',
            value='20 minutes'
        )
        # No entry in the History table on creation of the Allowance entry.
        proctored_exam_student_history = ProctoredExamStudentAllowanceHistory.objects.filter(user_id=1)
        self.assertEqual(len(proctored_exam_student_history), 0)

        # Update the allowance object twice
        ProctoredExamStudentAllowance.objects.filter(
            user_id=1,
            proctored_exam=proctored_exam,
        ).update(
            user=1,
            proctored_exam=proctored_exam,
            key='allowance_key update 1',
            value='10 minutes'
        )

        ProctoredExamStudentAllowance.objects.filter(
            user_id=1,
            proctored_exam=proctored_exam,
        ).update(
            user=1,
            proctored_exam=proctored_exam,
            key='allowance_key update 2',
            value='5 minutes'
        )

        # 2 new entries are created in the History table.
        proctored_exam_student_history = ProctoredExamStudentAllowanceHistory.objects.filter(user_id=1)
        self.assertEqual(len(proctored_exam_student_history), 2)

        # also check with save() method

        allowance = ProctoredExamStudentAllowance.objects.get(user_id=1, proctored_exam=proctored_exam)
        allowance.value = '15 minutes'
        allowance.save()

        proctored_exam_student_history = ProctoredExamStudentAllowanceHistory.objects.filter(user_id=1)
        self.assertEqual(len(proctored_exam_student_history), 3)

    def test_delete_proctored_exam_student_allowance_history(self):  # pylint: disable=invalid-name
        """
        Test to delete the proctored Exam Student Allowance object.
        Upon first save, a new entry is _not_ created in the History table
        However, a new entry in the History table is created every time the Student Allowance entry is updated.
        """
        proctored_exam = ProctoredExam.objects.create(
            course_id='test_course',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )
        allowance = ProctoredExamStudentAllowance.objects.create(
            user_id=1,
            proctored_exam=proctored_exam,
            key='allowance_key',
            value='20 minutes'
        )

        # No entry in the History table on creation of the Allowance entry.
        proctored_exam_student_history = ProctoredExamStudentAllowanceHistory.objects.filter(user_id=1)
        self.assertEqual(len(proctored_exam_student_history), 0)

        allowance.delete()

        proctored_exam_student_history = ProctoredExamStudentAllowanceHistory.objects.filter(user_id=1)
        self.assertEqual(len(proctored_exam_student_history), 1)
