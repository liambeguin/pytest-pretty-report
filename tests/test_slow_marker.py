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


def test_slow_stores_min_and_max():
    @pretty_report.slow(min=timedelta(seconds=1), max=timedelta(seconds=5))
    def test_x():
        pass

    (mark,) = [m for m in test_x.pytestmark if m.name == 'pretty_slow']
    assert mark.kwargs['min'] == timedelta(seconds=1)
    assert mark.kwargs['max'] == timedelta(seconds=5)


@pytest.mark.parametrize('name', ['min', 'max'])
def test_slow_rejects_non_timedelta_bounds(name):
    with pytest.raises(TypeError, match=name):
        pretty_report.slow(**{name: 3})


def test_slow_rejects_min_above_max():
    with pytest.raises(ValueError, match='min'):
        pretty_report.slow(min=timedelta(seconds=5), max=timedelta(seconds=1))
