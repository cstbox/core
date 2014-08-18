#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Eric Pascual - CSTB (eric.pascual@cstb.fr)'


import threading
import time

from fysom import Fysom
from pycstbox.sysutils import parse_period


class TimedFSA(Fysom):
    """ Specialized FSA providing time related features, such as timers,...
    """
    def __init__(self, fysom_cfg, simulate_time=False, log=None):
        """
        :param fysom_cfg: FSA configuration (see Fysom documentation)
        :param boolean simulate_time: set to True if time is simulated by explicit settings (useful for unit testing)
        :param Logger log: optional logger
        :return:
        """
        super(TimedFSA, self).__init__(fysom_cfg)
        self._timer_factory = self.get_simulated_timer if simulate_time else threading.Timer
        self._timer = None
        self._simulate_time = simulate_time
        self._simulated_time = 0
        self._log = log

        self.clock = self._get_simulated_time if simulate_time else time.time

    def _log_clock(self):
        if self._log:
            self._log.info("[SIM] clock is now %d", self._simulated_time)

    def start_timer(self, delay, function, *args, **kwargs):
        """ Starts a timer which will trigger a callback when expired.

        A common usage is to pass the timeout method generated for the associated event.

        :param delay: the timer delay, in seconds
        :param function: the function to be called at expiration time
        :param args: positional arguments to be transmitted to the callback
        :param kwargs: keyword arguments to be transmitted to the callback
        :return:
        """
        self.cancel_timer()
        self._timer = self._timer_factory(delay, function, *args, **kwargs)
        self._timer.start()

    def cancel_timer(self):
        """ Cancels the running timer, if any. Do nothing if none.
        """
        if self._timer:
            self._timer.cancel()
            self._timer = None

    @property
    def simulated_time(self):
        return self._simulated_time

    @simulated_time.setter
    def simulated_time(self, value):
        if not self._simulate_time:
            raise RuntimeError('cannot change time if not in simulated time mode')
        self._simulated_time = value
        self._log_clock()
        if self._timer and type(self._timer) is _SimulatedTimer:
            self._timer.set_clock(self._simulated_time)

    def set_clock(self, now):
        """ Manually sets the clock to a given time.

        Can be used only if the instance has been created with `simulate_time`
        parameter set to True.

        :param float now: the new time, as seconds
        :raise: RuntimeError if instance not created in simulated time mode
        """
        self.simulated_time = now

    def advance_clock(self, delay):
        """ Manually advances the clock by a given amount of seconds.

        Can be used only if the instance has been created with `simulate_time`
        parameter set to True.

        :param float delay: time shift to be applied (in seconds)
        :raise: RuntimeError if instance not created in simulated time mode
        """
        if type(delay) in (int, float):
            secs = int(delay)
        else:
            secs = parse_period(delay)
        self.simulated_time += secs

    def get_simulated_timer(self, delay, function, *args, **kwargs):
        timer = _SimulatedTimer(delay, function, self.clock(), *args, **kwargs)
        return timer


class _SimulatedTimer(object):
    _started = False
    _canceled = False
    _done = False

    def __init__(self, delay, function, now, args=[], kwargs={}):
        self._expiration_time = now + delay
        self.function = function
        self.args = args
        self.kwargs = kwargs

    def start(self):
        if self._done or self._started:
            raise RuntimeError('timers can only be started once' % id(self))
        self._started = True

    def cancel(self):
        self._canceled = True

    def set_clock(self, clock):
        if self._done:
            raise RuntimeError('timer already done (%d)' % id(self))
        if self._started and not self._canceled and self.function and clock >= self._expiration_time:
            self._done = True
            self.function(*self.args, **self.kwargs)
