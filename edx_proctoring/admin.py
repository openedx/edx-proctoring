"""
Django Admin pages
"""
# pylint: disable=no-self-argument, no-member

import pytz
from datetime import datetime, timedelta

from django import forms
from django.db.models import Q
from django.contrib import admin
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _
from edx_proctoring.models import (
    ProctoredExam,
    ProctoredExamReviewPolicy,
    ProctoredExamSoftwareSecureReview,
    ProctoredExamSoftwareSecureReviewHistory,
    ProctoredExamStudentAttempt,
    ProctoredExamStudentAttemptStatus,
)
from edx_proctoring.api import update_attempt_status
from edx_proctoring.utils import locate_attempt_by_attempt_code
from edx_proctoring.exceptions import (
    ProctoredExamIllegalStatusTransition,
    StudentExamAttemptDoesNotExistsException,
)
from edx_proctoring.backends import get_backend_provider, get_provider_name_by_course_id


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
    raw_data = forms.CharField(widget=forms.Textarea, label='Reviewer Notes')


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


class ProctoredExamListFilter(admin.SimpleListFilter):
    """
    Quick filter to allow admins to see which reviews have not been reviewed internally
    """

    title = _('active proctored exams')

    parameter_name = 'exam__id'

    def lookups(self, request, model_admin):
        """
        List of values to allow admin to select
        """

        now_utc = datetime.now(pytz.UTC)
        thirty_days_ago = now_utc - timedelta(days=30)
        one_week_from_now = now_utc + timedelta(days=7)

        # only consider proctored (not practice) exams that have a due date of no more than
        # a month ago as well as a week into the future. This is to help keep the list of
        # quick filters small and reasonable in length
        exams = ProctoredExam.objects.filter(
            Q(is_proctored=True) &
            Q(is_active=True) &
            Q(is_practice_exam=False) &
            Q(
                Q(due_date__gte=thirty_days_ago, due_date__lte=one_week_from_now) |
                Q(due_date__isnull=True)
            )
        )

        lookups = (())

        for exam in exams:
            course_id = exam.course_id

            # to help disambiguate exam names,
            # prepend the exam_name with a parsed out course_id
            lookups += ((
                exam.id,
                u'{course_id}: {exam_name}'.format(
                    course_id=prettify_course_id(course_id),
                    exam_name=exam.exam_name
                )
            ),)

        return lookups

    def queryset(self, request, queryset):
        """
        Return the filtered queryset
        """
        if not self.value():
            return queryset

        return queryset.filter(exam__id=self.value())


class ProctoredExamCoursesListFilter(admin.SimpleListFilter):
    """
    Quick filter to allow admins to see which reviews have not been reviewed internally
    """

    title = _('courses with active proctored exams')

    parameter_name = 'exam__course_id'

    def lookups(self, request, model_admin):
        """
        List of values to allow admin to select
        """

        now_utc = datetime.now(pytz.UTC)
        thirty_days_ago = now_utc - timedelta(days=30)
        one_week_from_now = now_utc + timedelta(days=7)

        # only consider proctored (not practice) exams that have a due date of no more than
        # a month ago as well as a week into the future. This is to help keep the list of
        # quick filters small and reasonable in length
        exams = ProctoredExam.objects.filter(
            is_proctored=True,
            is_active=True,
            is_practice_exam=False,
            due_date__gte=thirty_days_ago,
            due_date__lte=one_week_from_now
        )

        lookups = (())

        existing_course_ids = []

        for exam in exams:
            # make sure we don't have duplicate course_ids
            if exam.course_id not in existing_course_ids:
                lookups += ((exam.course_id, exam.course_id),)
                existing_course_ids.append(exam.course_id)

        return lookups

    def queryset(self, request, queryset):
        """
        Return the filtered queryset
        """

        if not self.value():
            return queryset

        return queryset.filter(
            exam__course_id=self.value(),
            exam__is_proctored=True,
            exam__is_active=True,
            exam__is_practice_exam=False
        )


class ProctoredExamSoftwareSecureReviewAdmin(admin.ModelAdmin):
    """
    The admin panel for SoftwareSecure Review records
    """

    readonly_fields = ['attempt_code', 'exam', 'student', 'reviewed_by', 'modified']
    list_filter = [
        ReviewListFilter,
        ProctoredExamListFilter,
        ProctoredExamCoursesListFilter,
        'review_status'
    ]
    list_select_related = True
    search_fields = ['student__username', 'attempt_code']
    ordering = ['-modified']
    form = ProctoredExamSoftwareSecureReviewForm

    def _get_exam_from_attempt_code(self, code):
        """Get exam from attempt code. Note that the attempt code could be an archived one"""
        (attempt_obj, __) = locate_attempt_by_attempt_code(code)
        return attempt_obj.proctored_exam if attempt_obj else None

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
            (attempt_obj, __) = locate_attempt_by_attempt_code(obj.attempt_code)
            return attempt_obj.user.username if attempt_obj else '(None)'

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
        """ Allow deletes """
        return True

    def save_model(self, request, review, form, change):
        """
        Override callback so that we can inject the user_id that made the change
        """
        review.reviewed_by = request.user
        review.save()
        # call the review saved and since it's coming from
        # the Django admin will we accept failures

        provider_name = get_provider_name_by_course_id(review.exam['course_id'])
        get_backend_provider(provider_name).on_review_saved(review, allow_status_update_on_fail=True)

    def get_form(self, request, obj=None, **kwargs):
        form = super(ProctoredExamSoftwareSecureReviewAdmin, self).get_form(request, obj, **kwargs)
        if 'video_url' in form.base_fields:
            del form.base_fields['video_url']
        return form

    def lookup_allowed(self, key, value):
        if key == 'exam__course_id':
            return True
        return super(ProctoredExamSoftwareSecureReviewAdmin, self).lookup_allowed(key, value)


class ProctoredExamSoftwareSecureReviewHistoryAdmin(ProctoredExamSoftwareSecureReviewAdmin):
    """
    The admin panel for SoftwareSecure Review records
    """

    readonly_fields = [
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


class ExamAttemptFilterByCourseId(admin.SimpleListFilter):
    """
    Quick filter to allow admins to see attempts by "course_id"
    """

    title = _('Course Id')
    parameter_name = 'proctored_exam__course_id'

    def lookups(self, request, model_admin):
        """
        List of values to allow admin to select
        """
        lookups = (())
        unique_course_ids = ProctoredExamStudentAttempt.objects.values_list(
            'proctored_exam__course_id',
            flat=True
        ).distinct()

        if unique_course_ids:
            lookups = [(course_id, prettify_course_id(course_id)) for course_id in unique_course_ids]

        return lookups

    def queryset(self, request, queryset):
        """
        Return the filtered queryset
        """
        if self.value():
            return queryset.filter(proctored_exam__course_id=self.value())
        else:
            return queryset


class ProctoredExamAttemptForm(forms.ModelForm):
    """
    Admin Form to display for reading/updating a Proctored Exam Attempt
    """

    class Meta(object):  # pylint: disable=missing-docstring
        model = ProctoredExamStudentAttempt
        fields = '__all__'

    STATUS_CHOICES = [
        (ProctoredExamStudentAttemptStatus.created, _('Created')),
        (ProctoredExamStudentAttemptStatus.download_software_clicked, _('Download Software Clicked')),
        (ProctoredExamStudentAttemptStatus.ready_to_start, _('Ready To Start')),
        (ProctoredExamStudentAttemptStatus.started, _('Started')),
        (ProctoredExamStudentAttemptStatus.ready_to_submit, _('Ready To Submit')),
        (ProctoredExamStudentAttemptStatus.declined, _('Declined')),
        (ProctoredExamStudentAttemptStatus.timed_out, _('Timed Out')),
        (ProctoredExamStudentAttemptStatus.submitted, _('Submitted')),
        (ProctoredExamStudentAttemptStatus.second_review_required, _('Second Review Required')),
        (ProctoredExamStudentAttemptStatus.verified, _('Verified')),
        (ProctoredExamStudentAttemptStatus.rejected, _('Rejected')),
        (ProctoredExamStudentAttemptStatus.error, _('Error')),
    ]

    status = forms.ChoiceField(choices=STATUS_CHOICES)


class ProctoredExamStudentAttemptAdmin(admin.ModelAdmin):
    """
    Admin panel for Proctored Exam Attempts
    """

    readonly_fields = [
        'user',
        'proctored_exam',
        'started_at',
        'completed_at',
        'last_poll_timestamp',
        'last_poll_ipaddr',
        'attempt_code',
        'external_id',
        'allowed_time_limit_mins',
        'taking_as_proctored',
        'is_sample_attempt',
        'student_name',
        'review_policy_id',
        'is_status_acknowledged'
    ]

    list_display = [
        'username',
        'exam_name',
        'course_id',
        'taking_as_proctored',
        'is_sample_attempt',
        'attempt_code',
        'status',
        'modified'
    ]

    search_fields = [
        'user__username',
        'attempt_code'
    ]

    list_filter = [
        'status',
        'taking_as_proctored',
        'is_sample_attempt',
        ExamAttemptFilterByCourseId
    ]

    form = ProctoredExamAttemptForm

    def username(self, obj):
        """ Return user's username of attempt"""
        return obj.user.username

    def exam_name(self, obj):
        """ Return exam_name of attempt"""
        return obj.proctored_exam.exam_name

    def course_id(self, obj):
        """ Return course_id of attempt"""
        return obj.proctored_exam.course_id

    def save_model(self, request, obj, form, change):
        """
        Override callback so that we can change the status by "update_attempt_status" function
        """
        try:
            if change:
                update_attempt_status(obj.proctored_exam.id, obj.user.id, form.cleaned_data['status'])
        except (ProctoredExamIllegalStatusTransition, StudentExamAttemptDoesNotExistsException) as ex:
            messages.error(request, ex.message)

    def has_add_permission(self, request):
        """Don't allow adds"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Don't allow deletes"""
        return False


def prettify_course_id(course_id):
    """
    Prettify the COURSE ID string
    """
    return course_id.replace('+', ' ').replace('/', ' ').replace('course-v1:', '')

admin.site.register(ProctoredExamStudentAttempt, ProctoredExamStudentAttemptAdmin)
admin.site.register(ProctoredExamReviewPolicy, ProctoredExamReviewPolicyAdmin)
admin.site.register(ProctoredExamSoftwareSecureReview, ProctoredExamSoftwareSecureReviewAdmin)
admin.site.register(ProctoredExamSoftwareSecureReviewHistory, ProctoredExamSoftwareSecureReviewHistoryAdmin)
