'''The ``pretty_progress`` fixture lets a test edit the live progress line.'''

import pytest

from pretty_report.progress import NullProgress, Progress
from pretty_report.reporter import _RunningLine


def make():
    line = _RunningLine('t.py::test_x', False, None)
    return line, Progress(line)


def test_update_sets_message_and_counts():
    line, progress = make()
    progress.update(message='working', completed=2, total=8)
    assert (line.message, line.completed, line.total) == ('working', 2, 8)


def test_update_leaves_unspecified_fields_alone():
    line, progress = make()
    progress.update(message='a', completed=2, total=8)
    progress.update(completed=5)
    assert (line.message, line.completed, line.total) == ('a', 5, 8)


def test_advance_increments_and_sets_message():
    line, progress = make()
    progress.update(total=3)
    progress.advance()
    progress.advance(2, message='done')
    assert (line.completed, line.message) == (3, 'done')


def test_properties_reflect_state():
    _, progress = make()
    progress.update(message='m', completed=1, total=4)
    assert (progress.message, progress.completed, progress.total) == ('m', 1, 4)


def test_null_progress_keeps_state_without_rendering():
    progress = NullProgress()
    progress.update(message='x', completed=1, total=2)
    progress.advance(message='y')
    assert (progress.completed, progress.total, progress.message) == (2, 2, 'y')


def test_fixture_is_no_op_without_pretty_reporter(pytester):
    pytester.makepyfile(
        '''
        def test_x(pretty_progress):
            pretty_progress.update(total=3)
            pretty_progress.advance(message='hi')
        '''
    )
    result = pytester.runpytest_subprocess('--no-pretty')
    result.assert_outcomes(passed=1)


def test_fixture_works_with_pretty_reporter(pytester):
    pytester.makepyfile(
        '''
        def test_x(pretty_progress):
            pretty_progress.update(total=3)
            pretty_progress.advance(message='hi')
            assert pretty_progress.completed == 1
        '''
    )
    result = pytester.runpytest_subprocess('--pretty')
    result.assert_outcomes(passed=1)
