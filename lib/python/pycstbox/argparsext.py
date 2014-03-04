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

import argparse
import ConfigParser
import os

__author__ = 'Eric PASCUAL - CSTB (eric.pascual@cstb.fr)'
__copyright__ = 'Copyright (c) 2012 CSTB'
__vcs_id__ = '$Id$'
__version__ = '1.0.0'


class ArgumentParser(argparse.ArgumentParser):
    """ An extended version of argparse.ArgumentParser which allows providing
    any arguments (even mandatory ones) from a configuration file and omitting
    them from the command line.

    The configuration file is provided by using the '-C/--cfgpath' option.
    If omitted, a fallback path can be used.

    In short, the fallback sequence for setting the value of an argument is :

    1/ command line
    2/ configuration file specified in the command line, if exists
    3/ default configuration file if defined and exists
    4/ default value set in the argument definition
"""

    def __init__(self, dflt_cfgpath, **kwargs):
        """
        :param str dfl_cfgpath :
            default path of the configuration file, if not specified by the -C option
            (other inherited constructor paramaters)
        """
        self.dflt_cfgpath = dflt_cfgpath
        argparse.ArgumentParser.__init__(self, **kwargs)

    def parse_args(self, argv=None):
        """ Overidden parse args method, taking care of parameters provided by
        a configuration file

        See inherited method for parameters documentation
        """
        # Create a "first stage" parser for loading parameters from a
        # configuration file This allows omitting  mandatory parameters from
        # the command line by getting their value from there
        conf_parser = argparse.ArgumentParser(add_help=False)
        conf_parser.add_argument('-C', '--cfgpath', dest='cfgpath')

        # use parse_known_args so that other parameters will not trigger the
        # "unrecognized arguments" error message
        args, remaining_argv = conf_parser.parse_known_args(argv)

        # handle all possible of situations wrt the config file specification
        if args.cfgpath:
            # provided in the command line
            cfgpath = args.cfgpath
        elif self.dflt_cfgpath and os.path.exists(self.dflt_cfgpath):
            # not provided, but the default one exists
            cfgpath = self.dflt_cfgpath
        else:
            # not provided and default one not found
            cfgpath = None

        # if we do have a configuration file available, we load parameters from
        # it and build a command line with them as if they were entered
        effective_argv = []
        if cfgpath:
            config = ConfigParser.SafeConfigParser()
            config.read([cfgpath])
            for k, v in config.items("globals"):
                effective_argv.extend(['--' + k, v])

        # add real command line arguments AFTER the loaded ones, so that it is
        # possible to override configuration file arguments by command line
        # ones
        effective_argv.extend(remaining_argv)

        # invoke the inherited parsing with the "faked" command line
        ns = argparse.ArgumentParser.parse_args(self, effective_argv)

        # add the configuration file setting to the parsing result, so that it
        # can be retrieved by the caller as all the other arguments
        ns.cfgpath = cfgpath

        return ns

