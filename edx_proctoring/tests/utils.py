"""
Subclasses Django test client to allow for easy login
"""

from importlib import import_module

from django.conf import settings
from django.contrib.auth import login
from django.http import HttpRequest
from django.test.client import Client
from django.test import TestCase
from django.contrib.auth.models import User


class TestClient(Client):
    """
    Allows for 'fake logins' of a user so we don't need to expose a 'login' HTTP endpoint
    """
    def login_user(self, user):
        """
        Login as specified user, does not depend on auth backend (hopefully)

        This is based on Client.login() with a small hack that does not
        require the call to authenticate()
        """
        if 'django.contrib.sessions' not in settings.INSTALLED_APPS:
            raise AssertionError("Unable to login without django.contrib.sessions in INSTALLED_APPS")
        user.backend = "django.contrib.auth.backends.ModelBackend"
        engine = import_module(settings.SESSION_ENGINE)

        # Create a fake request to store login details.
        request = HttpRequest()

        request.session = engine.SessionStore()
        login(request, user)

        # Set the cookie to represent the session.
        session_cookie = settings.SESSION_COOKIE_NAME
        self.cookies[session_cookie] = request.session.session_key
        cookie_data = {
            'max-age': None,
            'path': '/',
            'domain': settings.SESSION_COOKIE_DOMAIN,
            'secure': settings.SESSION_COOKIE_SECURE or None,
            'expires': None,
        }
        self.cookies[session_cookie].update(cookie_data)

        # Save the session values.
        request.session.save()


class LoggedInTestCase(TestCase):
    """
    All tests for the views.py
    """

    def setUp(self):
        """
        Setup for tests
        """

        self.client = TestClient()
        self.user = User(username='tester', email='tester@test.com')
        self.user.save()
        self.client.login_user(self.user)


def get_provider_name_test(*args, **kwargs):
    return "TEST"


def get_provider_name_software_secure(*args, **kwargs):
    return "SOFTWARE_SECURE"


class MockedCourseKey(object):
    def __new__(self, course_key):
        pass

class MockedCourse(object):
    def __init__(self, course_key):
        self.course_key = course_key
        self.available_proctoring_services = "a,b"
        self.proctoring_service = "a"

class MockedModulestore(object):
    def get_course(self, course_key):
        return MockedCourse(course_key)

    def update_item(self,course,user_id):
        pass
