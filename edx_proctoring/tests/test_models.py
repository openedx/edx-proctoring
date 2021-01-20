# coding=utf-8
# pylint: disable=invalid-name
"""
All tests for the models.py
"""

from django.contrib.auth import get_user_model

from edx_proctoring.models import (
    ProctoredExam,
    ProctoredExamReviewPolicy,
    ProctoredExamReviewPolicyHistory,
    ProctoredExamStudentAllowance,
    ProctoredExamStudentAllowanceHistory,
    ProctoredExamStudentAttempt,
    ProctoredExamStudentAttemptHistory
)
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus

from .utils import LoggedInTestCase

User = get_user_model()

# pragma pylint: disable=useless-super-delegation


class ProctoredExamModelTests(LoggedInTestCase):
    """
    All tests for the models.py
    """

    def setUp(self):
        """
        Build out test harnessing
        """
        super().setUp()

    def test_unicode(self):
        """
        Make sure we support Unicode characters
        """
        proctored_exam = ProctoredExam.objects.create(
            course_id='test_course',
            content_id='test_content',
            exam_name=u'अआईउऊऋऌ अआईउऊऋऌ',
            external_id='123aXqe3',
            time_limit_mins=90
        )
        output = str(proctored_exam)
        self.assertEqual(output, u"test_course: अआईउऊऋऌ अआईउऊऋऌ (inactive)")

        policy = ProctoredExamReviewPolicy.objects.create(
            set_by_user_id=self.user.id,
            proctored_exam=proctored_exam,
            review_policy='Foo Policy'
        )
        output = str(policy)
        self.assertEqual(output, u"ProctoredExamReviewPolicy: tester (test_course: अआईउऊऋऌ अआईउऊऋऌ (inactive))")

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
        # pylint: disable=no-member
        ProctoredExamStudentAllowance.objects.filter(
            user_id=1,
            proctored_exam=proctored_exam,
        ).update(
            user=1,
            proctored_exam=proctored_exam,
            key='allowance_key update 1',
            value='10 minutes'
        )

        # pylint: disable=no-member
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


class ProctoredExamStudentAttemptTests(LoggedInTestCase):
    """
    Tests for the ProctoredExamStudentAttempt Model
    """

    def test_exam_unicode(self):
        """
        Serialize the object as a display string
        """
        proctored_exam = ProctoredExam.objects.create(
            course_id='test_course',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )

        string = str(proctored_exam)
        self.assertEqual(string, "test_course: Test Exam (inactive)")

    def test_delete_proctored_exam_attempt(self):  # pylint: disable=invalid-name
        """
        Deleting the proctored exam attempt creates an entry in the history table.
        """
        proctored_exam = ProctoredExam.objects.create(
            course_id='test_course',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )

        attempt = ProctoredExamStudentAttempt.objects.create(
            proctored_exam_id=proctored_exam.id,
            user_id=1,
            student_name="John. D",
            allowed_time_limit_mins=10,
            attempt_code="123456",
            taking_as_proctored=True,
            is_sample_attempt=True,
            external_id=1
        )

        # No entry in the History table on creation of the Allowance entry.
        attempt_history = ProctoredExamStudentAttemptHistory.objects.filter(user_id=1)
        self.assertEqual(len(attempt_history), 0)

        attempt.delete_exam_attempt()

        attempt_history = ProctoredExamStudentAttemptHistory.objects.filter(user_id=1)
        self.assertEqual(len(attempt_history), 1)

        # make sure we can ready it back with helper class method
        deleted_item = ProctoredExamStudentAttemptHistory.get_exam_attempt_by_code("123456")
        self.assertEqual(deleted_item.student_name, "John. D")

        # re-create and delete again using same attempt_cde
        attempt = ProctoredExamStudentAttempt.objects.create(
            proctored_exam_id=proctored_exam.id,
            user_id=1,
            student_name="John. D Updated",
            allowed_time_limit_mins=10,
            attempt_code="123456",
            taking_as_proctored=True,
            is_sample_attempt=True,
            external_id=1
        )

        attempt.delete_exam_attempt()

        attempt_history = ProctoredExamStudentAttemptHistory.objects.filter(user_id=1)
        self.assertEqual(len(attempt_history), 2)

        deleted_item = ProctoredExamStudentAttemptHistory.get_exam_attempt_by_code("123456")
        self.assertEqual(deleted_item.student_name, "John. D Updated")

    def test_update_proctored_exam_attempt(self):
        """
        Deleting the proctored exam attempt creates an entry in the history table.
        """
        proctored_exam = ProctoredExam.objects.create(
            course_id='test_course',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )
        attempt = ProctoredExamStudentAttempt.objects.create(
            proctored_exam_id=proctored_exam.id,
            user_id=1,
            status=ProctoredExamStudentAttemptStatus.created,
            student_name="John. D",
            allowed_time_limit_mins=10,
            attempt_code="123456",
            taking_as_proctored=True,
            is_sample_attempt=True,
            external_id=1
        )

        # No entry in the History table on creation of the Allowance entry.
        attempt_history = ProctoredExamStudentAttemptHistory.objects.filter(user_id=1)
        self.assertEqual(len(attempt_history), 0)

        # re-saving, but not changing status should not make an archive copy
        attempt.student_name = 'John. D Updated'
        attempt.save()

        attempt_history = ProctoredExamStudentAttemptHistory.objects.filter(user_id=1)
        self.assertEqual(len(attempt_history), 0)

        # change status...
        attempt.status = ProctoredExamStudentAttemptStatus.started
        attempt.save()

        attempt_history = ProctoredExamStudentAttemptHistory.objects.filter(user_id=1)
        self.assertEqual(len(attempt_history), 1)

        # make sure we can ready it back with helper class method
        updated_item = ProctoredExamStudentAttemptHistory.get_exam_attempt_by_code("123456")
        self.assertEqual(updated_item.student_name, "John. D Updated")
        self.assertEqual(updated_item.status, ProctoredExamStudentAttemptStatus.created)

    def test_get_exam_attempts(self):
        """
        Test to get all the exam attempts for a course
        """
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )

        # create number of exam attempts
        for i in range(90):
            user = User.objects.create(username='tester{0}'.format(i), email='tester{0}@test.com'.format(i))
            ProctoredExamStudentAttempt.create_exam_attempt(
                proctored_exam.id, user.id, 'test_name{0}'.format(i),
                'test_attempt_code{0}'.format(i), True, False, 'test_external_id{0}'.format(i)
            )

        with self.assertNumQueries(1):
            exam_attempts = ProctoredExamStudentAttempt.objects.get_all_exam_attempts('a/b/c')
            self.assertEqual(len(exam_attempts), 90)

    def test_exam_review_policy(self):
        """
        Assert correct behavior of the Exam Policy model including archiving of updates and deletes
        """

        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )

        policy = ProctoredExamReviewPolicy.objects.create(
            set_by_user_id=self.user.id,
            proctored_exam=proctored_exam,
            review_policy='Foo Policy',
        )

        attempt = ProctoredExamStudentAttempt.create_exam_attempt(
            proctored_exam.id,
            self.user.id,
            'test_name{0}'.format(self.user.id),
            'test_attempt_code{0}'.format(self.user.id),
            True,
            False,
            'test_external_id{0}'.format(self.user.id)
        )
        attempt.review_policy_id = policy.id
        attempt.save()

        history = ProctoredExamReviewPolicyHistory.objects.all()
        self.assertEqual(len(history), 0)

        # now update it
        policy.review_policy = 'Updated Foo Policy'
        policy.save()

        # look in history
        history = ProctoredExamReviewPolicyHistory.objects.all()
        self.assertEqual(len(history), 1)
        previous = history[0]
        self.assertEqual(previous.set_by_user_id, self.user.id)
        self.assertEqual(previous.proctored_exam_id, proctored_exam.id)
        self.assertEqual(previous.original_id, policy.id)
        self.assertEqual(previous.review_policy, 'Foo Policy')

        # now delete updated one
        deleted_id = policy.id
        policy.delete()

        # look in history
        history = ProctoredExamReviewPolicyHistory.objects.all()
        self.assertEqual(len(history), 2)
        previous = history[0]
        self.assertEqual(previous.set_by_user_id, self.user.id)
        self.assertEqual(previous.proctored_exam_id, proctored_exam.id)
        self.assertEqual(previous.original_id, deleted_id)
        self.assertEqual(previous.review_policy, 'Foo Policy')

        previous = history[1]
        self.assertEqual(previous.set_by_user_id, self.user.id)
        self.assertEqual(previous.proctored_exam_id, proctored_exam.id)
        self.assertEqual(previous.original_id, deleted_id)
        self.assertEqual(previous.review_policy, 'Updated Foo Policy')

        # assert that we cannot delete history!
        with self.assertRaises(NotImplementedError):
            previous.delete()

        # now delete attempt, to make sure we preserve the policy_id in the archive table
        attempt.delete()

        attempts = ProctoredExamStudentAttemptHistory.objects.all()
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0].review_policy_id, deleted_id)
