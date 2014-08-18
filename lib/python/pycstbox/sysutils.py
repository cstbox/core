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

__author__ = 'Eric PASCUAL - CSTB (eric.pascual@cstb.fr)'

import os
import re
import subprocess
from collections import namedtuple
import datetime

import pycstbox.log as log
_logger = log.getLogger('sysutils')


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

    If the parameter is a datetime instance, the result is the number of milliseconds elapsed from the epoch.
    If it is provided as an integer, it is just returned as is since supposed to be already converted.

    :param datetime ts: time stamp
    :return: equivalent milliseconds from Epoch
    """
    if isinstance(ts, datetime.datetime):
        delta = ts - datetime.datetime.utcfromtimestamp(0)
        ts = delta.total_seconds() * 1000
    return ts


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

        self._svcs = {}
        for f in [f for f in os.listdir(self.INIT_SCRIPTS_DIR)
                  if self._re_scripts.match(f)]:
            svc_name = self._servicename_of(f)
            self._svcs[svc_name] = self._get_service_props(svc_name)

        _logger.debug('known services: %s', self._svcs)

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
        return ServiceInformation(
            props.descr,
            props.core,
            os.path.exists(self._pidfile_of(svc_name))
        )

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

    def start(self, svc_name):
        """ Starts a given service.

        :param str svc_name: the name of the service
        :raises ServicesManagerError: if the 'service start' command fails
        """
        if not svc_name:
            raise ValueError('missing mandatory parameter')

        self._checkroot()
        try:
            subprocess.check_output(
                ['/usr/bin/service', self._scriptname_of(svc_name), 'start'],
                stderr=subprocess.STDOUT
            )
        except subprocess.CalledProcessError as e:
            raise ServicesManagerError(
                'cannot start service %s (%s)' %
                (svc_name, e.output.split('\n')[1].strip())
            )

    def stop(self, svc_name):
        """ Stops a given service.

        :param str svc_name: the name of the service
        :raises ServicesManagerError: if the 'service stops' command fails
        """
        if not svc_name:
            raise ValueError('missing mandatory parameter')

        self._checkroot()
        try:
            subprocess.call(
                ['/usr/bin/service', self._scriptname_of(svc_name), 'stop'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        except subprocess.CalledProcessError as e:
            raise ServicesManagerError(
                'cannot stop service %s (%s)' %
                (svc_name, e.output.split('\n')[1].strip())
            )

    @staticmethod
    def application_layer_restart():
        """ Restarts only the application layer services."""
        ServicesManager._checkroot()
        subprocess.Popen(
            ['/usr/bin/service', 'cstbox', 'restart', '--applayer'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

    @staticmethod
    def cstbox_restart():
        """ Restarts all CSTBox services, including the core ones."""
        ServicesManager._checkroot()
        subprocess.Popen(
            ['/usr/bin/service', 'cstbox', 'restart'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

    @staticmethod
    def system_reboot():
        """ Reboots the whole Linux system."""
        ServicesManager._checkroot()
        subprocess.Popen(
            ['/sbin/reboot', 'now'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )


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

