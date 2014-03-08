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

""" This module lets application put persistent flags to notify for instance
that a restart is needed.

Flags can contain data as a simple string, such as the message to be displayed in the notification box.
"""

__author__ = 'Eric PASCUAL - CSTB (eric.pascual@cstb.fr)'
__copyright__ = 'Copyright (c) 2013 CSTB'
__vcs_id__ = '$Id$'
__version__ = '1.0.0'

import re
import os

FLAGS_HOME = '/var/run/cstbox/appdata'
USER_NOTIFICATION = 'notification'

_flags_fname_re = re.compile(r'^(.+)\.flg$')


def _fname(name):
    return '%s.flg' % name


def _fpath(name):
    return os.path.join(FLAGS_HOME, _fname(name))


def get_flags():
    """ Returns the list of flags currently defined.

    :returns: an iterator on the available flags
    """
    return (os.path.splitext(f)[0]
            for f in os.listdir(FLAGS_HOME)
            if _flags_fname_re.match(f) \
        )


def create_flag(name, content):
    """ Creates a flag.

    :param str name: the name of the flag
    :param str content: its content
    """
    with open(_fpath(name), 'wt') as f:
        if content:
            f.write(content)


def read_flag(name):
    """ Returns the content of a given flag.

    :param str name: the name of the flag
    :returns: an array of the text lines of the flag content
    :raises: any exception risen during flag file access
    """
    return [l.strip() for l in open(_fpath(name), 'r').readlines()]


def rm_flag(name):
    """ Removes a given flag, if it exists.

    :param str name: the name of the flag
    """
    path = _fpath(name)
    if os.path.exists(path):
        os.remove(path)

