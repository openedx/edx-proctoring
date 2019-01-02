"""
URL mapping for the exam instructor dashboard.
"""

from django.conf import settings
from django.conf.urls import url

from edx_proctoring import views

urlpatterns = [
    url(
        r'edx_proctoring/v1/instructor/{}/(?P<exam_id>\d+)$'.format(settings.COURSE_ID_PATTERN),
        views.InstructorDashboard.as_view(),
        name='instructor_dashboard_exam'
    ),
]
