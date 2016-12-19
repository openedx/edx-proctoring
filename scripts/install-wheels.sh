#!/usr/bin/env bash

cd `dirname $BASH_SOURCE` && cd ..

# Install "wheel" archives of the requirements for running the test suite.
# http://pip.readthedocs.org/en/latest/reference/pip_wheel.html
# This runs in Travis to install pre-built binary packages, which
# means the builds are faster and more reliable.
sudo pip install --upgrade pip
sudo pip install wheel

WHEELS_ARGS=""  # Get wheels from the internet by default

#if [ "$(expr substr $(uname -s) 1 5)" == "Linux" ]; then
#  # Use local wheels for faster TravisCI and Vagrant installs.
#  WHEELS_ARGS="--no-index --find-links=scripts/data/wheelhouse"
#fi

# Ensure that numpy is installed first; otherwise scipy won't be able to install
pip install --use-wheel --upgrade $WHEELS_ARGS numpy

# Then install everything else
pip install --use-wheel --upgrade $WHEELS_ARGS -r wheels.txt
