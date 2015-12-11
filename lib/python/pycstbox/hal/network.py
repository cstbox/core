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

""" Device(sub-)network abstraction.

It is implemented as a D-Bus service container, bundling one service object per
connected network, each service object being in charge of the communications
with the devices and acting as a gateway with the D-Bus eventing layer.

The service container can be created for a specific set of coordinator types,
giving the ability to create sub-networks which can be controlled in an
independent way. Refer to :py:class:`DeviceNetworkSvc` documentation for details.

The configuration loading process takes care of taking in account only the
equipments for which we have an implementation available. This allows heterogeneous
implementation (in terms of programming language for instance), by letting each
sub-system of the equipment support software pick only the devices and coordinators
it knows how to handle.
"""

import threading
import time
from collections import namedtuple
import json

import dbus.service
from dbus.exceptions import DBusException

from pycstbox.service import ServiceContainer
from pycstbox.sysutils import parse_period
import pycstbox.evtmgr
from pycstbox.hal.drivers import get_hal_device_classes
from pycstbox.hal import HalError
from pycstbox.log import Loggable
from pycstbox.hal.device import PollingError
from pycstbox.hal.device import log_setLevel as haldev_log_setLevel
from pycstbox.devcfg import Metadata

OBJECT_PATH = "/service"


class DeviceNetworkSvc(ServiceContainer):
    """ This class implements a service container gathering all the equipment
    we know about.

    Each sub-network attached to a given interface is represented by an
    independent service object responsible for managing the connected
    equipments.
    """
    def __init__(self, conn, svc_name, coord_types=None, coord_typemap=None):
        """
        :param Connection conn:
            the D-Bus connection of the container
        :param str svc_name:
            the name under which the service will be know on D-Bus
        :param list coord_types:
            a list of the coordinator types used to filter the device network
            configuration. If not provided, all know types as provided by the
            devcfg.Metedata class will be taken in account. The implementation
            class of the coordinators will be defaulted to CoordinatorServiceObject.
        :param dict coord_typemap:
            a dictionary providing for each coordinator type the associated
            implementation class. If both coord_types and coord_typemap parameters
            are used, coord_types is discarded.
        """
        super(DeviceNetworkSvc, self).__init__(svc_name, conn)
        self._loaded = False

        if coord_typemap:
            self._coord_types = coord_typemap

        else:
            if not coord_types:
                coord_types = Metadata.coordinator_types
            self._coord_types = dict([(k, CoordinatorServiceObject) for k in coord_types])

    def log_setLevel(self, level):
        """
        Defines the logging level for the container and its service objects.

        :param level: logging level (see module :py:mod:`logging`)
        """
        super(DeviceNetworkSvc, self).log_setLevel(level)
        haldev_log_setLevel(level)

    def load_configuration(self, cfg):
        """ Loads devices configuration.

        :param DeviceNetworkConfiguration cfg: network configuration
        """
        if self._loaded:
            raise RuntimeError('method can only be called once')

        # create a service object for each known hardware interface
        # and load the configuration of the devices connected to it
        cnt = 0
        for cid, cfg_coord in [
            (cid, cfg_coord) for cid, cfg_coord in cfg.iteritems()
            if cfg_coord.type in self._coord_types
        ]:
            coord_class = self._coord_types[cfg_coord.type]
            so = coord_class(cid)
            so.log_setLevel(self.log_getEffectiveLevel())
            so.load_configuration(cfg_coord)
            self.add(so, '/' + cid)
            cnt += 1

        if not cnt:
            self.log_warn("no matching coordinator found in configuration data")
        self._loaded = True

DeviceListEntry = namedtuple('DeviceListEntry', ['id_', 'cfg', 'haldev'])
""" Named tuple gathering all informations related to a device.

:key id\_: the device id
:key cfg: the device configuration data, as stored in the network configuration
:key haldev: the instance of HalDevice implementing the abstraction for the device
"""

PollTask = namedtuple('PollTask', ['dev', 'period', 'pause'])
""" Named tuple describing a polling task for a given device.

:key dev: the instance of the related device
:key period: the polling period (in seconds)
:key pause: the optional pause (in seconds) after the poll is done
"""

DFLT_POLL_PERIOD = 1    # secs
DFLT_POLL_PAUSE = 0
DEFAULT_EVENTS_MAX_AGE = 2 * 3600   # 2 hours


class CoordinatorServiceObject(dbus.service.Object, Loggable):
    """ DBus service object responsible for managing a given sub-network
    coordinator.

    It provides a generic mechanism for scheduling the poll of the devices
    using this type of communications.

    This class must be overridden most of the time if communication with the
    network is to be handled at the coordinator level. The only situation where
    it can be used as is is when device drivers know how to communicate
    directly with the equipments (such as those based on minimalmodbus for
    instance).

    c_serial.SerialCoordinatorServiceObject is an example of such a sub-class,
    dealing with network communicating through a serial port in a centralized
    way.
    """
    def __init__(self, cid):
        """
        :param str cid: coordinator id
        """
        dbus.service.Object.__init__(self)
        self._cid = cid
        self._cfg = None
        self._evtmgr = None
        self._polling_thread = None
        self._devices = {}

        Loggable.__init__(self, logname='%s' % str(self))

    @property
    def coordinator_id(self):
        return self._cid

    def __str__(self):
        return 'SO:' + self._cid

    def log_setLevel(self, level):
        """
        Defines the logging level for the container and its service objects.

        :param level: logging level (see module :py:mod:`logging`)
        """
        Loggable.log_setLevel(self, level)
        if self._polling_thread:
            self._polling_thread.log_setLevel(level)

    def load_configuration(self, cfg):
        """ Process the configuration data related to the coordinator and
        the devices attached to it.

        :param dict cfg: coordinator's configuration data
        :raises ValueError: if no or empty configuration passed
        """
        if not cfg:
            raise ValueError('configuration cannot be None or empty')

        self.log_info("loading configuration...")
        self._cfg = cfg
        self._configure_coordinator(self._cfg)
        self._devices = self._configure_devices(self._cfg)
        self.log_info("done")

    @property
    def cfg(self):
        """ Read access to the coordinator and attached devices configuration."""
        return self._cfg

    def _configure_coordinator(self, cfg):
        """ Process the configuration of the coordinator itself if needed.

        The default implementation does nothing.

        :param dict cfg: coordinator's configuration data (included attached devices list)
        """
        pass

    def _configure_devices(self, cfg):
        """ Load the configuration of the devices connected to this
        coordinator.

        Each device is implemented by an instance of a class registered
        in the HAL_DEVICE_CLASSES table, defined in pycstbox.hal.devclasses. This
        table gives the correspondence between the type of device used in the
        configuration data and the class modeling it.

        :param dict cfg: coordinator's attached devices configuration (keyed by the device ids)
        :returns: the dictionary of device asbtraction object instances, keyed by device ids
        """
        devices = {}
        devclasses = get_hal_device_classes()
        for id_, cfg_dev in [(k, v) for k, v in cfg.iteritems() if v.enabled]:
            self.log_info('loading configuration for device id=%s' % id_)
            self.log_debug('- configuration : %s' % cfg_dev.js_dict())
            _protocol, devtype = cfg_dev.type.split(':')
            self.log_info('- device type : %s' % devtype)
            if devtype in devclasses:
                class_ = devclasses[devtype]
                self.log_info('- driver class : %s' % class_)

                try:
                    haldev = class_(self._cfg, cfg_dev)
                except HalError as e:
                    self.log_error(e)
                except Exception as e:  #pylint: disable=W0703
                    self.log_exception(
                        "unexpected error while creating hw device instance: %s", e
                    )
                else:
                    if isinstance(haldev, Loggable):
                        haldev.log_setLevel(self.log_getEffectiveLevel())
                    devices[id_] = DeviceListEntry(id_, cfg_dev, haldev)

            else:
                self.log_error("no driver found for device type '%s'", devtype)
        return devices

    def send_command(self, command, callback=None):
        """ Provision for outbounds communication.

        To be overridden by sub-class when needed. The default implementation
        raises a NotImplementedError exception.

        :param str command: command to be sent (exact content is implementation dependent)
        :param method callback:
            an optional method to be called after the command has been sent
            (can be used for reply synchronous wait for instance)
        """
        raise NotImplementedError()

    def start(self):    #pylint: disable=R0912
        """ Processing to be done when the service objet is started.

        Called automatically by the framework when the service is started.
        """
        self.log_info('connecting to Event Manager...')
        self._evtmgr = pycstbox.evtmgr.get_object(pycstbox.evtmgr.SENSOR_EVENT_CHANNEL)
        self.log_info('success')

        # Build the polling scheduling list.
        # List items are tuples composed of :
        # - the device to be polled
        # - the polling period of the device
        # - the optional pause after polling
        # The list is sorted by increasing periods
        sched_tasks = []

        def get_duration_setting(name, default_value):
            try:
                s = getattr(dev.cfg, name).lower()
            except AttributeError:
                self.log_info('- no settings found for "%s" -> defaulted to %s', name, default_value)
                return default_value
            else:
                self.log_info('- settings found for "%s" : %s', name, s)
                try:
                    return parse_period(s)
                except ValueError:
                    self.log_error('- invalid value (%s) for "%s" -> defaulted to %s', s, name, default_value)
                    return default_value

        for dev in self._devices.itervalues():
            self.log_info(
                'processing polling settings for device : %s' % dev.id_
            )
            if dev.haldev.is_pollable():
                period = get_duration_setting('polling', DFLT_POLL_PERIOD)
                pause = get_duration_setting('pause', DFLT_POLL_PAUSE)

                sched_tasks.append(PollTask(dev, period, pause))

            else:
                self.log_info('- not a polled device')

        if sched_tasks:
            # Sort the list
            sched_tasks.sort(cmp=lambda x, y: x.period - y.period)

            # Start the scheduler worker task
            self._polling_thread = _PollingThread(
                owner=self,
                tasks=sched_tasks
            )
            self._polling_thread.log_setLevel(self.log_getEffectiveLevel())
            self._polling_thread.start()

        else:
            self.log_info('no device to be scheduled')

        self.log_info('started')

    def stop(self):
        """ Processing to be done when the service object is stopped.

        Called automatically by the framework when the service is stopped.
        """
        if self._polling_thread:
            self._polling_thread.terminate()
            self._polling_thread.join(self._polling_thread.period * 2)
            self._evtmgr = None
            self.log_info('stopped')

    def emit_event(self, *args):
        self._evtmgr.emitEvent(*args)


class DeviceNetworkError(Exception):
    """ Specialized exception for device network related errors.
    """

Schedule = namedtuple('Schedule', ['when', 'task'])
""" Named tuple describing a task schedule.

:key long when: schedule time (in second count from asbolute time origin)
:key task: the instance of the task to be executed
"""


class _PollingThread(threading.Thread, Loggable):
    """ Thread managing devices polling."""
    DFLT_TASK_CHECKING_PERIOD = 1

    def __init__(self, owner, tasks):
        """
        :param CoordinatorServiceObject owner: the coordinator in charge of the polling tasks
        :param tasks: the list of tasks corresponding to polling actions to be managed
        """
        threading.Thread.__init__(self)

        self._owner = owner
        self._tasks = tasks
        self._terminate = False
        self._task_trigger_checking_period = self.DFLT_TASK_CHECKING_PERIOD

        Loggable.__init__(self, logname='Poll:%s' % self._owner.coordinator_id)

    @property
    def period(self):
        return self._task_trigger_checking_period

    def run(self):  #pylint: disable=R0912
        """  Enqueues and activates tasks based on their periods.

        The queue contains tuples, composed of :
         - the next schedule time
         - the task description, as provided by the task list
         """
        if not self._tasks:
            raise PollingThreadError('empty task list')

        # retrieve the delay between successive polls, if configured
        coord_cfg = self._owner.cfg
        try:
            poll_delay = parse_period(coord_cfg.poll_delay)
            self.log_info('polling pace delay set to %.1fs', poll_delay)
        except AttributeError:
            poll_delay = 0
            self.log_warn("no polling pace delay")

        sched_queue = []

        def at(_when, _task):
            """ Mimics the system `at` command to schedule an action at a future time
            :param long _when: the schedule time (in absolute time)
            :param PollTask _task: the task to be executed
            """
            schedule = Schedule(_when, _task)
            sched_queue.append(schedule)
            self.log_debug('schedule added : when=%s dev=%s', schedule.when, schedule.task.dev.id_)

        # For all the devices to be polled at starting time, we add them
        # with a next time set to 0.
        for task in self._tasks:
            at(0, task)

        # Enter the scheduling loop.
        # Current time is checked every second and queued tasks having
        # reached their schedule are executed, then moved to the end of the
        # scheduling queue
        self.log_info('entering run loop')
        self._terminate = False
        dev_errcnt = {}
        polled_devs = []
        no_error = (0, 0)
        while not self._terminate:
            now = time.time()
            for task in [task for (when, task) in sched_queue if when <= now]:
                # check terminate flag as frequently a possible, since some devices can take a
                # while to be polled, and we can have a lot of polls to be done here
                if self._terminate:
                    break

                dev, period, pause = task
                dev_id = dev.id_

                # logs the polling operation in an optimized way, so that not
                # to fill up the log with recurrent messages
                if dev_id not in polled_devs:
                    self.log_info('first polling of device %s', dev_id)
                    polled_devs.append(dev_id)
                else:
                    self.log_debug('polling device %s', dev_id)

                poll_errs, crc_errs = dev_errcnt.get(dev_id, no_error)
                try:
                    # requests the device driver to execute the polling procedure
                    # and return us the list of events corresponding to the reply
                    # received in return
                    events = dev.haldev.poll()

                except PollingError as e:
                    poll_errs += 1
                    if poll_errs <= 2:
                        self.log_error(e.message)
                    if poll_errs == 2:
                        self.log_warn(
                            'duplicated errors will not be reported any more for device %s',
                            dev_id
                        )
                    dev_errcnt[dev_id] = (poll_errs, crc_errs)

                except (ValueError, TypeError) as e:
                    crc_errs += 1
                    if crc_errs <= 2:
                        self.log_error(
                            'unexpected polling error on device %s', dev_id
                        )
                        self.log_exception(e)
                    if crc_errs == 2:
                        self.log_warn(
                            'duplicated errors will not be reported any more for device %s',
                            dev_id
                        )
                    dev_errcnt[dev_id] = (poll_errs, crc_errs)

                else:
                    if dev_id in dev_errcnt:
                        self.log_info(
                            'communication restored with device %s', dev_id
                        )
                        del dev_errcnt[dev_id]

                    try:
                        for evt in events:
                            if self._terminate:
                                break
                            self.log_debug('emitting ' + str(evt))
                            self._owner.emit_event(
                                evt.var_type, evt.var_name, json.dumps(evt.data)
                            )
                    except DBusException as e:
                        if not self._terminate:
                            self.log_exception(e)

                # re-schedule this task
                next_time = now + period
                del sched_queue[0]
                at(next_time, task)

                # if we need to keep a cool pace, wait a bit before polling next guy
                pause = max(pause, poll_delay)
                if pause:
                    self.log_debug('polling pace pause (%.1f)...', pause)
                    time.sleep(pause)

            # wait until next checking, if we have not been requested to
            # terminate meanwhile
            if self._terminate:
                break

            delay = now + self._task_trigger_checking_period - time.time()
            if delay > 0:
                time.sleep(delay)

            else:
                # adjust the task trigger checking period, in case we observed
                # that the tasks to be done require more time
                self._task_trigger_checking_period += 1
                self.log_warning(
                    'time checking period too short. Extending it to %d secs',
                    self._task_trigger_checking_period
                )

        self.log_info('terminated')

    def terminate(self):
        """ Notifies the thread that it must terminate."""
        self.log_info('terminate request received')
        self._terminate = True


class PollingThreadError(Exception):
    """ Specialized exception for polling thread errors.
    """
