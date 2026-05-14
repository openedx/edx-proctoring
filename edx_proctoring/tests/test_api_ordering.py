"""
Tests for optional ordering parameter on api functions.

See: https://github.com/openedx/edx-proctoring/issues/1320
"""
from edx_proctoring.api import (
    create_exam,
    create_exam_attempt,
    get_all_exam_attempts,
    get_all_exams_for_course,
    get_allowances_for_course,
    get_filtered_exam_attempts
)
from edx_proctoring.models import ProctoredExamStudentAllowance
from edx_proctoring.runtime import set_runtime_service
from edx_proctoring.tests.test_services import (
    MockCertificateService,
    MockCreditService,
    MockInstructorService,
    MockNameAffirmationService
)
from edx_proctoring.tests.test_utils.utils import ProctoredExamTestCase


class TestGetAllExamAttemptsOrdering(ProctoredExamTestCase):
    """
    Tests for the ordering parameter on get_all_exam_attempts.
    """

    def setUp(self):
        super().setUp()
        self.proctored_exam_id = self._create_proctored_exam()
        set_runtime_service('credit', MockCreditService())
        set_runtime_service('certificates', MockCertificateService())
        set_runtime_service('instructor', MockInstructorService())
        set_runtime_service('name_affirmation', MockNameAffirmationService())

    def test_default_ordering_without_param(self):
        """
        When ordering is not provided, results use the default queryset ordering.
        """
        exam_id_2 = create_exam(
            course_id=self.course_id,
            content_id='test_content_2',
            exam_name='Second Exam',
            time_limit_mins=self.default_time_limit,
        )
        create_exam_attempt(exam_id=self.proctored_exam_id, user_id=self.user_id)
        create_exam_attempt(exam_id=exam_id_2, user_id=self.user_id)

        results = get_all_exam_attempts(self.course_id)
        self.assertEqual(len(results), 2)
        # Default is -created, so newest first
        self.assertGreaterEqual(results[0]['created'], results[1]['created'])

    def test_ordering_ascending(self):
        """
        When ordering='created', results are sorted oldest first.
        """
        exam_id_2 = create_exam(
            course_id=self.course_id,
            content_id='test_content_2',
            exam_name='Second Exam',
            time_limit_mins=self.default_time_limit,
        )
        create_exam_attempt(exam_id=self.proctored_exam_id, user_id=self.user_id)
        create_exam_attempt(exam_id=exam_id_2, user_id=self.user_id)

        results = get_all_exam_attempts(self.course_id, ordering='created')
        self.assertEqual(len(results), 2)
        self.assertLessEqual(results[0]['created'], results[1]['created'])

    def test_ordering_descending(self):
        """
        When ordering='-created', results are sorted newest first.
        """
        exam_id_2 = create_exam(
            course_id=self.course_id,
            content_id='test_content_2',
            exam_name='Second Exam',
            time_limit_mins=self.default_time_limit,
        )
        create_exam_attempt(exam_id=self.proctored_exam_id, user_id=self.user_id)
        create_exam_attempt(exam_id=exam_id_2, user_id=self.user_id)

        results = get_all_exam_attempts(self.course_id, ordering='-created')
        self.assertEqual(len(results), 2)
        self.assertGreaterEqual(results[0]['created'], results[1]['created'])

    def test_ordering_none_is_backward_compatible(self):
        """
        Passing ordering=None behaves the same as not passing it.
        """
        create_exam_attempt(exam_id=self.proctored_exam_id, user_id=self.user_id)
        results_default = get_all_exam_attempts(self.course_id)
        results_none = get_all_exam_attempts(self.course_id, ordering=None)
        self.assertEqual(results_default, results_none)


class TestGetFilteredExamAttemptsOrdering(ProctoredExamTestCase):
    """
    Tests for the ordering parameter on get_filtered_exam_attempts.
    """

    def setUp(self):
        super().setUp()
        self.proctored_exam_id = self._create_proctored_exam()
        set_runtime_service('credit', MockCreditService())
        set_runtime_service('certificates', MockCertificateService())
        set_runtime_service('instructor', MockInstructorService())
        set_runtime_service('name_affirmation', MockNameAffirmationService())

    def test_default_ordering_without_param(self):
        """
        When ordering is not provided, results use the default queryset ordering.
        """
        exam_id_2 = create_exam(
            course_id=self.course_id,
            content_id='test_content_2',
            exam_name='Second Exam',
            time_limit_mins=self.default_time_limit,
        )
        create_exam_attempt(exam_id=self.proctored_exam_id, user_id=self.user_id)
        create_exam_attempt(exam_id=exam_id_2, user_id=self.user_id)

        results = get_filtered_exam_attempts(self.course_id, self.user.username)
        self.assertEqual(len(results), 2)
        self.assertGreaterEqual(results[0]['created'], results[1]['created'])

    def test_ordering_ascending(self):
        """
        When ordering='created', results are sorted oldest first.
        """
        exam_id_2 = create_exam(
            course_id=self.course_id,
            content_id='test_content_2',
            exam_name='Second Exam',
            time_limit_mins=self.default_time_limit,
        )
        create_exam_attempt(exam_id=self.proctored_exam_id, user_id=self.user_id)
        create_exam_attempt(exam_id=exam_id_2, user_id=self.user_id)

        results = get_filtered_exam_attempts(self.course_id, self.user.username, ordering='created')
        self.assertEqual(len(results), 2)
        self.assertLessEqual(results[0]['created'], results[1]['created'])

    def test_ordering_none_is_backward_compatible(self):
        """
        Passing ordering=None behaves the same as not passing it.
        """
        create_exam_attempt(exam_id=self.proctored_exam_id, user_id=self.user_id)
        results_default = get_filtered_exam_attempts(self.course_id, self.user.username)
        results_none = get_filtered_exam_attempts(self.course_id, self.user.username, ordering=None)
        self.assertEqual(results_default, results_none)


class TestGetAllExamsForCourseOrdering(ProctoredExamTestCase):
    """
    Tests for the ordering parameter on get_all_exams_for_course.
    """

    def setUp(self):
        super().setUp()
        set_runtime_service('credit', MockCreditService())
        set_runtime_service('certificates', MockCertificateService())
        set_runtime_service('instructor', MockInstructorService())
        set_runtime_service('name_affirmation', MockNameAffirmationService())
        # Create exams with different names for ordering tests
        self.exam_id_a = create_exam(
            course_id=self.course_id,
            content_id='content_a',
            exam_name='Alpha Exam',
            time_limit_mins=30,
        )
        self.exam_id_b = create_exam(
            course_id=self.course_id,
            content_id='content_b',
            exam_name='Beta Exam',
            time_limit_mins=60,
        )

    def test_default_ordering_without_param(self):
        """
        When ordering is not provided, results use the default queryset ordering.
        """
        results = get_all_exams_for_course(self.course_id)
        self.assertEqual(len(results), 2)

    def test_ordering_by_exam_name(self):
        """
        When ordering='exam_name', results are sorted alphabetically by name.
        """
        results = get_all_exams_for_course(self.course_id, ordering='exam_name')
        self.assertEqual(results[0]['exam_name'], 'Alpha Exam')
        self.assertEqual(results[1]['exam_name'], 'Beta Exam')

    def test_ordering_by_exam_name_descending(self):
        """
        When ordering='-exam_name', results are sorted reverse alphabetically.
        """
        results = get_all_exams_for_course(self.course_id, ordering='-exam_name')
        self.assertEqual(results[0]['exam_name'], 'Beta Exam')
        self.assertEqual(results[1]['exam_name'], 'Alpha Exam')

    def test_ordering_none_is_backward_compatible(self):
        """
        Passing ordering=None behaves the same as not passing it.
        """
        results_default = get_all_exams_for_course(self.course_id)
        results_none = get_all_exams_for_course(self.course_id, ordering=None)
        self.assertEqual(results_default, results_none)


class TestGetAllowancesForCourseOrdering(ProctoredExamTestCase):
    """
    Tests for the ordering parameter on get_allowances_for_course.
    """

    def setUp(self):
        super().setUp()
        self.proctored_exam_id = self._create_proctored_exam()
        set_runtime_service('credit', MockCreditService())
        set_runtime_service('certificates', MockCertificateService())
        set_runtime_service('instructor', MockInstructorService())
        set_runtime_service('name_affirmation', MockNameAffirmationService())
        # Create two allowances with different values
        ProctoredExamStudentAllowance.objects.create(
            proctored_exam_id=self.proctored_exam_id,
            user_id=self.user_id,
            key='additional_time_granted',
            value='10',
        )
        ProctoredExamStudentAllowance.objects.create(
            proctored_exam_id=self.proctored_exam_id,
            user_id=self.user_id,
            key='review_policy_exception',
            value='5',
        )

    def test_default_ordering_without_param(self):
        """
        When ordering is not provided, results use the default queryset ordering.
        """
        results = get_allowances_for_course(self.course_id)
        self.assertEqual(len(results), 2)

    def test_ordering_by_created(self):
        """
        When ordering='created', results are sorted by creation time ascending.
        """
        results = get_allowances_for_course(self.course_id, ordering='created')
        self.assertEqual(len(results), 2)
        self.assertLessEqual(results[0]['created'], results[1]['created'])

    def test_ordering_descending(self):
        """
        When ordering='-created', results are sorted by creation time descending.
        """
        results = get_allowances_for_course(self.course_id, ordering='-created')
        self.assertEqual(len(results), 2)
        self.assertGreaterEqual(results[0]['created'], results[1]['created'])

    def test_ordering_none_is_backward_compatible(self):
        """
        Passing ordering=None behaves the same as not passing it.
        """
        results_default = get_allowances_for_course(self.course_id)
        results_none = get_allowances_for_course(self.course_id, ordering=None)
        self.assertEqual(results_default, results_none)
