"""
Django Admin pages
"""

from django.contrib import admin
from edx_proctoring.models import (
    ProctoredExamReviewPolicy,
    ProctoredExam,
)


class ProctoredExamReviewPolicyInline(admin.TabularInline):
    """
    Custom inline definition to show related fields
    """
    model = ProctoredExam
    fields = ('course_id', 'exam_name',)
    readonly_fields = ('course_id', 'exam_name',)


class ProctoredExamReviewPolicyAdmin(admin.ModelAdmin):
    """
    The admin panel for Review Policies
    """
    readonly_fields = ['set_by_user']

    def course_id(obj):  # pylint: disable=no-self-argument
        """
        return course_id of related model
        """
        return obj.proctored_exam.course_id  # pylint: disable=no-member

    def exam_name(obj):  # pylint: disable=no-self-argument
        """
        return exam name of related model
        """
        return obj.proctored_exam.exam_name  # pylint: disable=no-member

    list_display = [
        course_id,
        exam_name,
    ]
    list_select_related = True
    search_fields = ['proctored_exam__course_id', 'proctored_exam__exam_name']

    def save_model(self, request, obj, form, change):
        """
        Override callback so that we can inject the user_id that made the change
        """
        obj.set_by_user = request.user
        obj.save()

admin.site.register(ProctoredExamReviewPolicy, ProctoredExamReviewPolicyAdmin)
