"""Defines serializers used by the Proctoring API."""
from rest_framework import serializers
from edx_proctoring.models import ProctoredExam, ProctoredExamStudentAttempt, ProctoredExamStudentAllowance


class ProctoredExamSerializer(serializers.ModelSerializer):
    """
    Serializer for the ProctoredExam Model.
    """
    class Meta:
        """
        Meta Class
        """
        model = ProctoredExam
        fields = (
            "course_id", "content_id", "external_id", "exam_name",
            "time_limit_mins", "is_proctored", "is_active"
        )


class ProctoredExamStudentAttemptSerializer(serializers.ModelSerializer):
    """
    Serializer for the ProctoredExamStudentAttempt Model.
    """
    class Meta:
        """
        Meta Class
        """
        model = ProctoredExamStudentAttempt
        fields = (
            "created", "modified", "user_id", "started_at", "completed_at",
            "external_id", "status"
        )


class ProctoredExamStudentAllowanceSerializer(serializers.ModelSerializer):
    """
    Serializer for the ProctoredExamStudentAllowance Model.
    """
    class Meta:
        """
        Meta Class
        """
        model = ProctoredExamStudentAllowance
        fields = (
            "created", "modified", "user_id", "key", "value"
        )
