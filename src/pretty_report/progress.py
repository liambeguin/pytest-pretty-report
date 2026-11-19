'''Handle handed to tests through the ``pretty_progress`` fixture.'''

from __future__ import annotations


class Progress:
    '''Edit the live line shown while the current test runs.

    ``message`` is free text, ``completed`` / ``total`` draw a progress bar.
    '''

    def __init__(self, line):
        self._line = line

    @property
    def message(self) -> str | None:
        return self._line.message

    @property
    def completed(self) -> float:
        return self._line.completed

    @property
    def total(self) -> float | None:
        return self._line.total

    def update(self, *, message=None, completed=None, total=None) -> None:
        '''Set any of the fields; the ones left out are kept.'''
        if message is not None:
            self._line.message = message
        if completed is not None:
            self._line.completed = completed
        if total is not None:
            self._line.total = total

    def advance(self, step: float = 1, *, message=None) -> None:
        '''Move the bar forward by ``step`` and optionally set a message.'''
        self.update(completed=self._line.completed + step, message=message)


class NullProgress(Progress):
    '''Same API, used when the pretty reporter is not active.'''

    def __init__(self):
        class _Line:
            message = None
            completed = 0
            total = None

        super().__init__(_Line())
