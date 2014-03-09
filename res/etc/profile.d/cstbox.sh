#!/bin/bash

CSTBOX_BIN=/opt/cstbox/bin

export PATH="$CSTBOX_BIN:$PATH"
echo "[CSTBox] $CSTBOX_BIN added to the search path."

. /etc/cstbox/setenv

