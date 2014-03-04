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

""" Basic definitions and tools related to CSTBox events.

The instrumented environment (home, office, experiment,...) is represented by a
set of state and control variables. State variables containts the last known
value of a given sensor by instance, the current position of an actuator,...
while control variables are used to modify the state of an actuator, and thus
can represent its set point (ex: the status of a light switch). As a
generalization, a control variable can be used to set a message to be displayed
on a device, to be vocalized by an audio system, or to be sent as an SMS to a
phone number.

A special case of state variable without a value exists for notifications, such
as the ones provided by motion sensors. In this case, the event is used to signal
that a motion is detected, but does not convey any value (kind of Dirac function).

Basic events are composed of the following parts :

    - a variable type (ex: temperature)
    - a variable name
    - a dictionary containing event data if any, such as the value for events
      conveying one

(*) the dictionary must be included, and can be empty if the event has no data

Timed events add a time stamp field to these ones. The time stamp is expressed as
the number of milliseconds elapsed since the Epoch.

It must be noted that a state variable and a control variable can share the
same variable type. There will be no clash since the associated events will be
exchanged on distinct channels. This is by the way coherent with respect to
what variables represent. For instance, a temperature is always a temperature,
no matter if it is the temperature of a given room returned by a sensor, or the
set point for a temperature regulator.

Variable names must be unique within the same type, and only the association
(type, name) must be unique. For instance, on can have two variables named
"livingroom", one defined with the "temperature" type, and the other with the
"movement" one.

At implementation level, events are conveniently manipulated as tuples, which
components are the ones listed above. Python tuples are an efficient and
light weight representation allowing to manipulate data as a structured and
immutable entity.

For convenience, named tuples are also defined here, conveying explicitly the
name of the event components, and ensuring that the components sequence is
respected in the tuple.

"""

__author__ = 'Eric PASCUAL - CSTB (eric.pascual@cstb.fr)'
__copyright__ = 'Copyright (c) 2013 CSTB'
__vcs_id__ = '$Id$'
__version__ = '1.0.0'

from collections import namedtuple

BasicEvent = namedtuple(
    'BasicEvent',
    'var_type var_name data'
)

TimedEvent = namedtuple(
    'TimedEvent',
    'timestamp var_type var_name data'
)

# common data keys

VALUE = 'value'
UNITS = 'units'

# shared constants

# Default value for event time to live. 
#
# The event time to live is the maximum delay after which a variable value
# change event is considered as obsolete. Past the TTL, an event will be sent
# event if the received value for the observed variable is still the same.  
# This acts as a life sign mechanism,  making the rest of the system aware 
# of the fact that we are still up and running.
DEFAULT_EVENT_TTL = 2 * 3600   # 2 hours


def make_data(value=None, units=None, **kwargs):
    """ Builds the data dictionary of an event, handling common items such as
    the variable value and units if provided.

    :param value:
        the variable value to be integrated in the resulting dictionary
    :param str units:
        the variable units to be integrated in the resulting dictionary
    :param kwargs:
        optional named parameters to be added to the dictionary

    :returns: the dictionary containing the passed information
    """
    data = {}
    if value is not None:
        data[VALUE] = value
    if units:
        data[UNITS] = units
    data.update(**kwargs)
    return data


def make_basic_event(var_type, var_name, value=None, units=None, **kwargs):
    """ Returns a BasicEvent built with the provided pieces.

    The return event is used to signal a value change of a variable, or to
    control an equipment by sending it the new setting of one of its control
    variables.

    :param str var_type: the type of the variable
    :param str var_name: the name of the variable
    :param value: (optional) the value of the variable if relevant
    :param str units: (optional) the units of the variable value
    :param kwargs: optional named parameters to be added to the dictionary

    :returns: the corresponding BasicEvent instance
    """
    return BasicEvent(var_type, var_name, make_data(value, units, **kwargs))

def make_timed_event(ts, var_type, var_name, value=None, units=None, **kwargs):
    """ Same as make_basic_event, but for a TimedEvent.

    :param datetime.datetime ts: the event timestamp
        (see :py:func:`make_basic_event` for the other parameters)

    :returns: the corresponding TimeEvent instance
    """
    return TimedEvent(ts, var_type, var_name, make_data(value, units, **kwargs))

