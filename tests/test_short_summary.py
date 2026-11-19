"""The 'short test summary info' section and the -r option."""

import pytest

SOURCE = '''
import pytest

def test_ok(): pass

def test_bad():
    assert 1 == 2

@pytest.fixture
def broken():
    raise RuntimeError('fixture exploded')

def test_err(broken): pass

@pytest.mark.skip(reason='not today')
def test_skipped(): pass

@pytest.mark.xfail(reason='known bug')
def test_xf(): assert 0
'''


@pytest.fixture
def run(pytester):
    pytester.makepyfile(SOURCE)
    return pytester.runpytest_subprocess


def test_default_lists_failures_and_errors(run):
    result = run()
    result.stdout.fnmatch_lines(
        [
            '*short test summary info*',
            'FAILED *::test_bad - *assert 1 == 2*',
            'ERROR *::test_err - *fixture exploded*',
        ]
    )
    result.stdout.no_fnmatch_line('SKIPPED*')
    result.stdout.no_fnmatch_line('PASSED*')


def test_r_s_lists_skips_with_reason(run):
    result = run('-rs')
    result.stdout.fnmatch_lines(['SKIPPED [[]1] *test_r_s_lists_skips_with_reason.py:*: not today'])


def test_r_x_lists_xfail(run):
    result = run('-rx')
    result.stdout.fnmatch_lines(['XFAIL *::test_xf - known bug'])


def test_r_A_lists_everything_in_pytest_order(run):
    result = run('-rA')
    result.stdout.fnmatch_lines(
        [
            'PASSED *::test_ok',
            'SKIPPED*',
            'XFAIL *::test_xf*',
            'ERROR *::test_err*',
            'FAILED *::test_bad*',
        ]
    )


def test_r_N_hides_section(run):
    result = run('-rN')
    result.stdout.no_fnmatch_line('*short test summary info*')


def test_no_section_when_everything_passes(pytester):
    pytester.makepyfile('def test_ok(): pass')
    result = pytester.runpytest_subprocess()
    result.stdout.no_fnmatch_line('*short test summary info*')


def test_section_precedes_final_line(run):
    out = run().stdout.str()
    assert out.index('short test summary info') < out.index('1 failed')
