from factory import Sequence, SubFactory
from factory.django import DjangoModelFactory

from edx_proctoring.models import (
    ProctoredExamSoftwareSecureComment,
    ProctoredExamSoftwareSecureReview,
    ProctoredExamSoftwareSecureReviewHistory
)


class ProctoredExamSoftwareSecureReviewFactory(DjangoModelFactory):
    class Meta:
        model = ProctoredExamSoftwareSecureReview

    attempt_code = Sequence(lambda n: 'attempt_code_%d' % n)
    review_status = 'review status'
    raw_data = 'raw data'
    encrypted_video_url = b'www.example.com'


class ProctoredExamSoftwareSecureReviewHistoryFactory(ProctoredExamSoftwareSecureReviewFactory):
    class Meta:
        model = ProctoredExamSoftwareSecureReviewHistory


class ProctoredExamSoftwareSecureCommentFactory(DjangoModelFactory):
    class Meta:
        model = ProctoredExamSoftwareSecureComment

    review = SubFactory(ProctoredExamSoftwareSecureReviewFactory)
    comment = 'comment'
    status = 'status'
    start_time = 100
    stop_time = 150
    duration = 150
