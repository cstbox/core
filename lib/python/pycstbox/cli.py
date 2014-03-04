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

""" Complementary definitions to enhance `argparse` usage with commonly used
features.
"""

__author__ = 'Eric PASCUAL - CSTB (eric.pascual@cstb.fr)'
__copyright__ = 'Copyright (c) 2012 CSTB'
__vcs_id__ = '$Id$'
__version__ = '1.0.0'

import argparse
import os

import pycstbox.config


def _uppercase_string(s):
    """ ArgumentParser custom type handler """
    return s.upper()


def get_argument_parser(description, **kwargs):
    """ Returns an argument parser with common options already defined

    Included pre-defined options:

    -L --loglevel
    --debug

    :param str description: Brief description of the script
    :param kwargs: named arguments for ArgumentParser constructor
    """
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        **kwargs
    )

    parser.add_argument('-L', '--loglevel',
                        dest='loglevel',
                        type=_uppercase_string,
                        choices=['DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL'],
                        default='INFO',
                        help='logging level')

    parser.add_argument('--debug',
                        dest='debug',
                        action='store_true',
                        help='activates the debug mode')

    return parser


def add_config_file_option_to_parser(parser, dflt_name):
    """ Adds the command-line option to the parser for providing the path of
    the configuration file

    The default name provided will be used to build the full path of the
    configuration file, which directory is defined by CONFIG_DIR

    :param argparse.ArgumentParser parser:
            The parser to which the option will be added. Cannot be None
    :param str dflt_name:
            the default name of the file. Cannot be None or empty
    """
    assert parser, 'parser cannot be None'
    assert dflt_name, 'dflt_name cannot be None or empty'

    dflt = os.path.join(pycstbox.config.CONFIG_DIR, dflt_name)
    parser.add_argument('-c', '--config',
                        dest='config_path',
                        default=dflt,
                        help='path of the configuration file'
    )
