from datetime import timedelta

import pytest

import pretty_report


def test_slow_attaches_marker_with_runtime():
    @pretty_report.slow(runtime=timedelta(minutes=2))
    def test_x():
        pass

    (mark,) = [m for m in test_x.pytestmark if m.name == 'pretty_slow']
    assert mark.kwargs['runtime'] == timedelta(minutes=2)


def test_slow_without_args_is_allowed():
    @pretty_report.slow()
    def test_x():
        pass

    (mark,) = [m for m in test_x.pytestmark if m.name == 'pretty_slow']
    assert mark.kwargs['runtime'] is None


def test_slow_usable_as_bare_decorator():
    @pretty_report.slow
    def test_x():
        pass

    assert any(m.name == 'pretty_slow' for m in test_x.pytestmark)


def test_slow_rejects_non_timedelta_runtime():
    with pytest.raises(TypeError):
        pretty_report.slow(runtime=120)
