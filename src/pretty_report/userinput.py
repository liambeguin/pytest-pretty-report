'''Handle handed to tests through the ``pretty_input`` fixture.'''

from __future__ import annotations

import contextlib
import getpass
import signal
import time

import pytest

from _pytest.stash import StashKey

NO_TERMINAL = 'no terminal available for user input'

#: Seconds the current test spent waiting for the user.
WAITED = StashKey[float]()
#: Whether the max_runtime timer of the current test is armed.
TIMER_ARMED = StashKey[bool]()


@contextlib.contextmanager
def clock_paused(item):
    '''Do not count the time spent in the block towards ``max_runtime``.'''
    started = time.perf_counter()
    remaining = 0.0
    if item.stash.get(TIMER_ARMED, False):
        remaining = signal.setitimer(signal.ITIMER_REAL, 0)[0]
    try:
        yield
    finally:
        item.stash[WAITED] = item.stash.get(WAITED, 0.0) + time.perf_counter() - started
        if remaining:
            signal.setitimer(signal.ITIMER_REAL, remaining)


def with_default(message: str, default: str | None) -> str:
    if default is None:
        return message
    return f'{message.rstrip()} [{default}] '


class UserInput:
    '''Block the test until the user types an answer.

    ``pretty_input('Board name? ', default='rpi4')``. The answer is returned
    as a string; an empty answer gives ``default`` (or ``''``). With
    ``secret=True`` nothing is echoed. The test is skipped when there is no
    terminal to ask on. Time spent waiting does not count towards
    ``min_runtime``/``max_runtime``.
    '''

    def __init__(self, item, ask):
        self._item = item
        self._ask = ask

    def __call__(self, message: str, *, default: str | None = None, secret: bool = False) -> str:
        with clock_paused(self._item):
            answer = self._ask(with_default(message, default), secret)
        if answer == '' and default is not None:
            return default
        return answer


def builtin_ask(message: str, secret: bool) -> str:  # noqa: FBT001
    '''Fallback used when the pretty reporter is off: plain ``input()``.'''
    try:
        return getpass.getpass(message) if secret else input(message)
    except (OSError, EOFError):  # pytest raises OSError when stdin is captured
        pytest.skip(NO_TERMINAL)
