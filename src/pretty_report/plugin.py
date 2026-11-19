'''pytest plugin entry point.'''

from __future__ import annotations

import pytest

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
        f'{MARKER_NAME}(runtime=None): mark a slow test; the pretty reporter '
        'shows its elapsed time and the optional expected runtime (timedelta).',
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
