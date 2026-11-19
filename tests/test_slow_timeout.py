'''--enforce-max-runtime interrupts tests running beyond max_runtime.'''

import time

import pytest

SLEEPER = '''
    import time
    from datetime import timedelta
    import pretty_report

    @pretty_report.slow(max_runtime=timedelta(milliseconds=200))
    def test_x(): time.sleep(30)
'''


@pytest.fixture(params=['--pretty', '--no-pretty'])
def run(pytester, request):
    def _run(source, *args):
        pytester.makepyfile(source)
        return pytester.runpytest_subprocess(request.param, *args)

    return _run


def test_flag_interrupts_a_test_beyond_max(run):
    start = time.monotonic()
    result = run(SLEEPER, '--enforce-max-runtime')
    assert time.monotonic() - start < 15
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(['*test interrupted after 200ms*'])


def test_interrupts_a_busy_loop(run):
    result = run(
        '''
        from datetime import timedelta
        import pretty_report

        @pretty_report.slow(max_runtime=timedelta(milliseconds=200))
        def test_x():
            while True:
                pass
        ''',
        '--enforce-max-runtime',
    )
    result.assert_outcomes(failed=1)


def test_without_flag_the_test_is_not_interrupted(run):
    result = run(
        '''
        import time
        from datetime import timedelta
        import pretty_report

        @pretty_report.slow(max_runtime=timedelta(milliseconds=50))
        def test_x(): time.sleep(0.3)
        '''
    )
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(['*exceeded the maximum of 50ms*'])
    assert 'test interrupted after' not in result.stdout.str()


def test_test_within_max_passes_with_flag(run):
    result = run(
        '''
        from datetime import timedelta
        import pretty_report

        @pretty_report.slow(max_runtime=timedelta(seconds=30))
        def test_x(): pass
        ''',
        '--enforce-max-runtime',
    )
    result.assert_outcomes(passed=1)


def test_timer_does_not_leak_into_following_tests(run):
    result = run(
        '''
        import time
        from datetime import timedelta
        import pretty_report

        @pretty_report.slow(max_runtime=timedelta(seconds=1))
        def test_a(): pass

        def test_b(): time.sleep(1.5)
        ''',
        '--enforce-max-runtime',
    )
    result.assert_outcomes(passed=2)


def test_fixture_time_does_not_count(run):
    result = run(
        '''
        import time
        from datetime import timedelta
        import pytest
        import pretty_report

        @pytest.fixture
        def slow_fixture(): time.sleep(0.5)

        @pretty_report.slow(max_runtime=timedelta(milliseconds=300))
        def test_x(slow_fixture): pass
        ''',
        '--enforce-max-runtime',
    )
    result.assert_outcomes(passed=1)


def test_ini_enables_enforcement(pytester):
    pytester.makeini('[pytest]\nenforce_max_runtime = true\n')
    pytester.makepyfile(SLEEPER)
    result = pytester.runpytest_subprocess()
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(['*interrupted*'])


def test_help_lists_the_flag(pytester):
    result = pytester.runpytest('--help')
    result.stdout.fnmatch_lines(['*--enforce-max-runtime*'])
