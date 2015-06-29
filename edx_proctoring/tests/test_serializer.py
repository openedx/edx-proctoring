"""
Tests for the custom StrictBooleanField serializer used by the ProctoredExamSerializer
"""

import unittest
from edx_proctoring.serializers import ProctoredExamSerializer


class TestProctoredExamSerializer(unittest.TestCase):
    """
    Tests for ProctoredExamSerializer
    """
    def test_boolean_fields(self):
        """
        Tests the boolean fields. Should cause a validation error in case a field is required.
        """
        data = {
            'course_id': "a/b/c",
            'exam_name': "midterm1",
            'content_id': '123aXqe0',
            'time_limit_mins': 90,
            'external_id': '123',
            'is_proctored': 'bla',
            'is_active': 'f'
        }
        serializer = ProctoredExamSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertDictEqual(
            {'is_proctored': [u'This field is required.']}, serializer.errors
        )
