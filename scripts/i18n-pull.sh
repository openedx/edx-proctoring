
#!/usr/bin/env bash

###################################################################
#
#   Pull i18n strings from Transifex.
#
#   You will need to configure your Transifex credentials as
#   described here:
#
#       http://docs.transifex.com/developer/client/setup
#
#   Usage:
#
#       ./i18n-pull.sh
#
##################################################################


cd `dirname $BASH_SOURCE` && cd ..

echo "Pulling strings from Transifex..."
i18n_tool transifex pull

echo "Validating strings..."
i18n_tool validate

echo "Compiling strings..."
read -p "Compile strings? [y/n]   " RESP
if [ "$RESP" = "y" ]; then
    python manage.py compilemessages
else
    echo "Cancelled"
fi