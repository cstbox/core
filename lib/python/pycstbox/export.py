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

""" Base classes for defining events export jobs and process chains."""

__author__ = 'Eric PASCUAL - CSTB (eric.pascual@cstb.fr)'
__copyright__ = 'Copyright (c) 2013 CSTB'
__vcs_id__ = '$Id$'
__version__ = '1.0.0'

import datetime
import time
import os
import pickle
import re

from pycstbox.log import Loggable


class EventsExportJob(Loggable):
    """ Base abstract class for defining an export job.

    The export job is the unit of work responsible for extracting the data,
    transforming them according to the target system specification and sending
    the result to it.

    It is also responsible for handing the two steps retry mechanism in case
    of process failure :

        - retry on the moment of the failure, based on the provided
          configuration
        - put aside the job for later, so that it can be re-attempted on next
          data export time slot

    To get details on the sequencing of the operation, have a look at the run()
    method documentation.
    """

    # Pre-defined error codes for the steps of the job.
    # Since they are numbered by 100, it is possible to define sub-codes for
    # a finer reporting resolution.
    ERR_NONE = 0
    ERR_PREPARE = 100
    ERR_EXPORT_EVENTS = 200
    ERR_SEND = 300

    def __init__(self, jobname, jobid, parms, logger=None):
        """
        :param str jobname: job name (should be unique across the application)
        :param str jobid: the job id.
            Must be unique and allow sorting a job list and reflect their chronology
        :param parms: the execution parameters
        :param logger: (optional) message logger
        :raises ValueError: if mandatory parameters are not all non empty
        """
        if not jobname or not jobid or parms is None:
            raise ValueError("missing mandatory parameter")

        self._name = jobname

        Loggable.__init__(self, logname=jobname)

        self._id = jobid
        self._parms = parms

        self._error = None

        self.log_info('- job %s:%s created :', jobname, jobid)
        self.log_info('  + parameters : %s', self._format_parms())

    def _format_parms(self):
        """ Returns a displayable version of the parameters, used for logging
        purposes.

        The default implementation just "stringifies" their value, but sub-classes
        should override this behavior if the parameters contain sensitive data
        which should not be readable in the logs.
        """
        return str(self._parms)

    @property
    def job_id(self):
        return self._id

    @property
    def last_error(self):
        return self._error

    @staticmethod
    def make_jobid(ts=datetime.datetime.utcnow()):
        """ Return a job id based on a given timestamp, formatted as YYMMDDHHMMSS.

        If not specified, the current UTC date and time is used.

        Can be overridden if an other kind of id is needed.
        """
        return ts.strftime('%y%m%d%H%M%S')

    def run(self, max_try=1, retry_delay=10): #pylint: disable=R0912
        """ Job main line process.

        This method handles automatic retries in case of data transmission
        error. If max_try is provided and set to a value greater than 1, the
        transfer will be retried up to the corresponding total count. A
        delay of retry_delay seconds will be waited before successive attempts.

        There is normally no need for overriding this method, apart if a
        specific logic is needed.

        :param int max_try:
            total number of execution attempts (> 0)
        :param int retry_delay:
            the delay (in seconds) to be waited before restarting the
            process in case of multiple attempts. Don't choose something
            too short to avoid being banned as a DOS attack.

        :returns: 0 if successful execution, any other value for reporting an error.
            Codes ERR_xxx are pre-defined to report an error in one of the
            steps.
            In case of error, the property last_error can be used to store it
            for later access.

        :raises ValueError: if invalid parameter(s)
        """
        if not (max_try == int(max_try) and max_try > 0):
            raise ValueError('invalid max_try (%s)' % max_try)
        if not (retry_delay == int(retry_delay) and retry_delay > 0):
            raise ValueError('invalid retry_delay (%s)' % retry_delay)

        self._error = None
        error_code = self.ERR_PREPARE

        try:
            self.log_info('- preparing execution')
            self.prepare()

            self.log_info('- extracting and exporting events')
            error_code = self.ERR_EXPORT_EVENTS
            cnt = self.export_events()
            if cnt:
                self.log_info('  + %d events have been exported' % cnt)

                self.log_info('- sending data')
                error_code = self.ERR_SEND
                cur_try = 1
                while cur_try <= max_try:
                    try:
                        self.send_data()
                        break

                    except ExportError:
                        if cur_try < max_try:
                            self.log_error(
                                '  + upload attempt failed. Retrying in %s second(s)...',
                                retry_delay
                            )
                            time.sleep(retry_delay)
                            cur_try += 1
                            self.log_info('  + retrying (%d/%d)...' % (cur_try, max_try))
                        else:
                            self.log_error('  + max try count exhausted => aborting')
                            raise

            else:
                self.log_warn('no event found for requested criteria')

        except ExportError as e:
            self._error = e
            error_code += e.subcode
            self.cleanup(e)
            self.log_error('job failed with error : %s', e)

        else:
            self._error = None
            self.cleanup()
            self.log_info('job completed without error')
            error_code = self.ERR_NONE

        return error_code

    def prepare(self):
        """ Initialization of the job optional callback.

        Called at the very beginning of the job, before anything else being done. Can be
        overridden by sub-classes if they need to do something special at this step.

        :raises ExportError: in case of error
        """
        pass

    def export_events(self):
        """ Events export mandatory callback.

        Export the events in whatever form is suited for the process. Called
        just after the "prepare" step.

        :returns: the number of exported events
        :raises ExportError: in case of error
        """
        raise NotImplementedError()

    def send_data(self):
        """ Export data sending mandatory callback.

        Responsible for transmitting the exported data to the target system.
        Called if :py:meth:`export_events` method returns a not null event count.

        :raises ExportError: in case of error
        """
        raise NotImplementedError()

    def cleanup(self, error=None):
        """ Final cleaning optional callback.

        Invoked at the very end of the process, whatever is the result of
        previous steps.

        :param error: error encountered in processing if any
        """
        pass


class Backlog(object):
    """ A jobs backlog, implemented as a container and backed by a file based
    storage.

    A backlog manages information related to jobs which need to be re-run later.
    This implementation uses a separate directory for each named backlog, the
    directory name being the same as the backlog one. These directories are
    created under a root which path is provided when creating the instance.

    The default implementation uses pickle for persisting the data, but one can
    switch to any other format by overriding the methods _store() and _load().
    """

    DEFAULT_LOCATION_ROOT = '/var/spool/cstbox/export'
    FILE_EXTENSION = '.blog'

    _job_id_re = re.compile(r'[a-z-A-Z0-9-_.]+')

    def __init__(self, name, root=None):
        """
        :param str name:
            the name of the backlog. It must be a valid filename on the target OS
        :param str root:
            path of the root directory under which the backlog are stored.
            Each backlog uses a sub-directory
            If not specified, uses a sub-directory of DEFAULT_LOCATION_ROOT
            and which name is the backlog one. The directory (and its parents)
            is created if not yet existing

        :raises ValueError: if path does not comply with above constraints
        """
        if not name:
            raise ValueError('name parameter is mandatory')

        path = os.path.join(root if root else self.DEFAULT_LOCATION_ROOT, name)
        if not os.path.exists(path):
            os.makedirs(path)
        else:
            if not os.path.isdir(path) or not os.access(path, os.W_OK | os.X_OK):
                raise ValueError('invalid path : %s' % path)
        self._location = path

    def _fpath(self, job_id):
        return os.path.join(self._location, str(job_id)) + self.FILE_EXTENSION

    def clear(self):
        """ Clears all backlog items. """
        assert self._location
        os.system('rm %s/*%s' % (self._location, self.FILE_EXTENSION))

    def __setitem__(self, job_id, parms):
        """ Adds of updates an entry. """
        self._check_job_id(job_id)
        self._store(job_id, parms)

    def _store(self, job_id, parms):
        """ Stores the backlog data for a given job.

        Default implementation uses pickle for this. Override this method if a
        different format is needed.

        No validity check is done on job_id here since it is supposed to have
        been done at public methods level.
        """
        with open(self._fpath(job_id), 'wt') as fp:
            pickle.dump(parms, fp)

    def __delitem__(self, job_id):
        """ Removes an entry.

        :raises KeyError: if it does not exist
        """
        self._check_job_id(job_id)
        try:
            os.remove(self._fpath(job_id))
        except OSError:
            raise KeyError(job_id)
        else:
            return True

    def __getitem__(self, job_id):
        """ Returns an entry.

        :raises KeyError: if it does not exist
        """
        self._check_job_id(job_id)
        try:
            return self._load(job_id)
        except (IOError, OSError):
            raise KeyError(job_id)

    def _load(self, job_id):
        """ Load the backlog data for a given job.

        Default implementation uses pickle for this. Override hhis method if a
        different format is needed.
        """
        with open(self._fpath(job_id), 'rt') as fp:
            return pickle.load(fp)

    def __len__(self):
        return len([
            f for f in os.listdir(self._location)
            if f.endswith(self.FILE_EXTENSION)
        ])

    def is_empty(self):
        return len(self) == 0

    def __iter__(self):
        lg = len(self.FILE_EXTENSION)
        for item in sorted(f[:-lg]
                            for f in os.listdir(self._location)
                            if f.endswith(self.FILE_EXTENSION)
                            ):
            yield item

    def iteritems(self):
        for jobid, parms in ((jobid, self[jobid]) for jobid in self):
            yield jobid, parms

    def delete(self):
        """ Deletes the backlog directory.

        The backlog can no more be used afterwards, and any operation will
        raise an exception.

        :raises IOError: if not empty.
        """
        os.rmdir(self._location)

    @staticmethod
    def _check_job_id(job_id):
        """ Internal method for checking that the job id has an acceptable form."""
        if type(job_id) is not str:
            raise ValueError('job id must be a string')
        if not Backlog._job_id_re.match(job_id):
            raise ValueError('invalid job id (%s)' % job_id)


class ExportError(Exception):
    def __init__(self, msg, subcode=0):
        Exception.__init__(self, msg)
        self._subcode = subcode % 100

    @property
    def subcode(self):
        return self._subcode
