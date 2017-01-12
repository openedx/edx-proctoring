#!/usr/bin/env bash

###################################################################
#
#   Extract i18n strings and push them to Transifex.
#
#   You will need to configure your Transifex credentials as
#   described here:
#
#       http://docs.transifex.com/developer/client/setup
#
#   You also need to install gettext:
#
#       https://www.gnu.org/software/gettext/
#
#   Usage:
#
#       ./i18n-push.sh
#
##################################################################

cd `dirname $BASH_SOURCE` && cd ..

# Note we only extract the English language strings so they can be
# sent to Transifex. All other language strings will be pulled
# down from Transifex and so don't need to be generated.

echo "Extracting i18n strings..."
django-admin.py makemessages --locale=en --ignore="edx-proctoring/*" --ignore="build/*" --ignore="node_modules/*"

echo "Extracting client-side i18n strings..."
django-admin.py makemessages --locale=en --ignore="edx-proctoring/*" --ignore="build/*" --ignore="node_modules/*" -d djangojs

echo "Generating dummy strings..."
i18n_tool dummy

read -p "Push strings to Transifex? [y/n]  " RESP
if [ "$RESP" = "y" ]; then
    i18n_tool transifex push
    echo " == Pushed strings to Transifex"
else
    echo "Cancelled"
fi