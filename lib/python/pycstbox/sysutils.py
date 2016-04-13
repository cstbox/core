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

""" CSTBox system level utilities. """

import os
import re
import subprocess
from collections import namedtuple
import datetime
import pytz
import socket
import json
import time

import pycstbox.log as log

__author__ = 'Eric PASCUAL - CSTB (eric.pascual@cstb.fr)'

_logger = log.getLogger('sysutils')
_logger.setLevel(log.INFO)

ISO_DATE_FORMAT = "%Y-%m-%d"

CSTBOX_HOME = os.environ.get('CSTBOX_HOME', '/opt/cstbox')
CSTBOX_BIN_DIR = os.path.join(CSTBOX_HOME, 'bin')
CSTBOX_LIB_DIR = os.path.join(CSTBOX_HOME, 'lib/python')
CSTBOX_VERSION_DIR = os.path.join(CSTBOX_HOME, 'version')
CSTBOX_HOSTNAME = socket.getfqdn()

tz_UTC = pytz.UTC
tz_PARIS = pytz.timezone('Europe/Paris')

DEV_NULL = open(os.devnull)


def str_2_bool(s):
    """ Parses a boolean value provided as a string and returns it.

    Accepted values for True:

        true, t, yes, y, 1

    Any other value is converted as False
    """
    if not s:
        return False
    return s.lower() in ('true', 't', 'yes', 'y', '1')

_period_re = re.compile(r'^([\d]+)([smh]?)$')
_tod_re = re.compile(r'^(?P<hours>[\d]+):(?P<minutes>[\d]+)(:(?P<seconds>[\d]+))?')


def parse_period(s):
    """ Parses a period provided as a string and returns the equivalent
    number of seconds.

    The accepted format is:

        <nn> [ 's' | 'm' | 'h' ]

    with:

        <nn> : a positive integer value

    The suffix (if provided) indicates the units, with the following
    convention:

        's' : seconds
        'm' : minutes
        'h' : hours

    If not provided, units are defaulted to seconds.

    :returns: the corresponding number of seconds. If the parameter is None or an empty string, 0 is return.
    :raises ValueError: if input string is not valid
    """
    if not s:
        return 0

    m = _period_re.match(s)
    if m:
        value = int(m.group(1))
        unit = m.group(2)
        if unit in ('', 's'):
            period = value
        elif unit == 'm':
            period = value * 60
        elif unit == 'h':
            period = value * 3600
        return period

    else:
        raise ValueError('invalid period value (%s)' % s)


LocalTimeUnits = namedtuple('LocalTimeUnits', 'hour minute second')

_time_units_i18n = {
    'en': LocalTimeUnits(('hour', 'hours'), ('minute', 'minutes'), ('second', 'seconds')),
    'fr': LocalTimeUnits(('heure', 'heures'), ('minute', 'minutes'), ('seconde', 'secondes')),
}


def human_friendly_delay_format(secs, lang="en"):
    """ Returns a human friendly formatted string corresponding to the number of seconds.

    Multiples (minutes, hours,...) will be used to render the value the friendliest possible.

    :param int secs: the delay in seconds
    :param str lang: language code
    :return: a string such as "2 hours 12 minutes 5 seconds"
    """
    secs = int(secs)

    hours = int(secs / 3600)
    secs -= hours * 3600
    minutes = int(secs / 60)
    secs -= minutes * 60

    trans = _time_units_i18n.get(lang, _time_units_i18n['en'])

    s = []
    if hours:
        s.append('%d %s' % (hours, trans.hour[hours > 1]))
    if minutes:
        s.append('%d %s' % (minutes, trans.minute[minutes > 1]))
    if secs:
        s.append('%d %s' % (secs, trans.second[secs > 1]))

    return ' '.join(s)


def parse_time_of_day(s):
    """ Parses a string representing a (possibly abbreviated) time of day and returns the corresponding
    `datetime.time` instance.

    Parsed string must be expressed in 24 hours format, and must contains at least hours and minutes. If not
    present, seconds are defaulted to 0. Fields are separated by colons.

    :param str s: the string to be parsed
    :return: the corresponding time of day
    :rtype: datetime.time
    :raise: ValueError if the parsed string is not a valid time of day
    """
    if not s or s.isspace():
        raise ValueError('empty or blank argument')

    m = _tod_re.match(s + ":00")
    if m:
        fields = [int(m.group(g)) for g in ('hours', 'minutes', 'seconds')]
        return datetime.time(*fields)

    else:
        raise ValueError('invalid time of day (%s)' % s)


def time_in_span(t, start, end):
    """ Returns if a given time of day is in the span defined by two bounds.

    The following rule are applied, depending on t0 is before or after t1 :
    * t0 < t1 : returns True if t0 <= t <= t1
    * t0 > t1 : returns True if t >+ t0 or t <= t1

    The second case corresponds to an overnight time span.

    :param datetime.time t: tested time of day
    :param datetime.time start: span starting time of day
    :param datetime.time end: span ending time of day
    :return: True if t in the time span
    :rtype: boolean
    :raise ValueError: if any of the parameters is invalid of of t0 == t1
    """
    if start == end:
        raise ValueError("bounds cannot be equal")
    elif start < end:
        return start <= t <= end
    else:
        return t >= start or t <= end


def to_milliseconds(ts):
    """ Returns the milliseconds equivalent of a given time stamp.

    If the parameter is a datetime instance, the result is the number of milliseconds elapsed
    from the epoch. The passed datetime is supposed to be naive or UTC.

    If it is provided as an integer, it is just returned as is since supposed to be already converted.

    :param datetime.datetime ts: time stamp
    :return: equivalent milliseconds from Epoch
    :rtype: long
    """
    if isinstance(ts, datetime.datetime):
        delta = ts - datetime.datetime.utcfromtimestamp(0)
        ts = long(delta.total_seconds() * 1000)
    elif isinstance(ts, datetime.date):
        delta = datetime.datetime(ts.year, ts.month, ts.day) - datetime.datetime.utcfromtimestamp(0)
        ts = long(delta.total_seconds() * 1000)
    return ts


def tod_to_num(dt):
    """ Returns a numeric version of a time of day, using the formula :
    result = 10000 * hour + 100 * minute + second + microsecond / 1000000.

    :param dt: a datetime of time
    :return: the numeric "equivalent" of the time of day
    :rtype: float
    """
    return dt.hour * 10000 + dt.minute * 100 + dt.second + dt.microsecond / 1000000.


def day_start_time(day):
    """ Returns the naive datetime of the beginning of a given day (i.e. hour, minute,... set to 0)

    :param datetime.date day: the day for which we want the start time
    :return: the very first moment of the given day (as a UTC date time)
    :rtype: datetime
    """
    return datetime.datetime(day.year, day.month, day.day)


def day_end_time(day):
    """ Returns the naive datetime of the beginning of a given day (i.e. 1 epsilon time before the beginning
    of next day)

    :param datetime.date day: the day for which we want the end time
    :return: the very last second of the given day (as a naive date time)
    :rtype: datetime.datetime
    """
    return datetime.datetime(day.year, day.month, day.day) + datetime.timedelta(days=1, microseconds=-1)


def day_bounds(day):
    """
    :param datetime.date day: the day for which we want the bounds
    :return: a tuple containing the start and end times of the given day as naive datetime
    :rtype: tuple of [datetime.datetime]
    """
    return day_start_time(day), day_end_time(day)


def ts_to_datetime(msecs, tz=tz_UTC):
    """ Returns a non naive datetime from the equivalent milliseconds count.

    If not specified, the time zone is set to UTC.

    The function is tolerant and accepts an already converted datetime or date.
    If it is not naive, it is adjusted to the requested time zone. If it is naive,
    its time zone is set to the supplied one.

    :param int msecs: input time, supposed to be a number of milliseconds
    :param datetime.tzinfo: the timezone of the returned datetime
    :return: the equivalent UTC datetime
    :rtype: datetime.datetime
    """
    if isinstance(msecs, (datetime.datetime, datetime.date)):
        if isinstance(msecs, datetime.datetime):
            dt = msecs  # just rename it so that the code is more "natural" to read
            if dt.tzinfo:
                # non naive datetime => shift its time zone
                return dt.astimezone(tz)
            else:
                # naive datetime => set its time zone
                return dt.replace(tzinfo=tz)

        return msecs

    else:
        return datetime.datetime.fromtimestamp(msecs / 1000., tz=tz)


def string_to_lines(s):
    """ Given a string containing lines separated by newlines, returns
    the equivalent list of strings, stripping the spaces in excess at
    both ends.

    :param str s: the concatenated lines as a string
    :return: the concatenated lines as a list
    :rtype: list of [str]
    """
    s = s.strip()
    return [line.strip() for line in s.split('\n') if line]


ServiceInformation = namedtuple('ServiceInformation', 'descr core running')
""" Service descriptor namedtuple.

.. py:attribute:: descr

    service short description

.. py:attribute:: core

    flag telling if it is a core service (not user manageable) or not

.. py:attribute:: running

    flag telling if the service is currently active or not
"""

ServiceProperties = namedtuple('ServiceProperties', 'descr core')
""" Service properties namedtuple.

Is a subset of :py:class:`ServiceInformation`
"""


class ServicesManager(object):
    """ Mimics what is provided by the Linux 'service' command, applied to the
    CSTBox context."""

    PIDFILES_DIR = '/var/run/cstbox'
    PIDFILE_PATTERN = r'cstbox-(.*)\.pid'
    PIDFILE_FORMAT = 'cstbox-%s.pid'

    INIT_SCRIPTS_DIR = '/etc/init.d'
    INIT_SCRIPT_PATTERN = r'cstbox-(.*)'
    INIT_SCRIPT_FORMAT = 'cstbox-%s'

    def __init__(self):
        self._re_pidfiles = re.compile(self.PIDFILE_PATTERN)
        self._re_scripts = re.compile(self.INIT_SCRIPT_PATTERN)
        self._logger = _logger.getChild('svcmgr')

        self._svcs = {}
        for f in [f for f in os.listdir(self.INIT_SCRIPTS_DIR)
                  if self._re_scripts.match(f)]:
            svc_name = self._servicename_of(f)
            self._svcs[svc_name] = self._get_service_props(svc_name)

        self._logger.info('known services: %s', self._svcs)

    @property
    def known_services(self):
        """ Returns the list of services currently installed.

        Service names are returned in their shortened form, without the
        "cstbox-" prefix.
        """
        return self._svcs.keys()

    def running_services(self):
        """ Returns the list of currently running CSTBox services.

        Same remark as for known_services() method applies here with respect
        to the returned names.
        """
        svcs = []
        for f in [f for f in os.listdir(self.PIDFILES_DIR)
                  if self._re_pidfiles.match(f)]:
            svcs.append(self._servicename_of(f))

        return svcs

    def _pidfile_of(self, svc_name):
        """ Takes a service short name and returns the full path of the
        associated pid file (if used). """
        return os.path.join(self.PIDFILES_DIR, (self.PIDFILE_FORMAT % svc_name))

    def _scriptname_of(self, svc_name):
        """ Takes a service short name and returns the full path of the
        associated init script file. """
        return self.INIT_SCRIPT_FORMAT % svc_name

    def _servicename_of(self, fname):
        """ Takes the name of the path of a script or pid file, and returns the
        short name of the corresponding service. """
        fname = os.path.basename(fname)
        # try first as a pid file
        m = self._re_pidfiles.match(fname)
        if m:
            return m.groups()[0]
        else:
            # try as a init script file
            m = self._re_scripts.match(fname)
            if m:
                return m.groups()[0]
            else:
                return None

    def _get_service_props(self, svc_name):
        """ Returns the properties (as a dictionary) of a given service.

        See definition of ServiceProperies named tuple for list of contained
        fields.
        """
        descr, core = '', False
        searched_props = 2

        script = os.path.join(self.INIT_SCRIPTS_DIR, self._scriptname_of(svc_name))
        for line in file(script, 'rt'):
            if line.startswith('CORE_SVC='):
                core = str_2_bool(line.strip().split('=')[1])
                searched_props -= 1
            elif line.startswith('DESC='):
                descr = line.strip().split('=')[1].strip('"')
                searched_props -= 1
            if searched_props == 0:
                break
        return ServiceProperties(descr, core)

    @staticmethod
    def _checkroot():
        """ Checks if the current user is root, and raises an exception if not."""
        if os.getuid() != 0:
            raise ServicesManagerError('action requires root privileges')

    def _make_service_info(self, svc_name):
        """ Builds an instance of ServiceInformation named tuple, using the
        service name to retrieve the values ."""
        props = self._svcs[svc_name]
        pid_file = self._pidfile_of(svc_name)
        if os.path.exists(pid_file):
            pid = file(pid_file).readline().strip()
            is_running = subprocess.call(["ps", "-p", pid], stdout=DEV_NULL) == 0
        else:
            is_running = False

        return ServiceInformation(props.descr, props.core, is_running)

    def get_service_info(self, svc_name=None):
        """ Returns the information about a given service, or about all
        installed services.

        The returned information are packed in a ServiceInformation named tuple,

        If a service name is passed, the result is a single tuple. If non no
        parameter is passed, the result is a dictionary containing the
        information about all installed services, keyed by the service name.

        :param str svc_name:
            the name of the service which information is asked for. If not
            given, information about all installed services are returned

        :returns:
            a ServiceInformation instance for the requested service, or a
            dictionary ServiceInformation instances for a parameterless call

        :raises ValueError: if a given service is requested but does not exist
        """
        if svc_name:
            if svc_name in self.known_services:
                return self._make_service_info(svc_name)
            else:
                raise ValueError('unknown service : %s' % svc_name)

        else:
            result = dict([
                (svc, self._make_service_info(svc)) for svc in self.known_services
            ])
            return result

    def _start_stop_service(self, svc_name, action):
        """ Internal method factoring services start and stop common sequence
        :param str svc_name: the name of the service
        :param action: the action ('start', 'stop' or 'restart')
        """
        if not svc_name:
            raise ValueError('missing mandatory parameter')
        if action not in ('start', 'stop', 'restart'):
            raise ValueError('invalid action (must be "start", "stop" or "restart"')

        self._checkroot()
        try:
            script = self._scriptname_of(svc_name)
            self._logger.info('executing command : service %s %s', script, action)
            subprocess.check_output(
                [os.path.join(self.INIT_SCRIPTS_DIR, script), action],
                stderr=subprocess.STDOUT
            )
        except subprocess.CalledProcessError as e:
            raise ServicesManagerError(
                'cannot %s service %s (%s)' %
                (action, svc_name, e.output.split('\n')[1].strip())
            )

    def start(self, svc_name):
        """ Starts a given service.

        :param str svc_name: the name of the service
        :raises ServicesManagerError: if the 'service start' command fails
        """
        self._start_stop_service(svc_name, 'start')

    def stop(self, svc_name):
        """ Stops a given service.

        :param str svc_name: the name of the service
        :raises ServicesManagerError: if the 'service stop' command fails
        """
        self._start_stop_service(svc_name, 'stop')

    def restart(self, svc_name):
        """ Restarts a given service.

        :param str svc_name: the name of the service
        :raises ServicesManagerError: if the 'service restart' command fails
        """
        self._start_stop_service(svc_name, 'restart')

    @staticmethod
    def _issue_command(command):
        ServicesManager._checkroot()
        try:
            subprocess.check_output(command, shell=True)
        except subprocess.CalledProcessError as e:
            raise ServicesManagerError(json.dumps({
                "cmde": command,
                "returncode": e.returncode,
                "ouput": e.output
            }))

    @staticmethod
    def application_layer_restart():
        """ Restarts only the application layer services."""
        ServicesManager._issue_command("%s restart --applayer" % os.path.join(ServicesManager.INIT_SCRIPTS_DIR, 'cstbox'))

    @staticmethod
    def cstbox_restart():
        """ Restarts all CSTBox services, including the core ones.

        We don't use the restart sub-command, since it seems to create race conditions
        on really slow CPUs.
        """
        init_script_path = os.path.join(ServicesManager.INIT_SCRIPTS_DIR, 'cstbox')
        ServicesManager._issue_command("%s stop" % init_script_path)
        # let is go down quietly
        time.sleep(5)
        # bring it back up
        ServicesManager._issue_command("%s start" % init_script_path)

    @staticmethod
    def system_reboot():
        """ Reboots the whole Linux system."""
        ServicesManager._issue_command("/sbin/reboot now")


def get_services_manager():
    """ Poor man's singleton implementation, since it does not forbid to
    use ServicesManager() in your code.

    But we are all adults here, and the ServicesManager is not intended to be
    used by application integrators. Don't go with over-design if we can do
    without ;)
    """
    try:
        return get_services_manager.instance
    except AttributeError:
        get_services_manager.instance = ServicesManager()
        return get_services_manager.instance


class ServicesManagerError(Exception):
    """ Specialized error for CSTBox services management.
    """
    pass


def checked_dir(path):
    """ Internal helper for checking if the given path exists and is a
    directory.

    If not, raises a ValueError exception. If yes, return the corresponding
    absolute path.
    """
    if not os.path.exists(path):
        raise ValueError("path not found : %s" % path)
    if not os.path.isdir(path):
        raise ValueError("path is not a directory : %s" % path)
    return path


def to_unicode(s):
    """ Converts a string to unicode if needed.
    """
    if isinstance(s, unicode):
        return s
    elif isinstance(s, str):
        return s.decode('utf-8')
    else:
        raise TypeError()


def symbol_for_name(fqdn):
    """ Returns the symbol (class, def, module variable,...) which fully qualified name is passed.

    :param str fqdn: the fully qualified name of the symbol
    :return: the corresponding symbol, if found
    :rtype: Any
    :raises ImportError: if the package name could not be imported
    :raises NameError: if no symbol with the given name is not defined in the package
    """
    if not fqdn:
        raise ValueError('empty value passed to symbol_for_name')

    module_name, _, symbol_name = fqdn.rpartition('.')
    if not module_name or not symbol_name:
        raise ValueError("fqdn is not fully qualified (%s)" % fqdn)

    import importlib
    try:
        module = importlib.import_module(module_name)
        return getattr(module, symbol_name)

    except AttributeError:
        raise NameError("name '%s' is not defined" % fqdn)


SystemInformation = namedtuple('SystemInformation', 'version mem_usage disk_usage')
SystemVersion = namedtuple('SystemVersion', 'kernel arch')


class UsageStats(object):
    def __init__(self, total, used):
        self.total = total
        self.used = used
        self.free = total - used
        self.percent = round(float(used) / float(total) * 100., 1)


def get_system_info():
    """ Returns system indicators.

    Use direct system resources instead of using some cross-platform
    module such as `psutil`. A very good module, but overkill here.

    .. IMPORTANT::
        Works on Linux only, but since CSTBox is made for Linux only,
        this should not be a problem.

    Memory and disk space are given in Mbytes. Percentages are rounded
    to one decimal.

    :return:
        a SystemInformation instance
    """
    statvfs = os.statvfs('/')
    disk_total = statvfs.f_bsize * statvfs.f_blocks / 1024 / 1024
    disk_used = statvfs.f_bsize * (statvfs.f_blocks - statvfs.f_bfree) / 1024 / 1024

    output = subprocess.check_output('free -m', shell=True).split('\n')
    # extract the total memory from the first stats line
    mem_total = int(output[1].split(':')[1].split()[0])
    # extract values from the line "-/+ buffers/cache"
    mem_used = int(output[2].split(':')[-1].split()[0])

    uname = os.uname()

    return SystemInformation(
        SystemVersion(uname[2], uname[4]),
        UsageStats(mem_total, mem_used),
        UsageStats(disk_total, disk_used)
    )


ModuleVersion = namedtuple('ModuleVersion', 'version date')


def get_module_versions():
    """ Returns the version of the CSTBox modules.

    :return: a dictionary containing the version of each installed module
    :rtype: dict
    """
    versions = {}
    for f in os.listdir(CSTBOX_VERSION_DIR):
        version_file_path = os.path.join(CSTBOX_VERSION_DIR, f)
        version_info = file(version_file_path).readline().strip().split(' ', 1)
        if len(version_info) > 1:
            version, date = version_info
        else:
            version = version_info[0]
            date = datetime.datetime.fromtimestamp(os.path.getmtime(version_file_path)).strftime("%Y-%m-%d %H:%M:%S")
        versions[f] = ModuleVersion(version, date)
    return versions


_evtmgr = None

SVC_UNKNOWN, SVC_STOPPED, SVC_STARTING, SVC_RUNNING, SVC_STOPPING, SVC_ABORTING = range(6)
SVC_EVENT_VAR_TYPE = 'svcevt'
SVC_STATE_NAMES = {
    SVC_UNKNOWN: "unknown",
    SVC_STOPPED: "stopped",
    SVC_STARTING: "starting",
    SVC_RUNNING: "running",
    SVC_STOPPING: "stopping",
    SVC_ABORTING: "aborting"
}


class CSTBoxError(Exception):
    """ Root class of CSTBox specialized exceptions """


def emit_service_state_event(svc_name, state):
    _logger.debug("emit_service_state_event(%s, %s)", svc_name, state)

    from pycstbox import evtmgr

    # don't try to emit events for the event manager (egg and chicken problem)
    if svc_name == evtmgr.SERVICE_NAME:
        return

    if state not in SVC_STATE_NAMES:
        raise ValueError('invalid service state (%s)' % state)

    global _evtmgr
    if not _evtmgr:
        _evtmgr = evtmgr.get_object(evtmgr.FRAMEWORK_EVENT_CHANNEL)

    if not _evtmgr:
        _logger.error('service state event not emitted : unable to get event manager service')
        return False

    _evtmgr.emitEvent(SVC_EVENT_VAR_TYPE, svc_name, json.dumps({'state': state, "state_str": SVC_STATE_NAMES[state]}))
