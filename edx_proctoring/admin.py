"""
Django Admin pages
"""
# pylint: disable=no-self-argument, no-member

from django.contrib import admin
from django.utils.translation import ugettext_lazy as _
from django import forms
from edx_proctoring.models import (
    ProctoredExamReviewPolicy,
    ProctoredExamSoftwareSecureReview,
    ProctoredExamSoftwareSecureReviewHistory,
)
from edx_proctoring.utils import locate_attempt_by_attempt_code
from edx_proctoring.backends import get_backend_provider


class ProctoredExamReviewPolicyAdmin(admin.ModelAdmin):
    """
    The admin panel for Review Policies
    """
    readonly_fields = ['set_by_user']

    def course_id(obj):
        """
        return course_id of related model
        """
        return obj.proctored_exam.course_id

    def exam_name(obj):
        """
        return exam name of related model
        """
        return obj.proctored_exam.exam_name

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


class ProctoredExamSoftwareSecureReviewForm(forms.ModelForm):
    """Admin Form to display for reading/updating a Review"""
    class Meta(object):  # pylint: disable=missing-docstring
        model = ProctoredExamSoftwareSecureReview
        fields = '__all__'

    REVIEW_STATUS_CHOICES = [
        ('Clean', 'Clean'),
        ('Rules Violation', 'Rules Violation'),
        ('Suspicious', 'Suspicious'),
        ('Not Reviewed', 'Not Reviewed'),
    ]

    review_status = forms.ChoiceField(choices=REVIEW_STATUS_CHOICES)
    video_url = forms.URLField()
    raw_data = forms.CharField(widget=forms.Textarea, label='Reviewer Notes')


def video_url_for_review(obj):
    """Return hyperlink to review video url"""
    return (
        '<a href="{video_url}" target="_blank">{video_url}</a>'.format(video_url=obj.video_url)
    )
video_url_for_review.allow_tags = True


class ReviewListFilter(admin.SimpleListFilter):
    """
    Quick filter to allow admins to see which reviews have not been reviewed internally
    """

    title = _('internally reviewed')

    parameter_name = 'reviewed_by'

    def lookups(self, request, model_admin):
        """
        List of values to allow admin to select
        """
        return (
            ('all_unreviewed', _('All Unreviewed')),
            ('all_unreviewed_failures', _('All Unreviewed Failures')),
        )

    def queryset(self, request, queryset):
        """
        Return the filtered queryset
        """

        if self.value() == 'all_unreviewed':
            return queryset.filter(reviewed_by__isnull=True)
        elif self.value() == 'all_unreviewed_failures':
            return queryset.filter(reviewed_by__isnull=True, review_status='Suspicious')
        else:
            return queryset


class ProctoredExamSoftwareSecureReviewAdmin(admin.ModelAdmin):
    """
    The admin panel for SoftwareSecure Review records
    """

    readonly_fields = [video_url_for_review, 'attempt_code', 'exam', 'student', 'reviewed_by', 'modified']
    list_filter = [ReviewListFilter, 'review_status', 'exam__course_id', 'exam__exam_name']
    list_select_related = True
    search_fields = ['student__username', 'attempt_code']
    ordering = ['-modified']
    form = ProctoredExamSoftwareSecureReviewForm

    def _get_exam_from_attempt_code(self, code):
        """Get exam from attempt code. Note that the attempt code could be an archived one"""
        attempt = locate_attempt_by_attempt_code(code)
        return attempt.proctored_exam if attempt else None

    def course_id_for_review(self, obj):
        """Return course_id associated with review"""
        if obj.exam:
            return obj.exam.course_id
        else:
            exam = self._get_exam_from_attempt_code(obj.attempt_code)
            return exam.exam_name if exam else '(none)'

    def exam_name_for_review(self, obj):
        """Return course_id associated with review"""
        if obj.exam:
            return obj.exam.exam_name
        else:
            exam = self._get_exam_from_attempt_code(obj.attempt_code)
            return exam.exam_name if exam else '(none)'

    def student_username_for_review(self, obj):
        """Return username of student who took the test"""
        if obj.student:
            return obj.student.username
        else:
            attempt = locate_attempt_by_attempt_code(obj.attempt_code)
            return attempt.user.username if attempt else '(None)'

    list_display = [
        'course_id_for_review',
        'exam_name_for_review',
        'student_username_for_review',
        'attempt_code',
        'modified',
        'reviewed_by',
        'review_status'
    ]

    def has_add_permission(self, request):
        """Don't allow adds"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Don't allow deletes"""
        return False

    def save_model(self, request, review, form, change):
        """
        Override callback so that we can inject the user_id that made the change
        """
        review.reviewed_by = request.user
        review.save()
        # call the review saved and since it's coming from
        # the Django admin will we accept failures
        get_backend_provider().on_review_saved(review, allow_status_update_on_fail=True)

    def get_form(self, request, obj=None, **kwargs):
        form = super(ProctoredExamSoftwareSecureReviewAdmin, self).get_form(request, obj, **kwargs)
        del form.base_fields['video_url']
        return form


class ProctoredExamSoftwareSecureReviewHistoryAdmin(ProctoredExamSoftwareSecureReviewAdmin):
    """
    The admin panel for SoftwareSecure Review records
    """

    readonly_fields = [
        video_url_for_review,
        'review_status',
        'raw_data',
        'attempt_code',
        'exam',
        'student',
        'reviewed_by',
        'modified',
    ]

    def save_model(self, request, review, form, change):
        """
        History can't be updated
        """
        return


admin.site.register(ProctoredExamReviewPolicy, ProctoredExamReviewPolicyAdmin)
admin.site.register(ProctoredExamSoftwareSecureReview, ProctoredExamSoftwareSecureReviewAdmin)
admin.site.register(ProctoredExamSoftwareSecureReviewHistory, ProctoredExamSoftwareSecureReviewHistoryAdmin)
