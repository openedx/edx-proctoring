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
        Test to Save the proctored Exam Student Allowance object
        which also saves the entry in the History Table.
        """
        proctored_exam = ProctoredExam.objects.create(
            course_id='test_course',
            content_id='test_content',
            external_id='123aXqe3'
        )
        ProctoredExamStudentAllowance.objects.create(
            user_id=1,
            proctored_exam=proctored_exam,
            key='test_key',
            value='test_val'
        )
        proctored_exam_student_history = ProctoredExamStudentAllowanceHistory.objects.filter(user_id=1)
        self.assertEqual(len(proctored_exam_student_history), 1)
