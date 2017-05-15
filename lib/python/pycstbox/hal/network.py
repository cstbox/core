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
from pycstbox.hal.device import CommunicationError
from pycstbox.hal.device import log_setLevel as haldev_log_setLevel
from pycstbox.devcfg import Metadata, ConfigurationParms

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
            self.log_info('creating coordinator id=%s class=%s', cid, coord_class.__name__)
            so = coord_class(cid)
            so.log_setLevel(self.log_getEffectiveLevel())
            try:
                so.load_configuration(cfg_coord)
            except HalError as e:
                self.log_error(e)
            else:
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

PollTask = namedtuple('PollTask', ['dev', 'period'])
""" Named tuple describing a polling task for a given device.

:key dev: the instance of the related device
:key period: the polling period (in seconds)
"""

DFLT_POLL_PERIOD = 1                # secs
DFLT_POLL_REQ_INTERVAL = 0          # secs
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
        self._poll_req_interval = None
        self._devices = {}
        self._error_count = 0

        Loggable.__init__(self, logname='%s' % str(self))

    @property
    def coordinator_id(self):
        return self._cid

    @property
    def poll_req_interval(self):
        return self._poll_req_interval

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
        for haldev in (e.haldev for e in self._devices.itervalues() if isinstance(e.haldev, Loggable)):
            haldev.log_setLevel(self.log_getEffectiveLevel())

    def load_configuration(self, cfg):
        """ Process the configuration data related to the coordinator and
        the devices attached to it.

        :param dict cfg: coordinator's configuration data
        :raises ValueError: if no or empty configuration passed
        """
        if not cfg:
            raise ValueError('configuration cannot be None or empty')

        hline = '-' * 60
        self.log_info(hline)
        self.log_info("Devices configuration loading")
        self.log_info(hline)
        self._cfg = cfg
        self._configure_coordinator(self._cfg)
        self._devices = self._configure_devices(self._cfg)
        self.log_info(hline)
        if self._error_count == 0:
            self.log_info("devices configuration successfully loaded")
        else:
            self.log_error('devices configuration loaded with %d error(s)', self._error_count)
        self.log_info(hline)

    @property
    def cfg(self):
        """ Read access to the coordinator and attached devices configuration."""
        return self._cfg

    def _configure_coordinator(self, cfg):
        """ Process the configuration of the coordinator itself if needed.

        .. WARNING::

            Do not forget to invoke ``super`` in overridden versions.

        :param dict cfg: coordinator's configuration data (included attached devices list)
        """
        # retrieve the delay between successive polls, if configured
        self._poll_req_interval = float(
                getattr(cfg, ConfigurationParms.POLL_REQUESTS_INTERVAL, DFLT_POLL_REQ_INTERVAL)
        )
        if self._poll_req_interval:
            self.log_info('polling request interval set to %.1fs', self._poll_req_interval)
        else:
            self.log_warn("no polling request interval specified")

    def _configure_devices(self, cfg):
        """ Load the configuration of the devices connected to this
        coordinator.

        Each device is implemented by an instance of a class registered
        in the HAL_DEVICE_CLASSES table, defined in pycstbox.hal.devclasses. This
        table gives the correspondence between the type of device used in the
        configuration data and the class modeling it.

        :param dict cfg: coordinator's attached devices configuration (keyed by the device ids)
        :returns: the dictionary of device abstraction object instances, keyed by device ids
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
                self.log_info('- driver class : %s' % class_.__name__)

                try:
                    self.log_info('[%s] creating HW device instance', id_)
                    haldev = class_(self._cfg, cfg_dev)
                except Exception as e:
                    if isinstance(e, HalError):
                        self.log_error("[%s] %s", id_, e)
                    else:
                        self.log_exception("[%s] unexpected error : %s", id_, e)
                    self.log_error('[%s] device ignored', id_)
                    self._error_count += 1
                else:
                    hw_dev = haldev._hwdev
                    if isinstance(hw_dev, Loggable):
                        hw_dev.log_setLevel(self.log_getEffectiveLevel())
                    hw_dev.poll_req_interval = self._poll_req_interval
                    devices[id_] = DeviceListEntry(id_, cfg_dev, haldev)
                    self.log_info('[%s] device registered', id_)

            else:
                self.log_error("[%s] no driver found for device type '%s'", id_, devtype)
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
        try:
            self._evtmgr = pycstbox.evtmgr.get_object(pycstbox.evtmgr.SENSOR_EVENT_CHANNEL)
        except DBusException as e:
            raise DeviceNetworkError("cannot connect to Event Manager : %s" % e)
        else:
            self.log_info('connected to Event Manager')

        # Build the polling scheduling list.
        # List items are tuples composed of :
        # - the device to be polled
        # - the polling period of the device
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
                period = get_duration_setting(ConfigurationParms.POLL_PERIOD, DFLT_POLL_PERIOD)

                # set the device poll request interval in case it uses multiple low level requests
                dev.haldev.poll_req_interval = self._poll_req_interval

                sched_tasks.append(PollTask(dev, period))

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

            # signal to polled devices that they have to stop (some of them can loop over sub-polling)
            for haldev in (dev.haldev for dev in self._devices.itervalues() if dev.haldev.is_pollable()):
                self.log_info('sending termination signal to device %s', haldev)
                haldev.terminate()

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


class PollingStats(object):
    __slots__ = ['total_poll', 'comm_errs', 'crc_errs', 'unexp_errs', 'recovered']

    def __init__(self, total_poll=0, comm_errs=0, crc_errs=0, unexp_errs=0, recovered=0):
        self.total_poll, self.comm_errs, self.crc_errs, self.unexp_errs, self.recovered = \
            total_poll, comm_errs, crc_errs, unexp_errs, recovered

    def __str__(self):
        return "total_polls=%d, comm_errs=%d, crc_errs=%d, unexp_errs=%d, recovered=%d" % (
            self.total_poll, self.comm_errs, self.crc_errs, self.unexp_errs, self.recovered
        )

    def as_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}

    @classmethod
    def from_dict(cls, d):
        inst = PollingStats()
        for k in inst.__slots__:
            setattr(inst, k, d[k])
        return inst


class _PollingThread(threading.Thread, Loggable):
    """ Thread managing devices polling."""
    DFLT_TASK_CHECKING_PERIOD = 1
    STATS_INTERVAL = 1000
    STATS_STORAGE_PATH = '/var/db/cstbox/polling_stats-%s.dat'

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
        self._stats_file_path = self.STATS_STORAGE_PATH % self._owner.coordinator_id

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

        sched_queue = []
        poll_req_interval = self._owner.poll_req_interval

        def at(_when, _task):
            """ Mimics the system `at` command to schedule an action at a future time
            :param long _when: the schedule time (in absolute time)
            :param PollTask _task: the task to be executed
            """
            schedule = Schedule(_when, _task)

            if sched_queue:
                # find the right insert position of the schedule to maintain
                # the queue chronologically sorted, optimizing the trivial cases
                if sched_queue[-1].when <= _when:
                    sched_queue.append(schedule)
                else:
                    for i, sched in enumerate(sched_queue):
                        if sched.when > _when:
                            sched_queue.insert(i, schedule)
                            break
            else:
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

        # try to load previously saved stats if any.
        try:
            with open(self._stats_file_path) as fp:
                d = json.load(fp)
        except (IOError, ValueError):
            dev_stats = {}
        else:
            dev_stats = {k: PollingStats.from_dict(v) for k, v in d.iteritems()}
            self.log_info('previously recorded stats:')
            for dev_id, stats in dev_stats.iteritems():
                self.log_info('- [%s] %s', dev_id, stats)

        # accumulator for device errors (keyed by device id) used for reporting
        errors = {}

        polled_devs = []
        while not self._terminate:
            polling_start_time = time.time()
            if sched_queue:
                retried = []

                # process all the tasks which schedule is now or older, checking the termination
                # request while doing this
                while not self._terminate and sched_queue[0].when <= polling_start_time:
                    # dequeue the task and process it
                    when, task = sched_queue.pop(0)

                    dev, period = task
                    dev_id = dev.id_

                    # logs the polling operation in an optimized way, so that not
                    # to fill up the log with recurrent messages
                    if dev_id not in polled_devs:
                        self.log_info('[%s] first polling', dev_id)
                        polled_devs.append(dev_id)
                    else:
                        self.log_debug('[%s] polling device', dev_id)

                    # stats, err_level, in_error = dev_stats.get(dev_id, (PollingStats(), 0, False))
                    stats = dev_stats.get(dev_id, PollingStats())
                    try:
                        # requests the device driver to execute the polling procedure
                        # and return us the list of events corresponding to the reply
                        # received in return
                        stats.total_poll += 1
                        events = dev.haldev.poll()

                    except CommunicationError as e:
                        stats.comm_errs += 1
                        errors[dev_id] = e.message

                    except ValueError:
                        stats.crc_errs += 1
                        errors[dev_id] = 'CRC error'

                    except TypeError as e:
                        stats.unexp_errs += 1
                        errors[dev_id] = e.message

                    else:
                        if dev_id in errors:
                            self.log_info('[%s] recovered from %s', dev_id, errors[dev_id])
                            del errors[dev_id]
                            stats.recovered += 1

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

                    dev_stats[dev_id] = stats
                    error = errors.get(dev_id, None)
                    if stats.total_poll % self.STATS_INTERVAL == 0:
                        self.log_info('[%s] %s error=%s', dev_id, stats, error)
                        # save stats on disk
                        with open(self._stats_file_path, 'w') as fp:
                            d = {k: v.as_dict() for k, v in dev_stats.iteritems()}
                            json.dump(d, fp, indent=4)

                    # In case of error, and if it is the first one, let's give it a second chance for this task
                    # by re-enqueing it with the same scheduling time.
                    # Re-schedule it after the normal period otherwise (no error or not the first one)
                    if error:
                        if dev_id not in retried:
                            self.log_debug("... second chance given")
                            retried.append(dev_id)
                            period = 0
                        else:
                            self.log_error("[%s] non recovered error : %s", dev_id, error)

                    next_time = polling_start_time + period
                    at(next_time, task)

                    # if we need to calm down successive low level requests, wait a bit before polling next guy
                    if poll_req_interval:
                        self.log_debug('pausing %.1fs before polling next device...', poll_req_interval)
                        time.sleep(poll_req_interval)

            # wait until next checking, if we have not been requested to
            # terminate in the meantime
            if self._terminate:
                break

            elapsed = time.time() - polling_start_time
            remaining_delay = self._task_trigger_checking_period - elapsed
            if remaining_delay > 0:
                time.sleep(remaining_delay)

        self.log_info('terminated')

    def terminate(self):
        """ Notifies the thread that it must terminate."""
        self.log_info('terminate request received')
        self._terminate = True


class PollingThreadError(Exception):
    """ Specialized exception for polling thread errors.
    """
