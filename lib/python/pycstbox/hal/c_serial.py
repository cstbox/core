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

import serial
import threading
import json

from pycstbox.hal.network import CoordinatorServiceObject
from pycstbox.log import Loggable


class SerialCoordinatorServiceObject(CoordinatorServiceObject):
    """ Abstract class implementing the base tasks for a coordinator based on
    a serial port interface with the network.

    It has to be overridden to provide the dispatch_received_data() method which
    is responsible for handling the incoming data, depending on the protocol in
    use for the relevant equipments.
    """
    def __init__(self, c_id):
        """
        :param str c_id: coordinator id
        """
        super(SerialCoordinatorServiceObject, self).__init__(c_id)
        self._serial_port = None
        self._serial_config = None
        self._serial_lock = threading.Lock()
        self._rx_thread = None

    @property
    def serial_port(self):
        """ The serial port object used by the coordinator.
        """
        return self._serial_port

    def _configure_coordinator(self, cfg):
        super(SerialCoordinatorServiceObject, self)._configure_coordinator(cfg)

        # creates a serial configuration with default settings (but the port)
        self._serial_config = SerialPortConfiguration(cfg.port)
        # stores explicit settings in it
        self._serial_config.update(cfg)
        self.log_info('serial port configuration: %s' % self._serial_config)

    def start(self):
        """ Starts the service object.

        This will initialize the serial port, open it and start the data receive thread.
        """
        if self._serial_port:
            self.log_warning('already started')
            return

        # execute default process
        super(SerialCoordinatorServiceObject, self).start()

        # it's time to open the serial port, using the configuration provided
        # at instance creation
        self.log_info('initializing serial port...')
        self._serial_port = serial.Serial(
            port=self._serial_config.port,
            baudrate=self._serial_config.baudrate,
            bytesize=self._serial_config.bytesize,
            parity=self._serial_config.parity,
            stopbits=self._serial_config.stopbits,
            timeout=0.1
        )
        self._serial_port.flushInput()
        self._rx_thread = _ListenerThread(self)
        self._rx_thread.log_setLevel(self.log_getEffectiveLevel())
        self._rx_thread.start()

    def stop(self):
        """ Stops the service object.

        This will stop the receive thread and close the serial port.
        """
        if not self._serial_port:
            self.log_warning('not started')
            return

        if self._rx_thread:
            self._rx_thread.terminate()
            self._rx_thread.join(5000)
            self._rx_thread = None

        if self._serial_port:
            self._serial_port.close()
            self._serial_port = None

        super(SerialCoordinatorServiceObject, self).stop()

    def send_command(self, command, callback=None):
        """ Sends a command for a device attached to the coordinator, handling appropriate locking for guarantying
        the atomicity of the operation (command sending, callback invocation).

        :param str command: the command to be sent (device dependant)
        :param callable callback: an optional callable invoked is the command is send without error
        """
        self._serial_lock.acquire()
        try:
            self._serial_port.write(command)
            if callback:
                self.callback(command)

        finally:
            self._serial_lock.release()

    def data_received(self, data):
        """ Callback used by the receiver thread to notify us that a data packet is here to be processed.

        :param data: the received data
        """
        events = self.dispatch_received_data(data)
        for evt in events:
            self.log_debug('emitting ' + str(evt))
            self._evtmgr.emitEvent(
                evt.var_type, evt.var_name, json.dumps(evt.data)
            )

    def dispatch_received_data(self, data):
        """ Dispatch the received data to the relevant devices, so that they
        return us the corresponding events to be emitted (if any).

        This method must be implemented by concrete coordinators, in order to
        handle the device identification based on the protocol in use and
        transmit them the received data.

        :param data: the data to be processed
        :returns: a list of events to be emitted (can be empty)
        """
        raise NotImplementedError()


class _ListenerThread(threading.Thread, Loggable):
    """ Internal class implementing a thread dedicated to serial port data
    listening and data handling.
    """
    def __init__(self, owner):
        """
        :param CoordinatorServiceObject owner: the owning coordinator
        """
        threading.Thread.__init__(self)

        self._owner = owner
        self._serial_port = owner.serial_port
        self.name = 'ser-' + owner.coordinator_id
        self._terminate = False

        Loggable.__init__(self, logname='SerRX:%s' % owner.coordinator_id)

    def run(self):  #pylint: disable=R0912
        """ Processing executed by the thread.

        Endless loop waiting for incomming data and dispatching them. It exists when the `terminate` flags has been
        set by a call to :py:meth:`terminate`, of if an exception occured.
        """
        self.log_info('starting serial port listener...')
        try:
            while not self._terminate:
                waiting = self._serial_port.inWaiting()
                if waiting:
                    data = self._serial_port.read(waiting)
                    self._owner.data_received(data)

        except Exception as e:  #pylint: disable=W0703
            self.log_exception(e)

        self.log_info('terminated.')

    def terminate(self):
        """ Notifies the thread that it must terminate."""
        self.log_info('terminate request received')
        self._terminate = True


class SerialPortConfiguration(object):
    """ Convenience data holder for serial port configuration data, providing commonly used default settings.
    """
    def __init__(self, port,
                 baudrate=4800,
                 bytesize=serial.EIGHTBITS,
                 parity=serial.PARITY_NONE,
                 stopbits=serial.STOPBITS_ONE
                 ):
        self.port = port
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits

    def update(self, src):
        """ Updates attribute values based on information defined as attributes of another object (most often,
        an extract of the device network configuraton data structure).
        :param src: the configuration data source object
        """
        for attr in ['port', 'baudrate', 'bytesize', 'parity', 'stopbits', 'timeout']:
            if hasattr(src, attr):
                setattr(self, attr, getattr(src, attr))

    def __str__(self):
        return 'port=%s baudrate=%s bytesize=%s parity=%s stopbits=%s' % (
            self.port,
            self.baudrate,
            self.bytesize,
            self.parity,
            self.stopbits
        )
