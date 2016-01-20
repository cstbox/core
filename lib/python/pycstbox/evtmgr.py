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

""" CSTBox Event manager service.

Service taking care of events broadcasting to the rest of the framework and
application.

In order to be easily filtered by nature, events are exhanged on several
separate "channels". Each channel is managed by a distinct instance of the
event manager, which defines its own connection name (aka bus name), set as
ROOT_BUS_NAME suffixed by the channel name.

When started as a script, this module creates a bus for the channel passed
on the command line (use -h for detailed usage).

This allows a simple and efficient way for consumers to subscribe to only the
events of interest, without any complicated matching, just by using the
connection to the right manager.

The following channels are pre-defined as module properties:
    - SENSOR_EVENT_CHANNEL = 'sensor'
    - CONTROL_EVENT_CHANNEL = 'control'
    - SYSMON_EVENT_CHANNEL = 'sysmon'
    - FRAMEWORK_EVENT_CHANNEL = 'framework'

Public methods and signals published through D-Bus are accessed via a single
object which path is defined by the OBJECT_PATH module property. They are
grouped in an interface which name is provided by the SERVICE_INTERFACE module
property.

For details, refer to the documentation of method EventManager.emitEvent,
signal EventManager.onCSTBoxEvent and pycstbox.events module.
"""

import dbus
import dbus.service

import time
import threading
import json
from collections import namedtuple

from pycstbox import service
from pycstbox import dbuslib
from pycstbox.log import Loggable

__author__ = 'Eric PASCUAL - CSTB (eric.pascual@cstb.fr)'

# Various names definitions

SERVICE_NAME = "EventManager"

SENSOR_EVENT_CHANNEL = 'sensor'
CONTROL_EVENT_CHANNEL = 'control'
SYSMON_EVENT_CHANNEL = 'sysmon'
FRAMEWORK_EVENT_CHANNEL = 'framework'

ALL_CHANNELS = (SENSOR_EVENT_CHANNEL, CONTROL_EVENT_CHANNEL, SYSMON_EVENT_CHANNEL, FRAMEWORK_EVENT_CHANNEL)

SERVICE_INTERFACE = dbuslib.make_interface_name(SERVICE_NAME)


class EventManager(service.ServiceContainer):
    """ CSTBox Event manager service.

    This container will host a service object for each event channel, in order
    to keep the various communication separated, and this easing the subscription
    to a given family of event.
    """

    def __init__(self, conn, channels=None):
        """
        :param conn:
            the bus connection (Session, System,...)
        :param str channels:
            a list of strings enumerating the event channels (sensor, system,...). If
            not provided, all pre-defined channels will be used.
        """
        if not channels:
            channels = ALL_CHANNELS
        svc_objects = [(EventManagerObject(ch), '/' + ch) for ch in channels]

        super(EventManager, self).__init__(SERVICE_NAME, conn, svc_objects)


class EventManagerObject(dbus.service.Object, Loggable):
    """ The service object for a given event channel.

    One instance of this class is created for each event channel to be managed.
    """
    def __init__(self, channel):
        """
        :param str channel: the event channel
        """
        super(EventManagerObject, self).__init__()

        self._emitLock = threading.Lock()
        self._channel = channel

        Loggable.__init__(self, logname='SO:%s' % self._channel)

    @dbus.service.signal(SERVICE_INTERFACE, signature='tsss')
    def onCSTBoxEvent(self, timestamp, var_type, var_name, data):
        """ CSTBoxEvent broadcasting DBus signal

        :param unsigned64 timestamp:
            the event timestamp, in milliseconds since January 1st, 1970

        See :py:meth:`emitEvent` documentation for other parameters.
        """
        self.log_debug(
            "CSTBoxEvent signaled : timestamp=%s var_type=%s var_name=%s data=%s",
            timestamp, var_type, var_name, data)

    @dbus.service.method(SERVICE_INTERFACE, in_signature='sss')
    def emitEvent(self, var_type, var_name, data):
        """ Timestamps and posts a CSTBoxEvent on the message bus.

        Events are automatically timestamp'ed before being posted on the bus.
        The timestamp is set to the number of milliseconds elapsed since the
        origin of time (aka epoch).

        Appropriate synchronization is also applied to ensure events integrity
        in case of multi-threaded calls.

        :param str var_type:
            A string defining the type a the involved variable (ex: 'temperature')
        :param str var_name:
            The name of the variable
        :param str data:
            A string containing the event payload, formatted as a valid
            JSON representation.  The payload format is defined by the
            event class. Ex: {"value":"25.7","unit":"degC"}.  See json
            package documentation for details

        :returns: True if all is ok
        """
        with self._emitLock:
            timestamp = int(time.time() * 1000)
            self.log_debug(
                "emiting : timestamp=%s var_type=%s var_name=%s data=%s",
                timestamp, var_type, var_name, data)
            self.onCSTBoxEvent(timestamp, var_type, var_name, data)
            self.log_debug('Done')
        return True

    @dbus.service.method(SERVICE_INTERFACE, in_signature='tsss')
    def emitFullEvent(self, timestamp, var_type, var_name, data):
        with self._emitLock:
            self.log_debug(
                "emiting : timestamp=%s var_type=%s var_name=%s data=%s",
                timestamp, var_type, var_name, data)
            self.onCSTBoxEvent(timestamp, var_type, var_name, data)
            self.log_debug('Done')
        return True

    def emitTimedEvent(self, event):
        """ Posts an event provided as a tuple.

        This method is intended to be called by Python clients, and uses an
        objectified event instead of separate parameters.

        If the provided event is a TimedEvent instance, its timestamp will be
        discarded, since it can be outdated and thus introduce a break in the
        time line.

        :param event:
            the event to be emitted, as a events.BasicEvent or a events.TimedEvent instance
        """
        # delegates to the "universal" method
        return self.emitEvent(
            event.var_type,
            event.var_name,
            json.dumps(event.data)
        )


EventOnBus = namedtuple('EventOnBus', 'timestamp, var_type, var_name, data')
""" Content of an event as it circulates on D-Bus."""


def get_object(channel):
    """Returns the service proxy object for a given event channel if available

    :param str channel: the event channel managed by the requested service instance
    :returns: the requested service instance, if exists
    :raises ValueError: if no bus name match the requested channel
    """
    return dbuslib.get_object(SERVICE_NAME, '/' + channel)
