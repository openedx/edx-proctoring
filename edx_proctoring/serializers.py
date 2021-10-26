"""Defines serializers used by the Proctoring API."""

from rest_framework import serializers
from rest_framework.fields import DateTimeField

from django.contrib.auth import get_user_model

from edx_proctoring.models import (
    ProctoredExam,
    ProctoredExamReviewPolicy,
    ProctoredExamStudentAllowance,
    ProctoredExamStudentAttempt
)

User = get_user_model()


class ProctoredExamSerializer(serializers.ModelSerializer):
    """
    Serializer for the ProctoredExam Model.
    """
    id = serializers.IntegerField(required=False)  # pylint: disable=invalid-name
    course_id = serializers.CharField(required=True)
    content_id = serializers.CharField(required=True)
    external_id = serializers.CharField(required=True)
    exam_name = serializers.CharField(required=True)
    time_limit_mins = serializers.IntegerField(required=True)

    is_active = serializers.BooleanField(required=True)
    is_practice_exam = serializers.BooleanField(required=True)
    is_proctored = serializers.BooleanField(required=True)
    due_date = serializers.DateTimeField(required=False, format=None)
    hide_after_due = serializers.BooleanField(required=True)
    backend = serializers.CharField(required=False)

    class Meta:
        """
        Meta Class
        """
        model = ProctoredExam

        fields = (
            "id", "course_id", "content_id", "external_id", "exam_name",
            "time_limit_mins", "is_proctored", "is_practice_exam", "is_active",
            "due_date", "hide_after_due", "backend"
        )


class ProctoredExamJSONSafeSerializer(ProctoredExamSerializer):
    """
    ProctoredExam serializer which will return dates as strings.
    """
    due_date = serializers.DateTimeField(required=False)


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the User Model.
    """
    id = serializers.IntegerField(required=False)  # pylint: disable=invalid-name
    username = serializers.CharField(required=True)
    email = serializers.CharField(required=True)

    class Meta:
        """
        Meta Class
        """
        model = User

        fields = (
            "id", "username", "email"
        )


class ProctoredExamStudentAttemptSerializer(serializers.ModelSerializer):
    """
    Serializer for the ProctoredExamStudentAttempt Model.
    """
    proctored_exam = ProctoredExamSerializer()
    user = UserSerializer()

    # Django Rest Framework v3 defaults to `settings.DATE_FORMAT` when serializing
    # datetime fields.  We need to specify `format=None` to maintain the old behavior
    # of returning raw `datetime` objects instead of unicode.
    started_at = DateTimeField(format=None)
    completed_at = DateTimeField(format=None)

    class Meta:
        """
        Meta Class
        """
        model = ProctoredExamStudentAttempt

        fields = (
            "id", "created", "modified", "user", "started_at", "completed_at",
            "external_id", "status", "proctored_exam", "allowed_time_limit_mins",
            "attempt_code", "is_sample_attempt", "taking_as_proctored",
            "review_policy_id", "is_status_acknowledged",
            "time_remaining_seconds", "is_resumable", "ready_to_resume", "resumed"
        )


class ProctoredExamStudentAllowanceSerializer(serializers.ModelSerializer):
    """
    Serializer for the ProctoredExamStudentAllowance Model.
    """
    proctored_exam = ProctoredExamSerializer()
    user = UserSerializer()

    class Meta:
        """
        Meta Class
        """
        model = ProctoredExamStudentAllowance
        fields = (
            "id", "created", "modified", "user", "key", "value", "proctored_exam"
        )


class ProctoredExamReviewPolicySerializer(serializers.ModelSerializer):
    """
    Serializer for the ProctoredExamReviewPolicy Model.
    """
    proctored_exam = ProctoredExamSerializer()
    set_by_user = UserSerializer()

    class Meta:
        """
        Meta Class
        """
        model = ProctoredExamReviewPolicy
        fields = (
            "id", "created", "modified", "set_by_user", "proctored_exam", "review_policy",
        )
