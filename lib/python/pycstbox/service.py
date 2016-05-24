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

""" Root class and helpers for implementing CSTBox D-Bus based services.

The concept of service container is provided to leverage the possibility of
accessing several service objects through a single bus name. This container takes
care of running the main loop and catching signals to terminating it gracefully.

Services objects are added to the container to provide the required services, each
one being associated to a given path inside the container.
"""

import sys
import signal
import dbus.service
import gobject
import threading

from pycstbox import dbuslib
from pycstbox.log import Loggable
from pycstbox import sysutils

__author__ = 'Eric PASCUAL - CSTB (eric.pascual@cstb.fr)'

# The name of the interface gathering system level methods
SYSTEM_IFACE = dbuslib.IFACE_PREFIX + "__system__"
# The path of the framework level service object
SYSTEM_OBJECT_PATH = "/__system__"


class ServiceContainer(Loggable):
    """ A service container is used to host one or many service objects, made accessible
    via its connection to a bus.

    Service objects can be added either at container creation time or afterwards.

    A service object providing framework level features, such as termination request is
    automatically created and added (unless specified otherwise). Its path is defined
    by the SYSTEM_OBJECT_PATH constant.

    Simple usage :
        class SvcObject1(dbus.service.Object):
            ...

        class SvcObject2(dbus.service.Object):
            ...

        obj1 = SvcObject1(...)
        obj2 = SvcObject2(...)
        svc = ServiceContainer(
            'my_service',         --> will claim 'fr.cstb.cstbox.my_service' bus name on SessionBus
            [(obj1, '/path/to/obj1'),(obj2, '/path/to/obj2')]
            )
        svc.start()

    If automatic framework service object creation option is used (default),
    an addition service object is created for implementing the framework level interface,
    which includes the method ``terminate``. It is then possible to send to fr.cstb.cstbox.my_service a
    a method call message to framework.terminate for stopping the service.
    """

    def __init__(self, name, conn=None, svc_objects=None, auto_fw_object=True):
        """
        :param str name:
            the container's name. It is used to build the well-known name which will
            be claimed (see pycstbox.commons.make_bus_name())

        :param dbus_connection conn:
            the connection to the bus used by the service.
            Set to the session bus if not provided.

        :param list svc_objects:
            an optional list of service objects, which will be automatically added to
            the container during its initialization. The items of this list are tuples
            containing the service object instance and the path to be associated for it

        :param bool auto_fw_object:
            if True (the default) a service object implementing framework level functions
            is automatically created and added. If False, it is the responsibility of
            the application to provide it and adding it if framework level functions are
            required.
        """
        self._name = name
        self._conn = conn if conn else dbus.SessionBus()
        self._objects = []

        # claim our "well known" name on the conn
        self._wkn = dbus.service.BusName(dbuslib.make_bus_name(name), self._conn)

        self._loop = None
        self._terminating = False
        self._terminate_lock = threading.Lock()

        Loggable.__init__(self, logname='SC:%s' % self._name)

        # adds a service controller object if asked for
        if auto_fw_object:
            fwobj = _FrameworkServiceObject(self)
            self.add(fwobj, SYSTEM_OBJECT_PATH)

        # add provided service objects
        self.add_objects(svc_objects)

    def log_setLevel(self, level):
        """ Local override of log_setLevel fo handing the propagation of the
        level setting to the child service objects."""
        Loggable.log_setLevel(self, level)
        for so in [o for o in self._objects if isinstance(o, Loggable) and o is not self]:
            so.log_setLevel(level)

    def add(self, svc_object, path):
        """ Adds a service object to the container.

        :param ServiceObject svc_object: the service object
        :param str path: the path to which the object is accessed
        :raises ValueError: if parameters are None or not the right type
        """
        if not svc_object:
            raise ValueError('svc_object cannot be None')
        if not isinstance(svc_object, dbus.service.Object):
            raise ValueError('svc_object parameter must be a dbus.service.Object descendant')

        self.log_info('adding service object %s with path=%s', svc_object, path)

        try:
            svc_object.add_to_connection(self._conn, path)
            self._objects.append(svc_object)
        except KeyError:
            raise ValueError("path already in use : %s" % path)

    def add_objects(self, svc_objects):
        """ Adds a list of service object.

         :param list svc_objects:
            an optional list of service objects, which will be automatically added to
            the container during its initialization. The items of this list are tuples
            containing the service object instance and the path to be associated for it
        """
        if svc_objects:
            for obj, path in svc_objects:
                self.add(obj, path)

    def remove(self, svc_object):
        """ Removes a service object from the container.

        :param ServiceObject svc_object: the service object to be removed
        :raises ValueError: if parameter is None or not the right type
        """
        if not svc_object:
            raise ValueError('svc_object cannot be None')
        if not isinstance(svc_object, dbus.service.Object):
            raise ValueError('svc_object parameter must be a dbus.service.Object descendant')

        svc_object.remove_from_connection(self._conn)
        self._objects.remove(svc_object)

    def start(self):
        """ Starts the container.

        This starts the D-Bus main loop and allows the service to receive calls and signals
        from the outside.

        The container can be stopped then by :
        - calling its terminate() method
        - sending it a SIGTERM signal or a KeyboardInterrupt

        Starting a running container has no effect, apart a warning message in the log.
        """
        if not self._loop:
            self.log_info('starting container (wkn=%s)', self._wkn.get_name())
            sysutils.emit_service_state_event(self._name, sysutils.SVC_STARTING)

            self._terminating = False

            started = []
            for svc_obj in self._objects:
                try:
                    if hasattr(svc_obj, 'start') and callable(svc_obj.start):
                        svc_obj.start()
                    started.append(svc_obj)
                except Exception as e: #pylint: disable=W0703
                    self.log_critical('svcobj %s start failure (%s)' % (svc_obj, e))
                    for so in [o for o in started if hasattr(o, 'stop') and callable(getattr(o, 'stop'))]:
                        so.stop()
                    self.log_critical('container start process aborted')
                    sys.exit(1)
                else:
                    self.log_info('svcobj %s started' % svc_obj)

            self._loop = gobject.MainLoop()
            signal.signal(signal.SIGTERM, self.__sigterm_handler)
            try:
                sysutils.emit_service_state_event(self._name, sysutils.SVC_RUNNING)
                self._loop.run()

            except KeyboardInterrupt:
                print
                self.log_info("KeyboardInterrupt caught")
                self.terminate()

            except Exception as e:
                sysutils.emit_service_state_event(self._name, sysutils.SVC_ABORTING)
                self.log_exception(e)
                raise sysutils.CSTBoxError(e)

            self.log_info('terminated')
            sysutils.emit_service_state_event(self._name, sysutils.SVC_STOPPED)

        else:
            self.log_warn("ignored : already running")

    def terminate(self):
        """ Stops the container.

        This makes the event loop to exit and resources to be freed.

        Stopping a not running container has no effect, apart a warning message in the log.
        """
        if self._loop:
            with self._terminate_lock:
                if not self._terminating:
                    self._terminating = True
                    sysutils.emit_service_state_event(self._name, sysutils.SVC_STOPPING)

                    for so in [o for o in self._objects if hasattr(o, 'stop') and callable(getattr(o, 'stop'))]:
                        so.stop()

                    self._loop.quit()
                    self._loop = None
                    self._terminating = False

        else:
            self.log_warn("ignored : not currently running")

    def __sigterm_handler(self, signum, frame):     #pylint: disable=W0613
        """ Catches SIGTERM signals to gracefully stop the container if running. """
        self.log_info('SIGTERM received')
        if self._loop:
            self.terminate()


class _FrameworkServiceObject(dbus.service.Object):
    """ Private internal class implementing the framework level service object """
    def __init__(self, owner):
        super(_FrameworkServiceObject, self).__init__()
        self._owner = owner

    @dbus.service.method(SYSTEM_IFACE)
    def terminate(self):
        self._owner._logger.info('terminate request received')  #pylint: disable=W0212
        self._owner.terminate()


class SimpleService(ServiceContainer, dbus.service.Object):
    #FIXME: fix recursions problems
    """ This class is just a helper for implementation of a service composed of
    a single object.

    It is an hybrid class which packages the service container and the service object,
    and "connects" them automatically. If not provided, the service object path
    is set to '/service'.

    It must be sub-classed to implement the required methods and/or signals.

    **IMPORTANT** don't use this for the moment, it is a bit buggy

    """
    def __init__(self, name, conn=None, path='/service'):
        """
        :param str path: the path to be associated to the service object. Default: '/service'

        For other parameters, see :py:class:`ServiceContainer`
        """
        dbus.service.Object.__init__(self)
        ServiceContainer.__init__(self, name, conn, [(self, path)])

