#!/usr/bin/env python
"""
Scripts to ensure that the Python and npm versions match.
"""
import json
import sys

from edx_proctoring import __version__ as python_version

with open('package.json') as json_file:
    data = json.load(json_file)
    if data['version'] != python_version:
        print("\n\n\n")
        print("ERROR: Version mismatch. Please update version in edx_proctoring/__init__.py or edx_proctoring/package.json.\n")  # noqa E501 line too long
        sys.exit(1)
    else:
        print("Version check success!")
