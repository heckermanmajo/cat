#!/bin/bash

# todo: also upload the catknows-executables
# THIS file is intended to ONLY work on MY - majos - machine
# since YOU are not allowed to deploy to the catbrain production server - LOL
SCRIPT_PATH=$(realpath "$0")
SCRIPT_DIR=$(dirname "$SCRIPT_PATH")
ZIP_FILE_UPLOAD_PATH="/www/htdocs/w016728f/cat-knows.com/"
SSH_SERVER_ADDRESS="ssh-w016728f@w016728f.kasserver.com"

cd "$SCRIPT_DIR/../webserver/" && zip -r "$SCRIPT_DIR/../web.zip" ./* -x "*.md" "*excalidraw*"
scp "$SCRIPT_DIR/../web.zip" "$SSH_SERVER_ADDRESS:$ZIP_FILE_UPLOAD_PATH"
ssh "$SSH_SERVER_ADDRESS" "cd $ZIP_FILE_UPLOAD_PATH && unzip -o web.zip && rm web.zip"
rm $SCRIPT_DIR/../web.zip