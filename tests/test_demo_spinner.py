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
