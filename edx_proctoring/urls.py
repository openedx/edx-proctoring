"""
URL mappings for edX Proctoring Server.
"""
from edx_proctoring import views
from django.conf import settings

from django.conf.urls import patterns, url, include

urlpatterns = patterns(  # pylint: disable=invalid-name
    '',
    url(
        r'edx_proctoring/v1/proctored_exam/exam$',
        views.ProctoredExamView.as_view(),
        name='edx_proctoring.proctored_exam.exam'
    ),
    url(
        r'edx_proctoring/v1/proctored_exam/exam/exam_id/(?P<exam_id>\d+)$',
        views.ProctoredExamView.as_view(),
        name='edx_proctoring.proctored_exam.exam_by_id'
    ),
    url(
        r'edx_proctoring/v1/proctored_exam/exam/course_id/{}/content_id/(?P<content_id>[A-z0-9]+)$'.format(
            settings.COURSE_ID_PATTERN),
        views.ProctoredExamView.as_view(),
        name='edx_proctoring.proctored_exam.exam_by_content_id'
    ),
    url(
        r'edx_proctoring/v1/proctored_exam/attempt$',
        views.StudentProctoredExamAttempt.as_view(),
        name='edx_proctoring.proctored_exam.attempt'
    ),
    url(
        r'edx_proctoring/v1/proctored_exam/allowance$',
        views.ExamAllowanceView.as_view(),
        name='edx_proctoring.proctored_exam.allowance'
    ),
    url(
        r'edx_proctoring/v1/proctored_exam/active_exams_for_user$',
        views.ActiveExamsForUserView.as_view(),
        name='edx_proctoring.proctored_exam.active_exams_for_user'
    ),
    url(r'^', include('rest_framework.urls', namespace='rest_framework'))
)
