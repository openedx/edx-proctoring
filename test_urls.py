

from django.conf import settings
from django.conf.urls import include, url

from edx_proctoring import views

urlpatterns = [
  url(r'^', include('edx_proctoring.urls', namespace='edx_proctoring')),
  # Fake view to mock url pattern provided by edx_platform
  url(
        r'^courses/{}/jump_to/(?P<location>.*)$'.format(
            settings.COURSE_ID_PATTERN,
        ),
        views.StudentOnboardingStatusView.as_view(),
        name='jump_to',
    )
]
