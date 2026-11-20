'''Deliberately slow test so the spinner / elapsed-time display is visible.'''

import time

from datetime import timedelta

import pytest

import pretty_report


@pretty_report.slow(runtime=timedelta(seconds=5))
def test_demo_slow_with_expected_runtime():
    time.sleep(3)


@pretty_report.slow()
def test_demo_slow_without_expected_runtime():
    time.sleep(2)


def test_demo_normal():
    time.sleep(2)


@pytest.mark.skip('just a demo')
def test_demo_skip():
    time.sleep(2)


@pytest.fixture
def slow_setup():
    """Shows 'setting up' with elapsed time on the spinner line."""
    time.sleep(3)
    yield
    time.sleep(3)  # shows 'tearing down' after the test body


def test_demo_phases(slow_setup):
    '''Spinner goes: setting up (3s) -> running (3s) -> tearing down (3s).'''
    time.sleep(3)


def test_demo_output():
    '''Prints while running: visible live with `-s`, captured without it.'''
    for i in range(1, 6):
        print(f'demo stdout line {i}')
        time.sleep(1)
    print('demo done')


@pytest.mark.xfail(raises=pytest.fail.Exception, reason='interrupted by design')
@pretty_report.slow(runtime=timedelta(seconds=3), max_runtime=timedelta(seconds=4))
def test_demo_timeout(request):
    '''Run with `--enforce-max-runtime`: interrupted after 4s instead of 30s.

    Without the flag it is skipped, so the regular suite stays quick.
    '''
    if not request.config.getoption('enforce_max_runtime'):
        pytest.skip('run with --enforce-max-runtime to see the interruption')
    time.sleep(30)
