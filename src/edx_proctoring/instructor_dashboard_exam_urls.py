"""
URL mapping for the exam instructor dashboard.
"""

from django.conf import settings
from django.urls import re_path

from edx_proctoring import views

app_name = 'instructor'


urlpatterns = [
    re_path(
        fr'edx_proctoring/v1/instructor/{settings.COURSE_ID_PATTERN}/(?P<exam_id>\d+)$',
        views.InstructorDashboard.as_view(),
        name='instructor_dashboard_exam'
    ),
]
