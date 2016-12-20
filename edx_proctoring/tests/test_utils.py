"""
File that contains tests for the util methods.
"""

from __future__ import absolute_import

import unittest

from edx_proctoring.utils import humanized_time, _emit_event


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
