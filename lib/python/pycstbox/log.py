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

""" CSTBox logging helpers.

Built on top of Python default logging system, to provide a simplified use of logs and a uniform formatting. Can be
used as a drop-in replacement of ``logging`` module, since all toplevel functions and constants are surfaced
here.
"""

__author__ = 'Eric PASCUAL - CSTB (eric.pascual@cstb.fr)'
__copyright__ = 'Copyright (c) 2013 CSTB'
__vcs_id__ = '$Id$'
__version__ = '1.0.0'

import logging

# create aliases for logging root functions so that logging import is not
# needed for module users
info = logging.info
error = logging.error
critical = logging.critical
fatal = logging.fatal
warning = logging.warning
debug = logging.debug
exception = logging.exception
getLogger = logging.getLogger
getLevelName = logging.getLevelName

# same as above, but for logging levels
INFO = logging.INFO
WARNING = logging.WARNING
WARN = logging.WARN
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL
FATAL = logging.FATAL
DEBUG = logging.DEBUG


class Loggable(object):
    """ Mixin adding logging methods in a convenient way.

    This class takes care of creating a log instance, based on what is provided
    at instantiation time. See constructor documentation for details.

    It exposes common logging.Logger output methods, prefixing them by 'log\_'
    to avoid any name clash.
    """

    # Delegates for Logger methods, initialized by the constructor. Declared here so that lint-type
    # checkers do not complain about unresolved methods
    log_info = log_warn = log_warning = log_error = log_critical = log_fatal = log_exception = \
        log_debug = log_getEffectiveLevel = None

    def __init__(self, logger=None, logname=None):
        """
        Creates a log instance based on the parameters provided. If logger is
        defined, it is used as the logger. Otherwise a logger is created locally.
        If logname is provided, this logger will be named accordingly. Otherwise
        the class name is used.

        :param Logger logger:
            (optional) the logger to use

        :param str logname:
            (optional) the name of the log created locally, if logger is not provided.
            Default: the class name
        """
        if logger:
            self._logger = logger
        else:
            if not logname:
                logname = self.__class__.__name__
            self._logger = logging.getLogger(logname)

        # Makes Logger commonly used methods directly available by generating
        # delegates.
        #
        # This avoids creating a lot of code like this :
        # def log_info(self, *args, **kwargs):
        #   self.logger.info(*args, **kwargs)
        #
        # All other methods are accessible by using the logger property which
        # gives access to the embedded logger instance.
        for meth in ('info', 'warn', 'warning', 'error', 'critical', 'fatal',
                     'exception', 'debug', 'getEffectiveLevel'):
            setattr(self, 'log_' + meth, getattr(self._logger, meth))

    @property
    def logger(self):
        """ The embedded logger instance."""
        return self._logger

    def log_setLevel(self, level):
        self._logger.setLevel(level)
        self.log_info('log level changed to %s' % logging.getLevelName(level))

    def log_setLevel_from_args(self, args):
        """ Sets the logger level based on the attribute "loglevel" of the args
        parameter, if it exists. If not the case, this method has no effect.

        The typical use case of this method is to pass the result of
        ArgumentParser.parse_args for args.

        :param args:
            an object supposed to have an attribute named 'loglevel', which
            value is the (case insensitive) name of one of the log levels
            defined in logging
        """
        if hasattr(args, 'loglevel'):
            self.log_setLevel(getattr(logging, args.loglevel.upper()))


def setup_logging(name=None, level=logging.INFO):
    """ Setup the root log format and level, and optionally change its default
    name ("root") to the provided one.
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname).1s] %(name)s > %(message)s',
        datefmt='%d/%m %H:%M:%S'
        )
    if name:
        logging.getLogger().name = name


def set_loglevel_from_args(logger, args):
    """ Sets the level of a logger according to the 'loglevel' attribute
    of args got from an ArgumentParser.

    :param Logger logger: the logger which log level must be modified
    :param args: the CLI arguments, as parser by an argument parser
    """
    if logger:
        logger.setLevel(loglevel_from_args(args))


def loglevel_from_args(args):
    """ Returns the log level (as defined in logging) corresponding to the
    -L/--loglevel command line option value.

    :param args: the CLI arguments, as parser by an argument parser
    """
    return getattr(logging, args.loglevel.upper())


# default module initialization at import time
setup_logging()

