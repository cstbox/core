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

from pycstbox.hal.drivers import _global_registry
from pycstbox.devcfg import Metadata
from pycstbox.hal.device import EventDataDef

import logging

_logger = logging.getLogger('HAL')


def hal_device(device_type, coordinator_type):
    """ Decorator for classes implementing a device abstraction.

    The decorator performs two tasks:

    - it adds the _OUTPUTS_TO_EVENTS_MAPPING attribute to the class, pulling its content from the
    metadata defined for the related device and stored in `devcfg.d` sub-tree
    - it registers the class for use at devices instanciation time while loading the network
    configuration

    :param str device_type: the associated device type, as used in the network configuration
    :param str coordinator_type: the type of the coordinator this device is managed by
    """

    def decorator(cls):
        cls._device_type = device_type
        cls._coordinator_type = coordinator_type

        meta = Metadata.device(coordinator_type + ':' + device_type)
        outputs = meta['pdefs']['outputs']
        # adds the mapping table as a dynamically defined attribute containing the
        # corresponding dictionary. We use properties of the output which name is
        # not a "special" one, ie bracketed by double underscores
        setattr(cls, '_OUTPUTS_TO_EVENTS_MAPPING',
                dict((
                    (k, EventDataDef(v['__vartype__'], v.get('__varunits__', None)))
                    for k, v in outputs.iteritems()
                    if not k.startswith('__')
                ))
        )

        _global_registry[device_type] = cls

        _logger.info(
            "class %s registered as implementation of device type %s:%s",
            cls.__name__, coordinator_type, device_type
        )

        return cls

    return decorator


class HalError(Exception):
    """ Specialized error for HAL related actions.
    """