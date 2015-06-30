"""
File that contains tests for the util methods.
"""
import unittest
from edx_proctoring.utils import humanized_time


class TestHumanizedTime(unittest.TestCase):
    """
    Class to test the humanized_time utility function
    """
    def test_humanized_time(self):
        """
        tests the humanized_time utility function against different values.
        """
        human_time = humanized_time(0)
        self.assertEqual(human_time, "0 Minutes")

        human_time = humanized_time(1)
        self.assertEqual(human_time, "1 Minute")

        human_time = humanized_time(10)
        self.assertEqual(human_time, "10 Minutes")

        human_time = humanized_time(60)
        self.assertEqual(human_time, "1 Hour")

        human_time = humanized_time(61)
        self.assertEqual(human_time, "1 Hour and 1 Minute")

        human_time = humanized_time(62)
        self.assertEqual(human_time, "1 Hour and 2 Minutes")

        human_time = humanized_time(120)
        self.assertEqual(human_time, "2 Hours")

        human_time = humanized_time(121)
        self.assertEqual(human_time, "2 Hours and 1 Minute")

        human_time = humanized_time(150)
        self.assertEqual(human_time, "2 Hours and 30 Minutes")

        human_time = humanized_time(180)
        self.assertEqual(human_time, "3 Hours")
