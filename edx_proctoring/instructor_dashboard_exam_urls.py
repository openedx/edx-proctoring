"""
URL mapping for the exam instructor dashboard.
"""

from django.conf import settings
from django.conf.urls import url

from edx_proctoring import views

app_name = 'instructor'


urlpatterns = [
    url(
        fr'edx_proctoring/v1/instructor/{settings.COURSE_ID_PATTERN}/(?P<exam_id>\d+)$',
        views.InstructorDashboard.as_view(),
        name='instructor_dashboard_exam'
    ),
]
