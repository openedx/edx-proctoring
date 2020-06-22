"""
URL mappings for edX Proctoring Server.
"""

from django.conf import settings
from django.conf.urls import include, url

from edx_proctoring import callbacks, instructor_dashboard_exam_urls, views

app_name = u'edx_proctoring'

urlpatterns = [
    url(
        r'edx_proctoring/v1/proctored_exam/exam$',
        views.ProctoredExamView.as_view(),
        name='proctored_exam.exam'
    ),
    url(
        r'edx_proctoring/v1/proctored_exam/exam/exam_id/(?P<exam_id>\d+)$',
        views.ProctoredExamView.as_view(),
        name='proctored_exam.exam_by_id'
    ),
    url(
        r'edx_proctoring/v1/proctored_exam/exam/course_id/{}/content_id/(?P<content_id>[A-z0-9]+)$'.format(
            settings.COURSE_ID_PATTERN),
        views.ProctoredExamView.as_view(),
        name='proctored_exam.exam_by_content_id'
    ),
    url(
        r'edx_proctoring/v1/proctored_exam/exam/course_id/{}$'.format(
            settings.COURSE_ID_PATTERN),
        views.ProctoredExamView.as_view(),
        name='proctored_exam.exams_by_course_id'
    ),
    url(
        r'edx_proctoring/v1/proctored_exam/attempt/(?P<attempt_id>\d+)$',
        views.StudentProctoredExamAttempt.as_view(),
        name='proctored_exam.attempt'
    ),
    url(
        r'edx_proctoring/v1/proctored_exam/attempt/course_id/{}$'.format(settings.COURSE_ID_PATTERN),
        views.StudentProctoredExamAttemptsByCourse.as_view(),
        name='proctored_exam.attempts.course'
    ),
    url(
        r'edx_proctoring/v1/proctored_exam/attempt/course_id/{}/search/(?P<search_by>.+)$'.format(
            settings.COURSE_ID_PATTERN),
        views.StudentProctoredExamAttemptsByCourse.as_view(),
        name='proctored_exam.attempts.search'
    ),
    url(
        r'edx_proctoring/v1/proctored_exam/attempt$',
        views.StudentProctoredExamAttemptCollection.as_view(),
        name='proctored_exam.attempt.collection'
    ),
    url(
        r'edx_proctoring/v1/proctored_exam/attempt/(?P<attempt_id>\d+)/review_status$',
        views.ProctoredExamAttemptReviewStatus.as_view(),
        name='proctored_exam.attempt.review_status'
    ),
    url(
        r'edx_proctoring/v1/proctored_exam/attempt/(?P<external_id>[-\w]+)/ready$',
        views.ExamReadyCallback.as_view(),
        name='proctored_exam.attempt.ready_callback'
    ),
    url(
        r'edx_proctoring/v1/proctored_exam/attempt/(?P<external_id>[-\w]+)/reviewed$',
        views.ProctoredExamReviewCallback.as_view(),
        name='proctored_exam.attempt.callback'
    ),
    url(
        r'edx_proctoring/v1/proctored_exam/{}/allowance$'.format(settings.COURSE_ID_PATTERN),
        views.ExamAllowanceView.as_view(),
        name='proctored_exam.allowance'
    ),
    url(
        r'edx_proctoring/v1/proctored_exam/allowance$',
        views.ExamAllowanceView.as_view(),
        name='proctored_exam.allowance'
    ),
    url(
        r'edx_proctoring/v1/proctored_exam/active_exams_for_user$',
        views.ActiveExamsForUserView.as_view(),
        name='proctored_exam.active_exams_for_user'
    ),
    url(
        r'edx_proctoring/v1/instructor/{}$'.format(settings.COURSE_ID_PATTERN),
        views.InstructorDashboard.as_view(),
        name='instructor_dashboard_course'
    ),
    url(
        r'edx_proctoring/v1/retire_backend_user/(?P<user_id>[\d]+)/$',
        views.BackendUserManagementAPI.as_view(),
        name='backend_user_deletion_api'
    ),
    url(
        r'edx_proctoring/v1/retire_user/(?P<user_id>[\d]+)/$',
        views.UserRetirement.as_view(),
        name='user_retirement_api'
    ),

    # Unauthenticated callbacks from SoftwareSecure. Note we use other
    # security token measures to protect data
    #
    url(
        r'edx_proctoring/proctoring_launch_callback/start_exam/(?P<attempt_code>[-\w]+)$',
        callbacks.start_exam_callback,
        name='anonymous.proctoring_launch_callback.start_exam'
    ),
    url(
        r'edx_proctoring/proctoring_review_callback/$',
        views.AnonymousReviewCallback.as_view(),
        name='anonymous.proctoring_review_callback'
    ),
    url(r'^', include('rest_framework.urls', namespace='rest_framework'))
]

urlpatterns += instructor_dashboard_exam_urls.urlpatterns
