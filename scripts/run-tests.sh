#!/usr/bin/env bash

echo 'Beginning Test Run...'
echo ''
echo 'Removing *.pyc files'
find . -name "*.pyc" -exec rm -rf {} \;

echo 'Running test suite'
coverage run manage.py test edx_proctoring --verbosity=3
coverage report -m
coverage html
pep8 edx_proctoring
pylint edx_proctoring --report=no
echo ''
echo 'View the full coverage report at {CODE_PATH}/edx-proctoring/htmlcov/index.html'
echo ''
echo 'Testing Complete!'