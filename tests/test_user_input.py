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
    assert any('Board name?' in line for line in lines)
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
    assert any('[rpi4]' in line for line in lines)


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


def test_running_line_is_cleared_while_prompting(pytester, pty_session):
    pytester.makepyfile(ASK)
    lines, _ = pty_session(['--pretty'], [('Board name?', 'rpi4\n', 0.1)])
    prompts = [line for line in lines if 'Board name?' in line]
    assert len(prompts) == 1


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
