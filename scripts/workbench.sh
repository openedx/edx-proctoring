#!/usr/bin/env bash


cd `dirname $BASH_SOURCE` && cd ..

# Install dependencies
make install-python
make install-js
make javascript

# Configure Django settings
export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-"settings"}

# Create the database
echo "Updating the database..."
python manage.py syncdb

echo "Starting server..."
python manage.py runserver_plus "${@:1}"