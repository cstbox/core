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

""" A collection of definitions and helpers for D-Bus usage in the CSTBox
context.
"""

__author__ = 'Eric PASCUAL - CSTB (eric.pascual@cstb.fr)'
__copyright__ = 'Copyright (c) 2012 CSTB'
__vcs_id__ = '$Id$'
__version__ = '1.0.0'

import gobject
import dbus
import dbus.service
import dbus.mainloop.glib
import os

# the make_bus_name() helper function uses this value to build the full
# (public) bus name, based on a simplified one
WKN_PREFIX = 'fr.cstb.cstbox.'

# the make_interface_name() helper function uses this value to build the full
# (public) interface name, based on a simplified one
IFACE_PREFIX = 'fr.cstb.cstbox.'


def dbus_init():
    """ Initializes the D-Bus stuff so that messaging and signaling work.

    MUST be called at the very begining of any process using D-Bus.  """
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    gobject.threads_init()
    dbus.mainloop.glib.threads_init()


def get_bus(logger=None):
    """ Returns the D-Bus bus to be used.

    Depending on the fact that the environment variable DBUS_SESSION_BUS_ADDRESS
    is set or not, either we use our own session bus, or the X user's session one.
    """
    if logger:
        bus_addr = os.environ.get('DBUS_SESSION_BUS_ADDRESS', None)
        if bus_addr:
            logger.info('using CSTBox private session bus at address : %s', bus_addr)
        else:
            logger.warn('using default session bus')
    return dbus.SessionBus()


def get_object(svc_name, obj_path):
    """ Returns the service object corresponding to a connection name and
    an object path."""
    return get_bus().get_object(make_bus_name(svc_name), obj_path)


def make_bus_name(short_name):
    """ Returns a consistent bus name (well-known name), based on the short
    one (ie the last part) """
    assert short_name, 'short_name cannot be None or empty'
    return WKN_PREFIX + short_name


def make_interface_name(short_name):
    """ Returns a consistent interface name, based on the abbreviated one (ie
    the last part) """
    assert short_name, 'short_name cannot be None or empty'
    return IFACE_PREFIX + short_name

