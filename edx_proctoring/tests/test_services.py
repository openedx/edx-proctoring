# pylint: disable=unused-argument

"""
Test for the xBlock service
"""

import unittest
from edx_proctoring.services import (
    ProctoringService
)
from edx_proctoring import api as edx_proctoring_api
import types


class MockCreditService(object):
    """
    Simple mock of the Credit Service
    """

    def __init__(self):
        """
        Initializer
        """
        self.status = {
            'enrollment_mode': 'verified',
            'profile_fullname': 'Wolfgang von Strucker',
            'credit_requirement_status': []
        }

    def get_credit_state(self, user_id, course_key):  # pylint: disable=unused-argument
        """
        Mock implementation
        """

        return self.status

    def set_credit_requirement_status(self, user_id, course_key_or_id, req_namespace,
                                      req_name, status="satisfied", reason=None):
        """
        Mock implementation
        """

        found = [
            requirement
            for requirement in self.status['credit_requirement_status']
            if requirement['name'] == req_name and
            requirement['namespace'] == req_namespace and
            requirement['course_id'] == unicode(course_key_or_id)
        ]

        if not found:
            self.status['credit_requirement_status'].append({
                'course_id': unicode(course_key_or_id),
                'req_namespace': req_namespace,
                'namespace': req_namespace,
                'name': req_name,
                'status': status
            })
        else:
            found[0]['status'] = status


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

    def test_singleton(self):
        """
        Test to make sure the ProctoringService is a singleton.
        """
        service1 = ProctoringService()
        service2 = ProctoringService()
        self.assertIs(service1, service2)
