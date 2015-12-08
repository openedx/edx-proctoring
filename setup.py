#!/usr/bin/env python

from setuptools import setup, find_packages

def is_requirement(line):
    """
    Return True if the requirement line is a package requirement;
    that is, it is not blank, a comment, or editable.
    """
    # Remove whitespace at the start/end of the line
    line = line.strip()

    # Skip blank lines, comments, and editable installs
    return not (
        line == '' or
        line.startswith('-r') or
        line.startswith('#') or
        line.startswith('-e') or
        line.startswith('git+')
    )

def load_requirements(*requirements_paths):
    """
    Load all requirements from the specified requirements files.
    Returns a list of requirement strings.
    """
    requirements = set()
    for path in requirements_paths:
        requirements.update(
            line.strip() for line in open(path).readlines()
            if is_requirement(line)
        )
    return list(requirements)

setup(
    name='edx-proctoring',
    version='0.11.2',
    description='Proctoring subsystem for Open edX',
    long_description=open('README.md').read(),
    author='edX',
    url='https://github.com/edx/edx-proctoring',
    license='AGPL',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Framework :: Django',
    ],
    packages=find_packages(exclude=["tests"]),
    package_data={
        '': ['*.html', '*.underscore', '*.png', '*.js', '*swf']
    },
    dependency_links=[
    ],
    install_requires=load_requirements('requirements.txt'),
    tests_require=load_requirements('test_requirements.txt')
)
