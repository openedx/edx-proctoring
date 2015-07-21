"""
Integration with Software Secure's proctoring system
"""

from Crypto.Cipher import DES3
import base64
from hashlib import sha256
import requests
import hmac
import binascii
import datetime
import json
import logging

from edx_proctoring.backends.backend import ProctoringBackendProvider
from edx_proctoring.exceptions import (
    BackendProvideCannotRegisterAttempt,
    StudentExamAttemptDoesNotExistsException,
    ProctoredExamSuspiciousLookup,
    ProctoredExamReviewAlreadyExists,
)

from edx_proctoring. models import (
    ProctoredExamSoftwareSecureReview,
    ProctoredExamSoftwareSecureComment,
    ProctoredExamStudentAttempt,
    ProctoredExamStudentAttemptHistory
)

log = logging.getLogger(__name__)


class SoftwareSecureBackendProvider(ProctoringBackendProvider):
    """
    Implementation of the ProctoringBackendProvider for Software Secure's
    RPNow product
    """

    def __init__(self, organization, exam_sponsor, exam_register_endpoint,
                 secret_key_id, secret_key, crypto_key, software_download_url):
        """
        Class initializer
        """

        self.organization = organization
        self.exam_sponsor = exam_sponsor
        self.exam_register_endpoint = exam_register_endpoint
        self.secret_key_id = secret_key_id
        self.secret_key = secret_key
        self.crypto_key = crypto_key
        self.timeout = 10
        self.software_download_url = software_download_url

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
                'Could not register attempt_code = {attempt_code}. '
                'HTTP Status code was {status_code} and response was {response}.'.format(
                    attempt_code=attempt_code,
                    status_code=status,
                    response=response
                )
            )
            raise BackendProvideCannotRegisterAttempt(err_msg)

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

    def get_software_download_url(self):
        """
        Returns the URL that the user needs to go to in order to download
        the corresponding desktop software
        """
        return self.software_download_url

    def on_review_callback(self, payload):
        """
        Called when the reviewing 3rd party service posts back the results

        Documentation on the data format can be found from SoftwareSecure's
        documentation named "Reviewer Data Transfer"
        """

        log_msg = (
            'Received callback from SoftwareSecure with review data: {payload}'.format(
                payload=payload
            )
        )
        log.info(log_msg)

        # payload from SoftwareSecure is a JSON payload
        # which has been converted to a dict by our caller
        data = payload['payload']

        # what we consider the external_id is SoftwareSecure's 'ssiRecordLocator'
        external_id = data['examMetaData']['ssiRecordLocator']

        # what we consider the attempt_code is SoftwareSecure's 'examCode'
        attempt_code = data['examMetaData']['examCode']

        # do a lookup on the attempt by examCode, and compare the
        # passed in ssiRecordLocator and make sure it matches
        # what we recorded as the external_id. We need to look in both
        # the attempt table as well as the archive table

        attempt_obj = ProctoredExamStudentAttempt.objects.get_exam_attempt_by_code(attempt_code)

        if not attempt_obj:
            # try archive table
            attempt_obj = ProctoredExamStudentAttemptHistory.get_exam_attempt_by_code(attempt_code)

            if not attempt_obj:
                # still can't find, error out
                err_msg = (
                    'Could not locate attempt_code: {attempt_code}'.format(attempt_code=attempt_code)
                )
                raise StudentExamAttemptDoesNotExistsException(err_msg)

        # then make sure we have the right external_id
        if attempt_obj.external_id != external_id:
            err_msg = (
                'Found attempt_code {attempt_code}, but the recorded external_id did not '
                'match the ssiRecordLocator that had been recorded previously. Has {existing} '
                'but received {received}!'.format(
                    attempt_code=attempt_code,
                    existing=attempt_obj.external_id,
                    received=external_id
                )
            )
            raise ProctoredExamSuspiciousLookup(err_msg)

        # do we already have a review for this attempt?!? It should not be updated!
        review = ProctoredExamSoftwareSecureReview.get_review_by_attempt_code(attempt_code)

        if review:
            err_msg = (
                'We already have a review submitted from SoftwareSecure regarding '
                'attempt_code {attempt_code}. We do not allow for updates!'.format(
                    attempt_code=attempt_code
                )
            )
            raise ProctoredExamReviewAlreadyExists(err_msg)

        # do some limited parsing of the JSON payload
        review_status = data['reviewStatus']
        video_review_link = data['videoReviewLink']

        # make a new record in the review table
        review = ProctoredExamSoftwareSecureReview(
            attempt_code=attempt_code,
            raw_data=json.dumps(payload),
            review_status=review_status,
            video_url=video_review_link,
        )
        review.save()

        # go through and populate all of the specific comments
        for comment in data['webCamComments']:
            self._save_review_comment(review, comment)

        for comment in data['desktopComments']:
            self._save_review_comment(review, comment)

    def _save_review_comment(self, review, comment):
        """
        Helper method to save a review comment
        """
        comment = ProctoredExamSoftwareSecureComment(
            review=review,
            start_time=comment['eventStart'],
            stop_time=comment['eventFinish'],
            duration=comment['duration'],
            comment=comment['comments'],
            status=comment['eventStatus']
        )
        comment.save()

    def _encrypt_password(self, key, pwd):
        """
        Encrypt the exam passwork with the given key
        """
        block_size = DES3.block_size

        def pad(text):
            """
            Apply padding
            """
            return text + (block_size - len(text) % block_size) * chr(block_size - len(text) % block_size)
        cipher = DES3.new(key, DES3.MODE_ECB)
        encrypted_text = cipher.encrypt(pad(pwd))
        return base64.b64encode(encrypted_text)

    def _get_payload(self, exam, context):
        """
        Constructs the data payload that Software Secure expects
        """

        attempt_code = context['attempt_code']
        time_limit_mins = context['time_limit_mins']
        is_sample_attempt = context['is_sample_attempt']
        callback_url = context['callback_url']
        full_name = context['full_name']
        first_name = ''
        last_name = ''

        if full_name:
            name_elements = full_name.split(' ')
            first_name = name_elements[0]
            if len(name_elements) > 1:
                last_name = ' '.join(name_elements[1:])

        now = datetime.datetime.utcnow()
        start_time_str = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
        end_time_str = (now + datetime.timedelta(minutes=time_limit_mins)).strftime("%a, %d %b %Y %H:%M:%S GMT")
        return {
            "examCode": attempt_code,
            "organization": self.organization,
            "duration": time_limit_mins,
            "reviewedExam": not is_sample_attempt,
            "reviewerNotes": 'Closed Book',
            "examPassword": self._encrypt_password(self.crypto_key, attempt_code),
            "examSponsor": self.exam_sponsor,
            "examName": exam['exam_name'],
            "ssiProduct": 'rp-now',
            # need to pass in a URL to the LMS?
            "examUrl": callback_url,
            "orgExtra": {
                "examStartDate": start_time_str,
                "examEndDate": end_time_str,
                "noOfStudents": 1,
                "examID": exam['id'],
                "courseID": exam['course_id'],
                "firstName": first_name,
                "lastName": last_name,
            }
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

        return string

    def _body_string(self, body_json, prefix=""):
        """
        Serializes out the HTTP body that SoftwareSecure expects
        """
        keys = body_json.keys()
        keys.sort()
        string = ""
        for key in keys:
            value = body_json[key]
            if str(value) == 'True':
                value = 'true'
            if str(value) == 'False':
                value = 'false'
            if isinstance(value, (list, tuple)):
                for idx, arr in enumerate(value):
                    if isinstance(arr, dict):
                        string += self._body_string(arr, key + '.' + str(idx) + '.')
                    else:
                        string += key + '.' + str(idx) + ':' + arr + '\n'
            elif isinstance(value, dict):
                string += self._body_string(value, key + '.')
            else:
                if value != "" and not value:
                    value = "null"
                string += str(prefix) + str(key) + ":" + str(value).encode('utf-8') + '\n'

        return string

    def _sign_doc(self, body_json, method, headers, date):
        """
        Digitaly signs the datapayload that SoftwareSecure expects
        """
        body_str = self._body_string(body_json)

        method_string = method + '\n\n'

        headers_str = self._header_string(headers, date)
        message = method_string + headers_str + body_str

        # HMAC requires a string not a unicode
        message = str(message)

        log_msg = (
            'About to send payload to SoftwareSecure:\n{message}'.format(message=message)
        )
        log.info(log_msg)

        hashed = hmac.new(str(self.secret_key), str(message), sha256)
        computed = binascii.b2a_base64(hashed.digest()).rstrip('\n')

        return 'SSI ' + self.secret_key_id + ':' + computed

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
