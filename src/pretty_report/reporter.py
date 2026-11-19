"""Rich-based terminal reporter replacing pytest's default one."""

from __future__ import annotations

import os
import time

from datetime import timedelta

import pytest

from _pytest.config import create_terminal_writer
from rich.console import Console
from rich.live import Live
from rich.rule import Rule
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from .format import format_duration
from .markers import MARKER_NAME

STYLES = {
    'PASSED': 'green',
    'FAILED': 'bold red',
    'ERROR': 'bold red',
    'SKIPPED': 'yellow',
    'XFAIL': 'yellow',
    'XPASS': 'yellow',
}


def slow_runtime(item):
    '''Return (is_slow, expected_runtime) for a collected item.'''
    mark = item.get_closest_marker(MARKER_NAME)
    if mark is None:
        return False, None
    return True, mark.kwargs.get('runtime')


def timing_text(elapsed: float, expected: timedelta | None) -> str:
    text = f'took {format_duration(elapsed)}'
    if expected is not None:
        text += f' (expected {format_duration(expected.total_seconds())})'
    return text


SHOW_TIMING_AFTER = 2.0  # seconds before a regular test gets a timing row


class _CollectingLine:
    '''Renderable shown while pytest imports and collects test modules.'''

    def __init__(self, threshold: float = SHOW_TIMING_AFTER):
        self.threshold = threshold
        self.count = 0
        self.started = time.perf_counter()

    def __rich__(self):
        elapsed = time.perf_counter() - self.started
        noun = 'item' if self.count == 1 else 'items'
        text = f'collecting... {self.count} {noun}'
        if elapsed >= self.threshold:
            text += f' ({format_duration(elapsed)})'
        table = Table.grid(padding=(0, 1))
        table.add_row(Spinner('dots'), Text(text))
        return table


class _RunningLine:
    '''Renderable for the currently running test; re-evaluated on each refresh.

    ``phase`` is updated by the reporter ("setting up", "running",
    "tearing down"). Slow tests always show a timing row; regular tests get
    one once they have been busy for ``threshold`` seconds, so slow fixtures
    are visible too.
    '''

    def __init__(self, nodeid, slow, expected, threshold: float = SHOW_TIMING_AFTER):
        self.nodeid, self.slow, self.expected = nodeid, slow, expected
        self.threshold = threshold
        self.phase = 'setting up'
        self.started = time.perf_counter()

    def __rich__(self):
        table = Table.grid(padding=(0, 1))
        table.add_row(Spinner('dots'), Text(self.nodeid))
        elapsed = time.perf_counter() - self.started
        if self.slow or elapsed >= self.threshold:
            info = f'{self.phase} {format_duration(elapsed)}'
            if self.expected is not None:
                info += f' / expected {format_duration(self.expected.total_seconds())}'
            table.add_row('', Text(info, style='cyan'))
        return table


class PrettyReporter:
    def __init__(self, config, console: Console | None = None):
        self.config = config
        self._dup_file = None
        out = self._open_output(config.get_terminal_writer()._file)
        # pytest internals (assertion rewriting etc.) and other plugins expect a
        # `_tw` writer on whatever is registered as "terminalreporter". It shares
        # the file with the rich console so their output stays ordered.
        self._tw = create_terminal_writer(config, out)
        self.console = console or Console(file=out)
        # Same layout as TerminalReporter.stats: {category: [reports]}.
        self.stats: dict[str, list] = {}
        # Per-test outcomes used for our own summary: {'passed': [report], ...}.
        self._results: dict[str, list] = {}
        self._items: dict[str, tuple[bool, timedelta | None]] = {}
        self._total = 0
        self._done = 0
        self._reports: list = []
        self._live: Live | None = None
        self._collecting: _CollectingLine | None = None
        self._running: _RunningLine | None = None
        self._start = time.perf_counter()

    def _open_output(self, stream):
        """Return a file bound to the *real* terminal.

        Under pytest's fd-capture, fd 1 is redirected while a test runs, so the
        refresh thread of the live display would write into the capture file.
        A duplicate of fd 1 taken now (capture is suspended during configure)
        keeps pointing at the terminal, so the spinner animates with or
        without ``-s``.
        """
        try:
            self._dup_file = os.fdopen(
                os.dup(stream.fileno()), 'w', encoding='utf-8', errors='replace'
            )
        except (AttributeError, OSError, ValueError):  # no real fd (e.g. StringIO)
            return stream
        return self._dup_file

    # -- API expected by plugins that talk to the terminal reporter ----------
    @property
    def hasmarkup(self):
        return self._tw.hasmarkup

    @property
    def verbosity(self):
        return self.config.get_verbosity()

    def write(self, content, *, flush=False, **markup):
        self._tw.write(content, flush=flush, **markup)

    def write_line(self, line, **markup):
        self._tw.line(str(line), **markup)

    line = write_line

    def write_sep(self, sep, title=None, fullwidth=None, **markup):
        self._tw.sep(sep, title, fullwidth, **markup)

    def section(self, title, sep='=', **kw):
        self.write_sep(sep, title, **kw)

    def ensure_newline(self):
        pass  # every write goes through whole lines

    def getreports(self, name):
        return list(self.stats.get(name, []))

    def _record(self, report):
        category, _, _ = self.config.hook.pytest_report_teststatus(
            report=report, config=self.config
        )
        self.stats.setdefault(category, []).append(report)

    def pytest_unconfigure(self):
        if self._dup_file is not None:
            self._dup_file.close()
            self._dup_file = None

    # -- session -----------------------------------------------------------
    def pytest_sessionstart(self, session):
        self._start = time.perf_counter()
        self.console.print(Rule('test session starts'))
        self._collecting = _CollectingLine()
        self._live = Live(
            self._collecting, console=self.console, transient=True, refresh_per_second=10
        )
        self._live.start()

    def _stop_live(self):
        if self._live is not None:
            self._live.stop()
            self._live = None

    def pytest_collection_finish(self, session):
        self._stop_live()
        self._total = len(session.items)
        self._items = {i.nodeid: slow_runtime(i) for i in session.items}
        self.console.print(f'collected {self._total} item{"s" if self._total != 1 else ""}\n')

    def pytest_collectreport(self, report):
        if self._collecting is not None:
            self._collecting.count += sum(
                isinstance(node, pytest.Item) for node in (report.result or [])
            )
        if report.failed:
            self.stats.setdefault('error', []).append(report)
        elif report.skipped:
            self.stats.setdefault('skipped', []).append(report)
        if report.failed:
            self._results.setdefault('error', []).append(report)
            self.console.print(Text(f'ERROR collecting {report.nodeid}', style='bold red'))
            self.console.print(Text(report.longreprtext), highlight=False)

    # -- per test ----------------------------------------------------------
    def pytest_runtest_logstart(self, nodeid, location):
        self._reports = []
        slow, expected = self._items.get(nodeid, (False, None))
        self._running = _RunningLine(nodeid, slow, expected)
        self._live = Live(
            self._running,
            console=self.console,
            transient=True,
            refresh_per_second=10,
        )
        self._live.start()

    def _set_phase(self, phase):
        if self._running is not None:
            self._running.phase = phase

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_setup(self, item):
        self._set_phase('setting up')

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_call(self, item):
        self._set_phase('running')

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_teardown(self, item):
        self._set_phase('tearing down')

    def pytest_runtest_logreport(self, report):
        self._reports.append(report)
        self._record(report)

    def pytest_runtest_logfinish(self, nodeid, location):
        self._stop_live()
        self._done += 1
        label, key, final = self._classify(self._reports)
        self._results.setdefault(key, []).append(final)

        slow, expected = self._items.get(nodeid, (False, None))
        line = Text()
        line.append(nodeid + ' ')
        line.append(label, style=STYLES[label])
        pct = int(100 * self._done / self._total) if self._total else 100
        line.append(f'  [{pct:3d}%]', style='dim')
        if slow:
            elapsed = sum(r.duration for r in self._reports)
            line.append('  ' + timing_text(elapsed, expected), style='cyan')
        self.console.print(line, highlight=False, soft_wrap=True)

    @staticmethod
    def _classify(reports):
        by_when = {r.when: r for r in reports}
        setup, call, teardown = (by_when.get(w) for w in ('setup', 'call', 'teardown'))
        if setup is not None and setup.failed:
            return 'ERROR', 'error', setup
        if teardown is not None and teardown.failed and (call is None or call.passed):
            return 'ERROR', 'error', teardown
        if setup is not None and setup.skipped:
            return 'SKIPPED', 'skipped', setup
        if call is not None:
            if hasattr(call, 'wasxfail'):
                if call.passed:
                    return 'XPASS', 'xpassed', call
                return 'XFAIL', 'xfailed', call
            if call.failed:
                return 'FAILED', 'failed', call
            if call.skipped:
                return 'SKIPPED', 'skipped', call
            return 'PASSED', 'passed', call
        return 'PASSED', 'passed', reports[-1]

    # -- end ---------------------------------------------------------------
    def pytest_sessionfinish(self, session, exitstatus):
        self._stop_live()  # e.g. interrupted during collection
        failures = [r for k in ('failed', 'error') for r in self._results.get(k, [])]
        for rep in failures:
            self.console.print(Rule(f'{rep.nodeid} ({rep.when})', style='red'))
            self.console.print(Text(rep.longreprtext), highlight=False)
        # Sections added by other plugins (--durations, coverage, ...).
        self.config.hook.pytest_terminal_summary(
            terminalreporter=self, exitstatus=exitstatus, config=self.config
        )
        parts = []
        for key, style in (
            ('failed', 'bold red'),
            ('error', 'bold red'),
            ('passed', 'green'),
            ('skipped', 'yellow'),
            ('xfailed', 'yellow'),
            ('xpassed', 'yellow'),
        ):
            n = len(self._results.get(key, []))
            if n:
                parts.append((f'{n} {key}', style))
        elapsed = time.perf_counter() - self._start
        line = Text()
        for i, (txt, style) in enumerate(parts):
            line.append(', ' if i else '')
            line.append(txt, style=style)
        if not parts:
            line.append('no tests ran', style='yellow')
        line.append(f' in {elapsed:.2f}s')
        self.console.print(Rule(line, style='red' if failures else 'green'))
