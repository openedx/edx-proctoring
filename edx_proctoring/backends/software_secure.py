"""
Integration with Software Secure's proctoring system
"""

import base64
import binascii
import codecs
import datetime
import hmac
import json
import logging
import unicodedata
from hashlib import sha256

import requests
from crum import get_current_request
from Cryptodome.Cipher import DES3

from django.conf import settings
from django.urls import reverse

from edx_proctoring import constants
from edx_proctoring.backends.backend import ProctoringBackendProvider
from edx_proctoring.exceptions import BackendProviderCannotRegisterAttempt, ProctoredExamSuspiciousLookup
from edx_proctoring.statuses import SoftwareSecureReviewStatus
from edx_proctoring.utils import decode_and_decrypt

log = logging.getLogger(__name__)


SOFTWARE_SECURE_INVALID_CHARS = '[]<>#:|!?/\'"*\\'


class SoftwareSecureBackendProvider(ProctoringBackendProvider):
    """
    Implementation of the ProctoringBackendProvider for PSI's
    (formerly Software Secure's) RPNow product
    """
    verbose_name = 'RPNow'
    passing_statuses = SoftwareSecureReviewStatus.passing_statuses

    def __init__(self, organization, exam_sponsor, exam_register_endpoint,
                 secret_key_id, secret_key, crypto_key, software_download_url,
                 video_review_aes_key=None, send_email=False, **kwargs):
        """
        Class initializer
        """
        # pylint: disable=no-member
        super().__init__(**kwargs)
        self.organization = organization
        self.exam_sponsor = exam_sponsor
        self.exam_register_endpoint = exam_register_endpoint
        self.secret_key_id = secret_key_id
        self.secret_key = secret_key
        if isinstance(crypto_key, str):
            crypto_key = crypto_key.encode('utf-8')
        self.crypto_key = crypto_key
        self.timeout = 10
        self.software_download_url = software_download_url
        self.send_email = send_email
        self.video_review_aes_key = video_review_aes_key

    def register_exam_attempt(self, exam, context):
        """
        Method that is responsible for communicating with the backend provider
        to establish a new proctored exam
        """

        attempt_code = context['attempt_code']

        data = self._get_payload(
            exam,
            context
        )

        headers = {
            "Content-Type": 'application/json'
        }
        http_date = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
        signature = self._sign_doc(data, 'POST', headers, http_date)

        status, response = self._send_request_to_ssi(data, signature, http_date)

        if status not in [200, 201]:
            err_msg = (
                f'Could not register attempt_code={attempt_code}. '
                f'HTTP Status code was {status} and response was {response}.'
            )
            log.error(err_msg)
            raise BackendProviderCannotRegisterAttempt(err_msg, status)

        # get the external ID that Software Secure has defined
        # for this attempt
        ssi_record_locator = json.loads(response)['ssiRecordLocator']

        return ssi_record_locator

    def start_exam_attempt(self, exam, attempt):  # pylint: disable=unused-argument
        """
        Called when the exam attempt has been created but not started
        """
        return None

    def stop_exam_attempt(self, exam, attempt):
        """
        Method that is responsible for communicating with the backend provider
        to establish a new proctored exam
        """
        return None

    def mark_erroneous_exam_attempt(self, exam, attempt):
        """
        Method that would be responsible for communicating with the
        backend provider to mark a proctored session as having
        encountered a technical error
        """
        return None

    def remove_exam_attempt(self, exam, attempt):
        return None

    def get_software_download_url(self):
        """
        Returns the URL that the user needs to go to in order to download
        the corresponding desktop software
        """
        return self.software_download_url

    def on_review_callback(self, attempt, payload):
        """
        Called when the reviewing 3rd party service posts back the results

        Documentation on the data format can be found from SoftwareSecure's
        documentation named "Reviewer Data Transfer"
        """
        received_id = payload['examMetaData']['ssiRecordLocator'].lower()
        match = (
            attempt['external_id'].lower() == received_id.lower() or
            settings.PROCTORING_SETTINGS.get('ALLOW_CALLBACK_SIMULATION', False)
        )
        if not match:
            err_msg = (
                f"Found attempt_code {attempt['attempt_code']}, but the recorded external_id did not "
                f"match the ssiRecordLocator that had been recorded previously. Has {attempt['external_id']} "
                f'but received {received_id}!'
            )
            raise ProctoredExamSuspiciousLookup(err_msg)

        SoftwareSecureReviewStatus.validate(payload['reviewStatus'])
        review_status = SoftwareSecureReviewStatus.to_standard_status.get(payload['reviewStatus'], None)

        log_msg = (
            f"Received callback from SoftwareSecure for attempt_id={attempt['id']} with status={review_status}"
        )
        log.info(log_msg)

        comments = []
        for comment in payload.get('webCamComments', []) + payload.get('desktopComments', []):
            comments.append({
                'start': comment['eventStart'],
                'stop': comment['eventFinish'],
                'duration': comment['duration'],
                'comment': comment['comments'],
                'status': comment['eventStatus']
                })

        converted = {
            'status': review_status,
            'comments': comments,
            'payload': payload,
            'reviewed_by': None,
        }
        return converted

    def on_exam_saved(self, exam):
        """
        Called after an exam is saved.
        """

    def _encrypt_password(self, key, pwd):
        """
        Encrypt the exam passwork with the given key
        """
        block_size = DES3.block_size

        def pad(text):
            """
            Apply padding
            """
            return (text + (block_size - len(text) % block_size) *
                    chr(block_size - len(text) % block_size)).encode('utf-8')
        cipher = DES3.new(key, DES3.MODE_ECB)
        encrypted_text = cipher.encrypt(pad(pwd))
        return base64.b64encode(encrypted_text).decode('ascii')

    def _split_fullname(self, full_name):
        """
        Utility to break Full Name to first and last name
        """
        first_name = ''
        last_name = ''
        name_elements = full_name.split(' ')
        first_name = name_elements[0]
        if len(name_elements) > 1:
            last_name = ' '.join(name_elements[1:])

        return (first_name, last_name)

    def _get_payload(self, exam, context):
        """
        Constructs the data payload that Software Secure expects
        """

        attempt_code = context['attempt_code']
        time_limit_mins = context['time_limit_mins']
        is_sample_attempt = context['is_sample_attempt']
        full_name = context['full_name']
        review_policy = context.get('review_policy', constants.DEFAULT_SOFTWARE_SECURE_REVIEW_POLICY)
        review_policy_exception = context.get('review_policy_exception')
        scheme = 'https' if getattr(settings, 'HTTPS', 'on') == 'on' else 'http'
        path = reverse(
            'edx_proctoring:anonymous.proctoring_launch_callback.start_exam',
            args=[attempt_code]
        )
        callback_url = f'{scheme}://{settings.SITE_NAME}{path}'

        # compile the notes to the reviewer
        # this is a combination of the Exam Policy which is for all students
        # combined with any exceptions granted to the particular student
        reviewer_notes = review_policy
        if review_policy_exception:
            reviewer_notes = f'{reviewer_notes}; {review_policy_exception}'

        (first_name, last_name) = self._split_fullname(full_name)

        now = datetime.datetime.utcnow()
        start_time_str = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
        end_time_str = (now + datetime.timedelta(minutes=time_limit_mins)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        # remove all illegal characters from the exam name
        exam_name = exam['exam_name']
        exam_name = unicodedata.normalize('NFKD', exam_name).encode('ascii', 'ignore').decode('utf8')

        for character in SOFTWARE_SECURE_INVALID_CHARS:
            exam_name = exam_name.replace(character, '_')

        # if exam_name is blank because we can't normalize a potential unicode (like Chinese) exam name
        # into something ascii-like, then we have use a default otherwise
        # SoftwareSecure will fail on the exam registration API call
        if not exam_name:
            exam_name = 'Proctored Exam'

        org_extra = {
            "examStartDate": start_time_str,
            "examEndDate": end_time_str,
            "noOfStudents": 1,
            "examID": exam['id'],
            "courseID": exam['course_id'],
            "firstName": first_name,
            "lastName": last_name
        }
        if self.send_email:
            org_extra["email"] = context['email']

        return {
            "examCode": attempt_code,
            "organization": self.organization,
            "duration": time_limit_mins,
            "reviewedExam": not is_sample_attempt,
            # NOTE: we will have to allow these notes to be authorable in Studio
            # and then we will pull this from the exam database model
            "reviewerNotes": reviewer_notes,
            "examPassword": self._encrypt_password(self.crypto_key, attempt_code),
            "examSponsor": self.exam_sponsor,
            "examName": exam_name,
            "ssiProduct": 'rp-now',
            # need to pass in a URL to the LMS?
            "examUrl": callback_url,
            "orgExtra": org_extra
        }

    def _header_string(self, headers, date):
        """
        Composes the HTTP header string that SoftwareSecure expects
        """
        # Headers
        string = ""
        if 'Content-Type' in headers:
            string += headers.get('Content-Type')
            string += '\n'

        if date:
            string += date
            string += '\n'

        return string.encode('utf8')

    def _body_string(self, body_json, prefix=b""):
        """
        Serializes out the HTTP body that SoftwareSecure expects
        """
        keys = list(body_json.keys())
        keys.sort()
        string = b""
        for key in keys:
            value = body_json[key]
            if isinstance(value, bool):
                if value:
                    value = 'true'
                else:
                    value = 'false'
            key = key.encode('utf8')
            if isinstance(value, (list, tuple)):
                for idx, arr in enumerate(value):
                    pfx = b'%s.%d' % (key, idx)
                    if isinstance(arr, dict):
                        string += self._body_string(arr, pfx + b'.')
                    else:
                        string += b'%s:%s\n' % (pfx, str(arr).encode('utf8'))
            elif isinstance(value, dict):
                string += self._body_string(value, key + b'.')
            else:
                if value != "" and not value:
                    value = "null"
                string += b'%s%s:%s\n' % (prefix, key, str(value).encode('utf8'))

        return string

    def _sign_doc(self, body_json, method, headers, date):
        """
        Digitaly signs the datapayload that SoftwareSecure expects
        """
        body_str = self._body_string(body_json)

        method_string = method.encode('ascii') + b'\n\n'

        headers_str = self._header_string(headers, date)
        message = method_string + headers_str + body_str

        log_msg = (
            f"About to send payload to SoftwareSecure: examCode={body_json.get('examCode')}, "
            f"courseID={body_json.get('orgExtra').get('courseID')}"
        )
        log.info(log_msg)

        hashed = hmac.new(self.secret_key.encode('ascii'), message, sha256)
        computed = binascii.b2a_base64(hashed.digest()).rstrip(b'\n')

        return b'SSI %s:%s' % (self.secret_key_id.encode('ascii'), computed)

    def _send_request_to_ssi(self, data, sig, date):
        """
        Performs the webservice call to SoftwareSecure
        """
        response = requests.post(
            self.exam_register_endpoint,
            headers={
                'Content-Type': 'application/json',
                "Authorization": sig,
                "Date": date
            },
            data=json.dumps(data),
            timeout=self.timeout
        )

        return response.status_code, response.text

    def should_block_access_to_exam_material(self):
        """
        Whether learner access to exam content should be blocked during the exam

        Blocks learners from viewing exam course content from a
        browser other than PSI's secure browser
        """
        req = get_current_request()
        # pylint: disable=illegal-waffle-usage
        return not req.get_signed_cookie('exam', default=False)

    def get_proctoring_config(self):
        """
        Returns the metadata and configuration options for the proctoring service
        """
        proctoring_config = {
            'download_url': self.get_software_download_url(),
            'name': self.verbose_name,
            'rules': {},
            'instructions': []
        }
        return proctoring_config

    def get_video_review_aes_key(self):
        """
        Returns the aes key used to encrypt the video review url
        """
        return self.video_review_aes_key

    def get_instructor_url(
        self, course_id, user, exam_id=None, attempt_id=None,
        show_configuration_dashboard=False, encrypted_video_review_url=None
    ):
        """
        Returns the url for video reviews
        """
        # video_review_url is required for PSI backend
        if not encrypted_video_review_url:
            return None

        try:
            aes_key = codecs.decode(self.video_review_aes_key, "hex")
            decrypted_video_url = decode_and_decrypt(encrypted_video_review_url, aes_key).decode("utf-8")

            # reformat video url as per MST-871 findings
            reformatted_url = decrypted_video_url.replace('DirectLink-Generic', 'DirectLink-HTML5')
            return reformatted_url
        except Exception as err:  # pylint: disable=broad-except
            log.exception(
                'Could not decrypt video url for attempt_id=%(attempt_id)s '
                'due to the following error: %(error_string)s',
                {'attempt_id': attempt_id, 'error_string': str(err)}
            )
            return None
