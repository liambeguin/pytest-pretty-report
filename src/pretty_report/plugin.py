'''pytest plugin entry point.'''

from __future__ import annotations

import signal
import threading
import warnings

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
    group.addoption(
        '--enforce-max-runtime',
        dest='enforce_max_runtime',
        action='store_true',
        default=None,
        help='Interrupt slow() tests that run beyond their max_runtime.',
    )
    parser.addini(
        'enforce_max_runtime',
        type='bool',
        default=False,
        help='Interrupt slow() tests that run beyond their max_runtime.',
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
        f'{MARKER_NAME}(runtime=None, min_runtime=None, max_runtime=None): mark a '
        'slow test; the pretty reporter shows its elapsed time and the optional '
        'expected runtime; min_runtime/max_runtime (timedelta) fail the test '
        'when its body runs outside them.',
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


def _enforcing(config) -> bool:
    explicit = config.getoption('enforce_max_runtime')
    if explicit is not None:
        return explicit
    return config.getini('enforce_max_runtime')


def _can_interrupt() -> bool:
    return hasattr(signal, 'setitimer') and threading.current_thread() is threading.main_thread()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    '''Interrupt the test body once it runs past ``max_runtime``.'''
    mark = item.get_closest_marker(MARKER_NAME)
    high = mark.kwargs.get('max_runtime') if mark is not None else None
    if high is None or not _enforcing(item.config):
        yield
        return
    if not _can_interrupt():
        warnings.warn(
            pytest.PytestWarning(
                f'{item.nodeid}: --enforce-max-runtime needs signal.setitimer on the main '
                'thread; the test will not be interrupted'
            ),
            stacklevel=1,
        )
        yield
        return

    message = (
        f'test interrupted after {format_duration(high.total_seconds())}: '
        f'exceeded the maximum of {format_duration(high.total_seconds())}'
    )

    def interrupt(signum, frame):
        pytest.fail(message, pytrace=False)

    previous = signal.signal(signal.SIGALRM, interrupt)
    signal.setitimer(signal.ITIMER_REAL, high.total_seconds())
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
