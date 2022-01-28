#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pylint: disable=C0111,W6005,W6100


import os
import re
import sys

from setuptools import setup


def get_version(*file_paths):
    """
    Extract the version string from the file at the given relative path fragments.
    """
    filename = os.path.join(os.path.dirname(__file__), *file_paths)
    version_file = open(filename).read()
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError('Unable to find version string.')


VERSION = get_version('edx_proctoring', '__init__.py')

if sys.argv[-1] == 'tag':
    print("Tagging the version on github:")
    os.system("git tag -a %s -m 'version %s'" % (VERSION, VERSION))
    os.system("git push --tags")
    sys.exit()

README = open(os.path.join(os.path.dirname(__file__), 'README.rst')).read()
CHANGELOG = open(os.path.join(os.path.dirname(__file__), 'CHANGELOG.rst')).read()


def load_requirements(*requirements_paths):
    """
    Load all requirements from the specified requirements files.
    Returns a list of requirement strings.
    """
    requirements = set()
    for path in requirements_paths:
        requirements.update(
            line.split('#')[0].strip() for line in open(path).readlines()
            if is_requirement(line.strip())
        )
    return list(requirements)


def is_requirement(line):
    """
    Return True if the requirement line is a package requirement;
    that is, it is not blank, a comment, a URL, or an included file.
    """
    return not (line == '' or line.startswith(('-r', '#', '-e', 'git+', '-c')))


setup(
    name='edx-proctoring',
    version=VERSION,
    description='Proctoring subsystem for Open edX',
    long_description=README + '\n\n' + CHANGELOG,
    author='edX',
    author_email='oscm@edx.org',
    url='https://github.com/edx/edx-proctoring',
    license="AGPL 3.0",
    zip_safe=False,
    keywords='Django edx',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Django',
        'Framework :: Django :: 3.2',
        'Framework :: Django :: 4.0',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.8',
    ],
    packages=[
        'edx_proctoring',
    ],
    include_package_data=True,
    install_requires=load_requirements("requirements/base.in"),
    entry_points={
        'openedx.proctoring': [
            'mock = edx_proctoring.backends.mock:MockProctoringBackendProvider',
            'null = edx_proctoring.backends.null:NullBackendProvider',
            'software_secure = edx_proctoring.backends.software_secure:SoftwareSecureBackendProvider',
            'rpnow4 = edx_proctoring.backends.software_secure:SoftwareSecureBackendProvider',
        ],
        'lms.djangoapp': [
            "edx_proctoring = edx_proctoring.apps:EdxProctoringConfig",
        ],
        'cms.djangoapp': [
            "edx_proctoring = edx_proctoring.apps:EdxProctoringConfig",
        ],

    },
)
