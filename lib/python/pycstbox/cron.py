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

""" Lightweight tools for working with the CSTBox private crontab.

In order to avoid cluttering the host system, CSTBox cron settings are gathered
in a package related crontab stored in /etc/cron.d, as described in cron man page.
This way, we can deactivate all CSTBox cron tasks when shutting it down, without
loosing their definitions, and this be able to reactivate them back again when
restarting the framework.
"""

__author__ = 'Eric PASCUAL - CSTB (eric.pascual@cstb.fr)'

import re
import os
import pwd

# A symlink to this file is created as /etc/cron.d/cstbox so that the
# task definitions are persistent.
CSTBOX_CRONTAB = '/etc/cstbox/crontab'

CRONTAB_HEADER = """# /etc/cron.d/cstbox: crontab entries for the CSTBox package

SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
PYTHONPATH=/opt/cstbox/lib/python:/opt/cstbox/deps/python
"""

# try to import custom extensions
try:
    from cron_extensions import CronTabHooks
except ImportError:
    class CronTabHooks(object):
        """ Empty hooks used as fallback when no extension is installed.
        """
        def pre_write(self, path):
            """ Called before the crontab is written to disk.
            :param str path: the target path
            """

        def post_write(self, path):
            """ Called after the crontab has been written to disk.
            :param str path: the target path
            """


class CronItem(object):
    """ An item of the crontab, be it a job specification or anything
    else.
    """

    # regular expressions for parsing a string representing a job. Since we are
    # dealing with system-wide crontabs, it includes the "user" field
    SCHEDULE_SPECS = r'\s+'.join([r'([^@#\s]+)']*5)
    SCHEDULE_SPECS_RE = re.compile(SCHEDULE_SPECS)
    ITEM_RE = re.compile(r'^\s*' + SCHEDULE_SPECS + r'\s+([^@#\s]+)\s+([^#\n]*)(\s+#\s*([^\n]*)|$)')
    ITEM_RE_NO_USER_FIELD = re.compile(r'^\s*' + SCHEDULE_SPECS + r'\s+([^#\n]*)(\s+#\s*([^\n]*)|$)')

    def __init__(self, line=None, system_crontab=True):
        """ Constructor.

        :param str line:
            (optional) a line to be parsed. If not provided, all fields are
            initialized to an empty value. It item belongs to a system crontab,
            the user field is defaulted to the current user id
        :param bool system_crontab:
            if True (default), cron items use the system crontab format,
            including the user field. If false, no user field is included
            in the cron items.
        """
        self.line = line.strip() if line else None
        self.is_job = False
        self.enabled = False
        self._timespec = None
        self._system_crontab = system_crontab
        self.user = pwd.getpwuid(os.getuid()).pw_name if system_crontab else None
        self.command = None
        self.comment = None
        self._item_re = self.ITEM_RE if system_crontab else self.ITEM_RE_NO_USER_FIELD

        if line:
            self.parse(line)

    def parse(self, line):
        """ Parses a string supposed to be a crontab line.

        A basic analyze of the line is performed to decide if it can be a job
        specification or something else. It is quite rudimentary and not bullet
        proof in any way, since a comment line containing a number of words
        equal to the job definition field count is taken for a job.

        Maybe some more in-depth analyze could be done by checking if what is
        supposed to be the time specs fields are valid ones, but we don't need
        so much sophistication for the moment.

        :param str line:
            the line to be parsed
        """
        line = line.strip()
        if line:
            if line[0] == '#':
                match = self._item_re.match(line[1:])
                if match:
                    self.is_job = True
            else:
                match = self._item_re.match(line)
                if match:
                    self.is_job = True
                    self.enabled = True

            if self.is_job:
                grps = match.groups()
                self._timespec = tuple(grps[:5])
                if self._system_crontab:
                    self.user, self.command, _, self.comment = grps[5:]
                else:
                    self.command, _, self.comment = grps[5:]

    @property
    def timespec(self):
        return self._timespec

    @property
    def is_system_crontab(self):
        return self._system_crontab

    @timespec.setter
    def timespec(self, v):
        if isinstance(v, tuple):
            self._timespec = v
        elif isinstance(v, basestring):
            match = self.SCHEDULE_SPECS_RE.match(v)
            if match:
                self._timespec = match.groups()
            else:
                raise ValueError('invalid scheduling rule: ' + v)

    def render(self):
        """ Returns the crontab record corresponding to the item definition.

        The result is always a string, which can be empty if no attribute of
        the item is set.
        """
        self.is_job = self.timespec and self.command
        if self.is_job:
            parts = [] if self.enabled else ['#']
            parts.append(' '.join(self.timespec))
            parts.append(self.user)
            parts.append(self.command)
            if self.comment:
                parts.append('# ' + self.comment)
            return ' '.join(parts)
        else:
            return self.line or ''


class CronTab(object, CronTabHooks):
    """ The crontab.
    """
    def __init__(self, path=CSTBOX_CRONTAB, system_crontab=True):
        """ Constructor.

        :param str path:
            an optional path from which the crontab is loaded, if it exists.
            default: CSTBox crontab path
        :param bool system_crontab:
            if True (default), cron items use the system crontab format,
            including the user field. If false, no user field is included
            in the cron items.
        """
        self._path = path
        self._system_crontab = system_crontab
        self._items = [CronItem(line, system_crontab) for line in CRONTAB_HEADER.split('\n')]

        if path and os.path.exists(path):
            self.read(path)

    def read(self, path):
        """ Loads and parses the content of a crontab file.

        :param str path:
            the path of the file

        :raises:
            any IO error dealing with file access, including file not found
        """
        self._items = []
        with open(path, 'rt') as f:
            for line in f:
                self._items.append(CronItem(line))

    def write(self, path=None):
        """ Writes the crontab to disk.

        :param str path:
            the path of the file to be written. If not provided, the path
            defined at instantiation time is used. If none of these are
            defined, an exception is generated.
            If not provided at creation time, the path passed here will be
            stored in the instance.
        """
        wpath = path or self._path
        if not wpath:
            raise ValueError('no path defined for writing')

        self.pre_write(wpath)

        with open(wpath, 'wt') as f:
            for item in self._items:
                f.write('%s\n' % item.render())
        if not self._path:
            self._path = wpath

        self.post_write(wpath)

    def add(self, item):
        """ Adds an item to the crontab.

        Passing None is allowed and will add an empty CronItem.

        :param CronItem item:
            the item to be added

        :raises:
            ValueError if the passed item is not None and is not of same type
            (system or user) as the crontab itself
        """
        if item:
            if item.is_system_crontab != self._system_crontab:
                raise ValueError('cronitem type mismatch')
        self._items.append(item or CronItem(system_crontab=self._system_crontab))

    def remove(self, item):
        """ Removes a given item from the crontab."""
        self._items.remove(item)

    def __iter__(self):
        """ Returns an iterator on the whole item list."""
        return iter(self._items)

    def iterjobs(self):
        """ Returns an iterator on the cron items representing jobs."""
        return (item for item in self._items if item.is_job)

    def find_comment(self, comment):
        """ Return a list of cron items having a specific comment."""
        result = []
        for job in self.iterjobs():
            if job.comment == comment:
                result.append(job)
        return result

    def find_command(self, command):
        """ Return a list of cron items using a command."""
        result = []
        for job in self.iterjobs():
            if job.command == command:
                result.append(job)
        return result

    def render(self):
        """ Renders the whole crontab as a list of strings."""
        return [item.render() for item in self._items]


def make_timespec(minute='*', hour='*', day='*', month='*', dow='*'):
    return str(minute), str(hour), str(day), str(month), str(dow)

