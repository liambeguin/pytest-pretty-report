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
