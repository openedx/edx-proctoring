# pylint: disable=unused-argument

# remove pylint rule after we implement each method

"""
In-Proc API (aka Library) for the edx_proctoring subsystem. This is not to be confused with a HTTP REST
API which is in the views.py file, per edX coding standards
"""
import pytz
from datetime import datetime
from edx_proctoring.exceptions import (
    ProctoredExamAlreadyExists, ProctoredExamNotFoundException, StudentExamAttemptAlreadyExistsException,
    StudentExamAttemptDoesNotExistsException)
from edx_proctoring.models import (
    ProctoredExam, ProctoredExamStudentAllowance, ProctoredExamStudentAttempt
)
from edx_proctoring.serializers import ProctoredExamSerializer


def create_exam(course_id, content_id, exam_name, time_limit_mins,
                is_proctored=True, external_id=None, is_active=True):
    """
    Creates a new ProctoredExam entity, if the course_id/content_id pair do not already exist.
    If that pair already exists, then raise exception.

    Returns: id (PK)
    """
    if ProctoredExam.get_exam_by_content_id(course_id, content_id) is not None:
        raise ProctoredExamAlreadyExists

    proctored_exam = ProctoredExam.objects.create(
        course_id=course_id,
        content_id=content_id,
        external_id=external_id,
        exam_name=exam_name,
        time_limit_mins=time_limit_mins,
        is_proctored=is_proctored,
        is_active=is_active
    )
    return proctored_exam.id


def update_exam(exam_id, exam_name=None, time_limit_mins=None,
                is_proctored=None, external_id=None, is_active=None):
    """
    Given a Django ORM id, update the existing record, otherwise raise exception if not found.
    If an argument is not passed in, then do not change it's current value.

    Returns: id
    """
    proctored_exam = ProctoredExam.get_exam_by_id(exam_id)
    if proctored_exam is None:
        raise ProctoredExamNotFoundException

    if exam_name is not None:
        proctored_exam.exam_name = exam_name
    if time_limit_mins is not None:
        proctored_exam.time_limit_mins = time_limit_mins
    if is_proctored is not None:
        proctored_exam.is_proctored = is_proctored
    if external_id is not None:
        proctored_exam.external_id = external_id
    if is_active is not None:
        proctored_exam.is_active = is_active
    proctored_exam.save()
    return proctored_exam.id


def get_exam_by_id(exam_id):
    """
    Looks up exam by the Primary Key. Raises exception if not found.

    Returns dictionary version of the Django ORM object
    e.g.
    {
        "course_id": "edX/DemoX/Demo_Course",
        "content_id": "123",
        "external_id": "",
        "exam_name": "Midterm",
        "time_limit_mins": 90,
        "is_proctored": true,
        "is_active": true
    }
    """
    proctored_exam = ProctoredExam.get_exam_by_id(exam_id)
    if proctored_exam is None:
        raise ProctoredExamNotFoundException

    serialized_exam_object = ProctoredExamSerializer(proctored_exam)
    return serialized_exam_object.data


def get_exam_by_content_id(course_id, content_id):
    """
    Looks up exam by the course_id/content_id pair. Raises exception if not found.

    Returns dictionary version of the Django ORM object
    e.g.
    {
        "course_id": "edX/DemoX/Demo_Course",
        "content_id": "123",
        "external_id": "",
        "exam_name": "Midterm",
        "time_limit_mins": 90,
        "is_proctored": true,
        "is_active": true
    }
    """
    proctored_exam = ProctoredExam.get_exam_by_content_id(course_id, content_id)
    if proctored_exam is None:
        raise ProctoredExamNotFoundException

    serialized_exam_object = ProctoredExamSerializer(proctored_exam)
    return serialized_exam_object.data


def add_allowance_for_user(exam_id, user_id, key, value):
    """
    Adds (or updates) an allowance for a user within a given exam
    """
    ProctoredExamStudentAllowance.add_allowance_for_user(exam_id, user_id, key, value)


def remove_allowance_for_user(exam_id, user_id, key):
    """
    Deletes an allowance for a user within a given exam.
    """
    student_allowance = ProctoredExamStudentAllowance.get_allowance_for_user(exam_id, user_id, key)
    if student_allowance is not None:
        student_allowance.delete()


def start_exam_attempt(exam_id, user_id, external_id):
    """
    Signals the beginning of an exam attempt for a given
    exam_id. If one already exists, then an exception should be thrown.

    Returns: exam_attempt_id (PK)
    """
    exam_attempt_obj = ProctoredExamStudentAttempt.start_exam_attempt(exam_id, user_id, external_id)
    if exam_attempt_obj is None:
        raise StudentExamAttemptAlreadyExistsException
    else:
        return exam_attempt_obj.id


def stop_exam_attempt(exam_id, user_id):
    """
    Marks the exam attempt as completed (sets the completed_at field and updates the record)
    """
    exam_attempt_obj = ProctoredExamStudentAttempt.get_student_exam_attempt(exam_id, user_id)
    if exam_attempt_obj is None:
        raise StudentExamAttemptDoesNotExistsException
    else:
        exam_attempt_obj.completed_at = datetime.now(pytz.UTC)
        exam_attempt_obj.save()
        return exam_attempt_obj.id


def get_active_exams_for_user(user_id, course_id=None):
    """
    This method will return a list of active exams for the user,
    i.e. started_at != None and completed_at == None. Theoretically there
    could be more than one, but in practice it will be one active exam.

    If course_id is set, then attempts only for an exam in that course_id
    should be returned.

    The return set should be a list of dictionary objects which are nested


    [{
        'exam': <exam fields as dict>,
        'attempt': <student attempt fields as dict>,
        'allowances': <student allowances as dict of key/value pairs
    }, {}, ...]

    """
