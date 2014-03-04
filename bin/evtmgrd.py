#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

""" Event manager service daemon.

Starts an event manager as a service accessible on D-Bus
"""

import sys

import pycstbox.cli as cli
import pycstbox.dbuslib as dbuslib
import pycstbox.evtmgr as evtmgr
import pycstbox.log as log

if __name__ == '__main__':
    parser = cli.get_argument_parser('CSTBox Event Manager service')
    args = parser.parse_args()

    try:
        dbuslib.dbus_init()
        log.setup_logging()

        svc = evtmgr.EventManager(dbuslib.get_bus())
        svc.log_setLevel(getattr(log, args.loglevel.upper()))
        svc.start()

    except Exception as e: #pylint: disable=W0703
        log.exception(e)
        sys.exit(e)
