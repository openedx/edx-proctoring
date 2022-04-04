

from django.conf import settings
from django.urls import include, re_path

from edx_proctoring import views

urlpatterns = [
  re_path(r'^', include('edx_proctoring.urls', namespace='edx_proctoring')),
  # Fake view to mock url pattern provided by edx_platform
  re_path(
        r'^courses/{}/jump_to/(?P<location>.*)$'.format(
            settings.COURSE_ID_PATTERN,
        ),
        views.StudentOnboardingStatusView.as_view(),
        name='jump_to',
    )
]
