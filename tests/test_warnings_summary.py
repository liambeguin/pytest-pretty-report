'''Warnings are summarised at the end of the run.'''

import re


def test_warnings_summary_lists_warning(pytester):
    pytester.makepyfile(
        '''
        import warnings

        def test_warn():
            warnings.warn('be careful', UserWarning)
        '''
    )
    result = pytester.runpytest_subprocess()
    result.stdout.fnmatch_lines(['*warnings summary*', '*::test_warn', '*UserWarning: be careful*'])


def test_final_line_counts_warnings(pytester):
    pytester.makepyfile(
        '''
        import warnings

        def test_a():
            warnings.warn('one')

        def test_b():
            warnings.warn('two')
        '''
    )
    result = pytester.runpytest_subprocess()
    result.stdout.re_match_lines([r'.*2 passed, 2 warnings in .*'])


def test_singular_warning(pytester):
    pytester.makepyfile(
        '''
        import warnings

        def test_a():
            warnings.warn('one')
        '''
    )
    result = pytester.runpytest_subprocess()
    result.stdout.re_match_lines([r'.*1 passed, 1 warning in .*'])


def test_no_section_without_warnings(pytester):
    pytester.makepyfile('def test_ok(): pass')
    result = pytester.runpytest_subprocess()
    result.stdout.no_fnmatch_line('*warnings summary*')
    assert not re.search(r'\d+ warnings?', result.stdout.str())


def test_warnings_are_in_stats(pytester):
    pytester.makeconftest(
        '''
        def pytest_sessionfinish(session):
            tr = session.config.pluginmanager.getplugin('terminalreporter')
            open('n.txt', 'w').write(str(len(tr.stats.get('warnings', []))))
        '''
    )
    pytester.makepyfile(
        '''
        import warnings

        def test_a():
            warnings.warn('one')
        '''
    )
    pytester.runpytest_subprocess()
    assert (pytester.path / 'n.txt').read_text() == '1'
