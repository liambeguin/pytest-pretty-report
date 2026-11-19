'''Output written by tests and by pytest must not corrupt the live display.'''

import sys

import pytest

from conftest import SPINNER_FRAMES

pytestmark = pytest.mark.skipif(sys.platform == 'win32', reason='needs a pty')


def has_spinner(line):
    return any(c in line for c in SPINNER_FRAMES)


def test_rich_output_with_dash_s_leaves_no_stale_spinner_rows(pytester, pty_screen):
    pytester.makepyfile(
        '''
        import time
        import rich
        from rich.console import Console

        def test_out():
            print('PLAIN-PRINT')
            rich.print('[bold green]RICH-PRINT[/]')
            Console().print('[cyan]CONSOLE-PRINT[/]')
            time.sleep(0.4)
        '''
    )
    screen = pty_screen('-s')
    for text in ('PLAIN-PRINT', 'RICH-PRINT', 'CONSOLE-PRINT'):
        assert text in screen, screen  # on its own line, not glued to a spinner
    assert not any(has_spinner(line) for line in screen), screen
