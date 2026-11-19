'''pytest plugin entry point.'''

from __future__ import annotations

import pytest

from .format import format_duration
from .markers import MARKER_NAME


def pytest_addoption(parser):
    group = parser.getgroup('pretty-report')
    group.addoption(
        '--pretty',
        dest='pretty',
        action='store_const',
        const=True,
        default=None,
        help='Use the rich-based pretty reporter (default; overrides the ini).',
    )
    group.addoption(
        '--no-pretty',
        dest='pretty',
        action='store_const',
        const=False,
        help="Use pytest's default terminal reporter.",
    )
    parser.addini(
        'pretty_report',
        type='bool',
        default=True,
        help='Use the rich-based pretty reporter by default (default: true).',
    )


def _enabled(config) -> bool:
    explicit = config.getoption('pretty')
    if explicit is not None:
        return explicit
    return config.getini('pretty_report')


@pytest.hookimpl(trylast=True)  # after the default terminal reporter registers
def pytest_configure(config):
    config.addinivalue_line(
        'markers',
        f'{MARKER_NAME}(runtime=None): mark a slow test; the pretty reporter '
        'shows its elapsed time and the optional expected runtime (timedelta).',
    )
    if not _enabled(config) or config.option.collectonly:
        return
    pm = config.pluginmanager
    default = pm.getplugin('terminalreporter')
    if default is None:  # e.g. -p no:terminal, or an xdist worker
        return
    from .reporter import PrettyReporter

    reporter = PrettyReporter(config)  # needs the default reporter's writer
    pm.unregister(default)
    pm.register(reporter, 'terminalreporter')
    _retarget_live_logging(pm, default, reporter)


def _retarget_live_logging(pm, old, new):
    '''Make ``log_cli`` write through our reporter.

    The logging plugin keeps the terminal reporter it found when it was
    configured, i.e. the default one we just replaced.
    '''
    handler = getattr(pm.get_plugin('logging-plugin'), 'log_cli_handler', None)
    if getattr(handler, 'stream', None) is old:
        handler.stream = new


@pytest.fixture
def pretty_progress(request):
    '''Edit the live progress line of the running test.

    ``pretty_progress.update(message=..., completed=..., total=...)`` and
    ``pretty_progress.advance()``. A no-op when the pretty reporter is off.
    '''
    from .progress import NullProgress, Progress
    from .reporter import PrettyReporter

    reporter = request.config.pluginmanager.getplugin('terminalreporter')
    if isinstance(reporter, PrettyReporter) and reporter.running_line is not None:
        return Progress(reporter.running_line)
    return NullProgress()


def check_bounds(duration: float, mark) -> str | None:
    """Return a failure message when ``duration`` is outside the mark's bounds."""
    low, high = mark.kwargs.get('min_runtime'), mark.kwargs.get('max_runtime')
    took = format_duration(duration)
    if low is not None and duration < low.total_seconds():
        return f'test ran for {took}, below the minimum of {format_duration(low.total_seconds())}'
    if high is not None and duration > high.total_seconds():
        return (
            f'test ran for {took}, exceeded the maximum of {format_duration(high.total_seconds())}'
        )
    return None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    mark = item.get_closest_marker(MARKER_NAME)
    if mark is None or call.when != 'call' or not report.passed or hasattr(report, 'wasxfail'):
        return
    message = check_bounds(report.duration, mark)
    if message is not None:
        report.outcome = 'failed'
        report.longrepr = message
