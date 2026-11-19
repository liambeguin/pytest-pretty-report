from __future__ import annotations

from datetime import timedelta

import pytest

MARKER_NAME = 'pretty_slow'


def slow(
    func=None,
    *,
    runtime: timedelta | None = None,
    min_runtime: timedelta | None = None,
    max_runtime: timedelta | None = None,
):
    '''Mark a test as slow, optionally with an expected runtime and bounds.

    Usable as ``@slow``, ``@slow()`` or ``@slow(runtime=timedelta(minutes=2))``.

    ``min_runtime`` and ``max_runtime`` make the test fail when its body (not
    its fixtures) finishes in less than ``min_runtime`` or takes longer than
    ``max_runtime``. With ``--enforce-max-runtime`` a test running beyond
    ``max_runtime`` is interrupted.
    '''
    for name, value in (
        ('runtime', runtime),
        ('min_runtime', min_runtime),
        ('max_runtime', max_runtime),
    ):
        if value is not None and not isinstance(value, timedelta):
            raise TypeError(f'{name} must be a datetime.timedelta')
    if min_runtime is not None and max_runtime is not None and min_runtime > max_runtime:
        raise ValueError('min_runtime must not be greater than max_runtime')
    mark = getattr(pytest.mark, MARKER_NAME)(
        runtime=runtime, min_runtime=min_runtime, max_runtime=max_runtime
    )
    return mark(func) if func is not None else mark
