"""
Test for the xBlock service
"""

import unittest
from edx_proctoring.services import ProctoringService
from edx_proctoring import api as edx_proctoring_api
import types


class TestProctoringService(unittest.TestCase):
    """
    Tests for ProctoringService
    """
    def test_basic(self):
        """
        See if the ProctoringService exposes the expected methods
        """

        service = ProctoringService()

        for attr_name in dir(edx_proctoring_api):
            attr = getattr(edx_proctoring_api, attr_name, None)
            if isinstance(attr, types.FunctionType) and not attr_name.startswith('_'):
                self.assertTrue(hasattr(service, attr_name))
