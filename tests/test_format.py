import pytest

from pretty_report.format import format_duration


@pytest.mark.parametrize(
    'seconds, expected',
    [
        (0.0004, '<1ms'),
        (0.012, '12ms'),
        (1.234, '1.2s'),
        (59.94, '59.9s'),
        (61, '1m 01s'),
        (125, '2m 05s'),
        (3600, '1h 00m 00s'),
        (3725, '1h 02m 05s'),
    ],
)
def test_format_duration(seconds, expected):
    assert format_duration(seconds) == expected
