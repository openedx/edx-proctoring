"""
Some canned data for SoftwareSecure callback testing.
"""

import json

MOCK_EXAM_ID = "4d07a01a-1502-422e-b943-93ac04dc6ced"


def create_test_review_payload(exam_id=MOCK_EXAM_ID, attempt_code=None, external_id=None, review_status="Clean"):
    """
    Returns a test payload for reviews.
    """
    return json.dumps({
        "examDate": "Jul 15 2015  1:13AM",
        "examProcessingStatus": "Review Completed",
        "examTakerEmail": "4d07a01a-1502-422e-b943-93ac04dc6ced",
        "examTakerFirstName": "John",
        "examTakerLastName": "Doe",
        "keySetVersion": "",
        "examApiData": {
            "duration": 1,
            "examCode": "4d07a01a-1502-422e-b943-93ac04dc6ced",
            "examName": "edX Exams",
            "examPassword": "hQxvA8iUKKlsqKt0fQVBaXqmAziGug4NfxUChg94eGacYDcFwaIyBA==",
            "examSponsor": "edx LMS",
            "examUrl": "http://localhost:8000/api/edx_proctoring/proctoring_launch_callback/start_exam/" + exam_id,
            "orgExtra": {
                "courseID": "edX/DemoX/Demo_Course",
                "examEndDate": "Wed, 15 Jul 2015 05:11:31 GMT",
                "examID": exam_id,
                "examStartDate": "Wed, 15 Jul 2015 05:10:31 GMT",
                "noOfStudents": 1
            },
            "organization": "edx",
            "reviewedExam": True,
            "reviewerNotes": "Closed Book",
            "ssiProduct": "rp-now"
        },
        "overAllComments": ";Candidates should always wear suit and tie for exams.",
        "reviewStatus": review_status,
        "userPhotoBase64String": "",
        "videoReviewLink": "http://www.remoteproctor.com/AdminSite/Account/Reviewer/DirectLink-Generic.aspx?ID=foo",
        "examMetaData": {
            "examCode": attempt_code,
            "examName": "edX Exams",
            "examSponsor": "edx LMS",
            "organization": "edx",
            "reviewedExam": "True",
            "reviewerNotes": "Closed Book",
            "simulatedExam": "False",
            "ssiExamToken": "4E44F7AA-275D-4741-B531-73AE2407ECFB",
            "ssiProduct": "rp-now",
            "ssiRecordLocator": external_id
        },
        "desktopComments": [
            {
                "comments": "Browsing other websites",
                "duration": 88,
                "eventFinish": 88,
                "eventStart": 12,
                "eventStatus": "Suspicious"
            },
            {
                "comments": "Browsing local computer",
                "duration": 88,
                "eventFinish": 88,
                "eventStart": 15,
                "eventStatus": "Rules Violation"
            },
            {
                "comments": "Student never entered the exam.",
                "duration": 88,
                "eventFinish": 88,
                "eventStart": 87,
                "eventStatus": "Clean"
            }
        ],
        "webCamComments": [
            {
                "comments": "Photo ID not provided",
                "duration": 796,
                "eventFinish": 796,
                "eventStart": 0,
                "eventStatus": "Suspicious"
            },
            {
                "comments": "Exam environment not confirmed",
                "duration": 796,
                "eventFinish": 796,
                "eventStart": 10,
                "eventStatus": "Rules Violation"
            },
            {
                "comments": "Looking away from computer",
                "duration": 796,
                "eventFinish": 796,
                "eventStart": 107,
                "eventStatus": "Rules Violation"
            }
        ]
    })
