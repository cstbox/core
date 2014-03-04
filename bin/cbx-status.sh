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

PIDFILES_DIR=/var/run/cstbox

pidfiles=$(ls $PIDFILES_DIR/cstbox-*.pid 2> /dev/null)
if [ -n "$pidfiles" ] ; then
    echo "Currently running CSTBox services:"
    for f in $pidfiles ; do 
        svc=$(echo $(basename $f) | cut -d. -f1)
        read pid < $f
        echo "- $svc [$pid]"
    done
    rc=0
else
    echo "No CSTBox service is currently running."
    rc=2
fi
exit $rc
