

from django.conf import settings
from django.conf.urls import include

from edx_proctoring import views
from django.urls import path, re_path

urlpatterns = [
  path('', include('edx_proctoring.urls', namespace='edx_proctoring')),
  # Fake view to mock url pattern provided by edx_platform
  re_path(
        r'^courses/{}/jump_to/(?P<location>.*)$'.format(
            settings.COURSE_ID_PATTERN,
        ),
        views.StudentOnboardingStatusView.as_view(),
        name='jump_to',
    )
]
