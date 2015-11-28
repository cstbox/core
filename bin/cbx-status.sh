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

PID_FILES_DIR=/var/run/cstbox
INIT_SCRIPTS_DIR=/etc/init.d

scripts=$(ls $INIT_SCRIPTS_DIR/cstbox-* 2> /dev/null)
pidfiles=$(ls $PID_FILES_DIR/cstbox-*.pid 2> /dev/null)
not_deamons="cstbox-cron"

if [ -n "$pidfiles" ] ; then
    echo -e "\x1b[1mCSTBox services running status:\x1b[0m"
    for script in $scripts; do
        svc=$(basename $script)
        if [ -n "${not_deamons##*$svc*}" ] ; then
            label="$svc                                    "
            label=${svc:0:25}
            pidfile=$PID_FILES_DIR/$svc.pid
            if [ -f $pidfile ] ; then
                read pid < $pidfile
                if ps $pid > /dev/null ; then
                    echo -e "- $label [\x1b[32mrunning\x1b[0m]"
                else
                    echo -e "- $label [\x1b[31mstopped\x1b[0m] (orphan PID file)"
                fi
            else
                echo -e "- $label [\x1b[31mstopped\x1b[0m]"
            fi
        fi
    done
    rc=0
else
    echo -e "\x1b[31mNo CSTBox service is currently running.\x1b[0m"
    rc=2
fi
exit $rc
