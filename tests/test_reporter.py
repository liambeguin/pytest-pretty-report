import pytest


@pytest.fixture(autouse=True)
def _plain_env(monkeypatch):
    for var in ('FORCE_COLOR', 'COLUMNS'):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def run(pytester):
    def _run(source, *args):
        pytester.makepyfile(source)
        return pytester.runpytest_subprocess('--pretty', *args)

    return _run


def test_verbose_style_lines_with_outcomes(run):
    result = run(
        '''
        import pytest

        def test_ok(): pass
        def test_bad(): assert 1 == 2
        @pytest.mark.skip(reason="nope")
        def test_skipped(): pass
        @pytest.mark.xfail
        def test_xf(): assert False
        '''
    )
    result.stdout.re_match_lines(
        [
            r'.*test_verbose_style_lines_with_outcomes\.py::test_ok\s+PASSED\s+\[\s*25%\]',
            r'.*::test_bad\s+FAILED\s+\[\s*50%\]',
            r'.*::test_skipped\s+SKIPPED\s+\[\s*75%\]',
            r'.*::test_xf\s+XFAIL\s+\[100%\]',
        ]
    )


def test_default_reporter_is_replaced(run):
    result = run('def test_ok(): pass')
    result.stdout.no_fnmatch_line('*test_default_reporter_is_replaced.py .*')
    result.stdout.fnmatch_lines(['*PASSED*'])


def test_failure_details_and_summary(run):
    result = run('def test_bad():\n    assert 1 == 2\n')
    result.stdout.fnmatch_lines(['*assert 1 == 2*', '*1 failed*'])
    assert result.ret == 1


def test_summary_counts(run):
    result = run('def test_a(): pass\ndef test_b(): pass\n')
    result.stdout.re_match_lines([r'.*2 passed in .*'])


def test_session_header_and_collected_count(run):
    result = run('def test_a(): pass\ndef test_b(): pass\n')
    result.stdout.fnmatch_lines(['*test session starts*', 'collected 2 items'])


def test_slow_test_shows_elapsed_and_expected(run):
    result = run(
        '''
        import time
        from datetime import timedelta
        import pretty_report

        @pretty_report.slow(runtime=timedelta(minutes=2))
        def test_slow():
            time.sleep(0.05)
        '''
    )
    result.stdout.re_match_lines(
        [r'.*::test_slow PASSED\s+\[100%\]\s+took \d+ms \(expected 2m 00s\)']
    )


def test_slow_without_runtime_shows_only_elapsed(run):
    result = run(
        '''
        import pretty_report

        @pretty_report.slow
        def test_slow(): pass
        '''
    )
    result.stdout.re_match_lines([r'.*::test_slow PASSED\s+\[100%\]\s+took \S+$'])
    result.stdout.no_fnmatch_line('*expected*')


def test_regular_tests_show_no_timing(run):
    result = run('def test_fast(): pass')
    result.stdout.no_fnmatch_line('*took*')


def test_slow_failure_still_shows_elapsed(run):
    result = run(
        '''
        import pretty_report

        @pretty_report.slow()
        def test_slow(): assert False
        '''
    )
    result.stdout.re_match_lines([r'.*::test_slow FAILED\s+\[100%\]\s+took .*'])


def test_header_is_ours_not_default(run):
    result = run('def test_a(): pass')
    result.stdout.no_fnmatch_line('platform *')
    result.stdout.fnmatch_lines(['collected 1 item'])


def test_assertion_introspection_is_shown(run):
    result = run('def test_bad():\n    assert [1, 2] == [1, 3]\n')
    result.stdout.fnmatch_lines(['*At index 1 diff*'])
    result.stdout.no_fnmatch_line('*INTERNALERROR*')


def test_slow_call_test_shows_spinner_while_running(pytester, monkeypatch):
    monkeypatch.setenv('FORCE_COLOR', '1')  # make rich think it's a terminal
    monkeypatch.setenv('COLUMNS', '100')
    pytester.makepyfile(
        '''
        import time
        from datetime import timedelta
        import pretty_report

        @pretty_report.slow()
        def test_slow():
            time.sleep(0.6)
        '''
    )
    out = pytester.runpytest_subprocess('--pretty').stdout.str()
    spinner_frames = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    assert any(c in out for c in spinner_frames), 'no spinner frame rendered'
    assert 'running' in out


class TestEnablement:
    def test_on_by_default(self, pytester):
        pytester.makepyfile('def test_a(): pass')
        result = pytester.runpytest_subprocess()
        result.stdout.fnmatch_lines(['*test_a PASSED*'])

    def test_no_pretty_flag_restores_default_reporter(self, pytester):
        pytester.makepyfile('def test_a(): pass')
        result = pytester.runpytest_subprocess('--no-pretty')
        result.stdout.fnmatch_lines(['platform *'])
        result.stdout.no_fnmatch_line('*PASSED*')

    def test_ini_can_disable(self, pytester):
        pytester.makeini('[pytest]\npretty_report = false\n')
        pytester.makepyfile('def test_a(): pass')
        result = pytester.runpytest_subprocess()
        result.stdout.no_fnmatch_line('*PASSED*')

    def test_pretty_flag_overrides_ini(self, pytester):
        pytester.makeini('[pytest]\npretty_report = false\n')
        pytester.makepyfile('def test_a(): pass')
        result = pytester.runpytest_subprocess('--pretty')
        result.stdout.fnmatch_lines(['*test_a PASSED*'])

    def test_collect_only_uses_default_reporter(self, pytester):
        pytester.makepyfile('def test_a(): pass')
        result = pytester.runpytest_subprocess('--collect-only', '-q')
        result.stdout.fnmatch_lines(['*::test_a'])


def test_final_line_shows_bounds(run):
    result = run(
        '''
        import time
        from datetime import timedelta
        import pretty_report

        @pretty_report.slow(
            runtime=timedelta(seconds=2),
            min=timedelta(milliseconds=10),
            max=timedelta(minutes=1),
        )
        def test_slow():
            time.sleep(0.05)
        '''
    )
    result.stdout.re_match_lines(
        [r'.*::test_slow PASSED\s+\[100%\]\s+took \d+ms \(expected 2\.0s, min 10ms, max 1m 00s\)']
    )


def test_final_line_shows_only_max(run):
    result = run(
        '''
        from datetime import timedelta
        import pretty_report

        @pretty_report.slow(max=timedelta(seconds=30))
        def test_slow(): pass
        '''
    )
    result.stdout.re_match_lines([r'.*::test_slow PASSED\s+\[100%\]\s+took \S+ \(max 30\.0s\)'])
