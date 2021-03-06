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

""" Device configuration broker.

This modules implements a service acting as a provider for the configuration of the device
network used in and application.

Its main function is to keep the current configuration in memory and to provide its items
over D-Bus as requested by client components of the application.
"""

import logging
import json

import dbus.service

import pycstbox.service as service
import pycstbox.devcfg as devcfg
import pycstbox.dbuslib as dbuslib

__author__ = 'Eric PASCUAL - CSTB (eric.pascual@cstb.fr)'

SERVICE_NAME = "ConfigurationBroker"
BUS_NAME = dbuslib.make_bus_name(SERVICE_NAME)
OBJECT_PATH = "/"
SERVICE_INTERFACE = dbuslib.make_interface_name(SERVICE_NAME)

# symbolic constants for changes notification signal.
# Apart when notifying a global change using CFGCHG_GLOBAL, the change type
# is made by concatenating an object type (CFGCHG_OBJ_xx) and and
# operation type (CFGCHG_OP_)

CFGCHG_GLOBAL = '*'
CFGCHG_OBJ_COORDINATOR = 'c'
CFGCHG_OBJ_DEVICE = 'd'
CFGCHG_OP_ADDED = 'a'
CFGCHG_OP_DELETED = 'd'
CFGCHG_OP_UPDATED = 'u'


class ConfigurationBroker(service.ServiceContainer):
    def __init__(self, conn):
        """ Constructor

        Parameters:
            see service.ServiceObject.__init__()
        """
        super(ConfigurationBroker, self).__init__(SERVICE_NAME, conn)

        # we cannot add the service objects at instantiation time since we need
        # us to be fully initialized before for being able to pass them our logger
        self.add_objects([
            (BrokerObject(self._logger), OBJECT_PATH)
        ])


def get_object():
    """Returns the service proxy object of the configuration broker.

    Note that only a single broker is supposed to exist in the system. It is the
    responsibility of the application integrator to ensure this.

    :returns: the requested service instance, if exists
    """
    return dbuslib.get_object(SERVICE_NAME, OBJECT_PATH)


class BrokerObject(dbus.service.Object):
    def __init__(self, logger=None):
        super(BrokerObject, self).__init__()
        self._cfg = devcfg.DeviceNetworkConfiguration(autoload=True)
        self._logger = logger

    def set_logger(self, logger):
        self._logger = logger

    @property
    def ready(self):
        """ Tells if the proxied configuration is ready to be used.

        :rtype: bool
        """
        return self._cfg.is_ready

    @dbus.service.method(SERVICE_INTERFACE, out_signature='b')
    def is_ready(self):
        return self.ready

    @dbus.service.method(SERVICE_INTERFACE, in_signature='s', out_signature='s')
    def get_coordinator(self, c_id):
        """ Returns the properties of a coordinator given its id.

        :param str c_id: the id of the coordinator the device is attached to (ex: x2d1)
        :returns str: JSON representation of the coordinator properties
        """
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug("get_coordinator called with c_id=%s" % c_id)

        result = self._cfg.get_coordinator(c_id).js_ownprops_dict()
        return json.dumps(result)

    @dbus.service.method(SERVICE_INTERFACE, in_signature='ss', out_signature='s')
    def get_device(self, c_id, d_id):
        """ Returns a device given the id of the coordinator it is attached to and its
        own id in this scope.

        :param str c_id: the id of the coordinator the device is attached to (ex: x2d1)
        :param str d_id: the id of the device within its coordinator  (ex: MCX-CH1)
        :returns str: JSON representation of the device properties
        """
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug("get_device called with c_id=%s , d_id=%s" % (c_id, d_id))

        result = self._cfg.get_device(c_id, d_id).js_dict()
        return json.dumps(result)

    @dbus.service.method(SERVICE_INTERFACE, in_signature='s', out_signature='s')
    def get_device_by_uid(self, uid):
        """ Returns a device given its unique id.

        :param str uid:
            the device unique id, composed of the id of the coordinator it is
            attached to, and its own id inside this scope. Both parts are joined
            by a "/" (ex: x2d1/MCX-CH1)

        :returns str: JSON representation of the device properties
        """
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug("get_device called with uid=%s" % uid)

        result = self._cfg.get_device_by_uid(uid).js_dict()
        return json.dumps(result)

    @dbus.service.method(SERVICE_INTERFACE, out_signature='as')
    def get_coordinators(self):
        """ Returns the list of id of the coordinators currently defined
        in the configuration.

        :returns: an array if coordinator ids (string)
        """
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug("get_coordinators called")

        return self._cfg.keys()

    @dbus.service.method(SERVICE_INTERFACE, in_signature='s', out_signature='as')
    def get_coordinator_devices(self, c_id):
        """ Returns the list of id of the devices attached to a given coordinator.

        Note the the returned ids are the "local" ids of the devices and not the
        equivalent unique ids.

        :param str c_id: the id of the coordinator the device is attached to (ex: x2d1)
        :returns: an array if device local ids (string)
        """
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug("get_coordinator_devices called with c_id=%s" % c_id)

        return self._cfg.get_coordinator(c_id).keys()

    @dbus.service.method(SERVICE_INTERFACE, out_signature='s')
    def get_full_configuration(self):
        """ Returns the full configuration data as its JSON representation.
        """
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug("get_full_configuration called")

        return self._cfg.as_json()

    @dbus.service.method(SERVICE_INTERFACE, out_signature='as')
    def get_coordinator_types(self):
        """ Returns the list of registered coordinator types

        :returns: an array of coordinator type (str)
        """
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug("get_coordinator_types called")

        return devcfg.Metadata.coordinator_types()

    @dbus.service.method(SERVICE_INTERFACE, in_signature='s', out_signature='s')
    def get_coordinator_metadata(self, c_type):
        """ Returns the metadata for a given coordinator type.

         :param str c_type: coordinator type
         :returns str: JSON representation of the coordinator metadata
        """
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug("get_coordinator_metadata called with c_type=%s" % c_type)

        return json.dumps(devcfg.Metadata.coordinator(c_type))

    @dbus.service.method(SERVICE_INTERFACE, in_signature='s', out_signature='as')
    def get_device_types(self, c_type):
        """ Returns the list of device types for a given coordinator type.

         :param str c_type: coordinator type
         :returns: an array of device types
        """
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug("get_device_types called with c_type=%s" % c_type)

        return devcfg.Metadata.device_types(c_type)

    @dbus.service.method(SERVICE_INTERFACE, in_signature='s', out_signature='s')
    def get_device_metadata(self, fqdt):
        """ Returns the metadata for a given device fully qualified type.

         :param str fqdt: device fully qualified type (<c_type>:<d_type>)
         :returns: JSON representation of the device metadata
        """
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug("get_device_types called with fqdt=%s" % fqdt)

        return json.dumps(devcfg.Metadata.device(fqdt))

    @dbus.service.method(SERVICE_INTERFACE, in_signature='ss')
    def notify_configuration_change(self, chgtype=CFGCHG_GLOBAL, resid=None):
        """ Emits a "changed" signal.

        See changed() for parameters documentation
        """
        self.changed(chgtype, resid)

    @dbus.service.signal(SERVICE_INTERFACE, signature='ss')
    def changed(self, chgtype, resid):
        """ Notifies a change in the configuration.

        :param chgtype: the type of the change. Can be one of of the CFGCHG_xx constants.
        :param resid: the identifier of the modified resource (see restype documentation). Empty
            in case of a change at the global level
        """
        pass

