# coding=utf-8
# pylint: disable=too-many-lines, invalid-name

"""
All tests for the api.py
"""
import ddt
from datetime import datetime, timedelta
from django.core import mail
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
    mark_exam_attempt_timeout,
    mark_exam_attempt_as_ready,
    update_attempt_status,
    get_attempt_status_summary,
    update_exam_attempt,
    _check_for_attempt_timeout,
    _get_ordered_prerequisites,
    _are_prerequirements_satisfied,
    create_exam_review_policy,
    get_review_policy_by_exam_id,
    update_review_policy,
    remove_review_policy,
)
from edx_proctoring.exceptions import (
    ProctoredExamAlreadyExists,
    ProctoredExamNotFoundException,
    StudentExamAttemptAlreadyExistsException,
    StudentExamAttemptDoesNotExistsException,
    StudentExamAttemptedAlreadyStarted,
    UserNotFoundException,
    ProctoredExamIllegalStatusTransition,
    ProctoredExamPermissionDenied,
    AllowanceValueNotAllowedException,
    ProctoredExamReviewPolicyAlreadyExists,
    ProctoredExamReviewPolicyNotFoundException
)
from edx_proctoring.models import (
    ProctoredExam,
    ProctoredExamStudentAllowance,
    ProctoredExamStudentAttempt,
    ProctoredExamStudentAttemptStatus,
    ProctoredExamReviewPolicy,
)

from .utils import (
    LoggedInTestCase,
)

from edx_proctoring.tests.test_services import (
    MockCreditService,
    MockInstructorService,
)
from edx_proctoring.runtime import set_runtime_service, get_runtime_service
from eventtracking import tracker
from eventtracking.tracker import Tracker, TRACKERS


class MockTracker(Tracker):
    """
    A mocked out tracker which implements the emit method
    """
    def emit(self, name=None, data=None):
        """
        Overload this method to do nothing
        """
        pass


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
        self.content_id_for_exam_with_due_date = 'test_content_due_date_id'
        self.content_id = 'test_content_id'
        self.content_id_timed = 'test_content_id_timed'
        self.content_id_practice = 'test_content_id_practice'
        self.disabled_content_id = 'test_disabled_content_id'
        self.exam_name = 'Test Exam'
        self.user_id = self.user.id
        self.key = 'additional_time_granted'
        self.value = '10'
        self.external_id = 'test_external_id'
        self.proctored_exam_id = self._create_proctored_exam()
        self.timed_exam_id = self._create_timed_exam()
        self.practice_exam_id = self._create_practice_exam()
        self.disabled_exam_id = self._create_disabled_exam()

        # Messages for get_student_view
        self.start_an_exam_msg = 'This exam is proctored'
        self.exam_expired_msg = 'The due date for this exam has passed'
        self.timed_exam_msg = '{exam_name} is a Timed Exam'
        self.submitted_timed_exam_msg_with_due_date = 'After the due date has passed,'
        self.exam_time_expired_msg = 'You did not complete the exam in the allotted time'
        self.exam_time_error_msg = 'There was a problem with your proctoring session'
        self.chose_proctored_exam_msg = 'Follow these steps to set up and start your proctored exam'
        self.proctored_exam_optout_msg = 'Take this exam as an open exam instead'
        self.proctored_exam_completed_msg = 'Are you sure you want to end your proctored exam'
        self.proctored_exam_waiting_for_app_shutdown_msg = 'You are about to complete your proctored exam'
        self.proctored_exam_submitted_msg = 'You have submitted this proctored exam for review'
        self.proctored_exam_verified_msg = 'Your proctoring session was reviewed and passed all requirements'
        self.proctored_exam_rejected_msg = 'Your proctoring session was reviewed and did not pass requirements'
        self.start_a_practice_exam_msg = 'Get familiar with proctoring for real exams later in the course'
        self.practice_exam_submitted_msg = 'You have submitted this practice proctored exam'
        self.practice_exam_created_msg = 'Follow these steps to set up and start your proctored exam'
        self.practice_exam_completion_msg = 'Are you sure you want to end your proctored exam'
        self.ready_to_start_msg = 'Follow these instructions'
        self.practice_exam_failed_msg = 'There was a problem with your practice proctoring session'
        self.proctored_exam_email_subject = 'Proctoring Session Results Update'
        self.proctored_exam_email_body = 'the status of your proctoring session review'
        self.footer_msg = 'About Proctored Exams'

        set_runtime_service('credit', MockCreditService())
        set_runtime_service('instructor', MockInstructorService(is_user_course_staff=True))

        tracker.register_tracker(MockTracker())

        self.prerequisites = [
            {
                'namespace': 'proctoring',
                'name': 'proc1',
                'order': 2,
                'status': 'satisfied',
            },
            {
                'namespace': 'reverification',
                'name': 'rever1',
                'order': 1,
                'status': 'satisfied',
            },
            {
                'namespace': 'grade',
                'name': 'grade1',
                'order': 0,
                'status': 'pending',
            },
            {
                'namespace': 'reverification',
                'name': 'rever2',
                'order': 3,
                'status': 'failed',
            },
            {
                'namespace': 'proctoring',
                'name': 'proc2',
                'order': 4,
                'status': 'pending',
            },
        ]

        self.declined_prerequisites = [
            {
                'namespace': 'proctoring',
                'name': 'proc1',
                'order': 2,
                'status': 'satisfied',
            },
            {
                'namespace': 'reverification',
                'name': 'rever1',
                'order': 1,
                'status': 'satisfied',
            },
            {
                'namespace': 'grade',
                'name': 'grade1',
                'order': 0,
                'status': 'pending',
            },
            {
                'namespace': 'reverification',
                'name': 'rever2',
                'order': 3,
                'status': 'declined',
            },
            {
                'namespace': 'proctoring',
                'name': 'proc2',
                'order': 4,
                'status': 'pending',
            },
        ]

    def tearDown(self):
        """
        Cleanup
        """
        del TRACKERS['default']

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

    def _create_exam_with_due_time(self, is_proctored=True, is_practice_exam=False, due_date=None):
        """
        Calls the api's create_exam to create an exam object.
        """
        return create_exam(
            course_id=self.course_id,
            content_id=self.content_id_for_exam_with_due_date,
            exam_name=self.exam_name,
            time_limit_mins=self.default_time_limit,
            is_proctored=is_proctored,
            is_practice_exam=is_practice_exam,
            due_date=due_date
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
            is_proctored=True
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

    def _create_exam_attempt(self, exam_id, status='created'):
        """
        Creates the ProctoredExamStudentAttempt object.
        """
        return ProctoredExamStudentAttempt.objects.create(
            proctored_exam_id=exam_id,
            user_id=self.user_id,
            external_id=self.external_id,
            allowed_time_limit_mins=10,
            status=status
        )

    def _create_unstarted_exam_attempt(self, is_proctored=True, is_practice=False):
        """
        Creates the ProctoredExamStudentAttempt object.
        """
        if is_proctored:
            if is_practice:
                exam_id = self.practice_exam_id
            else:
                exam_id = self.proctored_exam_id
        else:
            exam_id = self.timed_exam_id

        return ProctoredExamStudentAttempt.objects.create(
            proctored_exam_id=exam_id,
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
            proctored_exam_id=self.proctored_exam_id if is_proctored else self.timed_exam_id,
            user_id=self.user_id,
            external_id=self.external_id,
            started_at=started_at if started_at else datetime.now(pytz.UTC),
            status=ProctoredExamStudentAttemptStatus.started,
            allowed_time_limit_mins=10,
            taking_as_proctored=is_proctored,
            is_sample_attempt=is_sample_attempt
        )

    def _create_started_practice_exam_attempt(self, started_at=None):
        """
        Creates the ProctoredExamStudentAttempt object.
        """
        return ProctoredExamStudentAttempt.objects.create(
            proctored_exam_id=self.practice_exam_id,
            taking_as_proctored=True,
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
            is_proctored=True, external_id='external_id', is_active=True,
            due_date=datetime.now(pytz.UTC)
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

        exams = get_all_exams_for_course(self.course_id, False)
        self.assertEqual(len(exams), 4)

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
            review_policy=u'allow use of paper'
        )

        # now get the exam review policy for the proctored exam
        exam_review_policy = get_review_policy_by_exam_id(proctored_exam['id'])

        self.assertEqual(exam_review_policy['proctored_exam']['id'], proctored_exam['id'])
        self.assertEqual(exam_review_policy['set_by_user']['id'], self.user_id)
        self.assertEqual(exam_review_policy['review_policy'], u'allow use of paper')

    def test_update_exam_review_policy(self):
        """
        Test to update existing exam review policy for
        proctored exam and tests that it stores in the
        db correctly and set the exam review policy to ''
        will remove the entry from the database.
        """
        proctored_exam = get_exam_by_id(self.proctored_exam_id)
        create_exam_review_policy(
            exam_id=proctored_exam['id'],
            set_by_user_id=self.user_id,
            review_policy=u'allow use of paper'
        )

        # now update the exam review policy for the proctored exam
        update_review_policy(
            exam_id=proctored_exam['id'],
            set_by_user_id=self.user_id,
            review_policy=u'allow use of calculator'
        )

        # now get the updated exam review policy for the proctored exam
        exam_review_policy = get_review_policy_by_exam_id(proctored_exam['id'])

        self.assertEqual(exam_review_policy['proctored_exam']['id'], proctored_exam['id'])
        self.assertEqual(exam_review_policy['set_by_user']['id'], self.user_id)
        self.assertEqual(exam_review_policy['review_policy'], u'allow use of calculator')

        # now update the exam review policy for the proctored exam
        # with review_policy value to "". This will delete the exam
        # review policy object from the database.
        update_review_policy(
            exam_id=proctored_exam['id'],
            set_by_user_id=self.user_id,
            review_policy=u''
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
            review_policy=u'allow use of paper'
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
                review_policy=u'allow use of calculator'
            )

    def test_create_exam_review_policy_with_same_exam_id(self):
        """
        Test to create a same exam review policy will raise exception
        """
        proctored_exam = get_exam_by_id(self.proctored_exam_id)
        create_exam_review_policy(
            exam_id=proctored_exam['id'],
            set_by_user_id=self.user_id,
            review_policy=u'allow use of paper'
        )

        # create the same review policy again will raise exception
        with self.assertRaises(ProctoredExamReviewPolicyAlreadyExists):
            create_exam_review_policy(
                exam_id=proctored_exam['id'],
                set_by_user_id=self.user_id,
                review_policy=u'allow use of paper'
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

        exams = get_all_exams_for_course(self.course_id, True)
        self.assertEqual(len(exams), 1)

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
        course_allowances = get_allowances_for_course(self.course_id, False)
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

    def test_create_exam_attempt_with_due_datetime(self):
        """
        Create the exam attempt with due date
        """

        due_date = datetime.now(pytz.UTC) + timedelta(days=1)

        # exam is created with due datetime > current_datetime and due_datetime < current_datetime + allowed_mins
        exam_id = self._create_exam_with_due_time(due_date=due_date)

        # due_date is exactly after 24 hours, our exam's allowed minutes are 21
        # student will get full allowed minutes if student will start exam within next 23 hours and 39 minutes
        # otherwise allowed minutes = due_datetime - exam_attempt_datetime
        # so if students arrives after 23 hours and 45 minutes later then he will get only 15 minutes

        minutes_before_past_due_date = 15
        reset_time = due_date - timedelta(minutes=minutes_before_past_due_date)
        with freeze_time(reset_time):
            attempt_id = create_exam_attempt(exam_id, self.user_id)
            attempt = get_exam_attempt_by_id(attempt_id)
            self.assertTrue(
                minutes_before_past_due_date - 1 <= attempt['allowed_time_limit_mins'] <= minutes_before_past_due_date
            )

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
        self.assertGreater(attempt_id, 0)

        attempt = get_exam_attempt_by_id(attempt_id)
        self.assertEqual(attempt['allowed_time_limit_mins'], self.default_time_limit + allowed_extra_time)

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
            proctored_exam_student_attempt.proctored_exam.id, self.user_id
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
            remove_exam_attempt(exam_attempt.proctored_exam_id)

            # make sure the credit requirement status is no longer there
            credit_status = credit_service.get_credit_state(self.user.id, exam_attempt.proctored_exam.course_id)

            self.assertEqual(len(credit_status['credit_requirement_status']), 0)
        else:
            # There is not an expected changed to the credit requirement table
            # given the attempt status
            self.assertEqual(len(credit_status['credit_requirement_status']), 0)

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
        self.assertIn(
            'data-exam-id="{proctored_exam_id}"'.format(proctored_exam_id=self.proctored_exam_id),
            rendered_response
        )
        self.assertIn(self.start_an_exam_msg.format(exam_name=self.exam_name), rendered_response)

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
        self.assertIn(self.start_a_practice_exam_msg.format(exam_name=self.exam_name), rendered_response)

    def test_get_honor_view_with_practice_exam(self):
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
        ('reverification', None, 'The following prerequisites are in a <strong>pending</strong> state', True),
        ('reverification', 'pending', 'The following prerequisites are in a <strong>pending</strong> state', True),
        ('reverification', 'failed', 'You did not satisfy the following prerequisites', True),
        ('reverification', 'satisfied', 'To be eligible to earn credit for this course', False),
        ('reverification', 'declined', None, False),
        ('proctored_exam', None, 'The following prerequisites are in a <strong>pending</strong> state', True),
        ('proctored_exam', 'pending', 'The following prerequisites are in a <strong>pending</strong> state', True),
        ('proctored_exam', 'failed', 'You did not satisfy the following prerequisites', True),
        ('proctored_exam', 'satisfied', 'To be eligible to earn credit for this course', False),
        ('proctored_exam', 'declined', None, False),
        ('grade', 'failed', 'To be eligible to earn credit for this course', False),
        # this is nonesense, but let's double check it
        ('grade', 'declined', 'To be eligible to earn credit for this course', False),
    )
    @ddt.unpack
    def test_prereq_scenarios(self, namespace, req_status, expected_content, should_see_prereq):
        """
        This test asserts that proctoring will not be displayed under the following
        conditions:

        - Verified student has not completed all 'reverification' requirements
        """

        exam = get_exam_by_id(self.proctored_exam_id)

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
                            'name': 'foo',
                            'display_name': 'Foo Requirement',
                            'status': req_status,
                            'order': 0
                        }
                    ]
                }
            }
        )

        if expected_content:
            self.assertIn(expected_content, rendered_response)
        else:
            self.assertIsNone(rendered_response)

        if req_status == 'declined' and not expected_content:
            # also we should have auto-declined if a pre-requisite was declined
            attempt = get_exam_attempt(exam['id'], self.user_id)
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
                'default_time_limit_mins': 90
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

    def test_get_studentview_unstarted_exam(self):
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
        self.assertIn(self.proctored_exam_optout_msg, rendered_response)

        # now make sure content remains the same if
        # the status transitions to 'download_software_clicked'
        update_attempt_status(
            self.proctored_exam_id,
            self.user_id,
            ProctoredExamStudentAttemptStatus.download_software_clicked
        )

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
        self.assertIn(self.proctored_exam_optout_msg, rendered_response)

    def test_get_studentview_unstarted_practice_exam(self):
        """
        Test for get_student_view Practice exam which has not started yet.
        """

        self._create_unstarted_exam_attempt(is_practice=True)

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id_practice,
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'is_practice_exam': True,
                'default_time_limit_mins': 90
            }
        )
        self.assertIn(self.chose_proctored_exam_msg, rendered_response)
        self.assertNotIn(self.proctored_exam_optout_msg, rendered_response)

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

    def test_get_studentview_started_exam(self):
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

    def test_get_studentview_started_practice_exam(self):
        """
        Test for get_student_view practice proctored exam which has started.
        """

        self._create_started_practice_exam_attempt()

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id_practice,
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90
            }
        )
        self.assertIsNone(rendered_response)

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

    @ddt.data(
        (datetime.now(pytz.UTC) + timedelta(days=1), False),
        (datetime.now(pytz.UTC) - timedelta(days=1), True),
    )
    @ddt.unpack
    def test_get_studentview_submitted_timed_exam_with_past_due_date(self, due_date, has_due_date_passed):
        """
        Test for get_student_view timed exam with the due date.
        """

        # exam is created with due datetime which has already passed
        exam_id = self._create_exam_with_due_time(is_proctored=False, due_date=due_date)

        # now create the timed_exam attempt in the submitted state
        self._create_exam_attempt(exam_id, status='submitted')

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id_for_exam_with_due_date,
            context={
                'is_proctored': False,
                'display_name': self.exam_name,
                'default_time_limit_mins': 10
            }
        )
        if not has_due_date_passed:
            self.assertIn(self.submitted_timed_exam_msg_with_due_date, rendered_response)
        else:
            self.assertIsNone(None)

    @ddt.data(
        (True, False),
        (True, True),
        (False, False),
    )
    @ddt.unpack
    def test_practice_exam_attempt_with_past_due_datetime(self, is_proctored, is_practice):
        """
        Test for get_student_view for practice proctored exam with past due datetime
        """

        due_date = datetime.now(pytz.UTC) + timedelta(days=1)

        # exam is created with due datetime which has already passed
        self._create_exam_with_due_time(
            is_proctored=is_proctored,
            is_practice_exam=is_practice,
            due_date=due_date
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
                    'is_proctored': True,
                    'is_practice_exam': True,
                    'display_name': self.exam_name,
                    'default_time_limit_mins': self.default_time_limit
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
                    'default_time_limit_mins': self.default_time_limit
                }
            )
            self.assertIn(self.exam_expired_msg, rendered_response)

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
                    'default_time_limit_mins': self.default_time_limit
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
                    'default_time_limit_mins': self.default_time_limit
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
                    'default_time_limit_mins': self.default_time_limit
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
                    'default_time_limit_mins': self.default_time_limit
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

    def test_get_studentview_submitted_status(self):
        """
        Test for get_student_view proctored exam which has been submitted.
        """
        exam_attempt = self._create_started_exam_attempt()
        exam_attempt.status = ProctoredExamStudentAttemptStatus.submitted
        exam_attempt.last_poll_timestamp = datetime.now(pytz.UTC)
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
        self.assertIn(self.proctored_exam_waiting_for_app_shutdown_msg, rendered_response)

        reset_time = datetime.now(pytz.UTC) + timedelta(minutes=2)
        with freeze_time(reset_time):
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

            # now make sure if this status transitions to 'second_review_required'
            # the student will still see a 'submitted' message
            update_attempt_status(
                exam_attempt.proctored_exam_id,
                exam_attempt.user_id,
                ProctoredExamStudentAttemptStatus.second_review_required
            )
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
            last_poll_timestamp=datetime.now(pytz.UTC)
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

    def test_get_studentview_submitted_status_practiceexam(self):
        """
        Test for get_student_view practice exam which has been submitted.
        """
        exam_attempt = self._create_started_practice_exam_attempt()
        exam_attempt.status = ProctoredExamStudentAttemptStatus.submitted
        exam_attempt.last_poll_timestamp = datetime.now(pytz.UTC)
        exam_attempt.save()

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id_practice,
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90
            }
        )
        self.assertIn(self.proctored_exam_waiting_for_app_shutdown_msg, rendered_response)

        reset_time = datetime.now(pytz.UTC) + timedelta(minutes=2)
        with freeze_time(reset_time):
            rendered_response = get_student_view(
                user_id=self.user_id,
                course_id=self.course_id,
                content_id=self.content_id_practice,
                context={
                    'is_proctored': True,
                    'display_name': self.exam_name,
                    'default_time_limit_mins': 90
                }
            )
            self.assertIn(self.practice_exam_submitted_msg, rendered_response)

    def test_get_studentview_created_status_practiceexam(self):
        """
        Test for get_student_view practice exam which has been created.
        """
        exam_attempt = self._create_started_practice_exam_attempt()
        exam_attempt.status = ProctoredExamStudentAttemptStatus.created
        exam_attempt.save()

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id_practice,
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90
            }
        )
        self.assertIn(self.practice_exam_created_msg, rendered_response)

    def test_get_studentview_ready_to_start_status_practiceexam(self):
        """
        Test for get_student_view practice exam which is ready to start.
        """
        exam_attempt = self._create_started_practice_exam_attempt()
        exam_attempt.status = ProctoredExamStudentAttemptStatus.ready_to_start
        exam_attempt.save()

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id_practice,
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90
            }
        )
        self.assertIn(self.ready_to_start_msg, rendered_response)

    def test_get_studentview_compelete_status_practiceexam(self):
        """
        Test for get_student_view practice exam when it is complete/ready to submit.
        """
        exam_attempt = self._create_started_practice_exam_attempt()
        exam_attempt.status = ProctoredExamStudentAttemptStatus.ready_to_submit
        exam_attempt.save()

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id_practice,
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90
            }
        )
        self.assertIn(self.practice_exam_completion_msg, rendered_response)

    def test_get_studentview_rejected_status(self):
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

    def test_get_studentview_verified_status(self):
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

    def test_get_studentview_completed_status(self):
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
        Test for get_student_view proctored exam which has expired. Since we don't have a template
        for that view rendering, it will throw a NotImplementedError
        """

        self._create_started_exam_attempt(started_at=datetime.now(pytz.UTC).replace(year=2010))

        with self.assertRaises(NotImplementedError):
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

    def test_get_studentview_erroneous_practice_exam(self):
        """
        Test for get_student_view practice exam which has exam status error.
        """

        exam_attempt = self._create_started_practice_exam_attempt()
        exam_attempt.status = ProctoredExamStudentAttemptStatus.error
        exam_attempt.save()

        rendered_response = get_student_view(
            user_id=self.user_id,
            course_id=self.course_id,
            content_id=self.content_id_practice,
            context={
                'is_proctored': True,
                'display_name': self.exam_name,
                'default_time_limit_mins': 90
            }
        )
        self.assertIn(self.practice_exam_failed_msg, rendered_response)

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
                'default_time_limit_mins': 90
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
        (
            ProctoredExamStudentAttemptStatus.ready_to_submit,
            'Are you sure that you want to submit your timed exam?'
        ),
        (
            ProctoredExamStudentAttemptStatus.submitted,
            'You have submitted your timed exam'
        ),
    )
    @ddt.unpack
    def test_get_studentview_completed_timed_exam(self, status, expected_content):
        """
        Test for get_student_view timed exam which has completed.
        """
        exam_attempt = self._create_started_exam_attempt(is_proctored=False)
        exam_attempt.status = status
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
        read_back = get_exam_attempt(exam_attempt.proctored_exam_id, self.user.id)
        self.assertEqual(read_back['status'], to_status)

        # make sure an attempt was made for second_exam
        second_exam_attempt = get_exam_attempt(second_exam_id, self.user_id)
        if expected_second_status:
            self.assertIsNotNone(second_exam_attempt)
            self.assertEqual(second_exam_attempt['status'], expected_second_status)
        else:
            self.assertIsNone(second_exam_attempt)

        # no auto-generated attempts for practice and timed exams
        self.assertIsNone(get_exam_attempt(practice_exam_id, self.user_id))
        self.assertIsNone(get_exam_attempt(timed_exam_id, self.user_id))
        self.assertIsNone(get_exam_attempt(inactive_exam_id, self.user_id))

    @ddt.data(
        (ProctoredExamStudentAttemptStatus.declined, ProctoredExamStudentAttemptStatus.eligible),
        (ProctoredExamStudentAttemptStatus.timed_out, ProctoredExamStudentAttemptStatus.created),
        (ProctoredExamStudentAttemptStatus.timed_out, ProctoredExamStudentAttemptStatus.download_software_clicked),
        (ProctoredExamStudentAttemptStatus.submitted, ProctoredExamStudentAttemptStatus.ready_to_start),
        (ProctoredExamStudentAttemptStatus.verified, ProctoredExamStudentAttemptStatus.started),
        (ProctoredExamStudentAttemptStatus.rejected, ProctoredExamStudentAttemptStatus.started),
        (ProctoredExamStudentAttemptStatus.not_reviewed, ProctoredExamStudentAttemptStatus.started),
        (ProctoredExamStudentAttemptStatus.error, ProctoredExamStudentAttemptStatus.started),
        (ProctoredExamStudentAttemptStatus.submitted, ProctoredExamStudentAttemptStatus.error),
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

    @ddt.data(
        ProctoredExamStudentAttemptStatus.submitted,
        ProctoredExamStudentAttemptStatus.verified,
        ProctoredExamStudentAttemptStatus.rejected
    )
    def test_send_email(self, status):
        """
        Assert that email is sent on the following statuses of proctoring attempt.
        """

        exam_attempt = self._create_started_exam_attempt()
        credit_state = get_runtime_service('credit').get_credit_state(self.user_id, self.course_id)
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            status
        )
        self.assertEquals(len(mail.outbox), 1)
        self.assertIn(self.proctored_exam_email_subject, mail.outbox[0].subject)
        self.assertIn(self.proctored_exam_email_body, mail.outbox[0].body)
        self.assertIn(ProctoredExamStudentAttemptStatus.get_status_alias(status), mail.outbox[0].body)
        self.assertIn(credit_state['course_name'], mail.outbox[0].body)

    @ddt.data(
        ProctoredExamStudentAttemptStatus.second_review_required,
        ProctoredExamStudentAttemptStatus.error
    )
    def test_email_not_sent(self, status):
        """
        Assert than email is not sent on the following statuses of proctoring attempt
        """

        exam_attempt = self._create_started_exam_attempt()
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            status
        )
        self.assertEquals(len(mail.outbox), 0)

    def test_send_email_unicode(self):
        """
        Assert that email can be sent with a unicode course name.
        """

        course_name = u'अआईउऊऋऌ अआईउऊऋऌ'
        set_runtime_service('credit', MockCreditService(course_name=course_name))

        exam_attempt = self._create_started_exam_attempt()
        credit_state = get_runtime_service('credit').get_credit_state(self.user_id, self.course_id)
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            ProctoredExamStudentAttemptStatus.submitted
        )
        self.assertEquals(len(mail.outbox), 1)
        self.assertIn(self.proctored_exam_email_subject, mail.outbox[0].subject)
        self.assertIn(course_name, mail.outbox[0].subject)
        self.assertIn(self.proctored_exam_email_body, mail.outbox[0].body)
        self.assertIn(
            ProctoredExamStudentAttemptStatus.get_status_alias(
                ProctoredExamStudentAttemptStatus.submitted
            ),
            mail.outbox[0].body
        )
        self.assertIn(credit_state['course_name'], mail.outbox[0].body)

    @ddt.data(
        ProctoredExamStudentAttemptStatus.eligible,
        ProctoredExamStudentAttemptStatus.created,
        ProctoredExamStudentAttemptStatus.download_software_clicked,
        ProctoredExamStudentAttemptStatus.ready_to_start,
        ProctoredExamStudentAttemptStatus.started,
        ProctoredExamStudentAttemptStatus.ready_to_submit,
        ProctoredExamStudentAttemptStatus.declined,
        ProctoredExamStudentAttemptStatus.timed_out,
        ProctoredExamStudentAttemptStatus.not_reviewed,
        ProctoredExamStudentAttemptStatus.error
    )
    @patch.dict('settings.PROCTORING_SETTINGS', {'ALLOW_TIMED_OUT_STATE': True})
    def test_not_send_email(self, status):
        """
        Assert that email is not sent on the following statuses of proctoring attempt.
        """

        exam_attempt = self._create_started_exam_attempt()
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            status
        )
        self.assertEquals(len(mail.outbox), 0)

    @ddt.data(
        ProctoredExamStudentAttemptStatus.submitted,
        ProctoredExamStudentAttemptStatus.verified,
        ProctoredExamStudentAttemptStatus.rejected
    )
    def test_not_send_email_sample_exam(self, status):
        """
        Assert that email is not sent when there is practice/sample exam
        """

        exam_attempt = self._create_started_exam_attempt(is_sample_attempt=True)
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            status
        )
        self.assertEquals(len(mail.outbox), 0)

    @ddt.data(
        ProctoredExamStudentAttemptStatus.submitted,
        ProctoredExamStudentAttemptStatus.verified,
        ProctoredExamStudentAttemptStatus.rejected
    )
    def test_not_send_email_timed_exam(self, status):
        """
        Assert that email is not sent when exam is timed/not-proctoring
        """

        exam_attempt = self._create_started_exam_attempt(is_proctored=False)
        update_attempt_status(
            exam_attempt.proctored_exam_id,
            self.user.id,
            status
        )
        self.assertEquals(len(mail.outbox), 0)

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
        self.assertIsNotNone(rendered_response)
        if status == ProctoredExamStudentAttemptStatus.submitted:
            exam_attempt.last_poll_timestamp = datetime.now(pytz.UTC)
            exam_attempt.save()

            reset_time = datetime.now(pytz.UTC) + timedelta(minutes=2)
            with freeze_time(reset_time):
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
                self.assertIn(self.footer_msg, rendered_response)
        else:
            self.assertIn(self.footer_msg, rendered_response)

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
