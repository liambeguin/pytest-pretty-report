'''Demo of the ``pretty_progress`` fixture; run it in a terminal to watch.'''

import time


def test_demo_progress_bar(pretty_progress):
    pretty_progress.update(total=10)
    for i in range(1, 11):
        pretty_progress.advance(message=f'processing item {i}')
        time.sleep(0.4)


def test_demo_status_message(pretty_progress):
    for step in ('connecting', 'authenticating', 'downloading', 'verifying'):
        pretty_progress.update(message=step)
        time.sleep(0.8)
