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

from collections import namedtuple
import logging
import time

import pycstbox.events as evts
import pycstbox.sysutils as sysutils

_logger = logging.getLogger('hal.device')


def log_setLevel(level):
    """ Set the level of module level logging."""
    _logger.setLevel(level)

DEFAULT_PRECISION = 3
""" Default precision for notified values."""


class HalDevice(object):    #pylint: disable=R0922
    """ Base class for modeling devices in the abstraction layer.

    It acts as a kind of driver and is responsible for interfacing
    the real equipments with the generic communication layer.

    This base class includes the generic mechanism which produces CSTBox events based on
    data produce by the equipment outputs (see :py:meth:`create_events`), and can be used
    as is for modeling asynchronous equipments which produce data on their own (ie without being
    polled).

    Polled devices are modeled by the :py:class:`PolledDevice` class, which provides the
    foundation for managing the dialog with the physical equipment in order to get its outputs.
    """
    def __init__(self, coord, cfg):
        """
        :param Coordinator coord: the parent coordinator
        :param dict cfg: the device configuration, as retrieved from the global configuration data
        """
        self.coord = coord
        self._cfg = cfg
        self._prev_values = {}
        self._last_event_times = {}

        # process configuration values, added default values for unspecified
        # generic parameters
        for output_cfg in self._cfg.outputs.itervalues():
            if 'prec' in output_cfg:
                output_cfg['prec'] = int(output_cfg['prec'])
            else:
                output_cfg['prec'] = DEFAULT_PRECISION
            if 'delta_min' in output_cfg:
                output_cfg['delta_min'] = float(output_cfg['delta_min'])
            else:
                output_cfg['delta_min'] = None

        # same for maximum age of last sent events, but globally for the device
        try:
            self._events_ttl = sysutils.parse_period(self._cfg.events_ttl)
        except AttributeError:
            self._events_ttl = evts.DEFAULT_EVENT_TTL
        else:
            if not self._events_ttl:    # None or 0
                self._events_ttl = evts.DEFAULT_EVENT_TTL
        _logger.info('events_ttl=%d', self._events_ttl)

    def is_pollable(self):
        """ Tells if the device can be polled.

        Polled equipments HalDevice sub-classes must provide a method named
        "poll", which takes no parameter and returns the list of CSTBox events
        reflecting the reply to the poll request.

        The returned events must be instances of pycstbox.events.BasicEvent or
        pycstbox.events.TimedEvents.

        The poll method must notify any error by raising a PollingError
        exception.
        """
        return hasattr(self, 'poll') and callable(self.poll)

    def create_events(self, output_values):
        """ Creates the list of events depending on the collected or received
        data from the device.

        This method takes care of handling the filtering of redundant events
        (same value received again and again), based of device settings such as
        the events time to live.

        Same for filtering small variations of the values.

        It relies on the method get_output_data_definition(), which must be
        implemented by subclasses to provide the value type and unit associated
        to a given device output. These information are used to build the
        event to be produced.

        :param tuple output_values:
            a tuple containing the values produced by the output(s) of the
            device. Output values set to None are silently ignored

        :returns list: a (possibly empty) list of events to be emitted
        """
        events = []

        for output, output_cfg in [
            (k, v) for k,v in self._cfg.outputs.iteritems() if v['enabled']
        ]:
            try:
                prev = self._prev_values[output]
            except KeyError:
                prev = None

            raw_value = getattr(output_values, output)
            if raw_value is None:
                continue

            value = round(raw_value, output_cfg['prec'])
            var_type, units = self.get_output_data_definition(output)
            var_name = output_cfg['varname']

            # Small variations filtering

            # If the variation is under the threshold, we act as if the exact
            # same value as previously has been received, rather that simply
            # ignoring the new one.
            # This is done so that the event time to live mechanism is not
            # altered by the filtering.
            delta_min = output_cfg['delta_min']
            if delta_min and prev is not None and abs(value - prev) <= delta_min:
                value = prev

            # compute the age of last event we sent for this variable
            now = time.time()
            evt_age = now - self._last_event_times.get(var_name, 0)

            # if the value has changed since last time, or if last
            # notification is too old, add an event to the send list
            if value != prev or (
                self._events_ttl is not None and evt_age >= self._events_ttl
            ):
                events.append(evts.make_basic_event(var_type, var_name, value, units))
                self._prev_values[output] = value
                self._last_event_times[var_name] = now

        return events

    @classmethod
    def get_output_data_definition(cls, output):
        """ Returns the type of the data and its units (if any) for a given
        output.

        "type of the data" is taken at the semantic level, not at computer
        language level. It can be something like "temperature", "voltage",...

        The `_OUTPUTS_TO_EVENTS_MAPPING` attribute is initialized at initialization time
        of the HAL, using the introspection mechanism based on the
        :py:func:`pycstbox.hal.hal_device` decorator.

        :param str output: the name of the output

        :returns:
            a tuple composed of:

            - the type of the data
            - the units (if any)
        """
        try:
            return cls._OUTPUTS_TO_EVENTS_MAPPING[output]
        except AttributeError:
            raise RuntimeError("class has not been properly registered")


EventDataDef = namedtuple('EventDataDef', ['var_type', 'units'])
""" Named tuple describing the data to be conveyed by sensor notification events

:key var_type: type of the variable which change is notified by the event
:key units: units used for the value
"""


class PolledDevice(HalDevice):  #pylint: disable=W0223
    """ A device which works by polling and not spontaneaous notification.

    This class adds the method :py:meth:`poll` which takes care  of:

    - invoking the low level interface (``self._hwdev``) for querying the
      values. The device implementation classes can do it on their own if
      they can, or rely to the ``send_device_command()`` method provided by a
      specialized coordinator class

    - translating the received values into the corresponding collection of
      events to be broadcasted by calling the super-class :py:meth:`create_events`
      method

    .. important::

        This class cannot be used as is for implementing devices, but must be sub-classed to add in
        its initialization code the connection with an object responsible for the
        low-level interactions with the equipment. This connection is established by initializing
        the private attribute ``_hwdev`` with and instance of an object implementing a ``poll`
        method.
        Proper initialization is checked at first poll time, and the device will be tagged as invalid
        (and will be no more polled) if not compliant.
    """

    def __init__(self, coord, cfg):
        """ Refer to :py:class:`pycstbox.hal.device.HalDevice` for parameters definition."""
        super(PolledDevice, self).__init__(coord, cfg)
        self._hwdev = None
        self._is_checked = self._is_valid = False

    def poll(self):
        """ Refer to :py:class:`pycstbox.hal.device.HalDevice` for details."""

        # check that the sub-class has properly initialized the HW device
        # interface with a valid instance, and invalidates the device otherwise
        if not self._is_checked:
            self._is_checked = True
            if not self._hwdev:
                _logger.error('no HW device defined for %s', self._cfg.uid)
                return
            if not hasattr(self._hwdev, 'poll') or \
               not callable(self._hwdev.poll):
                _logger.error('HW device %s does not define the poll method', self._cfg)
                return

            self._is_valid = True

        if not self._is_valid:
            return

        # query the device for polled parameters
        try:
            output_values = self._hwdev.poll()
            _logger.debug("dev=%s outputs=%s", self._cfg.uid, output_values)

        except IOError as e:
            raise PollingError(self._cfg.uid, e)

        else:
            if output_values:
                # build the corresponding event list

                # emit events for all enabled outputs for which the value has changed
                # since last time
                return self.create_events(output_values)
            else:
                return []

    def terminate(self):
        """ Sends a termination signal to the device, to let it gently stops if needed
        """
        self._hwdev.terminate = True


class PollingError(Exception):
    """ Specialized exception for polling errors.
    """
    def __init__(self, dev_id, error):
        """
        :param str dev_id: id of the device being polled
        :param Exception error: reported error
        """
        super(PollingError, self).__init__(
            'polling error on device %s : %s' % (dev_id, error.message)
        )
        self.dev_id, self.error = dev_id, error
