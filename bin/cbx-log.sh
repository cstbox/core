#!/bin/bash

# This file is part of CSTBox.
#
# CSTBox is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# CSTBox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with CSTBox.  If not, see <http://www.gnu.org/licenses/>.

LOG_DIR="/var/log/cstbox"

if [ -z "$PAGER" ] ; then
    if (which most > /dev/null); then
        PAGER='most'
    else
        PAGER='more'
    fi
fi

if [ -n "$1" ] ; then
    if [[ "$1" == "cstbox-"* ]] ; then 
        log_file="$LOG_DIR/$1"
    else
        log_file="$LOG_DIR/cstbox-$1"
    fi
    if [[ "$log_file" != "*.log" ]] ; then 
        log_file="${log_file}.log"
    fi

    if [ -e "$log_file" ]; then
        $PAGER $log_file
    else
        echo "[ERROR] CSTBox log file '$1' ($log_file) does not exist"
        exit 1
    fi

else
    echo "Available log files:"
    for f in $(ls $LOG_DIR/cstbox-*); do
        bn=$(basename $f)
        ln=${bn/cstbox-/}
        echo "- ${ln/.log/} ($f)"
    done
fi
