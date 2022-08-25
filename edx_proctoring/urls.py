"""
URL mappings for edX Proctoring Server.
"""

from django.conf import settings
from django.urls import include, path, re_path

from edx_proctoring import callbacks, instructor_dashboard_exam_urls, views

app_name = 'edx_proctoring'

CONTENT_ID_PATTERN = r'(?P<content_id>([A-z0-9]+|(?:i4x://?[^/]+/[^/]+/[^/]+/[^@]+(?:@[^/]+)?)|(?:[^/]+)))'

urlpatterns = [
    path('edx_proctoring/v1/proctored_exam/exam', views.ProctoredExamView.as_view(),
         name='proctored_exam.exam'
         ),
    path('edx_proctoring/v1/proctored_exam/exam/exam_id/<int:exam_id>', views.ProctoredExamView.as_view(),
         name='proctored_exam.exam_by_id'
         ),
    re_path(
        (fr'edx_proctoring/v1/proctored_exam/exam/course_id/{settings.COURSE_ID_PATTERN}'
         '/content_id/(?P<content_id>[A-z0-9]+)$'),
        views.ProctoredExamView.as_view(),
        name='proctored_exam.exam_by_content_id'
    ),
    re_path(
        fr'edx_proctoring/v1/proctored_exam/exam/course_id/{settings.COURSE_ID_PATTERN}$',
        views.ProctoredExamView.as_view(),
        name='proctored_exam.exams_by_course_id'
    ),
    re_path(
        fr'edx_proctoring/v1/proctored_exam/exam_registration/course_id/{settings.COURSE_ID_PATTERN}$',
        views.RegisterProctoredExamsView.as_view(),
        name='proctored_exam.register_exams_by_course_id'
    ),
    path('edx_proctoring/v1/proctored_exam/attempt/<int:attempt_id>', views.StudentProctoredExamAttempt.as_view(),
         name='proctored_exam.attempt'
         ),
    re_path(
        fr'edx_proctoring/v1/proctored_exam/attempt/grouped/course_id/{settings.COURSE_ID_PATTERN}$',
        views.StudentProctoredGroupedExamAttemptsByCourse.as_view(),
        name='proctored_exam.attempts.grouped.course'
    ),
    re_path(
        'edx_proctoring/v1/proctored_exam/attempt/grouped/course_id/'
        fr'{settings.COURSE_ID_PATTERN}/search/(?P<search_by>.+)$',
        views.StudentProctoredGroupedExamAttemptsByCourse.as_view(),
        name='proctored_exam.attempts.grouped.search'
    ),
    path('edx_proctoring/v1/proctored_exam/attempt',
         views.StudentProctoredExamAttemptCollection.as_view(),
         name='proctored_exam.attempt.collection'
         ),
    path('edx_proctoring/v1/proctored_exam/attempt/<int:attempt_id>/review_status',
         views.ProctoredExamAttemptReviewStatus.as_view(),
         name='proctored_exam.attempt.review_status'
         ),
    path('edx_proctoring/v1/proctored_exam/attempt/<slug:external_id>/ready',
         views.ExamReadyCallback.as_view(),
         name='proctored_exam.attempt.ready_callback'
         ),
    path('edx_proctoring/v1/proctored_exam/attempt/<slug:external_id>/reviewed',
         views.ProctoredExamReviewCallback.as_view(),
         name='proctored_exam.attempt.callback'
         ),
    re_path(
        fr'edx_proctoring/v1/proctored_exam/{settings.COURSE_ID_PATTERN}/allowance$',
        views.ExamAllowanceView.as_view(),
        name='proctored_exam.allowance'
    ),
    path('edx_proctoring/v1/proctored_exam/allowance', views.ExamAllowanceView.as_view(),
         name='proctored_exam.allowance'
         ),
    re_path(
        fr'edx_proctoring/v1/proctored_exam/{settings.COURSE_ID_PATTERN}/bulk_allowance$',
        views.ExamBulkAllowanceView.as_view(),
        name='proctored_exam.bulk_allowance'
    ),
    path('edx_proctoring/v1/proctored_exam/bulk_allowance', views.ExamBulkAllowanceView.as_view(),
         name='proctored_exam.bulk_allowance'
         ),
    re_path(
        fr'edx_proctoring/v1/proctored_exam/{settings.COURSE_ID_PATTERN}/grouped/allowance$',
        views.GroupedExamAllowancesByStudent.as_view(),
        name='proctored_exam.allowance.grouped.course'
    ),
    path('edx_proctoring/v1/proctored_exam/active_exams_for_user', views.ActiveExamsForUserView.as_view(),
         name='proctored_exam.active_exams_for_user'
         ),
    path('edx_proctoring/v1/user_onboarding/status', views.StudentOnboardingStatusView.as_view(),
         name='user_onboarding.status'
         ),
    re_path(
        fr'edx_proctoring/v1/user_onboarding/status/course_id/{settings.COURSE_ID_PATTERN}$',
        views.StudentOnboardingStatusByCourseView.as_view(),
        name='user_onboarding.status.course'
    ),
    re_path(
        fr'edx_proctoring/v1/instructor/{settings.COURSE_ID_PATTERN}$',
        views.InstructorDashboard.as_view(),
        name='instructor_dashboard_course'
    ),
    re_path(
        r'edx_proctoring/v1/retire_backend_user/(?P<user_id>[\d]+)/$',
        views.BackendUserManagementAPI.as_view(),
        name='backend_user_deletion_api'
    ),
    re_path(
        r'edx_proctoring/v1/retire_user/(?P<user_id>[\d]+)/$',
        views.UserRetirement.as_view(),
        name='user_retirement_api'
    ),
    re_path(
        fr'edx_proctoring/v1/proctored_exam/attempt/course_id/{settings.COURSE_ID_PATTERN}$',
        views.ProctoredExamAttemptView.as_view(),
        name='proctored_exam.exam_attempts'
    ),
    path('edx_proctoring/v1/proctored_exam/settings/exam_id/<int:exam_id>/', views.ProctoredSettingsView.as_view(),
         name='proctored_exam.proctoring_settings'
         ),
    path('edx_proctoring/v1/proctored_exam/review_policy/exam_id/<int:exam_id>/',
         views.ProctoredExamReviewPolicyView.as_view(),
         name='proctored_exam.review_policy'
         ),

    # Unauthenticated callbacks from SoftwareSecure. Note we use other
    # security token measures to protect data
    #
    path('edx_proctoring/proctoring_launch_callback/start_exam/<slug:attempt_code>', callbacks.start_exam_callback,
         name='anonymous.proctoring_launch_callback.start_exam'
         ),
    path('edx_proctoring/proctoring_review_callback/', views.AnonymousReviewCallback.as_view(),
         name='anonymous.proctoring_review_callback'
         ),
    re_path(
        r'edx_proctoring/v1/proctored_exam/exam_id/(?P<exam_id>\d+)/user_id/(?P<user_id>[\d]+)/reset_attempts$',
        views.StudentProctoredExamResetAttempts.as_view(),
        name='proctored_exam.attempts.reset'
    ),
    path('', include('rest_framework.urls', namespace='rest_framework')),
]

urlpatterns += instructor_dashboard_exam_urls.urlpatterns
