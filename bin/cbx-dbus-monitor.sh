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

# CSTBox dedicated DBus traffic monitor

die() {
    echo "[ERROR] $@"
    exit 1
}

DBUS_VARS_FILE="/var/run/cstbox/cstbox-dbus"

if [ -e "$DBUS_VARS_FILE" ] ; then
    . $DBUS_VARS_FILE
    echo "[INFO] monitoring CSTBox private session bus at address $DBUS_SESSION_BUS_ADDRESS"
    echo
    [[ $EUID -eq 0 ]] || die "must use sudo or be root to run this command in this context"
    selector="--address $DBUS_SESSION_BUS_ADDRESS" 
else
    echo "[WARNING] using default session bus"
    selector="--session"
fi

dbus-monitor \
    $selector \
    "interface='fr.cstb.cstbox.ConfigurationBroker'" \
    "interface='fr.cstb.cstbox.EventManager'" \
#    | grep fr.cstb.cstbox

