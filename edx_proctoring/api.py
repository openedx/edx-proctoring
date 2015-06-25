# pylint: disable=unused-argument

# remove pylint rule after we implement each method

"""
In-Proc API (aka Library) for the edx_proctoring subsystem. This is not to be confused with a HTTP REST
API which is in the views.py file, per edX coding standards
"""


def create_exam(course_id, content_id, exam_name, time_limit_mins,
                is_proctored=True, external_id=None, is_active=True):
    """
    Creates a new ProctoredExam entity, if the course_id/content_id pair do not already exist.
    If that pair already exists, then raise exception.

    Returns: id (PK)
    """


def update_exam(exam_id, exam_name=None, time_limit_mins=None,
                is_proctored=None, external_id=None, is_active=None):
    """
    Given a Django ORM id, update the existing record, otherwise raise exception if not found.
    If an argument is not passed in, then do not change it's current value.

    Returns: id
    """


def get_exam_by_id(exam_id):
    """
    Looks up exam by the Primary Key. Raises exception if not found.

    Returns dictionary version of the Django ORM object
    """


def get_exam_by_content_id(course_id, content_id):
    """
    Looks up exam by the course_id/content_id pair. Raises exception if not found.

    Returns dictionary version of the Django ORM object
    """


def add_allowance_for_user(exam_id, user_id, key, value):
    """
    Adds (or updates) an allowance for a user within a given exam
    """


def remove_allowance_for_user(exam_id, user_id, key):
    """
    Deletes an allowance for a user within a given exam.
    """


def start_exam_attempt(exam_id, user_id, external_id):
    """
    Signals the beginning of an exam attempt for a given
    exam_id. If one already exists, then an exception should be thrown.

    Returns: exam_attempt_id (PK)
    """


def stop_exam_attempt(exam_id, user):
    """
    Marks the exam attempt as completed (sets the completed_at field and updates the record)
    """


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
