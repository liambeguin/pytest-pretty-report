"""Rich-based terminal reporter replacing pytest's default one."""

from __future__ import annotations

import contextlib
import os
import sys
import time
import warnings
from pathlib import Path

from datetime import timedelta
from typing import NamedTuple

import pytest

from _pytest.config import create_terminal_writer
from _pytest.pathlib import bestrelpath
from _pytest.terminal import getreportopt
from rich.console import Console
from rich.file_proxy import FileProxy
from rich.live import Live
from rich.progress_bar import ProgressBar
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


class _OutputProxy(FileProxy):
    """Route text written by tests above the live display.

    rich's own FileProxy advertises the real file through ``rich_proxied_file``,
    which makes every ``Console()`` created without an explicit file (so also
    ``rich.print``) unwrap it and write straight to the terminal, leaving the
    spinner row behind. Advertising ourselves keeps those consoles going
    through the live display.
    """

    @property
    def rich_proxied_file(self):
        return self


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
        # Edited by tests through the ``pretty_progress`` fixture.
        self.message: str | None = None
        self.completed: float = 0
        self.total: float | None = None

    def __rich__(self):
        table = Table.grid(padding=(0, 1))
        table.add_row(Spinner('dots'), Text(self.nodeid))
        elapsed = time.perf_counter() - self.started
        if self.slow or elapsed >= self.threshold:
            info = f'{self.phase} {format_duration(elapsed)}'
            if self.expected is not None:
                info += f' / expected {format_duration(self.expected.total_seconds())}'
            table.add_row('', Text(info, style='cyan'))
        if self.message or self.total is not None:
            table.add_row('', self._progress_row())
        return table

    def _progress_row(self):
        row = Table.grid(padding=(0, 1))
        cells = []
        if self.total is not None:
            cells.append(ProgressBar(total=self.total, completed=self.completed, width=24))
            cells.append(Text(f'{self.completed:g}/{self.total:g}'))
        if self.message:
            cells.append(Text(self.message))
        row.add_row(*cells)
        return row


class WarningEntry(NamedTuple):
    """One recorded warning, stored in ``stats['warnings']``."""

    nodeid: str
    message: str


WARNINGS_DOCS = 'https://docs.pytest.org/en/stable/how-to/capture-warnings.html'


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
        self._saved_streams = (sys.stdout, sys.stderr)
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

    # These write through the terminal writer, which knows nothing about the
    # live display, so pause it meanwhile (pytest's live logging relies on it).
    def write(self, content, *, flush=False, **markup):
        with self._live_paused():
            self._tw.write(content, flush=flush, **markup)

    def write_line(self, line, **markup):
        with self._live_paused():
            self._tw.line(str(line), **markup)

    line = write_line

    def write_sep(self, sep, title=None, fullwidth=None, **markup):
        with self._live_paused():
            self._tw.sep(sep, title, fullwidth, **markup)

    def flush(self):
        self._tw.flush()

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
        self._start_live(self._collecting)

    def _start_live(self, renderable):
        self._live = Live(
            renderable,
            console=self.console,
            transient=True,
            refresh_per_second=10,
            redirect_stdout=False,  # we install our own proxies below
            redirect_stderr=False,
        )
        self._live.start()
        self._saved_streams = (sys.stdout, sys.stderr)
        sys.stdout = _OutputProxy(self.console, sys.stdout)
        sys.stderr = _OutputProxy(self.console, sys.stderr)

    def _stop_live(self):
        if self._live is None:
            return
        # Only undo what is still ours: pytest's capture may have swapped them.
        saved_out, saved_err = self._saved_streams
        if isinstance(sys.stdout, _OutputProxy):
            sys.stdout = saved_out
        if isinstance(sys.stderr, _OutputProxy):
            sys.stderr = saved_err
        self._live.stop()
        self._live = None

    @contextlib.contextmanager
    def _live_paused(self):
        '''Stop the live display while something else writes to the terminal.'''
        live = self._live
        if live is None:
            yield
            return
        renderable = live.renderable
        self._stop_live()
        try:
            yield
        finally:
            self._start_live(renderable)

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
        self._start_live(self._running)

    @property
    def running_line(self) -> _RunningLine | None:
        '''Live line of the test being run, if any.'''
        return self._running

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

    @staticmethod
    def _crash_line(report):
        """First line of the crash message, or '' when there is none."""
        crash = getattr(report.longrepr, 'reprcrash', None)
        message = getattr(crash, 'message', '') or ''
        return message.splitlines()[0] if message else ''

    def _skip_lines(self):
        skips: dict[tuple, int] = {}
        for rep in self._results.get('skipped', []):
            path, lineno, reason = rep.longrepr
            key = (
                bestrelpath(self.config.invocation_params.dir, Path(path)),
                lineno,
                reason.removeprefix('Skipped: '),
            )
            skips[key] = skips.get(key, 0) + 1
        return [
            ('SKIPPED', f'[{count}] {path}:{lineno}: {reason}', 'yellow')
            for (path, lineno, reason), count in skips.items()
        ]

    def _outcome_lines(self, key, word, style, detail):
        return [
            (word, f'{rep.nodeid} - {info}' if (info := detail(rep)) else rep.nodeid, style)
            for rep in self._results.get(key, [])
        ]

    def _short_summary_lines(self):
        '''Lines for the -r characters, in the order pytest would print them.'''
        sections = {
            'f': lambda: self._outcome_lines('failed', 'FAILED', 'bold red', self._crash_line),
            'E': lambda: self._outcome_lines('error', 'ERROR', 'bold red', self._crash_line),
            's': self._skip_lines,
            'x': lambda: self._outcome_lines('xfailed', 'XFAIL', 'yellow', lambda r: r.wasxfail),
            'X': lambda: self._outcome_lines('xpassed', 'XPASS', 'yellow', lambda r: r.wasxfail),
            'p': lambda: self._outcome_lines('passed', 'PASSED', 'green', lambda r: ''),
        }
        sections['P'] = sections['p']
        lines, seen = [], set()
        for char in getreportopt(self.config):
            if char in sections and sections[char] not in seen:
                seen.add(sections[char])
                lines.extend(sections[char]())
        return lines

    def _print_short_summary(self):
        lines = self._short_summary_lines()
        if not lines:
            return
        self.console.print(Rule('short test summary info', style='dim'))
        for word, text, style in lines:
            line = Text()
            line.append(word, style=style)
            line.append(' ' + text)
            self.console.print(line, highlight=False, soft_wrap=True)

    def pytest_warning_recorded(self, warning_message, when, nodeid, location):
        text = warnings.formatwarning(
            warning_message.message,
            warning_message.category,
            warning_message.filename,
            warning_message.lineno,
            warning_message.line,
        )
        self.stats.setdefault('warnings', []).append(WarningEntry(nodeid or when, text.rstrip()))

    def _print_warnings(self):
        entries = self.stats.get('warnings', [])
        if not entries:
            return
        self.console.print(Rule('warnings summary', style='yellow'))
        by_node: dict[str, list[str]] = {}
        for entry in entries:
            by_node.setdefault(entry.nodeid, []).append(entry.message)
        for nodeid, messages in by_node.items():
            self.console.print(Text(nodeid, style='bold'))
            for message in messages:
                self.console.print(Text(message), highlight=False)
        self.console.print(Text(f'-- Docs: {WARNINGS_DOCS}', style='dim'))

    def _print_captured(self, report):
        '''Print captured stdout/stderr/log sections honoring --show-capture.'''
        mode = self.config.option.showcapture
        if mode == 'no':
            return
        for title, content in report.sections:
            if mode != 'all' and mode not in title.lower():
                continue
            self.console.print(Rule(title, style='dim'))
            self.console.print(Text(content.rstrip('\n')), highlight=False)

    # -- end ---------------------------------------------------------------
    def pytest_sessionfinish(self, session, exitstatus):
        self._stop_live()  # e.g. interrupted during collection
        failures = [r for k in ('failed', 'error') for r in self._results.get(k, [])]
        for rep in failures:
            self.console.print(Rule(f'{rep.nodeid} ({rep.when})', style='red'))
            self.console.print(Text(rep.longreprtext), highlight=False)
            self._print_captured(rep)
        self._print_warnings()
        # Sections added by other plugins (--durations, coverage, ...).
        self.config.hook.pytest_terminal_summary(
            terminalreporter=self, exitstatus=exitstatus, config=self.config
        )
        self._print_short_summary()
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
        n_warn = len(self.stats.get('warnings', []))
        if n_warn:
            parts.append((f'{n_warn} warning{"s" if n_warn != 1 else ""}', 'yellow'))
        elapsed = time.perf_counter() - self._start
        line = Text()
        for i, (txt, style) in enumerate(parts):
            line.append(', ' if i else '')
            line.append(txt, style=style)
        if not parts:
            line.append('no tests ran', style='yellow')
        line.append(f' in {elapsed:.2f}s')
        self.console.print(Rule(line, style='red' if failures else 'green'))
