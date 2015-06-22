"""
URL mappings for edX Proctoring Server.
"""
from edx_proctoring import views

from django.conf.urls import patterns, url, include

urlpatterns = patterns(  # pylint: disable=invalid-name
    '',
    url(
        r'edx_proctoring/v1/proctored_exam/status$',
        views.StudentProctoredExamStatus.as_view(),
        name='edx_proctoring.proctored_exam.status'
    ),
    url(r'^', include('rest_framework.urls', namespace='rest_framework'))
)
