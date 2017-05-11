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

""" This package level module provides the package directory exploration mechanisme,
for finding modules which provide HAL device classes and add them to the known devices.

All modules are analyzed, except those which name starts with a double underscore.
Candidate modules must publish a dictionary named HAL_DEVICE_CLASSES providing the
mapping table between devices symbolic names and corresponding implementation
classes.

Collected dictionaries are merged into the global one published here, at
package level. Extension distribution packages providing such classes must
thus deploy them in the `<PYCSTBOX_LIB_ROOT>/hal/drivers` directory.

Existing entries will be replaced in case of duplicate names, and a warning will
be issued in the log. Implementors are thus strongly encouraged to choose
identifiers carefully so that name clashes have almost no chance to occur, for
instance by prefixing them by the maker name (ex: worldcompany.motionsensor).

However, since the modules are loaded by name order, one can take advantage of
this behavior to replace an existing device by a new version.
"""

import os.path
import importlib
import pkgutil
import logging

from pycstbox.devcfg import InvalidCfgFile

_logger = logging.getLogger('HAL')

_global_registry = {}


def get_hal_device_classes():
    if not _global_registry:
        hline = '-' * 60
        _logger.info(hline)
        _logger.info("HAL device classes discovery")
        _logger.info(hline)
        for modname in [
            n for _, n, ispkg in pkgutil.iter_modules([os.path.dirname(__file__)])
            if not ispkg and not 'test_' in n and not '_test' in n
        ]:
            modfqn = __package__ + '.' + modname
            _logger.info("- analyzing %s :", modfqn)
            try:
                m = importlib.import_module(modfqn)
            except InvalidCfgFile as e:
                _logger.error("invalid metadata : (%s) %s", e.message, e.reason)
            except SyntaxError as e:
                _logger.error("syntax error in module '%s' (%d:%d)", e.filename, e.lineno, e.offset)
            except Exception as e:
                _logger.error("registration error : (%s) %s", e.__class__.__name__, e.message)
            else:
                del m

        _logger.info(hline)

    return _global_registry
