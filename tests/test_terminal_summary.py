'''Sections other plugins add through ``pytest_terminal_summary``.'''


def test_third_party_section_is_shown(pytester):
    pytester.makeconftest(
        '''
        def pytest_terminal_summary(terminalreporter):
            terminalreporter.write_sep('=', 'my plugin report')
            terminalreporter.write_line('hello from a plugin')
        '''
    )
    pytester.makepyfile('def test_ok(): pass')
    result = pytester.runpytest_subprocess()
    result.stdout.fnmatch_lines(['*my plugin report*', 'hello from a plugin'])


def test_plugin_section_comes_before_final_line(pytester):
    pytester.makeconftest(
        '''
        def pytest_terminal_summary(terminalreporter):
            terminalreporter.write_line('PLUGIN-LINE')
        '''
    )
    pytester.makepyfile('def test_ok(): pass')
    out = pytester.runpytest_subprocess().stdout.str()
    assert out.index('PLUGIN-LINE') < out.index('1 passed')


def test_durations_option_works(pytester):
    pytester.makepyfile(
        '''
        import time

        def test_a(): time.sleep(0.02)
        def test_b(): pass
        '''
    )
    result = pytester.runpytest_subprocess('--durations=1', '--durations-min=0')
    result.stdout.fnmatch_lines(['*slowest 1 duration*', '*test_a*'])
