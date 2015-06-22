"""
All tests for the proctored_exams.py
"""
from django.test.client import Client
from django.core.urlresolvers import reverse, NoReverseMatch

from .utils import (
    LoggedInTestCase
)

from edx_proctoring.urls import urlpatterns


class ProctoredExamsApiTests(LoggedInTestCase):
    """
    All tests for the views.py
    """

    def setUp(self):
        """
        Build out test harnessing
        """
        super(ProctoredExamsApiTests, self).setUp()

    def test_no_anonymous_access(self):
        """
        Make sure we cannot access any API methods without being logged in
        """

        self.client = Client()  # use AnonymousUser on the API calls

        for urlpattern in urlpatterns:
            if hasattr(urlpattern, 'name'):
                try:
                    response = self.client.get(reverse(urlpattern.name))
                except NoReverseMatch:
                    # some of our URL mappings may require a argument substitution
                    response = self.client.get(reverse(urlpattern.name, args=[0]))

                self.assertEqual(response.status_code, 403)

    def test_get_proctored_exam_status(self):
        """
        Test Case for retrieving student proctored exam status.
        """

        response = self.client.get(
            reverse('edx_proctoring.proctored_exam.status')
        )
        self.assertEqual(response.status_code, 200)
