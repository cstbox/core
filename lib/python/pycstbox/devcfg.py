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

""" Devices network configuration data access tools.

The configuration data are stored as a single JSON file, which default path
is **/etc/cstbox/devices.cfg**.
"""

import json
import os

__author__ = 'Eric PASCUAL - CSTB (eric.pascual@cstb.fr)'


DEFAULT_PATH = '/etc/cstbox/devices.cfg'
METADATA_HOME = os.path.join(os.path.dirname(__file__), "devcfg.d")


class ConfigurationParms(object):
    """ Names of the parameters used in the configuration file.
    """
    COORDINATORS_SECTION = 'coordinators'
    COORDINATOR_PORT = 'port'

    DEVICES_SECTION = 'devices'

    DEVICE_ROOT_SECTION = 'root'
    DEVICE_OUTPUTS_SECTION = 'outputs'
    DEVICE_INPUTS_SECTION = 'inputs'
    DEVICE_CONTROLS_SECTION = 'controls'

    PROPERTY_DEFINITIONS = 'pdefs'

    ENABLED = 'enabled'
    VAR_NAME = 'varname'
    ADDRESS = 'address'
    TYPE = 'type'
    DELTA_MIN = 'delta_min'
    POLL_PERIOD = 'polling'
    POLL_REQUESTS_INTERVAL = 'poll_req_interval'
    LOCATION = 'location'
    EVENTS_TTL = 'events_ttl'
    DEFAULT_VALUE = 'defvalue'


class DeviceNetworkConfiguration(dict):
    """ Abstraction class providing the access to the devices network
    configuration data.

    It is an extended dictionary, containing the collection of the
    coordinators and attached devices, with safe manipulation methods
    """

    def __init__(self, path=DEFAULT_PATH, autoload=False, logger=None):
        """
        :param str path:
            the path of the root dir under which are stored the
            configuration data.
            Default value : as specified by DEFAULT_PATH module variable

        :raises ValueError:
            if invalid value passed (None, empty, existing path but
            not pointing to a valid file,...)
        """
        dict.__init__(self)

        if not path:
            raise ValueError("path cannot be None or empty")
        if os.path.exists(path) and not os.path.isfile(path):
            raise ValueError("path is not a file : %s" % path)
        self._path = path

        self._logger = logger

        if autoload:
            self.load()

    @property
    def path(self):
        """ The path of the configuration file. """
        return self._path

    def load(self, path=None):
        """ Loads the configuration data from a file.

        :param str path:
            the path of the configuration file
            (default: as defined at instantiation time)

        :raises ValueError:
            if data are not valid
        """

        if not path:
            path = self._path

        if self._logger:
            self._logger.info("loading configuration from '%s'", path)

        with open(path, 'r') as f:
            try:
                cfg = json.load(f)
                if type(cfg) is not dict:
                    raise Exception('data must be a valid dictionary')
            except Exception as e:
                if self._logger:
                    self._logger.exception(e)
                raise ValueError('invalid device configuration file (%s)' % str(e))
            else:
                self.load_dict(cfg)

    def load_str(self, s):
        """ Loads the configuration date from a string containing the JSON
        serialization of the configuration.
        """
        if not s:
            raise ValueError()

        try:
            cfg = json.loads(s)
            if type(cfg) is not dict:
                raise Exception('data must be a valid dictionary')
        except Exception as e:
            if self._logger:
                self._logger.exception(e)
            raise ValueError('invalid device configuration data (%s)' % str(e))
        else:
            self.load_dict(cfg)

    def load_dict(self, cfg):
        """ Load the configuration data from a dictionary.

        The passed dictionary must conform to the following structure, where
        each level is a dictionary and optional parts are indicated
        by square brackets:

        - coordinators/
            - <coord_uid>/
                - type
                - [custom props if required]
                - devices/
                    - <device_uid>/
                        - type
                        - address
                        - location
                        - [custom props if required]
        - [configuration level custom props if required]

        If the device is not a single endpoint, relevant sub-dictionaries
        must exist, keyed by 'outputs' or 'controls' depending on the
        endpoint nature. Endpoint definition is device type dependent.

        :param dict cfg:
                the configuration data as a dictionary
        """
        self.clear()

        # load configuration global attributes (ie those not keyed by
        # "coordinators")
        for k, v in [(k, v) for (k, v) in cfg.iteritems() if k != ConfigurationParms.COORDINATORS_SECTION]:
            setattr(self, k, v)

        # load the coordinators
        for cid, cdata in cfg[ConfigurationParms.COORDINATORS_SECTION].iteritems():
            # instantiate a coordinator, passing it all the extra attributes
            # stored in the configuration if any
            attrs = dict([(k, v) for k, v in cdata.iteritems() if k != ConfigurationParms.DEVICES_SECTION])
            coord = Coordinator(cid, **attrs)   #pylint: disable=W0142

            # load the devices attached to the coordinator
            devices = cdata[ConfigurationParms.DEVICES_SECTION]
            for did, ddata in devices.iteritems():
                d = Device(did, **ddata)        #pylint: disable=W0142
                coord.add_device(d)

            self.add_coordinator(coord)

        if self._logger:
            self._logger.info('--> success')

    def store(self, path=None):
        if not path:
            path = self._path
        with open(path, 'w') as f:
            f.write(self.as_json(formatted=True))

    def as_json(self, formatted=False):
        return json.dumps(dict(
            [(k, v) for (k, v) in self.__dict__.iteritems() if not k.startswith('_')] +
            [
                (ConfigurationParms.COORDINATORS_SECTION, dict([(uid, c.js_dict()) for (uid, c) in self.iteritems()]))
            ]
        ), indent=(4 if formatted else 0))

    def as_tree(self, _sorted=False):
        tree = {}
        for (cid, devs) in [(k, v.keys()) for (k, v) in self.iteritems()]:
            if _sorted:
                devs.sort()
            tree[cid] = devs
        return tree

    def __setitem__(self, key, value):
        if not isinstance(value, Coordinator):
            raise TypeError("value must be an instance of Coordinator")
        dict.__setitem__(self, key, value)

    def get_coordinator(self, c_id):
        """ Returns a coordinator by its id.

        This is just an alias of the inherited dictionary item retrieval operator,
        but it can be more explicit like this in user's code, since similar to
        get_device call.
        """
        return self[c_id]

    def add_coordinator(self, c):
        """ Adds a coordinator to the configuration

        :param Coordinator c:
            the coordinator to be added

        :raises DuplicatedCoordinator:
            if instance is not a valid coordinator, of if it exists already
        """
        c.check()
        uid = c.uid
        if uid in self:
            raise DuplicatedCoordinator(uid)
        self[uid] = c

    def del_coordinator(self, c_id):
        """ Deletes the coordinator and its devices.

        :param str c_id:
            the id of coordinator to be deleted

        :raises KeyError: if coordinator does not exist
        """
        del self[c_id]

    def add_device(self, c, d):
        """ Adds a device to a coordinator.

        :param Coordinator/str c:
            the coordinator instance, or its id
        :param Device d:
            the device instance

        :raises ValueError: if the device is not valid
        """
        d.check()
        if isinstance(c, basestring):
            c = self[c]
        c.add_device(d)

    def get_device(self, c, d_id):
        """ Returns a device, knowing its parent and its local id.

        :param Coordinator/str c:
            the coordinator instance, or its id
        :param str d_id:
            the id of the device within this coordinator

        :raises KeyError: if not found
        """
        if isinstance(c, basestring):
            c = self[c]
        return c[d_id]

    def get_device_by_uid(self, uid):
        """ Returns a device, knowing its parent and its unique id.

        The unique id is something like the absolute path of a file.
        It is composed of the id of the parent coordinator, concatenated
        with the id of the device itself.

        :param str uid:
            the unique id of the device (<coord_id> '/' <dev_id>)

        :raises ValueError: if the id is not valid
        :raises KeyError: if not found
        """

        c_id, d_id = DevCfgObject.split_uid(uid)
        c = self[c_id]
        return c[d_id]

    def del_device(self, c, d):
        """ Deletes a device.

        It is removed from the parent coordinator, and its storage is deleted
        too.

        :param Coordinator/str c:
            the coordinator instance, or its id
        :param Device d:
            the device instance
        """
        if isinstance(c, basestring):
            c = self[c]
        c.del_device(d)

    def del_device_by_uid(self, uid):
        """ Deletes a device.

        :param str uid:
            the unique id of the device (<coord_id> '/' <dev_id>)
        """
        c_id, d_id = DevCfgObject.split_uid(uid)
        c = self[c_id]
        c.del_device(d_id)

    def rename_device(self, uid, newid):
        """ Changes the id of a device.

        :params str uid :
            the unique id of the device (<coord_id> '/' <dev_id>)

        :params str newid:
            the new device local id (ie without the coord_id part)

        :raises DuplicatedDevice: if the new id already exists
        """
        c_id, d_id = DevCfgObject.split_uid(uid)
        c = self[c_id]

        if newid in c:
            raise DuplicatedDevice(newid)

        d = c[d_id]
        c.del_device(d_id)
        c[newid] = d


class Metadata(object):
    """ This class bundles static methods working at the global level. They
    could have just been top-level functions, but it seemed cleaner to packaged
    them in a well identified structure.
    """

    _DIR_EXT = '.d'

    @staticmethod
    def _coordinator_dir(c_type):
        """ Internal method returning the path of the directory containing the metadata
        files of devices managed to a given coordinator type. """
        return os.path.join(METADATA_HOME, c_type + Metadata._DIR_EXT)

    @staticmethod
    def _device_path(fqdt):
        """ Internal method returning the full path of the file containing the metadata for
        a given fully qualified device type.

        :param str or tuple fqdt:
            Fully qualified device type, which can be either :
            - a string in which the coordinator type and the device type are joined by
            a colon (ex: 'x2d:minicox')
            - a tuple containing these two components (ex: ('x2d', 'minicox'))
        """
        c_type, d_type = Metadata._devicetypename_to_components(fqdt)
        return os.path.join(Metadata._coordinator_dir(c_type), d_type)

    @staticmethod
    def _devicetypename_to_components(arg):
        """ Return the FQDT as a tuple containing its components, by parsing its string form.

        In case a tuple is already provided, it is returned as is. Any other form raises a
        ValueError exception.
        """
        if isinstance(arg, basestring):
            return arg.split(':', 1)
        elif type(arg) is tuple:
            return arg
        else:
            raise ValueError(arg)

    @staticmethod
    def coordinator_types():
        """ Returns the list of known coordinator types. """
        res = []
        for n in [n for n in os.listdir(METADATA_HOME) if not n.startswith('.')]:
            if os.path.isfile(os.path.join(METADATA_HOME, n)):
                res.append(n)
        return res

    @staticmethod
    def coordinator(c_type):
        """ Returns the metadata for a given coordinator type.

        :raises ValueError: if not available
        """
        path = os.path.join(METADATA_HOME, c_type)
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
        else:
            raise ValueError('unknown coordinator type (%s)' % c_type)

    @staticmethod
    def device_types(c_type):
        """ Returns the device types supported by a given coordinator type.

        :param str c_type: the coordinator type
        :returns: the (maybe empty) list of supported device types
        :raises ValueError: if unknown coordinator type
        """
        res = []
        for d_type in [
            n for n in os.listdir(Metadata._coordinator_dir(c_type))
                if not n.startswith('.')]:
            res.append(c_type + ':' + d_type)
        return res

    @staticmethod
    def device(fqdt):
        """ Returns the metadata for a given device.

        :param str or tuple fqdt:
            fully qualified device type
            (see ``_device_path`` documentation for details)

        :returns: the device metadata as a dictionary
        :raises ValueError: if unknown device type
        :raises InvalidCfgFile: if device metadata file has errors
        """
        path = Metadata._device_path(fqdt)
        if not os.path.exists(path):
            raise DeviceTypeNotFound(fqdt)
        with open(path, 'r') as f:
            try:
                return json.load(f)
            except ValueError as e:
                raise InvalidCfgFile(f.name, e)


class DevCfgObject(object):
    """ Base class for all device configuration objects

    It manages integrity checking by providing a method ensuring that all
    required attributes are defined. The list is defined by the class
    attribute _required_attrs, which can be overridden in descendants.

    It also provides a generic JSON serialization mechanism, managing not
    persisted attributes.
    """
    _transients = ['uid']
    _required_attrs = ['uid']

    def __init__(self, uid):
        """
        :param str uid: the id of the object (cannot be None or empty)
        :raises ValueError: if arguments not valid
        """
        if not uid:
            raise ValueError('uid is mandatory')
        self.uid = uid

    def __str__(self):
        return str(self.__dict__)

    @classmethod
    def required_attrs(cls):
        """ Returns the list of the required attributes, which must thus be
        present in the configuration data as keys in the dictionary describing
        the object.
        """
        return cls._required_attrs

    def check(self):
        """ Check that all required attributes are defined.

        Their list is defined by the class attribute _requited_attrs

        :raises ValueError: if at least one attribute is missing
        """
        for a in self._required_attrs:
            if not hasattr(self, a):
                raise MissingAttribute(a)

    def js_dict(self):
        """ JSON serializer for DevCfgObject's and descendant.
        (see json package documentation for details about custom serializers)

        :returns:
            a dictionary containing the attributes to be persisted. Transient
            (ie not persisted) ones are defined by the class attribute
            _transient
        """
        return dict([(k, v) for (k, v) in self.__dict__.iteritems()
                     if k not in self._transients])

    @staticmethod
    def make_uid(c_id, d_id):
        return '/'.join((c_id, d_id))

    @staticmethod
    def split_uid(uid):
        return uid.split('/')


class Coordinator(DevCfgObject, dict):
    """ Network coordinator model

    The coordinator has devices attached to it. It is implemented as a typed
    dictionary, augmented with convenience methods.

    Required attributes :
        - type
    """

    _required_attrs = DevCfgObject._required_attrs + ['type']

    def __init__(self, uid, **kwargs):
        """
        :param str uid: (see :py:class:`DevCfgObject`)
        :param kwargs: optional complementary named parameters
        """
        dict.__init__(self)
        DevCfgObject.__init__(self, uid)
        for k in kwargs:
            setattr(self, k, kwargs[k])

    def __str__(self):
        return '%s(%s)' % (self.uid, self.type)

    def __setitem__(self, key, value):
        """ Type safe version of dict's method.

        Only Device instances are accepted as value.

        :raises TypeError: if value type is not valid
        :raises ValueError: if passed instance is not a valid Device
        """
        if not isinstance(value, Device):
            raise TypeError("value must be an instance of Device")
        value.check()
        super(Coordinator, self).__setitem__(key, value)

    def add_device(self, d):
        """ Adds a device to the coordinator.

        :param Device d: the device instance
        :raises ValueError: if the passed object is not a device, is invalid, or already exists
        """
        if not isinstance(d, Device):
            raise ValueError('argument is not a Device')
        d.check()
        uid = d.uid
        if uid in self:
            raise DuplicatedDevice(uid)

        super(Coordinator, self).__setitem__(uid, d)

    def del_device(self, d):
        """ Deletes a device

        :param Device d: the device to be deleted, or its id
        :raises ValueError: if the passed parameter is neither a Device nor a string.
        :raises KeyError: if the device does not exist
        """
        if isinstance(d, Device):
            d = d.uid
        elif not isinstance(d, basestring):
            raise ValueError('argument is not a Device nor a str : %s' % type(d))

        del self[d]

    def js_dict(self):
        d = self.js_ownprops_dict()
        d.update(dict([
            (ConfigurationParms.DEVICES_SECTION, dict([(uid, dev.js_dict())
                              for (uid, dev) in self.iteritems()]))
        ]))
        return d

    def js_ownprops_dict(self):
        return dict([(k, v) for (k, v) in self.__dict__.iteritems()
                     if k not in self._transients + [ConfigurationParms.DEVICES_SECTION]])


class Device(DevCfgObject):
    """ Device model

    By default all the attributes of the instances are persisted.

    Required attributes :

    - address
    - type
    - location
    """
    #    _transients = []
    _required_attrs = DevCfgObject._required_attrs + [
        ConfigurationParms.ADDRESS,
        ConfigurationParms.TYPE,
        ConfigurationParms.LOCATION
    ]

    address = None
    type = None
    location = None
    enabled = False

    def __init__(self, uid, **kwargs):
        """ Constructor

        If a device type is provided in the extra parameters, the end points
        defined in the corresponding device metadata are automatically added
        to the new instance. Passed extra parameters are added afterwards, so
        that they can override those defined in the metadata.

        :param str uid: (see :py:class:`DevCfgObject`)
        :param kwargs: optional complementary named parameters
        """
        DevCfgObject.__init__(self, uid)

        # add specific properties and end-points defined in the metadata,
        # if any, when the device type has been provided
        if ConfigurationParms.TYPE in kwargs:
            dev_type = kwargs[ConfigurationParms.TYPE]
            pdefs = Metadata.device(dev_type)[ConfigurationParms.PROPERTY_DEFINITIONS]

            for k, v in ((k, v)
                         for k, v in pdefs[ConfigurationParms.DEVICE_ROOT_SECTION].iteritems()
                         if not k.startswith('__')):
                setattr(self, k, v.get(ConfigurationParms.DEFAULT_VALUE, ''))

            for endpt in (ConfigurationParms.DEVICE_OUTPUTS_SECTION, ConfigurationParms.DEVICE_CONTROLS_SECTION):
                try:
                    outputs_defs = pdefs[endpt]
                except KeyError:
                    pass
                else:
                    setattr(
                        self,
                        endpt,
                        dict(
                            (k, {})
                            for k in outputs_defs if not k.startswith('__')
                        )
                    )

        # add explicitly passed attributes
        for k in kwargs:
            setattr(self, str(k), kwargs[k])

    def __str__(self):
        return '%s(%s)' % (self.uid, self.type)

#
# Exceptions
#


class DevCfgError(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)


class InvalidCfgFile(DevCfgError):
    def __init__(self, path, reason):
        DevCfgError.__init__(self, path)
        self.reason = reason


class MissingAttribute(DevCfgError):
    def __init__(self, attr):
        DevCfgError.__init__(self, attr)


class DuplicatedDevice(DevCfgError):
    def __init__(self, uid):
        DevCfgError.__init__(self, uid)


class DeviceTypeNotFound(DevCfgError):
    def __init__(self, devtype):
        DevCfgError.__init__(self, devtype)


class DuplicatedCoordinator(DevCfgError):
    def __init__(self, uid):
        DevCfgError.__init__(self, uid)

