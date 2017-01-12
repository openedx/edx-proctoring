#!/usr/bin/env bash

# Create "wheel" archives of the requirements for running the test suite.
# http://pip.readthedocs.org/en/latest/reference/pip_wheel.html
# Run this whenever you update requirements to speed up test jobs in Travis.
# Since the archives contain binary distributions, however,
# you MUST run the script within an Ubuntu 12.04 box.

cd `dirname $BASH_SOURCE` && cd ..

pip install --upgrade pip
pip install wheel

WHEELHOUSE="scripts/data/wheelhouse"
pip wheel --wheel-dir=$WHEELHOUSE -r wheels.txt