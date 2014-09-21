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
PYTHONPATH=/opt/cstbox/lib/python
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

    def __init__(self, line=None):
        """ Constructor.

        :param str line:
            (optional) a line to be parsed. If not provided, all fields are
            initialized to an empty value, but the user one, defaulted to
            the current user id
        """
        self.line = line.strip() if line else None
        self.is_job = False
        self.enabled = False
        self.timespec = None
        self.user = pwd.getpwuid(os.getuid()).pw_name
        self.command = None
        self.comment = None

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
                match = self.ITEM_RE.match(line[1:])
                if match:
                    self.is_job = True
            else:
                match = self.ITEM_RE.match(line)
                if match:
                    self.is_job = True
                    self.enabled = True

            if self.is_job:
                grps = match.groups()
                self.timespec = tuple(grps[:5])
                self.user = grps[5]
                self.command = grps[6]
                self.comment = grps[8]

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


class CronTab(object):
    """ The crontab.
    """
    def __init__(self, path=CSTBOX_CRONTAB):
        """ Constructor.

        :param str path:
            an optional path from which the crontab is loaded, if it exists.
            default: CSTBox crontab path
        """
        self._path = path
        self._items = [CronItem(line) for line in CRONTAB_HEADER.split('\n')]

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
        with open(wpath, 'wt') as f:
            for item in self._items:
                f.write('%s\n' % item.render())
        if not self._path:
            self._path = wpath

    def add(self, item):
        """ Adds an item to the crontab.

        Passing None is allowed and will add an empty CronItem.
        """
        self._items.append(item or CronItem())

    def remove(self, item):
        """ Removes a given item from the crontab."""
        self._items.remove(item)

    def __iter__(self):
        """ Returns an iterator on the whole item list."""
        return iter(self._items)

    def iterjobs(self):
        """ Returns an iterator on the items representing jobs."""
        return (item for item in self._items if item.is_job)

    def find_comment(self, comment):
        """ Return a list of crons having a specific comment."""
        result = []
        for job in self.iterjobs():
            if job.comment == comment:
                result.append(job)
        return result

    def find_command(self, command):
        """ Return a list of crons using a command."""
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

