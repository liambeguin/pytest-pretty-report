'''Shared helpers: run pytest inside a pseudo-terminal and emulate the screen.'''

import os
import pty
import subprocess
import sys

import pyte
import pytest

SPINNER_FRAMES = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'


@pytest.fixture
def pty_screen(pytester, monkeypatch):
    '''Return ``run(*args) -> list[str]``: what the user sees after the run.'''
    monkeypatch.delenv('FORCE_COLOR', raising=False)
    monkeypatch.setenv('COLUMNS', '100')

    def run(*args):
        master, slave = pty.openpty()
        proc = subprocess.Popen(
            [sys.executable, '-m', 'pytest', '-p', 'no:cacheprovider', *args],
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
        screen = pyte.Screen(100, 400)
        pyte.Stream(screen).feed(b''.join(chunks).decode(errors='replace'))
        return [line.rstrip() for line in screen.display if line.strip()]

    return run


@pytest.fixture
def pty_session(pytester, monkeypatch):
    '''Return ``run(args, script) -> (lines, returncode)`` driving pytest as a user would.

    ``script`` is a list of ``(wait_for, send, delay)``: once ``wait_for`` shows
    up in the output, sleep ``delay`` seconds and type ``send``. Stdin is the
    terminal too, so the tests under run can prompt for input.
    '''
    import select
    import time

    monkeypatch.delenv('FORCE_COLOR', raising=False)
    monkeypatch.setenv('COLUMNS', '100')

    def render(chunks):
        screen = pyte.Screen(100, 400)
        pyte.Stream(screen).feed(b''.join(chunks).decode(errors='replace'))
        return [line.rstrip() for line in screen.display if line.strip()]

    def run(args, script):
        run.snapshots = []  # screen at the time each scripted answer was typed
        master, slave = pty.openpty()
        proc = subprocess.Popen(
            [sys.executable, '-m', 'pytest', '-p', 'no:cacheprovider', *args],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            cwd=pytester.path,
        )
        os.close(slave)
        chunks, pending, seen = [], list(script), b''
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if not select.select([master], [], [], 0.1)[0]:
                if proc.poll() is not None:
                    break
                continue
            try:
                data = os.read(master, 4096)
            except OSError:
                break
            if not data:
                break
            chunks.append(data)
            seen += data
            while pending and pending[0][0].encode() in seen:
                _, send, delay = pending.pop(0)
                seen = b''
                run.snapshots.append(render(chunks))
                time.sleep(delay)
                os.write(master, send.encode())
        proc.wait(timeout=30)
        os.close(master)
        return render(chunks), proc.returncode

    return run
