"""
File that contains tests for the util methods.
"""

import unittest
from datetime import datetime, timedelta
from itertools import product

import ddt
import pytz
from freezegun import freeze_time

from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus
from edx_proctoring.tests.test_services import MockScheduleData, MockScheduleItemData
from edx_proctoring.utils import (
    _emit_event,
    get_time_remaining_for_attempt,
    get_visibility_check_date,
    humanized_time,
    is_reattempting_exam,
    obscured_user_id
)


class TestGetTimeRemainingForAttempt(unittest.TestCase):
    """
    Class to test get_time_remaining_for_attempt
    """
    def setUp(self):
        """
        Initialize
        """
        super().setUp()
        self.now_utc = datetime.now(pytz.UTC)

    def test_not_started(self):
        """
        Test to return 0 if the exam attempt has not been started.
        """
        attempt = {
            'started_at': None,
            'allowed_time_limit_mins': 10,
            'time_remaining_seconds': None
        }
        time_remaining_seconds = get_time_remaining_for_attempt(attempt)
        self.assertEqual(time_remaining_seconds, 0)

    def test_get_time_remaining_started(self):
        """
        Test to get the time remaining on an attempt after the exam has started.
        """
        with freeze_time(self.now_utc):
            attempt = {
                'started_at': self.now_utc,
                'allowed_time_limit_mins': 10,
                'time_remaining_seconds': None
            }
            time_remaining_seconds = get_time_remaining_for_attempt(attempt)
            self.assertEqual(time_remaining_seconds, 600)


class TestHumanizedTime(unittest.TestCase):
    """
    Class to test the humanized_time utility function
    """
    def test_humanized_time(self):
        """
        tests the humanized_time utility function against different values.
        """
        human_time = humanized_time(0)
        self.assertEqual(human_time, "0 minutes")

        human_time = humanized_time(1)
        self.assertEqual(human_time, "1 minute")

        human_time = humanized_time(10)
        self.assertEqual(human_time, "10 minutes")

        human_time = humanized_time(60)
        self.assertEqual(human_time, "1 hour")

        human_time = humanized_time(61)
        self.assertEqual(human_time, "1 hour and 1 minute")

        human_time = humanized_time(62)
        self.assertEqual(human_time, "1 hour and 2 minutes")

        human_time = humanized_time(120)
        self.assertEqual(human_time, "2 hours")

        human_time = humanized_time(121)
        self.assertEqual(human_time, "2 hours and 1 minute")

        human_time = humanized_time(150)
        self.assertEqual(human_time, "2 hours and 30 minutes")

        human_time = humanized_time(180)
        self.assertEqual(human_time, "3 hours")

        human_time = humanized_time(-60)
        self.assertEqual(human_time, "error")


@ddt.ddt
class TestUtils(unittest.TestCase):
    """
    Class to test misc utilities
    """
    def test_emit_event(self):
        """
        Call through to emit event to the analytics pipeline.
        NOTE: We're just testing one specific case where the context is None
        We get full coverage on other cases, via the test_api.py file
        """

        # call without a context
        _emit_event(
            'foo.bar',
            None,
            {
                'one': 'two'
            }
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
                ProctoredExamStudentAttemptStatus.ready_to_start,
            ]
        )
    )
    @ddt.unpack
    def test_is_reattempting_exam_from_in_progress_state(self, from_status, to_status):
        """Tests that re-attempting exam returns true while transiting from given statuses"""
        self.assertTrue(is_reattempting_exam(from_status, to_status))

    @ddt.data(
        ProctoredExamStudentAttemptStatus.created,
        ProctoredExamStudentAttemptStatus.download_software_clicked,
        ProctoredExamStudentAttemptStatus.ready_to_start,
        ProctoredExamStudentAttemptStatus.submitted,
        ProctoredExamStudentAttemptStatus.verified,
    )
    def test_is_reattempting_exam_from_other_status(self, from_status):
        """Tests that re-attempting exam returns false while transiting from given status"""
        self.assertFalse(
            is_reattempting_exam(from_status, 'foo')
        )

    def test_obscured_user_id(self):
        user_id = 32432455
        expected_obscured_user_id = '9b82efd5d28f1a170b23b8f648c3093e75a0a0ca'
        self.assertEqual(expected_obscured_user_id, obscured_user_id(user_id))

    @ddt.data(
        (1, 3, 1),
        (None, 4, 4),
        (2, None, 2),
        (-1, -3, -1),
        (None, -2, -2),
        (-3, None, -3)
    )
    @ddt.unpack
    def test_get_visibility_check_date(self, mock_due_offset, mock_end_offset, expected_offset):
        cur_time = pytz.utc.localize(datetime.now())
        expected_datetime = cur_time + timedelta(days=expected_offset)
        mock_due = None
        if mock_due_offset:
            mock_due = cur_time + timedelta(days=mock_due_offset)
        mock_course_end = None
        if mock_end_offset:
            mock_course_end = cur_time + timedelta(days=mock_end_offset)
        mock_usage_key = '32fjkle2jf3'
        mock_sequences = {
            mock_usage_key: MockScheduleItemData(cur_time, mock_due)
        }
        mock_schedule = MockScheduleData(mock_sequences, mock_course_end)
        with freeze_time(cur_time):
            due_date = get_visibility_check_date(mock_schedule, mock_usage_key)
            self.assertEqual(due_date, expected_datetime)
