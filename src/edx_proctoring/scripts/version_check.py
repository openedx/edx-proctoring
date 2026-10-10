#!/usr/bin/env python
"""
Scripts to ensure that the Python and npm versions match.
"""
import json
import sys

from edx_proctoring import __version__ as python_version

# When running on a PR branch without the release tag, setuptools-scm returns
# a dev version (e.g. "0.0.0.dev0"). Skip the check in that case — there is
# nothing to validate until the release tag is reachable.
if python_version.endswith('.dev0') or '.dev' in python_version:
    print(f"Version check skipped (dev version detected: {python_version}).")
    sys.exit(0)

with open('package.json') as json_file:
    data = json.load(json_file)
    if data['version'] != python_version:
        print("\n\n\n")
        print("ERROR: Version mismatch. Please update version in edx_proctoring/__init__.py or edx_proctoring/package.json.\n")  # noqa E501 line too long
        sys.exit(1)
    else:
        print("Version check success!")
