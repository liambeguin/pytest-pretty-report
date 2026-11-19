"""Failure reports include captured output, like pytest's default reporter."""

import pytest

SOURCE = '''
import logging
import sys

def test_bad():
    print('out-text')
    print('err-text', file=sys.stderr)
    logging.getLogger().warning('log-text')
    assert 0
'''


@pytest.fixture
def run(pytester):
    pytester.makepyfile(SOURCE)
    return pytester.runpytest_subprocess


def test_captured_stdout_is_shown(run):
    result = run()
    result.stdout.fnmatch_lines(['*Captured stdout call*', 'out-text'])


def test_captured_stderr_and_log_are_shown(run):
    result = run()
    result.stdout.fnmatch_lines(['*Captured stderr call*', 'err-text'])
    result.stdout.fnmatch_lines(['*Captured log call*', '*log-text*'])


def test_show_capture_no_hides_sections(run):
    result = run('--show-capture=no')
    result.stdout.no_fnmatch_line('*Captured*')
    result.stdout.no_fnmatch_line('out-text')


def test_show_capture_stdout_only(run):
    result = run('--show-capture=stdout')
    result.stdout.fnmatch_lines(['*Captured stdout call*'])
    result.stdout.no_fnmatch_line('*Captured stderr*')
    result.stdout.no_fnmatch_line('*Captured log*')


def test_passing_test_shows_nothing(pytester):
    pytester.makepyfile('def test_ok(): print("quiet")')
    result = pytester.runpytest_subprocess()
    result.stdout.no_fnmatch_line('*Captured*')
