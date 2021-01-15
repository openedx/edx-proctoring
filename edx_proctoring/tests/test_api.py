# coding=utf-8
# pylint: disable=too-many-lines, invalid-name

"""
All tests for the api.py
"""

from datetime import datetime, timedelta
from itertools import product

import ddt
import pytz
from freezegun import freeze_time
from mock import MagicMock, patch

from edx_proctoring.api import (
    _are_prerequirements_satisfied,
    _check_for_attempt_timeout,
    _get_ordered_prerequisites,
    _get_review_policy_by_exam_id,
    add_allowance_for_user,
    create_exam,
    create_exam_attempt,
    create_exam_review_policy,
    does_backend_support_onboarding,
    get_active_exams_for_user,
    get_all_exam_attempts,
    get_all_exams_for_course,
    get_allowances_for_course,
    get_attempt_status_summary,
    get_backend_provider,
    get_current_exam_attempt,
    get_exam_attempt_by_id,
    get_exam_by_content_id,
    get_exam_by_id,
    get_exam_configuration_dashboard_url,
    get_exam_violation_report,
    get_filtered_exam_attempts,
    get_integration_specific_email,
    get_last_exam_completion_date,
    get_review_policy_by_exam_id,
    is_backend_dashboard_available,
    mark_exam_attempt_as_ready,
    mark_exam_attempt_timeout,
    remove_allowance_for_user,
    remove_exam_attempt,
    remove_review_policy,
    reset_practice_exam,
    start_exam_attempt,
    start_exam_attempt_by_code,
    stop_exam_attempt,
    update_attempt_status,
    update_exam,
    update_exam_attempt,
    update_review_policy
)
from edx_proctoring.constants import DEFAULT_CONTACT_EMAIL
from edx_proctoring.exceptions import (
    AllowanceValueNotAllowedException,
    BackendProviderSentNoAttemptID,
    ProctoredExamAlreadyExists,
    ProctoredExamIllegalStatusTransition,
    ProctoredExamNotFoundException,
    ProctoredExamPermissionDenied,
    ProctoredExamReviewPolicyAlreadyExists,
    ProctoredExamReviewPolicyNotFoundException,
    StudentExamAttemptAlreadyExistsException,
    StudentExamAttemptDoesNotExistsException,
    StudentExamAttemptedAlreadyStarted,
    StudentExamAttemptOnPastDueProctoredExam,
    UserNotFoundException
)
from edx_proctoring.models import (
    ProctoredExam,
    ProctoredExamReviewPolicy,
    ProctoredExamSoftwareSecureComment,
    ProctoredExamSoftwareSecureReview,
    ProctoredExamStudentAllowance,
    ProctoredExamStudentAttempt,
    ProctoredExamStudentAttemptHistory
)
from edx_proctoring.runtime import get_runtime_service, set_runtime_service
from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus
from edx_proctoring.tests import mock_perm

from .test_services import (
    MockCertificateService,
    MockCreditService,
    MockCreditServiceNone,
    MockCreditServiceWithCourseEndDate,
    MockGradesService
)
from .utils import ProctoredExamTestCase


@patch('django.urls.reverse', MagicMock)
@ddt.ddt
class ProctoredExamApiTests(ProctoredExamTestCase):
    """
    All tests for the models.py
    """

    def setUp(self):
        """
        Initialize
        """
        super().setUp()
        set_runtime_service('certificates', MockCertificateService())

    def tearDown(self):
        """
        When tests are done
        """
        super().tearDown()
        set_runtime_service('certificates', None)

    def _add_allowance_for_user(self):
        """
        creates allowance for user.
        """
        return ProctoredExamStudentAllowance.objects.create(
            proctored_exam_id=self.proctored_exam_id, user_id=self.user_id, key=self.key, value=self.value
        )

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
            self.practice_exam_id, time_limit_mins=31, is_practice_exam=True, backend='null'
        )

        # only those fields were updated, whose
        # values are passed.
        self.assertEqual(self.practice_exam_id, updated_practice_exam_id)

        update_practice_exam = ProctoredExam.objects.get(id=updated_practice_exam_id)

        self.assertEqual(update_practice_exam.time_limit_mins, 31)
        self.assertEqual(update_practice_exam.course_id, self.course_id)
        self.assertEqual(update_practice_exam.content_id, 'test_content_id_practice')
        self.assertEqual(update_practice_exam.backend, 'null')

    def test_update_proctored_exam(self):
        """
        test update the existing proctored exam
        """
        updated_proctored_exam_id = update_exam(
            self.proctored_exam_id, exam_name='Updated Exam Name', time_limit_mins=30,
            is_proctored=True, external_id='external_id', is_active=True,
            due_date=datetime.now(pytz.UTC)
        )

        # only those fields were updated, whose
        # values are passed.
        self.assertEqual(self.proctored_exam_id, updated_proctored_exam_id)

        update_proctored_exam = ProctoredExam.objects.get(id=updated_proctored_exam_id)

        self.assertEqual(update_proctored_exam.exam_name, 'Updated Exam Name')
        self.assertEqual(update_proctored_exam.time_limit_mins, 30)
        self.assertEqual(update_proctored_exam.course_id, self.course_id)
        self.assertEqual(update_proctored_exam.content_id, 'test_content_id')

    def test_update_timed_exam(self):
        """
        test update the existing timed exam
        """
        updated_timed_exam_id = update_exam(self.timed_exam_id, hide_after_due=True)

        self.assertEqual(self.timed_exam_id, updated_timed_exam_id)

        update_timed_exam = ProctoredExam.objects.get(id=updated_timed_exam_id)

        self.assertEqual(update_timed_exam.hide_after_due, True)

    def test_switch_from_proctored_to_timed(self):
        """
        Test that switches an exam from proctored to timed.
        The backend should be notified that the exam is inactive
        """
        proctored_exam = get_exam_by_id(self.proctored_exam_id)
        update_exam(self.proctored_exam_id, is_proctored=False)
        backend = get_backend_provider(proctored_exam)
        self.assertEqual(backend.last_exam['is_active'], False)

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
        self.assertEqual(len(exams), 5)

    def test_create_exam_review_policy(self):
        """
        Test to create a new exam review policy for
        proctored exam and tests that it stores in the
        db correctly
        """
        proctored_exam = get_exam_by_id(self.proctored_exam_id)
        create_exam_review_policy(
            exam_id=proctored_exam['id'],
            set_by_user_id=self.user_id,
            review_policy=u'allow use of paper',
        )

        # now get the exam review policy for the proctored exam
        exam_review_policy = get_review_policy_by_exam_id(proctored_exam['id'])

        self.assertEqual(exam_review_policy['proctored_exam']['id'], proctored_exam['id'])
        self.assertEqual(exam_review_policy['set_by_user']['id'], self.user_id)
        self.assertEqual(exam_review_policy['review_policy'], u'allow use of paper')

        # this tests that the backend received the callback when the review policy changed
        backend = get_backend_provider(proctored_exam)
        self.assertEqual(backend.last_exam['rule_summary'], u'allow use of paper')

    def test_get_exam_review_policy(self):
        """
        Test that creates a new exam policy and tests
        that the policy can be properly retrieved
        """
        proctored_exam = get_exam_by_id(self.proctored_exam_id)
        create_exam_review_policy(
            exam_id=proctored_exam['id'],
            set_by_user_id=self.user_id,
            review_policy=u'allow use of paper',
        )

        # now get the exam review policy for the proctored exam
        exam_review_policy_string = _get_review_policy_by_exam_id(proctored_exam['id'])

        self.assertEqual(exam_review_policy_string, u'allow use of paper')

    def test_update_exam_review_policy_updates_review_policy(self):
        """
        Test to update existing exam review policy's review
        policy for proctored exam and tests that it stores in the
        db correctly.
        """
        proctored_exam = get_exam_by_id(self.proctored_exam_id)
        create_exam_review_policy(
            exam_id=proctored_exam['id'],
            set_by_user_id=self.user_id,
            review_policy=u'allow use of paper',
        )

        # now update the exam review policy's review policy for the proctored exam
        update_review_policy(
            exam_id=proctored_exam['id'],
            set_by_user_id=self.user_id,
            review_policy=u'allow use of calculator',
        )

        # now get the updated exam review policy for the proctored exam
        exam_review_policy = get_review_policy_by_exam_id(proctored_exam['id'])

        self.assertEqual(exam_review_policy['proctored_exam']['id'], proctored_exam['id'])
        self.assertEqual(exam_review_policy['set_by_user']['id'], self.user_id)
        self.assertEqual(exam_review_policy['review_policy'], u'allow use of calculator')

    def test_update_review_policy_with_empty_review_policy_removes_review_policy(self):
        """
        Test that updating an proctored exam's exam review policy with an
        empty review policy removes the exam review policy.
        """
        proctored_exam = get_exam_by_id(self.proctored_exam_id)
        create_exam_review_policy(
            exam_id=proctored_exam['id'],
            set_by_user_id=self.user_id,
            review_policy=u'allow use of paper',
        )
        # now update the exam review policy for the proctored exam
        # with review_policy value to "" and rules value to "".
        # This will delete the exam
        # review policy object from the database.
        update_review_policy(
            exam_id=proctored_exam['id'],
            set_by_user_id=self.user_id,
            review_policy=u'',
        )
        with self.assertRaises(ProctoredExamReviewPolicyNotFoundException):
            get_review_policy_by_exam_id(proctored_exam['id'])

    def test_remove_existing_exam_review_policy(self):
        """
        Test to remove existing exam review policy for
        proctored exam
        """
        proctored_exam = get_exam_by_id(self.proctored_exam_id)
        create_exam_review_policy(
            exam_id=proctored_exam['id'],
            set_by_user_id=self.user_id,
            review_policy=u'allow use of paper',
        )

        # now remove the exam review policy for the proctored exam
        remove_review_policy(
            exam_id=proctored_exam['id']
        )

        # now get the exam review policy for the proctored exam
        # which will raise the exception because the exam review
        # policy has been removed.
        with self.assertRaises(ProctoredExamReviewPolicyNotFoundException):
            get_review_policy_by_exam_id(proctored_exam['id'])

    def test_remove_non_existing_exam_review_policy(self):
        """
        Test to remove non existing exam review policy for
        proctored exam which will raise exception
        """
        proctored_exam = get_exam_by_id(self.proctored_exam_id)

        # now try to remove the non-existing exam review policy
        # for the proctored exam which will raise exception
        with self.assertRaises(ProctoredExamReviewPolicyNotFoundException):
            remove_review_policy(
                exam_id=proctored_exam['id']
            )

    def test_update_non_existing_exam_review_policy(self):
        """
        Test to update non existing exam review policy for
        proctored exam and it will raises exception
        """

        # update the non existing exam review policy for the proctored exam
        with self.assertRaises(ProctoredExamReviewPolicyNotFoundException):
            update_review_policy(
                exam_id=self.practice_exam_id,
                set_by_user_id=10,
                review_policy=u'allow use of calculator',
            )

    def test_create_exam_review_policy_with_same_exam_id(self):
        """
        Test to create a same exam review policy will raise exception
        """
        proctored_exam = get_exam_by_id(self.proctored_exam_id)
        create_exam_review_policy(
            exam_id=proctored_exam['id'],
            set_by_user_id=self.user_id,
            review_policy=u'allow use of paper',
        )

        # create the same review policy again will raise exception
        with self.assertRaises(ProctoredExamReviewPolicyAlreadyExists):
            create_exam_review_policy(
                exam_id=proctored_exam['id'],
                set_by_user_id=self.user_id,
                review_policy=u'allow use of paper',
            )

    def test_get_non_existing_review_policy_raises_exception(self):
        """
        Test to get the non-existing review policy raises exception
        """
        with self.assertRaises(ProctoredExamReviewPolicyNotFoundException):
            # now get the exam review policy for the proctored exam
            get_review_policy_by_exam_id(self.practice_exam_id)

    def test_get_timed_exam(self):
        """
        test to get the exam by the exam_id and
        then compare their values.
        """
        timed_exam = get_exam_by_id(self.timed_exam_id)
        self.assertEqual(timed_exam['course_id'], self.course_id)
        self.assertEqual(timed_exam['content_id'], self.content_id_timed)
        self.assertEqual(timed_exam['exam_name'], self.exam_name)

        timed_exam = get_exam_by_content_id(self.course_id, self.content_id_timed)
        self.assertEqual(timed_exam['course_id'], self.course_id)
        self.assertEqual(timed_exam['content_id'], self.content_id_timed)
        self.assertEqual(timed_exam['exam_name'], self.exam_name)

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

    @ddt.data('invalid', '-2', '-99', 'invalid123')
    def test_add_invalid_allowance_value(self, allowance_value):
        """
        Test to add allowance for invalid allowance value.
        """
        with self.assertRaises(AllowanceValueNotAllowedException):
            add_allowance_for_user(self.proctored_exam_id, self.user.username, self.key, allowance_value)

    def test_update_existing_allowance(self):
        """
        Test updation to the allowance that already exists.
        """
        student_allowance = self._add_allowance_for_user()
        add_allowance_for_user(student_allowance.proctored_exam.id, self.user.username, self.key, '4')

        student_allowance = ProctoredExamStudentAllowance.get_allowance_for_user(
            student_allowance.proctored_exam.id, self.user_id, self.key
        )
        self.assertIsNotNone(student_allowance)
        self.assertEqual(student_allowance.value, '4')

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

    def test_exam_attempt_with_due_datetime(self):
        """
        Test the exam attempt with due date
        """

        due_date = datetime.now(pytz.UTC) + timedelta(days=1)

        # exam is created with due datetime > current_datetime and due_datetime < current_datetime + allowed_mins
        exam_id = self._create_exam_with_due_time(due_date=due_date)
        attempt_id = create_exam_attempt(exam_id, self.user_id)

        # due_date is exactly after 24 hours, our exam's allowed minutes are 21
        # student will get full allowed minutes if student will start exam within next 23 hours and 39 minutes
        # otherwise allowed minutes = due_datetime - exam_attempt_datetime
        # so if students starts exam after 23 hours and 45 minutes later then he will get only 15 minutes
        minutes_before_past_due_date = 15
        reset_time = due_date - timedelta(minutes=minutes_before_past_due_date)

        with freeze_time(reset_time):
            __ = start_exam_attempt(exam_id, self.user_id)
            attempt = get_exam_attempt_by_id(attempt_id)
            self.assertLessEqual(minutes_before_past_due_date - 1, attempt['allowed_time_limit_mins'])
            self.assertLessEqual(attempt['allowed_time_limit_mins'], minutes_before_past_due_date)

    def test_no_time_limit_if_not_started(self):
        """
        Test the the time limit is not calculated before an attempt is started.
        """
        attempt_id = create_exam_attempt(exam_id=self.proctored_exam_id, user_id=self.user_id)
        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertIsNone(attempt['allowed_time_limit_mins'])

    def test_resumed_exam_attempt_time_limit(self):
        """
        Test that a resumed exam attempt accounts for the time remaining when calculating the time limit
        """
        attempt_id = create_exam_attempt(exam_id=self.proctored_exam_id, user_id=self.user_id)
        update_exam_attempt(attempt_id, time_remaining_seconds=60)
        with freeze_time(datetime.now(pytz.UTC)):
            start_exam_attempt(self.proctored_exam_id, self.user_id)
            attempt = get_exam_attempt_by_id(attempt_id)
            # assert that the time limit matches the saved time remaining, rather than the exam's
            # default time limit
            self.assertEqual(attempt['allowed_time_limit_mins'], 1)

    @ddt.data(
        True,
        False
    )
    def test_exam_attempt_past_due_datettime(self, taking_as_proctored):
        """
        Testing creating the exam attempt while the exam due date is in the past
        """
        due_date = datetime.now(pytz.UTC) - timedelta(hours=1)

        exam_id = self._create_exam_with_due_time(due_date=due_date)

        if taking_as_proctored:
            with self.assertRaises(StudentExamAttemptOnPastDueProctoredExam):
                attempt_id = create_exam_attempt(
                    exam_id,
                    self.user_id,
                    taking_as_proctored=taking_as_proctored
                )
        else:
            attempt_id = create_exam_attempt(
                exam_id,
                self.user_id,
                taking_as_proctored=taking_as_proctored
            )
            attempt = get_exam_attempt_by_id(attempt_id)
            self.assertIsNotNone(attempt)
            self.assertIsNone(attempt.get('external_id'))

    def test_create_an_exam_attempt(self):
        """
        Create an unstarted exam attempt.
        """
        attempt_id = create_exam_attempt(self.proctored_exam_id, self.user_id)
        self.assertGreater(attempt_id, 0)

    def test_attempt_with_review_policy(self):
        """
        Create an unstarted exam attempt with a review policy associated with it.
        """

        policy = ProctoredExamReviewPolicy.objects.create(
            set_by_user_id=self.user_id,
            proctored_exam_id=self.proctored_exam_id,
            review_policy='Foo Policy'
        )

        attempt_id = create_exam_attempt(self.proctored_exam_id, self.user_id)
        self.assertGreater(attempt_id, 0)

        # make sure we recorded the policy id at the time this was created
        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertEqual(attempt['review_policy_id'], policy.id)

    def test_attempt_with_allowance(self):
        """
        Create an unstarted exam attempt with additional time.
        """
        allowed_extra_time = 10
        add_allowance_for_user(
            self.proctored_exam_id,
            self.user.username,
            ProctoredExamStudentAllowance.ADDITIONAL_TIME_GRANTED,
            str(allowed_extra_time)
        )
        attempt_id = create_exam_attempt(self.proctored_exam_id, self.user_id)
        start_exam_attempt(self.proctored_exam_id, self.user_id)
        self.assertGreater(attempt_id, 0)

        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertEqual(attempt['allowed_time_limit_mins'], self.default_time_limit + allowed_extra_time)

    @ddt.data(
        ProctoredExamStudentAttemptStatus.ready_to_resume,
        ProctoredExamStudentAttemptStatus.resumed,
    )
    def test_resume_exam_attempt(self, status):
        """
        Create a resumed exam attempt with remaining time saved from the previous attempt.
        """
        # create an attempt that has been marked ready to resume
        initial_attempt = self._create_exam_attempt(self.proctored_exam_id, status)
        # populate the remaining time
        initial_attempt.time_remaining_seconds = 600
        initial_attempt.save()

        # create a new attempt, which should save the remaining time
        # and update the previous attempt's status to 'resumed'
        current_attempt_id = create_exam_attempt(self.proctored_exam_id, self.user_id)
        previous_attempt = get_exam_attempt_by_id(initial_attempt.id)
        current_attempt = get_exam_attempt_by_id(current_attempt_id)
        self.assertEqual(current_attempt['time_remaining_seconds'], 600)
        self.assertEqual(previous_attempt['status'], ProctoredExamStudentAttemptStatus.resumed)

    @ddt.data(
        ProctoredExamStudentAttemptStatus.eligible,
        ProctoredExamStudentAttemptStatus.created,
        ProctoredExamStudentAttemptStatus.download_software_clicked,
        ProctoredExamStudentAttemptStatus.ready_to_start,
        ProctoredExamStudentAttemptStatus.started,
        ProctoredExamStudentAttemptStatus.ready_to_submit,
        ProctoredExamStudentAttemptStatus.declined,
        ProctoredExamStudentAttemptStatus.timed_out,
        ProctoredExamStudentAttemptStatus.submitted,
        ProctoredExamStudentAttemptStatus.second_review_required,
        ProctoredExamStudentAttemptStatus.rejected,
        ProctoredExamStudentAttemptStatus.expired
    )
    def test_resume_from_invalid_attempt(self, status):
        """
        An exam cannot be resumed if the previous attempt is not 'ready to resume' or 'resumed'
        """
        self._create_exam_attempt(self.proctored_exam_id, status)
        with self.assertRaises(StudentExamAttemptAlreadyExistsException):
            create_exam_attempt(self.proctored_exam_id, self.user_id)

    @ddt.data(
        *ProctoredExamStudentAttemptStatus.onboarding_errors
    )
    def test_attempt_onboarding_error(self, onboarding_error):
        """
        Test that onboarding errors move the attempt to an errored state
        """
        test_backend = get_backend_provider(name='test')
        test_backend.attempt_error = onboarding_error
        attempt_id = create_exam_attempt(self.proctored_exam_id, self.user_id, taking_as_proctored=True)
        attempt = get_exam_attempt_by_id(attempt_id)
        assert attempt['status'] == onboarding_error
        test_backend.attempt_error = None

    def test_attempt_without_attempt_id(self):
        """
        Test that the exam attempt is throwing exceptions when the attempt id is not included in the
        API response from proctoring backend
        """
        test_backend = get_backend_provider(name='test')
        test_backend.no_attempt_id_error = 'No id returned'
        with self.assertRaises(BackendProviderSentNoAttemptID):
            create_exam_attempt(self.proctored_exam_id, self.user_id, taking_as_proctored=True)
        test_backend.no_attempt_id_error = None

    def test_no_existing_attempt(self):
        """
        Make sure we get back a None when calling get_exam_attempt_by_id() with a non existing attempt
        """
        self.assertIsNone(get_exam_attempt_by_id(0))

    def test_check_for_attempt_timeout_with_none(self):
        """
        Make sure that we can safely pass in a None into _check_for_attempt_timeout
        """
        self.assertIsNone(_check_for_attempt_timeout(None))

    def test_recreate_an_exam_attempt(self):
        """
        Start an exam attempt that has already been created.
        Raises StudentExamAttemptAlreadyExistsException
        """
        proctored_exam_student_attempt = self._create_unstarted_exam_attempt()
        with self.assertRaises(StudentExamAttemptAlreadyExistsException):
            create_exam_attempt(proctored_exam_student_attempt.proctored_exam.id, self.user_id)

    def test_recreate_a_practice_exam_attempt(self):
        """
        Taking the practice exam several times should not cause an exception.
        """
        practice_exam_student_attempt = self._create_started_practice_exam_attempt()
        new_attempt_id = create_exam_attempt(practice_exam_student_attempt.proctored_exam.id, self.user_id)
        self.assertGreater(new_attempt_id, practice_exam_student_attempt.id, "New attempt not created.")

    def test_get_current_exam_attempt(self):
        """
        Test to get the current exam attempt. Old attempts should be ignored
        """
        self._create_exam_attempt(self.proctored_exam_id, ProctoredExamStudentAttemptStatus.error)
        recent_attempt = self._create_unstarted_exam_attempt()
        exam_attempt = get_current_exam_attempt(self.proctored_exam_id, self.user_id)

        self.assertEqual(exam_attempt['proctored_exam']['id'], self.proctored_exam_id)
        self.assertEqual(exam_attempt['user']['id'], self.user_id)
        self.assertEqual(exam_attempt['id'], recent_attempt.id)

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
            proctored_exam_student_attempt.proctored_exam.id, self.user_id
        )
        self.assertEqual(proctored_exam_student_attempt.id, proctored_exam_attempt_id)

    def test_remove_exam_attempt(self):
        """
        Calling the api remove function removes the attempt.
        """
        with self.assertRaises(StudentExamAttemptDoesNotExistsException):
            remove_exam_attempt(9999, requesting_user=self.user)

        proctored_exam_student_attempt = self._create_unstarted_exam_attempt()
        remove_exam_attempt(proctored_exam_student_attempt.id, requesting_user=self.user)
        test_backend = get_backend_provider(name='test')

        self.assertEqual(
            test_backend.last_attempt_remove, (
                proctored_exam_student_attempt.proctored_exam.external_id,
                proctored_exam_student_attempt.external_id
            )
        )
        with self.assertRaises(StudentExamAttemptDoesNotExistsException):
            remove_exam_attempt(proctored_exam_student_attempt.id, requesting_user=self.user)

    def test_remove_no_user(self):
        """
        Attempting to remove an exam attempt without providing a requesting user will fail.
        """
        proctored_exam_student_attempt = self._create_unstarted_exam_attempt()
        with self.assertRaises(UserNotFoundException):
            remove_exam_attempt(proctored_exam_student_attempt.id, requesting_user={})

    @ddt.data(
        (ProctoredExamStudentAttemptStatus.verified, 'satisfied'),
        (ProctoredExamStudentAttemptStatus.submitted, 'submitted'),
        (ProctoredExamStudentAttemptStatus.declined, 'declined'),
        (ProctoredExamStudentAttemptStatus.error, 'failed'),
        (ProctoredExamStudentAttemptStatus.second_review_required, None),
    )
    @ddt.unpack
    def test_remove_exam_attempt_with_status(self, to_status, requirement_status):
        """
        Test to remove the exam attempt which calls
        the Credit Service method `remove_credit_requirement_status`.
        """

        exam_attempt = self._create_started_exam_attempt()
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            to_status
        )

        # make sure the credit requirement status is there
        credit_service = get_runtime_service('credit')
        credit_status = credit_service.get_credit_state(self.user.id, exam_attempt.proctored_exam.course_id)

        if requirement_status:
            self.assertEqual(len(credit_status['credit_requirement_status']), 1)
            self.assertEqual(
                credit_status['credit_requirement_status'][0]['status'],
                requirement_status
            )

            # now remove exam attempt which calls the credit service method 'remove_credit_requirement_status'
            remove_exam_attempt(exam_attempt.proctored_exam_id, requesting_user=self.user)

            # make sure the credit requirement status is no longer there
            credit_status = credit_service.get_credit_state(self.user.id, exam_attempt.proctored_exam.course_id)

            self.assertEqual(len(credit_status['credit_requirement_status']), 0)
        else:
            # There is not an expected changed to the credit requirement table
            # given the attempt status
            self.assertEqual(len(credit_status['credit_requirement_status']), 0)

    def test_reset_practice_exam(self):
        """
        Reset returns a user's exam attempt to the created state
        """
        with self.assertRaises(StudentExamAttemptDoesNotExistsException):
            reset_practice_exam(self.practice_exam_id, self.user_id, self.user)

        practice_attempt = self._create_exam_attempt(
            self.practice_exam_id,
            status=ProctoredExamStudentAttemptStatus.rejected,
            is_practice_exam=True,
        )
        reset_practice_exam(self.practice_exam_id, self.user_id, self.user)

        current_attempt = ProctoredExamStudentAttempt.objects.get_current_exam_attempt(
            self.practice_exam_id, self.user.id
        )
        self.assertEqual(current_attempt.status, ProctoredExamStudentAttemptStatus.created)
        self.assertIsNone(current_attempt.started_at)
        self.assertIsNone(current_attempt.completed_at)
        self.assertIsNone(current_attempt.allowed_time_limit_mins)

        practice_attempt.refresh_from_db()
        self.assertEqual(practice_attempt.status, ProctoredExamStudentAttemptStatus.onboarding_reset)

    def test_reset_exam_in_progress(self):
        """
        If an attempt is in progress it may not be reset
        """
        self._create_exam_attempt(
            self.practice_exam_id,
            status=ProctoredExamStudentAttemptStatus.started,
            is_practice_exam=True,
        )
        with self.assertRaises(ProctoredExamIllegalStatusTransition):
            reset_practice_exam(self.practice_exam_id, self.user_id, self.user)

    def test_reset_non_practice_exam(self):
        """
        Only practice exams may be reset
        """
        self._create_exam_attempt(
            self.proctored_exam_id,
            status=ProctoredExamStudentAttemptStatus.rejected,
            is_practice_exam=True,
        )
        with self.assertRaises(ProctoredExamIllegalStatusTransition):
            reset_practice_exam(self.proctored_exam_id, self.user_id, self.user)

    def test_reset_verified_exam(self):
        """
        If an attempt has been verified it may not be reset
        """
        self._create_exam_attempt(
            self.practice_exam_id,
            status=ProctoredExamStudentAttemptStatus.verified,
            is_practice_exam=True,
        )
        with self.assertRaises(ProctoredExamIllegalStatusTransition):
            reset_practice_exam(self.practice_exam_id, self.user_id, self.user)

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
            proctored_exam_student_attempt.proctored_exam.id, self.user_id
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
        add_allowance_for_user(self.proctored_exam_id, self.user.username, 'new_key', '2')
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

    def test_get_filtered_exam_attempts_resumed(self):
        """
        Test to get all exam attempts from a single user who has resumed from previous attempts.
        """
        # create the first attempt
        first_exam_attempt = self._create_exam_attempt(
            exam_id=self.proctored_exam_id,
            status=ProctoredExamStudentAttemptStatus.ready_to_resume,
            time_remaining_seconds=600
        )
        # create the second attempt, transitioning from error to ready_to_resume
        second_exam_attempt_id = create_exam_attempt(exam_id=self.proctored_exam_id, user_id=self.user_id)
        update_attempt_status(self.proctored_exam_id, self.user_id, ProctoredExamStudentAttemptStatus.error)
        update_exam_attempt(second_exam_attempt_id, time_remaining_seconds=500)
        update_attempt_status(self.proctored_exam_id, self.user_id, ProctoredExamStudentAttemptStatus.ready_to_resume)
        # create the third attempt, then assert that all attempts return correctly
        third_exam_attempt_id = create_exam_attempt(exam_id=self.proctored_exam_id, user_id=self.user_id)
        all_attempts = get_filtered_exam_attempts(self.course_id, self.user.username)
        self.assertEqual(len(all_attempts), 3)
        self.assertEqual(all_attempts[0]['id'], third_exam_attempt_id)
        self.assertEqual(all_attempts[1]['id'], second_exam_attempt_id)
        self.assertEqual(all_attempts[2]['id'], first_exam_attempt.id)
        # the time remaining on the newest attempt should match the previous attempt
        self.assertEqual(all_attempts[0]['time_remaining_seconds'], all_attempts[1]['time_remaining_seconds'])
        # when a new attempt is created, the previous attempt should transition from ready_to_resume to resumed
        self.assertEqual(all_attempts[0]['status'], ProctoredExamStudentAttemptStatus.created)
        self.assertEqual(all_attempts[1]['status'], ProctoredExamStudentAttemptStatus.resumed)
        self.assertEqual(all_attempts[2]['status'], ProctoredExamStudentAttemptStatus.resumed)

    def test_get_last_exam_completion_date_when_course_is_incomplete(self):
        """
        Test to get the last proctored exam's completion date when course is not complete
        """
        self._create_started_exam_attempt()
        completion_date = get_last_exam_completion_date(self.course_id, self.user.username)
        self.assertIsNone(completion_date)

    def test_get_last_exam_completion_date_when_course_is_complete(self):
        """
        Test to get the last proctored exam's completion date when course is complete
        """
        exam_attempt = self._create_started_exam_attempt()
        exam_attempt.completed_at = datetime.now(pytz.UTC)
        exam_attempt.save()
        completion_date = get_last_exam_completion_date(self.course_id, self.user.username)
        self.assertIsNotNone(completion_date)

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

    def test_proctored_status_summary_passed_end_date(self):
        """
        Assert that we get the expected status summaries
        """

        set_runtime_service('credit', MockCreditServiceWithCourseEndDate())

        exam = get_exam_by_id(self.proctored_exam_id)
        summary = get_attempt_status_summary(self.user.id, exam['course_id'], exam['content_id'])

        expected = {
            'status': ProctoredExamStudentAttemptStatus.expired,
            'short_description': 'Proctored Option No Longer Available',
            'suggested_icon': 'fa-times-circle',
            'in_completed_state': False
        }
        self.assertIn(summary, [expected])

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
        (
            ProctoredExamStudentAttemptStatus.declined,
            False,
            None,
            ProctoredExamStudentAttemptStatus.declined
        ),
        (
            ProctoredExamStudentAttemptStatus.rejected,
            False,
            None,
            None
        ),
        (
            ProctoredExamStudentAttemptStatus.rejected,
            True,
            ProctoredExamStudentAttemptStatus.created,
            ProctoredExamStudentAttemptStatus.created
        ),
        (
            ProctoredExamStudentAttemptStatus.rejected,
            True,
            ProctoredExamStudentAttemptStatus.verified,
            ProctoredExamStudentAttemptStatus.verified
        ),
        (
            ProctoredExamStudentAttemptStatus.declined,
            True,
            ProctoredExamStudentAttemptStatus.submitted,
            ProctoredExamStudentAttemptStatus.submitted
        ),
    )
    @ddt.unpack
    def test_cascading(self, to_status, create_attempt, second_attempt_status, expected_second_status):
        """
        Make sure that when we decline/reject one attempt all other exams in the course
        are auto marked as declined
        """

        set_runtime_service('grades', MockGradesService())
        # create other exams in course
        second_exam_id = create_exam(
            course_id=self.course_id,
            content_id="2nd exam",
            exam_name="2nd exam",
            time_limit_mins=self.default_time_limit,
            is_practice_exam=False,
            is_proctored=True
        )

        practice_exam_id = create_exam(
            course_id=self.course_id,
            content_id="practice",
            exam_name="practice",
            time_limit_mins=self.default_time_limit,
            is_practice_exam=True,
            is_proctored=True
        )

        timed_exam_id = create_exam(
            course_id=self.course_id,
            content_id="timed",
            exam_name="timed",
            time_limit_mins=self.default_time_limit,
            is_practice_exam=False,
            is_proctored=False
        )

        inactive_exam_id = create_exam(
            course_id=self.course_id,
            content_id="inactive",
            exam_name="inactive",
            time_limit_mins=self.default_time_limit,
            is_practice_exam=False,
            is_proctored=True,
            is_active=False
        )

        if create_attempt:
            create_exam_attempt(second_exam_id, self.user_id, taking_as_proctored=False)

            if second_attempt_status:
                update_attempt_status(second_exam_id, self.user_id, second_attempt_status)

        exam_attempt = self._create_started_exam_attempt()
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            to_status
        )

        # make sure we reamain in the right status
        read_back = get_current_exam_attempt(exam_attempt.proctored_exam_id, self.user.id)
        self.assertEqual(read_back['status'], to_status)

        # make sure an attempt was made for second_exam
        second_exam_attempt = get_current_exam_attempt(second_exam_id, self.user_id)
        if expected_second_status:
            self.assertIsNotNone(second_exam_attempt)
            self.assertEqual(second_exam_attempt['status'], expected_second_status)
        else:
            self.assertIsNone(second_exam_attempt)

        # no auto-generated attempts for practice and timed exams
        self.assertIsNone(get_current_exam_attempt(practice_exam_id, self.user_id))
        self.assertIsNone(get_current_exam_attempt(timed_exam_id, self.user_id))
        self.assertIsNone(get_current_exam_attempt(inactive_exam_id, self.user_id))

    def test_grade_override(self):
        """
        Verify that putting an attempt into the rejected state will override
        the learner's subsection grade for the exam and also invalidate the
        learner's certificate
        """
        set_runtime_service('grades', MockGradesService())

        grades_service = get_runtime_service('grades')
        certificates_service = get_runtime_service('certificates')
        exam_attempt = self._create_started_exam_attempt()
        # Pretend learner answered 5 graded questions in the exam correctly
        grades_service.init_grade(
            user_id=self.user.id,
            course_key_or_id=exam_attempt.proctored_exam.course_id,
            usage_key_or_id=exam_attempt.proctored_exam.content_id,
            earned_all=5.0,
            earned_graded=5.0
        )

        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            ProctoredExamStudentAttemptStatus.rejected
        )

        # Rejected exam attempt should override learner's grade to 0
        override = grades_service.get_subsection_grade_override(
            user_id=self.user.id,
            course_key_or_id=exam_attempt.proctored_exam.course_id,
            usage_key_or_id=exam_attempt.proctored_exam.content_id
        )

        self.assertDictEqual({
            'earned_all': override.earned_all_override,
            'earned_graded': override.earned_graded_override
        }, {
            'earned_all': 0.0,
            'earned_graded': 0.0
        })

        # Rejected exam attempt should invalidate learner's certificate
        invalid_generated_certificate = certificates_service.get_invalidated_certificate(
            user_id=self.user.id,
            course_key_or_id=exam_attempt.proctored_exam.course_id
        )

        self.assertDictEqual({
            'verify_uuid': invalid_generated_certificate.verify_uuid,
            'download_uuid': invalid_generated_certificate.download_uuid,
            'download_url': invalid_generated_certificate.download_url,
            'grade': invalid_generated_certificate.grade,
            'status': invalid_generated_certificate.status
        }, {
            'verify_uuid': '',
            'download_uuid': '',
            'download_url': '',
            'grade': '',
            'status': 'unavailable'
        })

        # The MockGradeService updates the PersistentSubsectionGrade synchronously, but in the real GradesService, this
        # would be updated by an asynchronous recalculation celery task.

        grade = grades_service.get_subsection_grade(
            user_id=self.user.id,
            course_key_or_id=exam_attempt.proctored_exam.course_id,
            usage_key_or_id=exam_attempt.proctored_exam.content_id
        )

        self.assertDictEqual({
            'earned_all': grade.earned_all,
            'earned_graded': grade.earned_graded
        }, {
            'earned_all': 0.0,
            'earned_graded': 0.0
        })

        # Verify that transitioning an attempt from the rejected state to the verified state
        # will remove the override for the learner's subsection grade on the exam that was created
        # when the attempt entered the rejected state.
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            ProctoredExamStudentAttemptStatus.verified
        )

        override = grades_service.get_subsection_grade_override(
            user_id=self.user.id,
            course_key_or_id=exam_attempt.proctored_exam.course_id,
            usage_key_or_id=exam_attempt.proctored_exam.content_id
        )
        self.assertIsNone(override)

        grade = grades_service.get_subsection_grade(
            user_id=self.user.id,
            course_key_or_id=exam_attempt.proctored_exam.course_id,
            usage_key_or_id=exam_attempt.proctored_exam.content_id
        )

        # Grade has returned to original score
        self.assertDictEqual({
            'earned_all': grade.earned_all,
            'earned_graded': grade.earned_graded
        }, {
            'earned_all': 5.0,
            'earned_graded': 5.0
        })

    def test_grade_overrider(self):
        """
        Check we pass along the overrider appropriately, as one would when a rejection-worthy review comes in
        """
        grades_service = MockGradesService()
        grades_service.override_subsection_grade = MagicMock()
        set_runtime_service('grades', grades_service)
        exam_attempt = self._create_started_exam_attempt()
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            ProctoredExamStudentAttemptStatus.rejected,
            update_attributable_to=self.user
        )

        assert grades_service.override_subsection_grade.called
        # did we pass the user to whom we're attributing the override along?
        assert grades_service.override_subsection_grade.call_args[1]['overrider'].id == self.user.id

    def test_grade_override_comment(self):
        """
        Check we pass along the backend of the exam for which something failed
        """
        grades_service = MockGradesService()
        grades_service.override_subsection_grade = MagicMock()
        set_runtime_service('grades', grades_service)
        exam_attempt = self._create_started_exam_attempt()
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            ProctoredExamStudentAttemptStatus.rejected
        )

        assert grades_service.override_subsection_grade.called
        # did we pass a comment referring to our backend?
        assert "Unknown" in grades_service.override_subsection_grade.call_args[1]['comment']

    def test_disabled_grade_override(self):
        """
        Verify that when the REJECTED_EXAM_OVERRIDES_GRADE flag is disabled for a course,
        the learner's subsection grade for the exam will not be overriden.
        """
        set_runtime_service('grades', MockGradesService(rejected_exam_overrides_grade=False))

        grades_service = get_runtime_service('grades')
        exam_attempt = self._create_started_exam_attempt()
        # Pretend learner answered 5 graded questions in the exam correctly
        grades_service.init_grade(
            user_id=self.user.id,
            course_key_or_id=exam_attempt.proctored_exam.course_id,
            usage_key_or_id=exam_attempt.proctored_exam.content_id,
            earned_all=5.0,
            earned_graded=5.0
        )

        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            ProctoredExamStudentAttemptStatus.rejected
        )

        # Rejected exam attempt should not override learner's grade
        override = grades_service.get_subsection_grade_override(
            user_id=self.user.id,
            course_key_or_id=exam_attempt.proctored_exam.course_id,
            usage_key_or_id=exam_attempt.proctored_exam.content_id
        )

        self.assertIsNone(override)

        grade = grades_service.get_subsection_grade(
            user_id=self.user.id,
            course_key_or_id=exam_attempt.proctored_exam.course_id,
            usage_key_or_id=exam_attempt.proctored_exam.content_id
        )

        # Grade is not overriden
        self.assertDictEqual({
            'earned_all': grade.earned_all,
            'earned_graded': grade.earned_graded
        }, {
            'earned_all': 5.0,
            'earned_graded': 5.0
        })

        # Transitioning from rejected to verified will also have no effect
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            ProctoredExamStudentAttemptStatus.verified
        )

        override = grades_service.get_subsection_grade_override(
            user_id=self.user.id,
            course_key_or_id=exam_attempt.proctored_exam.course_id,
            usage_key_or_id=exam_attempt.proctored_exam.content_id
        )
        self.assertIsNone(override)

        grade = grades_service.get_subsection_grade(
            user_id=self.user.id,
            course_key_or_id=exam_attempt.proctored_exam.course_id,
            usage_key_or_id=exam_attempt.proctored_exam.content_id
        )

        # Grade has still the original score
        self.assertDictEqual({
            'earned_all': grade.earned_all,
            'earned_graded': grade.earned_graded
        }, {
            'earned_all': 5.0,
            'earned_graded': 5.0
        })

    @ddt.data(
        (ProctoredExamStudentAttemptStatus.declined, ProctoredExamStudentAttemptStatus.eligible),
        (ProctoredExamStudentAttemptStatus.timed_out, ProctoredExamStudentAttemptStatus.created),
        (ProctoredExamStudentAttemptStatus.timed_out, ProctoredExamStudentAttemptStatus.download_software_clicked),
        (ProctoredExamStudentAttemptStatus.submitted, ProctoredExamStudentAttemptStatus.ready_to_start),
        (ProctoredExamStudentAttemptStatus.verified, ProctoredExamStudentAttemptStatus.started),
        (ProctoredExamStudentAttemptStatus.rejected, ProctoredExamStudentAttemptStatus.started),
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

    def test_time_out_as_submitted(self):
        """
        Verified that timed_out will automatically state transition
        to submitted
        """

        exam_attempt = self._create_started_exam_attempt()
        random_timestamp = datetime.now(pytz.UTC) - timedelta(hours=4)
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            ProctoredExamStudentAttemptStatus.timed_out,
            timeout_timestamp=random_timestamp
        )

        exam_attempt = get_exam_attempt_by_id(exam_attempt.id)

        self.assertEqual(
            exam_attempt['status'],
            ProctoredExamStudentAttemptStatus.submitted
        )

        self.assertEqual(
            exam_attempt['completed_at'],
            random_timestamp
        )

    @ddt.data(
        *product(
            [
                ProctoredExamStudentAttemptStatus.started,
                ProctoredExamStudentAttemptStatus.ready_to_submit,

            ],
            [
                ProctoredExamStudentAttemptStatus.created,
                ProctoredExamStudentAttemptStatus.download_software_clicked,
                ProctoredExamStudentAttemptStatus.ready_to_start
            ],
        )

    )
    @ddt.unpack
    def test_reattempt_as_submitted(self, from_status, to_status):
        """
        Tests that when there is an case to update the exam attempt status
        from started to the given status, the attempt is submitted automatically.
        """
        exam_attempt = self._create_exam_attempt(self.proctored_exam_id, from_status)

        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            to_status,
        )
        exam_attempt = get_exam_attempt_by_id(exam_attempt.id)
        self.assertEqual(
            exam_attempt['status'],
            ProctoredExamStudentAttemptStatus.submitted
        )

    def test_immediate_timeout(self):
        """
        Verify that exams started after their due date will be immediately submitted once started
        """

        exam_attempt = ProctoredExamStudentAttempt.objects.create(
            proctored_exam_id=self.proctored_exam_id,
            user_id=self.user_id,
            external_id=self.external_id,
            status='ready_to_start'
        )
        exam_attempt.proctored_exam.due_date = datetime.now(pytz.UTC) - timedelta(hours=4)
        exam_attempt.proctored_exam.save()

        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            ProctoredExamStudentAttemptStatus.started
        )

        exam_attempt = get_exam_attempt_by_id(exam_attempt.id)

        self.assertEqual(
            exam_attempt['status'],
            ProctoredExamStudentAttemptStatus.submitted
        )

        self.assertEqual(
            exam_attempt['allowed_time_limit_mins'],
            0
        )

    @patch.dict('django.conf.settings.PROCTORING_SETTINGS', {'ALLOW_TIMED_OUT_STATE': True})
    def test_timeout_not_submitted(self):
        """
        Test that when the setting is disabled, the status remains timed_out
        """
        exam_attempt = self._create_started_exam_attempt()
        random_timestamp = datetime.now(pytz.UTC) - timedelta(hours=4)
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            ProctoredExamStudentAttemptStatus.timed_out,
            timeout_timestamp=random_timestamp
        )

        exam_attempt = get_exam_attempt_by_id(exam_attempt.id)

        self.assertEqual(
            exam_attempt['status'],
            ProctoredExamStudentAttemptStatus.timed_out
        )

        self.assertNotEqual(
            exam_attempt['completed_at'],
            random_timestamp
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

    def test_update_attempt_without_credit_state(self):
        """
        Test updating an attempt that does not have a corresponding credit state.
        """
        exam_attempt = self._create_started_exam_attempt()
        set_runtime_service('credit', MockCreditServiceNone())
        new_attempt = update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            ProctoredExamStudentAttemptStatus.verified
        )

        self.assertEqual(new_attempt, exam_attempt.id)

    @ddt.data(
        (
            ProctoredExamStudentAttemptStatus.eligible, {
                'status': ProctoredExamStudentAttemptStatus.eligible,
                'short_description': 'Proctored Option Available',
                'suggested_icon': 'fa-pencil-square-o',
                'in_completed_state': False
            }
        ),
        (
            ProctoredExamStudentAttemptStatus.declined, {
                'status': ProctoredExamStudentAttemptStatus.declined,
                'short_description': 'Taking As Open Exam',
                'suggested_icon': 'fa-pencil-square-o',
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
            ProctoredExamStudentAttemptStatus.second_review_required, {
                'status': ProctoredExamStudentAttemptStatus.second_review_required,
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
                'suggested_icon': 'fa-pencil-square-o',
                'in_completed_state': False
            }
        ),
        (
            ProctoredExamStudentAttemptStatus.download_software_clicked, {
                'status': ProctoredExamStudentAttemptStatus.download_software_clicked,
                'short_description': 'Taking As Proctored Exam',
                'suggested_icon': 'fa-pencil-square-o',
                'in_completed_state': False
            }
        ),
        (
            ProctoredExamStudentAttemptStatus.ready_to_start, {
                'status': ProctoredExamStudentAttemptStatus.ready_to_start,
                'short_description': 'Taking As Proctored Exam',
                'suggested_icon': 'fa-pencil-square-o',
                'in_completed_state': False
            }
        ),
        (
            ProctoredExamStudentAttemptStatus.started, {
                'status': ProctoredExamStudentAttemptStatus.started,
                'short_description': 'Taking As Proctored Exam',
                'suggested_icon': 'fa-pencil-square-o',
                'in_completed_state': False
            }
        ),
        (
            ProctoredExamStudentAttemptStatus.ready_to_submit, {
                'status': ProctoredExamStudentAttemptStatus.ready_to_submit,
                'short_description': 'Taking As Proctored Exam',
                'suggested_icon': 'fa-pencil-square-o',
                'in_completed_state': False
            }
        ),
        (
            ProctoredExamStudentAttemptStatus.expired, {
                'status': ProctoredExamStudentAttemptStatus.expired,
                'short_description': 'Proctored Option No Longer Available',
                'suggested_icon': 'fa-times-circle',
                'in_completed_state': False
            }
        )
    )
    @ddt.unpack
    def test_attempt_status_summary(self, status, expected):
        """
        Assert that we get the expected status summaries
        """
        set_runtime_service('grades', MockGradesService())

        exam_attempt = self._create_exam_attempt(self.proctored_exam_id)
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
                'suggested_icon': '',
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
            {
                'short_description': 'Timed Exam',
                'suggested_icon': 'fa-clock-o',
                'in_completed_state': False
            },
        )
    )
    @ddt.unpack
    def test_timed_exam_status_summary(self, expected):
        """
        Assert that we get the expected status summaries
        for the timed exams.
        """
        timed_exam = get_exam_by_id(self.timed_exam_id)
        summary = get_attempt_status_summary(
            self.user.id,
            timed_exam['course_id'],
            timed_exam['content_id']
        )

        self.assertIn(summary, [expected])

    @ddt.data(
        (
            ProctoredExamStudentAttemptStatus.eligible, {
                'status': ProctoredExamStudentAttemptStatus.eligible,
                'short_description': 'Ungraded Practice Exam',
                'suggested_icon': '',
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
        set_runtime_service('credit', MockCreditService(course_name=''))
        expected = {
            'status': ProctoredExamStudentAttemptStatus.eligible,
            'short_description': 'Ungraded Practice Exam',
            'suggested_icon': '',
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

    def test_status_summary_no_perm(self):
        """
        The summary should be None for users who don't have permission
        (For the tests, that means non-authenticated users)
        """
        set_runtime_service('credit', MockCreditService(enrollment_mode='verified'))
        exam_attempt = self._create_started_exam_attempt()
        with mock_perm('edx_proctoring.can_take_proctored_exam'):
            summary = get_attempt_status_summary(
                self.user.id,
                exam_attempt.proctored_exam.course_id,
                exam_attempt.proctored_exam.content_id
            )

        self.assertIsNone(summary)

    def test_proctored_exam_status_summary_no_credit_service(self):
        """
        Assert that we get the expected status summary.

        Cover case that credit service is unavailable.
        """
        set_runtime_service('credit', None)
        expected = {
            'status': ProctoredExamStudentAttemptStatus.eligible,
            'short_description': 'Proctored Option Available',
            'suggested_icon': 'fa-pencil-square-o',
            'in_completed_state': False
        }

        exam = get_exam_by_id(self.proctored_exam_id)

        summary = get_attempt_status_summary(
            self.user.id,
            exam['course_id'],
            exam['content_id']
        )
        self.assertIn(summary, [expected])

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
                time_remaining_seconds=600,
                status='foo'
            )

        now = datetime.now(pytz.UTC)
        update_exam_attempt(
            exam_attempt.id,
            last_poll_timestamp=now,
            last_poll_ipaddr='1.1.1.1',
            time_remaining_seconds=600,
        )

        attempt = get_exam_attempt_by_id(exam_attempt.id)

        self.assertEqual(attempt['last_poll_timestamp'], now)
        self.assertEqual(attempt['last_poll_ipaddr'], '1.1.1.1')
        self.assertEqual(attempt['time_remaining_seconds'], 600)

    @ddt.data(
        ProctoredExamStudentAttemptStatus.eligible,
        ProctoredExamStudentAttemptStatus.created,
        ProctoredExamStudentAttemptStatus.download_software_clicked,
        ProctoredExamStudentAttemptStatus.ready_to_start,
        ProctoredExamStudentAttemptStatus.started,
        ProctoredExamStudentAttemptStatus.ready_to_submit,
        ProctoredExamStudentAttemptStatus.declined,
        ProctoredExamStudentAttemptStatus.timed_out,
        ProctoredExamStudentAttemptStatus.submitted,
        ProctoredExamStudentAttemptStatus.second_review_required,
        ProctoredExamStudentAttemptStatus.rejected,
        ProctoredExamStudentAttemptStatus.expired,
        ProctoredExamStudentAttemptStatus.resumed
    )
    def test_update_exam_attempt_ready_to_resume_invalid_transition(self, initial_status):
        """
        Assert that an attempted transition of a proctored exam attempt from a non-error state
        to the ready_to_resume_state raises a ProctoredExamIllegalStatusTransition exception.
        """
        exam_attempt = self._create_exam_attempt(self.proctored_exam_id, status=initial_status)

        with self.assertRaises(ProctoredExamIllegalStatusTransition):
            update_attempt_status(
                exam_attempt.proctored_exam_id,
                self.user.id,
                ProctoredExamStudentAttemptStatus.ready_to_resume
            )

    def test_update_exam_attempt_ready_to_resume(self):
        """
        Assert that an attempted transition of a proctored exam attempt from an error state
        to a ready_to_resume state completes successfully and does not raise a
        ProctoredExamIllegalStatusTransition exception.
        """
        exam_attempt = self._create_started_exam_attempt()

        attempt = get_exam_attempt_by_id(exam_attempt.id)
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.started)

        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            ProctoredExamStudentAttemptStatus.error
        )

        attempt = get_exam_attempt_by_id(exam_attempt.id)
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.error)

        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            ProctoredExamStudentAttemptStatus.ready_to_resume
        )

        attempt = get_exam_attempt_by_id(exam_attempt.id)
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.ready_to_resume)

    @ddt.data(
        ProctoredExamStudentAttemptStatus.eligible,
        ProctoredExamStudentAttemptStatus.created,
        ProctoredExamStudentAttemptStatus.download_software_clicked,
        ProctoredExamStudentAttemptStatus.ready_to_start,
        ProctoredExamStudentAttemptStatus.started,
        ProctoredExamStudentAttemptStatus.ready_to_submit,
        ProctoredExamStudentAttemptStatus.declined,
        ProctoredExamStudentAttemptStatus.timed_out,
        ProctoredExamStudentAttemptStatus.submitted,
        ProctoredExamStudentAttemptStatus.second_review_required,
        ProctoredExamStudentAttemptStatus.rejected,
        ProctoredExamStudentAttemptStatus.expired
    )
    def test_update_exam_attempt_resumed_invalid_transition(self, from_status):
        """
        Assert that an attempted transition of a proctored exam attempt to 'resumed' from a state
        that is not 'ready_to_resume' or 'resumed' raises an exception.
        """
        exam_attempt = self._create_exam_attempt(self.proctored_exam_id, status=from_status)

        with self.assertRaises(ProctoredExamIllegalStatusTransition):
            update_attempt_status(
                exam_attempt.proctored_exam_id,
                self.user.id,
                ProctoredExamStudentAttemptStatus.resumed
            )

    @ddt.data(
        ProctoredExamStudentAttemptStatus.ready_to_resume,
        ProctoredExamStudentAttemptStatus.resumed
    )
    def test_update_exam_attempt_resumed(self, from_status):
        """
        Assert that transition status to 'resumed' is successful if the previous status is
        'ready_to_resume' or 'resumed'.
        """
        exam_attempt = self._create_exam_attempt(self.proctored_exam_id, status=from_status)
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            ProctoredExamStudentAttemptStatus.resumed
        )
        attempt = get_exam_attempt_by_id(exam_attempt.id)
        self.assertEqual(attempt['status'], ProctoredExamStudentAttemptStatus.resumed)

    def test_requirement_status_order(self):
        """
        Make sure that we get a correct ordered list of all statuses sorted in the correct
        order
        """

        # try unfiltered version first
        ordered_list = _get_ordered_prerequisites(self.prerequisites)

        self.assertEqual(len(ordered_list), 5)

        # check the ordering
        for idx in range(5):
            self.assertEqual(ordered_list[idx]['order'], idx)

        # now filter out the 'grade' namespace
        ordered_list = _get_ordered_prerequisites(self.prerequisites, ['grade'])

        self.assertEqual(len(ordered_list), 4)

        # check the ordering
        for idx in range(4):
            # we +1 on the idx because we know we filtered out one
            self.assertEqual(ordered_list[idx]['order'], idx + 1)

        # check other expected ordering
        self.assertEqual(ordered_list[0]['namespace'], 'reverification')
        self.assertEqual(ordered_list[0]['name'], 'rever1')
        self.assertEqual(ordered_list[1]['namespace'], 'proctoring')
        self.assertEqual(ordered_list[1]['name'], 'proc1')
        self.assertEqual(ordered_list[2]['namespace'], 'reverification')
        self.assertEqual(ordered_list[2]['name'], 'rever2')
        self.assertEqual(ordered_list[3]['namespace'], 'proctoring')
        self.assertEqual(ordered_list[3]['name'], 'proc2')

    @ddt.data(
        ('rever1', True, 0, 0, 0, 0),
        ('proc1', True, 1, 0, 0, 0),
        ('rever2', True, 2, 0, 0, 0),
        ('proc2', False, 2, 1, 0, 0),
        ('unknown', False, 2, 1, 1, 0),
        (None, False, 2, 1, 1, 0),
    )
    @ddt.unpack
    def test_are_prerequisite_satisifed(self, content_id,
                                        expected_are_prerequisites_satisifed,
                                        expected_len_satisfied_prerequisites,
                                        expected_len_failed_prerequisites,
                                        expected_len_pending_prerequisites,
                                        expected_len_declined_prerequisites):
        """
        verify proper operation of the logic when computing is prerequisites are satisfied
        """

        results = _are_prerequirements_satisfied(
            self.prerequisites,
            content_id,
            filter_out_namespaces=['grade']
        )

        self.assertEqual(results['are_prerequisites_satisifed'], expected_are_prerequisites_satisifed)
        self.assertEqual(len(results['satisfied_prerequisites']), expected_len_satisfied_prerequisites)
        self.assertEqual(len(results['failed_prerequisites']), expected_len_failed_prerequisites)
        self.assertEqual(len(results['pending_prerequisites']), expected_len_pending_prerequisites)
        self.assertEqual(len(results['declined_prerequisites']), expected_len_declined_prerequisites)

    @ddt.data(
        ('rever1', True, 0, 0, 0, 0),
        ('proc1', True, 1, 0, 0, 0),
        ('rever2', True, 2, 0, 0, 0),
        ('proc2', False, 2, 0, 0, 1),
        ('unknown', False, 2, 0, 1, 1),
        (None, False, 2, 0, 1, 1),
    )
    @ddt.unpack
    def test_declined_prerequisites(self, content_id,
                                    expected_are_prerequisites_satisifed,
                                    expected_len_satisfied_prerequisites,
                                    expected_len_failed_prerequisites,
                                    expected_len_pending_prerequisites,
                                    expected_len_declined_prerequisites):
        """
        verify proper operation of the logic when computing is prerequisites are satisfied
        """

        results = _are_prerequirements_satisfied(
            self.declined_prerequisites,
            content_id,
            filter_out_namespaces=['grade']
        )

        self.assertEqual(results['are_prerequisites_satisifed'], expected_are_prerequisites_satisifed)
        self.assertEqual(len(results['satisfied_prerequisites']), expected_len_satisfied_prerequisites)
        self.assertEqual(len(results['failed_prerequisites']), expected_len_failed_prerequisites)
        self.assertEqual(len(results['pending_prerequisites']), expected_len_pending_prerequisites)
        self.assertEqual(len(results['declined_prerequisites']), expected_len_declined_prerequisites)

    def test_get_exam_violation_report(self):
        """
        Test to get all the exam attempts.
        """
        # attempt with comments in multiple categories
        exam1_id = create_exam(
            course_id=self.course_id,
            content_id='test_content_1',
            exam_name='DDDDDD',
            time_limit_mins=self.default_time_limit
        )

        exam1_attempt_id = create_exam_attempt(
            exam_id=exam1_id,
            user_id=self.user_id
        )

        exam1_attempt = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_id(
            exam1_attempt_id
        )

        exam1_review = ProctoredExamSoftwareSecureReview.objects.create(
            exam=ProctoredExam.get_exam_by_id(exam1_id),
            attempt_code=exam1_attempt.attempt_code,
            review_status="Suspicious"
        )

        ProctoredExamSoftwareSecureComment.objects.create(
            review=exam1_review,
            status="Rules Violation",
            comment="foo",
            start_time=0,
            stop_time=1,
            duration=1
        )

        ProctoredExamSoftwareSecureComment.objects.create(
            review=exam1_review,
            status="Suspicious",
            comment="bar",
            start_time=0,
            stop_time=1,
            duration=1
        )

        ProctoredExamSoftwareSecureComment.objects.create(
            review=exam1_review,
            status="Suspicious",
            comment="baz",
            start_time=0,
            stop_time=1,
            duration=1
        )

        # attempt with comments in only one category
        exam2_id = create_exam(
            course_id=self.course_id,
            content_id='test_content_2',
            exam_name='CCCCCC',
            time_limit_mins=self.default_time_limit
        )

        exam2_attempt_id = create_exam_attempt(
            exam_id=exam2_id,
            user_id=self.user_id
        )

        exam2_attempt = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_id(
            exam2_attempt_id
        )

        exam2_review = ProctoredExamSoftwareSecureReview.objects.create(
            exam=ProctoredExam.get_exam_by_id(exam2_id),
            attempt_code=exam2_attempt.attempt_code,
            review_status="Rules Violation"
        )

        ProctoredExamSoftwareSecureComment.objects.create(
            review=exam2_review,
            status="Rules Violation",
            comment="bar",
            start_time=0,
            stop_time=1,
            duration=1
        )

        # attempt with no comments, on a different exam
        exam3_id = create_exam(
            course_id=self.course_id,
            content_id='test_content_3',
            exam_name='BBBBBB',
            time_limit_mins=self.default_time_limit
        )

        exam3_attempt_id = create_exam_attempt(
            exam_id=exam3_id,
            user_id=self.user_id
        )

        exam3_attempt = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_id(
            exam3_attempt_id
        )

        ProctoredExamSoftwareSecureReview.objects.create(
            exam=ProctoredExam.get_exam_by_id(exam3_id),
            attempt_code=exam3_attempt.attempt_code,
            review_status="Clean"
        )

        # attempt with no comments or review
        exam4_id = create_exam(
            course_id=self.course_id,
            content_id='test_content_4',
            exam_name='AAAAAA',
            time_limit_mins=self.default_time_limit
        )

        exam4_attempt_id = create_exam_attempt(
            exam_id=exam4_id,
            user_id=self.user_id
        )

        ProctoredExamStudentAttempt.objects.get_exam_attempt_by_id(
            exam4_attempt_id
        )

        report = get_exam_violation_report(self.course_id)

        self.assertEqual(len(report), 4)
        self.assertEqual([attempt['exam_name'] for attempt in report], [
            'AAAAAA',
            'BBBBBB',
            'CCCCCC',
            'DDDDDD'
        ])
        self.assertTrue('Rules Violation Comments' in report[3])  # pylint: disable=wrong-assert-type
        self.assertEqual(len(report[3]['Rules Violation Comments']), 1)
        self.assertTrue('Suspicious Comments' in report[3])  # pylint: disable=wrong-assert-type
        self.assertEqual(len(report[3]['Suspicious Comments']), 2)
        self.assertEqual(report[3]['review_status'], 'Suspicious')

        self.assertTrue('Suspicious Comments' not in report[2])  # pylint: disable=wrong-assert-type
        self.assertTrue('Rules Violation Comments' in report[2])  # pylint: disable=wrong-assert-type
        self.assertEqual(len(report[2]['Rules Violation Comments']), 1)
        self.assertEqual(report[2]['review_status'], 'Rules Violation')

        self.assertEqual(report[1]['review_status'], 'Clean')

        self.assertIsNone(report[0]['review_status'])

    def test_get_exam_violation_report_with_deleted_exam_attempt(self):
        """
        Tests that get_exam_violation_report does not fail in scenerio
        where an exam attempt does not exist for related review.
        """
        test_exam_id = create_exam(
            course_id=self.course_id,
            content_id='test_content_1',
            exam_name='test_exam',
            time_limit_mins=self.default_time_limit
        )

        test_attempt_id = create_exam_attempt(
            exam_id=test_exam_id,
            user_id=self.user_id
        )

        exam1_attempt = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_id(test_attempt_id)

        ProctoredExamSoftwareSecureReview.objects.create(
            exam=ProctoredExam.get_exam_by_id(test_exam_id),
            attempt_code=exam1_attempt.attempt_code,
            review_status="Suspicious"
        )

        # exam attempt is deleted but corresponding review instance exists.
        exam1_attempt.delete()

        report = get_exam_violation_report(self.course_id)

        # call to get_exam_violation_report did not fail. Assert that report is empty as
        # the only exam atempt was deleted.
        self.assertEqual(len(report), 0)

    def test_dashboard_availability(self):
        ProctoredExam.objects.filter(course_id=self.course_id).delete()
        # no exams yet
        self.assertFalse(is_backend_dashboard_available(self.course_id))
        create_exam(
            course_id=self.course_id,
            content_id='test_content_1',
            exam_name='test_exam',
            time_limit_mins=60,
            backend='null'
        )
        # backend with no dashboard
        self.assertFalse(is_backend_dashboard_available(self.course_id))
        create_exam(
            course_id=self.course_id,
            content_id='test_content_2',
            exam_name='test_exam2',
            time_limit_mins=60,
            backend='test'
        )
        # backend with a dashboard
        self.assertTrue(is_backend_dashboard_available(self.course_id))

    def test_does_provider_support_onboarding(self):
        self.assertTrue(does_backend_support_onboarding('test'))
        self.assertFalse(does_backend_support_onboarding('mock'))

    def test_exam_configuration_dashboard_url(self):
        # test if exam doesn't exist
        ProctoredExam.objects.filter(course_id=self.course_id).delete()
        self.assertEqual(get_exam_configuration_dashboard_url(self.course_id, 'test_content_1'), None)

        # test if exam dashboard is not available
        create_exam(
            course_id=self.course_id,
            content_id='test_content_1',
            exam_name='test_exam',
            time_limit_mins=60,
            backend='null'
        )
        self.assertEqual(get_exam_configuration_dashboard_url(self.course_id, 'test_content_1'), None)

        # test if exam exists and dashboard is available
        exam_id = create_exam(
            course_id=self.course_id,
            content_id='test_content_2',
            exam_name='test_exam2',
            time_limit_mins=60,
            backend='test'
        )
        self.assertEqual(
            get_exam_configuration_dashboard_url(self.course_id, 'test_content_2'),
            '/edx_proctoring/v1/instructor/a/b/c/{}?config=true'.format(exam_id)
        )

    def test_clear_onboarding_errors(self):
        """
        Tests that reviewing onboarding exams will clear pending proctored attempts
        """
        # create a proctored attempt before onboarding
        test_backend = get_backend_provider(name='test')
        test_backend.attempt_error = ProctoredExamStudentAttemptStatus.onboarding_missing
        attempt_id = create_exam_attempt(self.proctored_exam_id, self.user_id, taking_as_proctored=True)
        test_backend.attempt_error = None
        assert get_exam_attempt_by_id(attempt_id)['status'] == ProctoredExamStudentAttemptStatus.onboarding_missing

        # now create the practice attempt
        create_exam_attempt(self.onboarding_exam_id, self.user_id)
        # and move the status to verified
        update_attempt_status(self.onboarding_exam_id, self.user_id, ProctoredExamStudentAttemptStatus.verified)
        # now the original attempt will be deleted
        assert get_exam_attempt_by_id(attempt_id) is None
        # ensure that the attempt is still in the history table
        hist_attempt = ProctoredExamStudentAttemptHistory.objects.get(attempt_id=attempt_id)
        assert hist_attempt.status == ProctoredExamStudentAttemptStatus.onboarding_missing

    def test_get_integration_specific_email(self):
        """Test that the correct integration_specific_email is returned for a provider."""
        test_backend = get_backend_provider(name='test')

        assert get_integration_specific_email(test_backend) == DEFAULT_CONTACT_EMAIL

        integration_specific_email = 'edx@example.com'
        test_backend.integration_specific_email = integration_specific_email
        assert get_integration_specific_email(test_backend) == integration_specific_email

        del test_backend.integration_specific_email
        assert get_integration_specific_email(test_backend) == DEFAULT_CONTACT_EMAIL
