"""
Various callback paths that support callbacks from SoftwareSecure
"""

import logging
from django.template import Context, loader
from django.conf import settings
from django.http import HttpResponse
import pytz
from datetime import datetime

from edx_proctoring.models import ProctoredExamStudentAttempt
from ipware.ip import get_ip
from django.core.urlresolvers import reverse

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.negotiation import BaseContentNegotiation

from edx_proctoring.api import (
    get_exam_attempt_by_code,
    mark_exam_attempt_as_ready,
    update_exam_attempt,
    _get_exam_attempt
)
from edx_proctoring.models import ProctoredExamStudentAttemptStatus
from edx_proctoring.exceptions import ProctoredBaseException
from edx_proctoring.utils import locate_attempt_by_attempt_code
from edx_proctoring.backends import get_backend_provider, get_proctoring_settings, get_provider_name_by_course_id


log = logging.getLogger(__name__)


def start_exam_callback(request, attempt_code):  # pylint: disable=unused-argument
    """
    A callback endpoint which is called when SoftwareSecure completes
    the proctoring setup and the exam should be started.

    NOTE: This returns HTML as it will be displayed in an embedded browser

    This is an authenticated endpoint and the attempt_code is passed in
    as part of the URL path

    IMPORTANT: This is an unauthenticated endpoint, so be VERY CAREFUL about extending
    this endpoint
    """

    attempt = get_exam_attempt_by_code(attempt_code)
    if not attempt:
        return HttpResponse(
            content='You have entered an exam code that is not valid.',
            status=404
        )

    if attempt['status'] in [ProctoredExamStudentAttemptStatus.created,
                             ProctoredExamStudentAttemptStatus.download_software_clicked]:
        mark_exam_attempt_as_ready(attempt['proctored_exam']['id'], attempt['user']['id'])

    template = loader.get_template('proctored_exam/proctoring_launch_callback.html')

    poll_url = reverse(
        'edx_proctoring.anonymous.proctoring_poll_status',
        args=[attempt_code]
    )

    provider_name = get_provider_name_by_course_id(attempt['proctored_exam']['course_id'])
    proctoring_settings = get_proctoring_settings(provider_name)
    return HttpResponse(
        template.render(
            Context({
                'exam_attempt_status_url': poll_url,
                'platform_name': settings.PLATFORM_NAME,
                'link_urls': proctoring_settings.get('LINK_URLS', {})
            })
        )
    )


def bulk_start_exams_callback(request, attempt_codes):
    """
    A callback when SoftwareSecure completes setup and the exams should be started.

    A callback endpoint which is called when SoftwareSecure completes
    the proctoring setup and the exams should be started.

    NOTE: This returns HTML as it will be displayed in an embedded browser

    This is an authenticated endpoint and comaseparated attempt codes is passed
    in as part of the URL path

    IMPORTANT: This is an unauthenticated endpoint, so be VERY CAREFUL about extending
    this endpoint
    """
    code_list = attempt_codes.split(',')

    attempts = ProctoredExamStudentAttempt.objects.filter(
         attempt_code__in=code_list
    )
    if not attempts:
        return HttpResponse(
            content='You have entered an exam codes that are not valid.',
            status=404
        )


    for attempt_obj in attempts:
        attempt = _get_exam_attempt(attempt_obj)
        mark_exam_attempt_as_ready(attempt['proctored_exam']['id'], attempt['user']['id'])
        provider_name = get_provider_name_by_course_id(attempt['proctored_exam']['course_id'])
        proctoring_settings = get_proctoring_settings(provider_name)

    template = loader.get_template(
        'proctored_exam/proctoring_launch_callback.html'
    )
    return HttpResponse(
        template.render(
            Context({
                'exam_attempt_status_url': '',
                'platform_name': settings.PLATFORM_NAME,
                'link_urls': proctoring_settings.get('LINK_URLS', {})
            })
        )
    )


class IgnoreClientContentNegotiation(BaseContentNegotiation):
    """
    This specialized class allows for more tolerance regarding
    what the passed in Content-Type is. This is taken directly
    from the Django REST Framework:

    http://tomchristie.github.io/rest-framework-2-docs/api-guide/content-negotiation
    """
    def select_parser(self, request, parsers):
        """
        Select the first parser in the `.parser_classes` list.
        """
        return parsers[0]

    def select_renderer(self, request, renderers, format_suffix):  # pylint: disable=signature-differs
        """
        Select the first renderer in the `.renderer_classes` list.
        """
        return (renderers[0], renderers[0].media_type)


class ExamReviewCallback(APIView):
    """
    This endpoint is called by a 3rd party proctoring review service when
    there are results available for us to record

    IMPORTANT: This is an unauthenticated endpoint, so be VERY CAREFUL about extending
    this endpoint
    """

    content_negotiation_class = IgnoreClientContentNegotiation

    def post(self, request):
        """
        Post callback handler
        """
        try:
            attempt_code = request.data['examMetaData']['examCode']
        except KeyError, ex:
            log.exception(ex)
            return Response(data={'reason': unicode(ex)}, status=400)

        attempt_obj, is_archived_attempt = locate_attempt_by_attempt_code(attempt_code)
        course_id = attempt_obj.proctored_exam.course_id
        provider_name = get_provider_name_by_course_id(course_id)
        provider = get_backend_provider(provider_name)

        # call down into the underlying provider code
        try:
            provider.on_review_callback(request.data)
        except ProctoredBaseException, ex:
            log.exception(ex)
            return Response(data={'reason': unicode(ex)}, status=400)

        return Response(data='OK', status=200)


class BulkExamReviewCallback(APIView):
    """
    This endpoint is called by a 3rd party proctoring review service when
    there are results available for us to record

    IMPORTANT: This is an unauthenticated endpoint, so be VERY CAREFUL about extending
    this endpoint
    """

    content_negotiation_class = IgnoreClientContentNegotiation

    def post(self, request):
        """
        Post callback handler
        """
        data = request.data
        course_id = ""
        for review in data:
            try:
                attempt_code = review['examMetaData']['examCode']
            except KeyError, ex:
                continue
            attempt_obj, is_archived_attempt = locate_attempt_by_attempt_code(attempt_code)
            if course_id != attempt_obj.proctored_exam.course_id:
                course_id = attempt_obj.proctored_exam.course_id
                provider_name = get_provider_name_by_course_id(course_id)
                provider = get_backend_provider(provider_name)

            # call down into the underlying provider code
            try:
                provider.on_review_callback(review)
            except ProctoredBaseException, ex:
                log.exception(ex)

        return Response(data='OK', status=200)


class BulkExamReviewCallback(APIView):
    """
    This endpoint is called by a 3rd party proctoring review service when
    there are results available for us to record

    IMPORTANT: This is an unauthenticated endpoint, so be VERY CAREFUL about extending
    this endpoint
    """

    content_negotiation_class = IgnoreClientContentNegotiation

    def post(self, request):
        """
        Post callback handler
        """
        data = request.data
        course_id = ""
        for review in data:
            try:
                attempt_code = review['examMetaData']['examCode']
            except KeyError, ex:
                continue
            attempt_obj, is_archived_attempt = locate_attempt_by_attempt_code(attempt_code)
            if course_id != attempt_obj.proctored_exam.course_id:
                course_id = attempt_obj.proctored_exam.course_id
                provider_name = get_provider_name_by_course_id(course_id)
                provider = get_backend_provider(provider_name)

            # call down into the underlying provider code
            try:
                provider.on_review_callback(review)
            except ProctoredBaseException, ex:
                log.exception(ex)

        return Response(
            data='OK',
            status=200
        )


class AttemptStatus(APIView):
    """
    This endpoint is called by a 3rd party proctoring review service to determine
    status of an exam attempt.

    IMPORTANT: This is an unauthenticated endpoint, so be VERY CAREFUL about extending
    this endpoint
    """

    def get(self, request, attempt_code):  # pylint: disable=unused-argument
        """
        Returns the status of an exam attempt. Given that this is an unauthenticated
        caller, we will only return the status string, no additional information
        about the exam
        """

        attempt = get_exam_attempt_by_code(attempt_code)
        ip_address = get_ip(request)
        timestamp = datetime.now(pytz.UTC)
        if not attempt:
            return HttpResponse(
                content='You have entered an exam code that is not valid.',
                status=404
            )

        update_exam_attempt(attempt['id'], last_poll_timestamp=timestamp, last_poll_ipaddr=ip_address)

        return Response(
            data={
                # IMPORTANT: Don't add more information to this as it is an
                # unauthenticated endpoint
                'status': attempt['status'],
            },
            status=200
        )
