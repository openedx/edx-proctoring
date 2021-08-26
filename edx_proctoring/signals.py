"""edx-proctoring signals"""
from django.dispatch import Signal

# Signal that is emitted when an attempt status is updated. Added to utils to avoid cyclic import in signals.py file
exam_attempt_status_signal = Signal(providing_args=[
    "attempt_id",
    "user_id",
    "status",
    "full_name",
    "profile_name",
    "is_practice_exam",
    "is_proctored"
    "backend_supports_onboarding"
])
