from __future__ import annotations

from datetime import timedelta

import pytest

MARKER_NAME = 'pretty_slow'


def slow(func=None, *, runtime: timedelta | None = None):
    '''Mark a test as slow, optionally with an expected runtime.

    Usable as ``@slow``, ``@slow()`` or ``@slow(runtime=timedelta(minutes=2))``.
    '''
    if runtime is not None and not isinstance(runtime, timedelta):
        raise TypeError('runtime must be a datetime.timedelta')
    mark = getattr(pytest.mark, MARKER_NAME)(runtime=runtime)
    return mark(func) if func is not None else mark
