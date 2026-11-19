from __future__ import annotations

from datetime import timedelta

import pytest

MARKER_NAME = 'pretty_slow'


def slow(
    func=None,
    *,
    runtime: timedelta | None = None,
    min: timedelta | None = None,  # noqa: A002
    max: timedelta | None = None,  # noqa: A002
):
    '''Mark a test as slow, optionally with an expected runtime and bounds.

    Usable as ``@slow``, ``@slow()`` or ``@slow(runtime=timedelta(minutes=2))``.

    ``min`` and ``max`` make the test fail when its body (not its fixtures)
    finishes in less than ``min`` or takes longer than ``max``.
    '''
    for name, value in (('runtime', runtime), ('min', min), ('max', max)):
        if value is not None and not isinstance(value, timedelta):
            raise TypeError(f'{name} must be a datetime.timedelta')
    if min is not None and max is not None and min > max:
        raise ValueError('min must not be greater than max')
    mark = getattr(pytest.mark, MARKER_NAME)(runtime=runtime, min=min, max=max)
    return mark(func) if func is not None else mark
