#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Eric Pascual - CSTB (eric.pascual@cstb.fr)'


import threading
import time

from fysom import Fysom
from pycstbox.sysutils import parse_period


class TimedFSA(Fysom):
    def __init__(self, fysom_cfg, simulate_time=False, log=None):
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
        self.cancel_timer()
        self._timer = self._timer_factory(delay, function, *args, **kwargs)
        self._timer.start()

    def cancel_timer(self):
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def set_clock(self, time):
        if not self._simulate_time:
            raise RuntimeError('cannot change time if not in simulation')

        self._simulated_time = time
        self._log_clock()

        if self._timer and type(self._timer) is _SimulatedTimer:
            self._timer.set_clock(self._simulated_time)

    def advance_clock(self, delay):
        if not self._simulate_time:
            raise RuntimeError('cannot change time if not in simulation')

        if type(delay) in (int, float):
            secs = int(delay)
        else:
            secs = parse_period(delay)
        self._simulated_time += secs
        self._log_clock()

        if self._timer and type(self._timer) is _SimulatedTimer:
            self._timer.set_clock(self._simulated_time)

    def _get_simulated_time(self):
        return self._simulated_time

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
