'''The ``pretty_input`` fixture blocks for an answer typed by the user.'''

import pytest

ASK = '''
    def test_x(pretty_input):
        assert pretty_input('Board name? ') == 'rpi4'
'''


def test_prompt_is_shown_and_answer_returned(pytester, pty_session):
    pytester.makepyfile(ASK)
    lines, code = pty_session(['--pretty'], [('Board name?', 'rpi4\n', 0.1)])
    assert code == 0, lines
    assert any('Board name?' in line for line in pty_session.snapshots[0])
    assert '1 passed' in lines[-1]


def test_wrong_answer_is_seen_by_the_test(pytester, pty_session):
    pytester.makepyfile(ASK)
    lines, code = pty_session(['--pretty'], [('Board name?', 'other\n', 0.1)])
    assert code == 1, lines


def test_default_is_shown_and_used_on_empty_answer(pytester, pty_session):
    pytester.makepyfile(
        '''
        def test_x(pretty_input):
            assert pretty_input('Board? ', default='rpi4') == 'rpi4'
        '''
    )
    lines, code = pty_session(['--pretty'], [('Board?', '\n', 0.1)])
    assert code == 0, lines
    assert any('[rpi4]' in line for line in pty_session.snapshots[0])


def test_secret_answer_is_not_echoed(pytester, pty_session):
    pytester.makepyfile(
        '''
        def test_x(pretty_input):
            assert pretty_input('Token? ', secret=True) == 'hunter2'
        '''
    )
    lines, code = pty_session(['--pretty'], [('Token?', 'hunter2\n', 0.1)])
    assert code == 0, lines
    assert not any('hunter2' in line for line in lines)


def test_prompt_is_shown_under_the_test_name_and_indented(pytester, pty_session):
    pytester.makepyfile(ASK)
    pty_session(['--pretty'], [('Board name?', 'rpi4\n', 0.1)])
    (screen,) = pty_session.snapshots
    (name_row,) = [i for i, line in enumerate(screen) if '::test_x' in line]
    prompt_row = next(i for i, line in enumerate(screen) if 'Board name?' in line)
    assert prompt_row > name_row
    assert screen[prompt_row] == '  Board name?'  # under the name, past the spinner


def test_prompt_lines_up_with_the_slow_timing_row(pytester, pty_session):
    pytester.makepyfile(
        '''
        import pretty_report

        @pretty_report.slow()
        def test_x(pretty_input):
            pretty_input('Ready? ')
        '''
    )
    pty_session(['--pretty'], [('Ready?', '\n', 0.1)])
    (screen,) = pty_session.snapshots
    timing = next(line for line in screen if 'running' in line)
    prompt = next(line for line in screen if 'Ready?' in line)
    assert timing.index('running') == prompt.index('Ready?')
    assert screen.index(timing) < screen.index(prompt)


def test_prompt_is_erased_once_answered(pytester, pty_session):
    pytester.makepyfile(ASK)
    lines, _ = pty_session(['--pretty'], [('Board name?', 'rpi4\n', 0.1)])
    assert not any('Board name?' in line for line in lines)


def test_waiting_does_not_count_towards_max_runtime(pytester, pty_session):
    pytester.makepyfile(
        '''
        from datetime import timedelta
        import pretty_report

        @pretty_report.slow(max_runtime=timedelta(seconds=1))
        def test_x(pretty_input):
            pretty_input('Ready? ')
        '''
    )
    lines, code = pty_session(['--pretty'], [('Ready?', '\n', 2.0)])
    assert code == 0, lines


def test_waiting_does_not_trigger_the_interruption(pytester, pty_session):
    pytester.makepyfile(
        '''
        from datetime import timedelta
        import pretty_report

        @pretty_report.slow(max_runtime=timedelta(seconds=1))
        def test_x(pretty_input):
            pretty_input('Ready? ')
        '''
    )
    lines, code = pty_session(['--pretty', '--enforce-max-runtime'], [('Ready?', '\n', 2.0)])
    assert code == 0, lines


def test_time_after_the_prompt_still_counts(pytester, pty_session):
    pytester.makepyfile(
        '''
        import time
        from datetime import timedelta
        import pretty_report

        @pretty_report.slow(max_runtime=timedelta(seconds=1))
        def test_x(pretty_input):
            pretty_input('Ready? ')
            time.sleep(1.5)
        '''
    )
    lines, code = pty_session(['--pretty'], [('Ready?', '\n', 0.1)])
    assert code == 1, lines


@pytest.mark.parametrize('flag', ['--pretty', '--no-pretty'])
def test_skipped_without_a_terminal(pytester, flag):
    pytester.makepyfile(ASK)
    result = pytester.runpytest_subprocess(flag, '-rs')
    result.assert_outcomes(skipped=1)
    result.stdout.fnmatch_lines(['*no terminal*'])


def test_with_no_pretty_input_works_under_dash_s(pytester, pty_session):
    pytester.makepyfile(ASK)
    lines, code = pty_session(['--no-pretty', '-s'], [('Board name?', 'rpi4\n', 0.1)])
    assert code == 0, lines
