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

pidfiles=$(ls $PID_FILES_DIR/cstbox-*.pid 2> /dev/null)
for pifdile in $pifdiles; do
    read pid < $pidfile
    ps $pid > /dev/null || rm $pidfile
done
