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
            exam_name='अआईउऊऋऌ अआईउऊऋऌ',
            external_id='123aXqe3',
            time_limit_mins=90
        )
        output = str(proctored_exam)
        self.assertEqual(output, "test_course: अआईउऊऋऌ अआईउऊऋऌ (inactive)")

        policy = ProctoredExamReviewPolicy.objects.create(
            set_by_user_id=self.user.id,
            proctored_exam=proctored_exam,
            review_policy='Foo Policy'
        )
        output = str(policy)
        self.assertEqual(output, "ProctoredExamReviewPolicy: tester (test_course: अआईउऊऋऌ अआईउऊऋऌ (inactive))")

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

    def test_get_practice_proctored_exams_for_course(self):
        """
        Test get_practice_proctored_exams_for_course method returns only active
        practice proctored exams.
        """
        course_id = 'test_course'
        # create proctored exam
        ProctoredExam.objects.create(
            course_id=course_id,
            content_id='test_content_1',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True,
            is_proctored=True,
        )
        # create practice proctored exam
        ProctoredExam.objects.create(
            course_id=course_id,
            content_id='test_content_2',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90,
            is_active=True,
            is_proctored=True,
            is_practice_exam=True,
        )
        practice_proctored_exams = ProctoredExam.objects.filter(
            course_id=course_id,
            is_active=True,
            is_proctored=True,
            is_practice_exam=True
        )

        self.assertQuerysetEqual(
            ProctoredExam.get_practice_proctored_exams_for_course(course_id),
            [repr(exam) for exam in practice_proctored_exams]
        )


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

    def test_get_historic_attempt_by_code(self):
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
            allowed_time_limit_mins=10,
            attempt_code="123456",
            taking_as_proctored=True,
            is_sample_attempt=True,
            external_id="external"
        )

        # No entry in the old history table
        attempt_history = ProctoredExamStudentAttemptHistory.objects.filter(attempt_code="123456")
        self.assertEqual(len(attempt_history), 0)

        # Simple history does have an entry and get_historic finds it
        # pylint: disable=no-member
        self.assertEqual(1, len(ProctoredExamStudentAttempt.history.filter(attempt_code="123456")))
        hist_attempt = ProctoredExamStudentAttempt.get_historic_attempt_by_code(attempt.attempt_code)
        self.assertEqual(attempt.external_id, hist_attempt.external_id)

        attempt.delete_exam_attempt()

        # Now there an entry in the old history table
        attempt_history = ProctoredExamStudentAttemptHistory.objects.filter(attempt_code="123456")
        self.assertEqual(len(attempt_history), 1)

        # we need to empty simple history out for this test
        # pylint: disable=no-member
        ProctoredExamStudentAttempt.history.all().delete()
        # pylint: disable=no-member
        self.assertEqual(0, len(ProctoredExamStudentAttempt.history.filter(attempt_code="123456")))

        # and get_historic finds the attempt out of the old table
        hist_attempt = ProctoredExamStudentAttempt.get_historic_attempt_by_code(attempt.attempt_code)
        self.assertEqual(attempt.external_id, hist_attempt.external_id)

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
            allowed_time_limit_mins=10,
            attempt_code="123456",
            taking_as_proctored=True,
            is_sample_attempt=True,
            external_id="external"
        )

        # No entry in the old history table on creation of the Allowance entry.
        attempt_history = ProctoredExamStudentAttemptHistory.objects.filter(user_id=1)
        self.assertEqual(len(attempt_history), 0)

        # Simple history does have an entry
        self.assertEqual(1, len(attempt.history.all()))

        attempt.delete_exam_attempt()

        attempt_history = ProctoredExamStudentAttemptHistory.objects.filter(user_id=1)
        self.assertEqual(len(attempt_history), 1)

        # simple history table has more data
        # pylint: disable=no-member
        attempt_history = ProctoredExamStudentAttempt.history.filter(user_id=1)
        self.assertEqual(len(attempt_history), 2)

        # make sure we can ready it back with the old helper class method
        deleted_item = ProctoredExamStudentAttemptHistory.get_exam_attempt_by_code("123456")
        self.assertEqual(deleted_item.external_id, "external")
        # and the new way
        deleted_item = ProctoredExamStudentAttempt.get_historic_attempt_by_code("123456")
        self.assertEqual(deleted_item.external_id, "external")

        # re-create and delete again using same attempt_code
        attempt = ProctoredExamStudentAttempt.objects.create(
            proctored_exam_id=proctored_exam.id,
            user_id=1,
            allowed_time_limit_mins=10,
            attempt_code="123456",
            taking_as_proctored=True,
            is_sample_attempt=True,
            external_id="updated"
        )

        attempt.delete_exam_attempt()

        attempt_history = ProctoredExamStudentAttemptHistory.objects.filter(user_id=1)
        self.assertEqual(len(attempt_history), 2)

        # simple history table has more data
        # pylint: disable=no-member
        attempt_history = ProctoredExamStudentAttempt.history.filter(user_id=1)
        self.assertEqual(len(attempt_history), 4)

        deleted_item = ProctoredExamStudentAttemptHistory.get_exam_attempt_by_code("123456")
        self.assertEqual(deleted_item.external_id, "updated")
        # and the new way
        deleted_item = ProctoredExamStudentAttempt.get_historic_attempt_by_code("123456")
        self.assertEqual(deleted_item.external_id, "updated")

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
            allowed_time_limit_mins=10,
            attempt_code="123456",
            taking_as_proctored=True,
            is_sample_attempt=True,
            external_id=1
        )

        # No entry in the old History table on creation of the Allowance entry.
        attempt_history = ProctoredExamStudentAttemptHistory.objects.filter(user_id=1)
        self.assertEqual(len(attempt_history), 0)

        # Simple history does have an entry
        self.assertEqual(1, len(attempt.history.all()))

        # re-saving, but not changing status should not make an archive copy
        attempt.external_id = "changed"
        attempt.save()

        attempt_history = ProctoredExamStudentAttemptHistory.objects.filter(user_id=1)
        self.assertEqual(len(attempt_history), 0)

        # Simple history has an entry per change
        self.assertEqual(2, len(attempt.history.all()))

        # change status...
        attempt.status = ProctoredExamStudentAttemptStatus.started
        attempt.save()

        attempt_history = ProctoredExamStudentAttemptHistory.objects.filter(user_id=1)
        self.assertEqual(len(attempt_history), 1)

        # Simple history has an entry per change
        self.assertEqual(3, len(attempt.history.all()))

        # make sure we can ready it back with old helper class method
        updated_item = ProctoredExamStudentAttemptHistory.get_exam_attempt_by_code("123456")
        self.assertEqual(updated_item.external_id, "changed")
        self.assertEqual(updated_item.status, ProctoredExamStudentAttemptStatus.created)

        # simple history reads the latest status
        updated_item = ProctoredExamStudentAttempt.get_historic_attempt_by_code("123456")
        self.assertEqual(updated_item.external_id, "changed")
        self.assertEqual(updated_item.status, ProctoredExamStudentAttemptStatus.started)

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
                proctored_exam.id, user.id,
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

    def test_exam_attempt_is_resumable(self):
        # Create an exam.
        proctored_exam = ProctoredExam.objects.create(
            course_id='a/b/c',
            content_id='test_content',
            exam_name='Test Exam',
            external_id='123aXqe3',
            time_limit_mins=90
        )
        # Create a user and their attempt
        user = User.objects.create(username='testerresumable', email='testerresumable@test.com')
        ProctoredExamStudentAttempt.create_exam_attempt(
            proctored_exam.id, user.id,
            'test_attempt_code_resumable', True, False, 'test_external_id_resumable'
        )

        filter_query = {
            'user_id': user.id,
            'proctored_exam_id': proctored_exam.id
        }

        attempt = ProctoredExamStudentAttempt.objects.get(**filter_query)
        self.assertFalse(attempt.is_resumable)

        # No entry in the History table on creation of the Allowance entry.
        attempt_history = ProctoredExamStudentAttemptHistory.objects.filter(**filter_query)
        self.assertEqual(len(attempt_history), 0)

        # Simple history does have an entry
        # pylint: disable=no-member
        attempt_history = ProctoredExamStudentAttempt.history.filter(**filter_query)
        self.assertEqual(len(attempt_history), 1)

        # Saving as an error status
        attempt.is_resumable = True
        attempt.status = ProctoredExamStudentAttemptStatus.error
        attempt.save()

        attempt = ProctoredExamStudentAttempt.objects.get(**filter_query)
        self.assertTrue(attempt.is_resumable)

        attempt_history = ProctoredExamStudentAttemptHistory.objects.filter(**filter_query)
        self.assertEqual(len(attempt_history), 1)
        self.assertFalse(attempt_history.first().is_resumable)

        # simple history has two entries including the resumable entry
        # pylint: disable=no-member
        attempt_history = ProctoredExamStudentAttempt.history.filter(**filter_query)
        self.assertEqual(len(attempt_history), 2)

        # Saving as a Reviewed status, but not changing is_resumable
        attempt.status = ProctoredExamStudentAttemptStatus.verified
        attempt.save()
        attempt = ProctoredExamStudentAttempt.objects.get(**filter_query)
        self.assertTrue(attempt.is_resumable)

        attempt_history = ProctoredExamStudentAttemptHistory.objects.filter(**filter_query)
        self.assertEqual(len(attempt_history), 2)
        self.assertTrue(attempt_history.last().is_resumable)

        # pylint: disable=no-member
        attempt_history = ProctoredExamStudentAttempt.history.filter(**filter_query)
        self.assertEqual(len(attempt_history), 3)
