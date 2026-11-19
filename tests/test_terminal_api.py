"""The reporter must look enough like pytest's TerminalReporter for plugins."""

import pytest

CONFTEST = '''
import json

def pytest_sessionfinish(session):
    tr = session.config.pluginmanager.getplugin('terminalreporter')
    data = {k: len(v) for k, v in tr.stats.items()}
    data['getreports_passed'] = len(tr.getreports('passed'))
    with open('stats.json', 'w') as f:
        json.dump(data, f)
'''


@pytest.fixture
def stats(pytester):
    import json

    def _run(source):
        pytester.makeconftest(CONFTEST)
        pytester.makepyfile(source)
        pytester.runpytest_subprocess()
        return json.loads((pytester.path / 'stats.json').read_text())

    return _run


def test_stats_follow_pytest_categories(stats):
    data = stats(
        '''
        import pytest

        def test_ok(): pass
        def test_bad(): assert 0
        @pytest.mark.skip
        def test_skip(): pass
        '''
    )
    assert data['passed'] == 1
    assert data['failed'] == 1
    assert data['skipped'] == 1
    # setup/teardown reports of passing phases live under '' like in pytest
    assert data[''] >= 4


def test_getreports(stats):
    assert stats('def test_ok(): pass')['getreports_passed'] == 1


def test_writer_api_present(pytester):
    pytester.makeconftest(
        '''
        def pytest_sessionfinish(session):
            tr = session.config.pluginmanager.getplugin('terminalreporter')
            for name in ('write', 'write_line', 'write_sep', 'section', 'line',
                         'ensure_newline', 'hasmarkup', 'verbosity'):
                assert hasattr(tr, name), name
        '''
    )
    pytester.makepyfile('def test_ok(): pass')
    result = pytester.runpytest_subprocess()
    output = result.stdout.str() + result.stderr.str()
    assert 'INTERNALERROR' not in output, output
    assert result.ret == 0
