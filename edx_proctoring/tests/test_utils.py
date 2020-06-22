"""
File that contains tests for the util methods.
"""

import unittest
from itertools import product

import ddt

from edx_proctoring.statuses import ProctoredExamStudentAttemptStatus
from edx_proctoring.utils import _emit_event, humanized_time, is_reattempting_exam


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
