'''slow(min=..., max=...) fails tests whose body runs outside the bounds.'''

import pytest


@pytest.fixture(params=['--pretty', '--no-pretty'])
def run(pytester, request):
    def _run(source):
        pytester.makepyfile(source)
        return pytester.runpytest_subprocess(request.param)

    return _run


def test_too_fast_test_fails(run):
    result = run(
        '''
        from datetime import timedelta
        import pretty_report

        @pretty_report.slow(min=timedelta(seconds=1))
        def test_x(): pass
        '''
    )
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(['*below the minimum of 1.0s*'])


def test_too_slow_test_fails(run):
    result = run(
        '''
        import time
        from datetime import timedelta
        import pretty_report

        @pretty_report.slow(max=timedelta(milliseconds=50))
        def test_x(): time.sleep(0.3)
        '''
    )
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(['*exceeded the maximum of 50ms*'])


def test_within_bounds_passes(run):
    result = run(
        '''
        import time
        from datetime import timedelta
        import pretty_report

        @pretty_report.slow(min=timedelta(milliseconds=50), max=timedelta(seconds=5))
        def test_x(): time.sleep(0.2)
        '''
    )
    result.assert_outcomes(passed=1)


def test_failing_test_keeps_its_own_failure(run):
    result = run(
        '''
        from datetime import timedelta
        import pretty_report

        @pretty_report.slow(min=timedelta(seconds=1))
        def test_x(): assert 1 == 2
        '''
    )
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(['*assert 1 == 2*'])
    result.stdout.no_fnmatch_line('*below the minimum*')


def test_setup_time_does_not_count(run):
    result = run(
        '''
        import time
        from datetime import timedelta
        import pytest
        import pretty_report

        @pytest.fixture
        def slow_fixture(): time.sleep(0.4)

        @pretty_report.slow(max=timedelta(milliseconds=200))
        def test_x(slow_fixture): pass
        '''
    )
    result.assert_outcomes(passed=1)


def test_unbounded_slow_test_is_unaffected(run):
    result = run(
        '''
        import pretty_report

        @pretty_report.slow()
        def test_x(): pass
        '''
    )
    result.assert_outcomes(passed=1)


def test_xfail_is_not_overridden(run):
    result = run(
        '''
        from datetime import timedelta
        import pytest
        import pretty_report

        @pytest.mark.xfail(reason='known')
        @pretty_report.slow(min=timedelta(seconds=1))
        def test_x(): assert 0
        '''
    )
    result.assert_outcomes(xfailed=1)


def test_short_summary_shows_the_reason(run):
    result = run(
        '''
        import time
        from datetime import timedelta
        import pretty_report

        @pretty_report.slow(max=timedelta(milliseconds=50))
        def test_x(): time.sleep(0.3)
        '''
    )
    result.stdout.fnmatch_lines(['FAILED *::test_x - test ran for *'])
