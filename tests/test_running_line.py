from datetime import timedelta

from rich.console import Console

from pretty_report.reporter import _CollectingLine, _RunningLine


def render(line):
    console = Console(width=80, record=True, file=open('/dev/null', 'w'))
    console.print(line)
    return console.export_text()


def test_slow_line_shows_running_time_and_expected():
    line = _RunningLine('t.py::test_x', True, timedelta(minutes=2))
    line.phase = 'running'
    line.started -= 65  # pretend it has been running for 65s
    out = render(line)
    assert 't.py::test_x' in out
    assert 'running 1m 05s / expected 2m 00s' in out


def test_slow_line_without_expected_omits_it():
    line = _RunningLine('t.py::test_x', True, None)
    line.phase = 'running'
    out = render(line)
    assert 'running' in out
    assert 'expected' not in out


def test_regular_line_shows_no_timing():
    out = render(_RunningLine('t.py::test_x', False, None))
    assert 't.py::test_x' in out
    assert 'running' not in out


def test_slow_line_shows_current_phase():
    line = _RunningLine('t.py::test_x', True, None)
    assert 'setting up' in render(line)  # first phase, before any hook ran
    line.phase = 'tearing down'
    assert 'tearing down' in render(line)


def test_regular_line_shows_phase_and_elapsed_once_past_threshold():
    line = _RunningLine('t.py::test_x', False, None, threshold=2.0)
    line.started -= 3
    line.phase = 'setting up'
    out = render(line)
    assert 'setting up 3.0s' in out
    assert 'expected' not in out


def test_regular_line_stays_quiet_below_threshold():
    line = _RunningLine('t.py::test_x', False, None, threshold=2.0)
    line.started -= 1
    assert 'setting up' not in render(line)


def test_collecting_line_shows_item_count():
    line = _CollectingLine()
    line.count = 42
    out = render(line)
    assert 'collecting' in out
    assert '42 items' in out


def test_collecting_line_shows_elapsed_past_threshold():
    line = _CollectingLine(threshold=2.0)
    assert '1.' not in render(line)
    line.started -= 3
    assert '3.0s' in render(line)
