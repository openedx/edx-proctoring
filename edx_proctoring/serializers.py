"""Defines serializers used by the Proctoring API."""
from rest_framework import serializers
from edx_proctoring.models import ProctoredExam


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
