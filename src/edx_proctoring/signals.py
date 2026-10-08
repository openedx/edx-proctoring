"""edx-proctoring signals"""
from django.dispatch import Signal

# Signal that is emitted when an attempt status is updated. Added to utils to avoid cyclic import in signals.py file
exam_attempt_status_signal = Signal()
