'''Pure formatting helpers.'''

from __future__ import annotations


def format_duration(seconds: float) -> str:
    if seconds < 0.001:
        return '<1ms'
    if seconds < 1:
        return f'{round(seconds * 1000)}ms'
    if seconds < 60:
        return f'{seconds:.1f}s'
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f'{hours}h {minutes:02d}m {secs:02d}s'
    return f'{minutes}m {secs:02d}s'
