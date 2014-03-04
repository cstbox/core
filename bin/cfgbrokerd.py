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

""" Device configuration broker service daemon.

Starts a configuration broker as a service accessible on D-Bus. See module
pycstbox.cfgbroker for detailed documentation.
"""

import sys

import pycstbox.cfgbroker as cfgbroker
import pycstbox.log as log
import pycstbox.cli as cli
import pycstbox.dbuslib as dbuslib

if __name__ == '__main__':
    log.setup_logging('cfgbroker.main')

    parser = cli.get_argument_parser('CSTBox Configuration Broker service')
    args = parser.parse_args()

    try:
        log.info('starting')
        dbuslib.dbus_init()

        svc = cfgbroker.ConfigurationBroker(dbuslib.get_bus())
        svc.log_setLevel(log.loglevel_from_args(args))
        svc.start()

    except Exception as e:  #pylint: disable=W0703
        log.exception(e)
        sys.exit(e)

    else:
        log.info('terminated')
