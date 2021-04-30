"""
URL mappings for edX micro frontend services.
"""

from django.conf import settings
from django.conf.urls import url

from edx_proctoring import views


MFE_USAGE_ID_PATERN = r'([A-z0-9]+|(?:i4x://?[^/]+/[^/]+/[^/]+/[^@]+(?:@[^/]+)?)|(?:[^/]+))'

urlpatterns = [
    url(
        r'edx_proctoring/v1/proctored_exam/exam_attempts/course_id/{}/content_id/(?P<usage_id>{})$'.format(
            settings.COURSE_ID_PATTERN, MFE_USAGE_ID_PATERN),
        views.ProctoredExamAttemptsMFEView.as_view(),
        name='proctored_exam.exam_attempts'
    ),
]
