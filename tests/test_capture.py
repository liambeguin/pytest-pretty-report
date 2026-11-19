'''The spinner must be visible with and without output capture (-s).'''

import os
import pty
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform == 'win32', reason='needs a pty')

SPINNER_FRAMES = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'

SOURCE = '''
import time
import pretty_report

@pretty_report.slow()
def test_slow():
    print("hello-from-test")
    time.sleep(0.6)
'''


@pytest.fixture
def run_in_pty(pytester, monkeypatch):
    monkeypatch.delenv('FORCE_COLOR', raising=False)
    monkeypatch.setenv('COLUMNS', '100')
    pytester.makepyfile(SOURCE)

    def _run(*args):
        master, slave = pty.openpty()
        proc = subprocess.Popen(
            [sys.executable, '-m', 'pytest', '--pretty', '-p', 'no:cacheprovider', *args],
            stdout=slave,
            stderr=slave,
            cwd=pytester.path,
        )
        os.close(slave)
        chunks = []
        while True:
            try:
                data = os.read(master, 4096)
            except OSError:  # EIO once the child closes the pty
                break
            if not data:
                break
            chunks.append(data)
        proc.wait()
        os.close(master)
        return b''.join(chunks).decode(errors='replace')

    return _run


def frames_drawn(out):
    return sum(out.count(c) for c in SPINNER_FRAMES)


def test_spinner_animates_with_capture_enabled(run_in_pty):
    out = run_in_pty()
    assert frames_drawn(out) >= 3, out  # a frozen spinner draws only once


def test_spinner_animates_with_dash_s(run_in_pty):
    out = run_in_pty('-s')
    assert frames_drawn(out) >= 3, out


def test_dash_s_still_disables_capture(run_in_pty):
    assert 'hello-from-test' in run_in_pty('-s')


def test_output_is_captured_by_default(run_in_pty):
    assert 'hello-from-test' not in run_in_pty()


def frames_before(out, marker):
    return frames_drawn(out.split(marker)[0])


def test_spinner_shown_while_collecting(pytester, monkeypatch, run_in_pty):
    pytester.makeconftest('import time\ntime.sleep(0.8)\n')
    out = run_in_pty()
    assert 'collecting' in out, out
    assert frames_before(out, 'collected 1 item') >= 3, out


def test_slow_session_fixture_labelled_and_timed(pytester, run_in_pty):
    pytester.makepyfile(
        '''
        import time
        import pytest

        @pytest.fixture(scope="session")
        def db():
            time.sleep(2.6)

        def test_a(db):
            pass
        '''
    )
    out = run_in_pty('test_slow_session_fixture_labelled_and_timed.py')
    assert 'setting up 2.' in out, out
