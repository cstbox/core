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

""" CSTBox system wide configuration routines and definitions.

This implementation is based on INI like configuration files.
"""

__author__ = 'Eric PASCUAL - CSTB (eric.pascual@cstb.fr)'
__copyright__ = 'Copyright (c) 2013 CSTB'
__vcs_id__ = '$Id$'
__version__ = '1.0.0'

import ConfigParser
import os

#
# Common definitions
#

# root dir of all configuration files
CONFIG_DIR = '/etc/cstbox'


def make_config_file_path(filename):
    """ Returns the full path of a configuration file located in CSTBox
    default configuration directory.
    """
    assert filename
    return os.path.join(CONFIG_DIR, filename)


class GlobalSettings(ConfigParser.SafeConfigParser):
    """ A special pre-defined configuration file containing application wide
    parameters.

    The file name is pre-defined, and data are automatically loaded when creating
    the instance, thus relieving from explicitly call the read() method.

    In addition, since this file is single section, simplified get/set methods
    are proposed, removing the need to specify a section name.

    Some fixed settings are also provided as class attributes.
    """
    _CONFIG_FILE = 'cstbox.cfg'
    SECTION = 'cstbox'
    DEFAULTS = dict(prefix='', system_id=os.uname()[1], dao_name='fsys')

    LOGFILES_DIR = '/var/log/cstbox'
    LOGFILES_EXT = '.log'

    def __init__(self, path=None):
        """
        :param str path: configuration file path, used only for unit tests
        """
        ConfigParser.SafeConfigParser.__init__(self)
        if not path:
            path = make_config_file_path(self._CONFIG_FILE)
        self.read(path)

    def get(self, option):
        """ Overridden :py:meth:`ConfigParser.SafeConfigParser.get` hiding parameters having no use in this version
        for simplication's sake.
        """
        try:
            return ConfigParser.SafeConfigParser.get(self, self.SECTION, option)
        except ConfigParser.NoOptionError:
            return self.DEFAULTS[option]

    def set(self, option, value):
        """ Overridden :py:meth:`ConfigParser.SafeConfigParser.set` hiding parameters having no use in this version
        for simplication's sake.
        """
        ConfigParser.SafeConfigParser.set(self, self.SECTION, option, value)

    def write(self):
        """ Overridden :py:meth:`ConfigParser.SafeConfigParser.write` hiding parameters having no use in this version
        since storage file is defined at instanciation time (see constructor).
        """
        with open(make_config_file_path(self._CONFIG_FILE), 'wt') as fp:
            print('writing to %s' % make_config_file_path(self._CONFIG_FILE))
            ConfigParser.SafeConfigParser.write(self, fp)

    def as_dict(self):
        """ Returns the configuration content as a dictionary.
        """
        return dict(self.items(self.SECTION))
