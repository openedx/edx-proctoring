"""Defines serializers used by the Proctoring API."""
from rest_framework import serializers
from edx_proctoring.models import ProctoredExam


class ProctoredExamSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProctoredExam
        fields = (
            "course_id", "content_id", "external_id", "exam_name",
            "time_limit_mins", "is_proctored", "is_active"
        )
