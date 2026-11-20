# pytest-pretty-report

A small [rich](https://github.com/Textualize/rich)-based reporter for pytest.

```
pip install -e .
pytest            # the pretty reporter is on by default
```

Turn it off with `--no-pretty`, or per project in `pytest.ini` /
`pyproject.toml`:

```ini
[pytest]
pretty_report = false
```

`--pretty` forces it on (overriding the ini). `--collect-only` and runs
without a terminal reporter (`-p no:terminal`) use pytest's default output.

Output resembles `pytest -v`, with a spinner on the running test:

```
test_demo.py::test_fast PASSED  [ 25%]
test_demo.py::test_slow PASSED  [ 50%]  took 1.5s (expected 3.0s)
```

## Slow tests

```python
from datetime import timedelta
import pretty_report

@pretty_report.slow(runtime=timedelta(minutes=2))
def test_big_import(): ...
```

While running, the spinner line shows live elapsed time (and the expected
runtime if given); the final line shows `took ... (expected ...)`.
`@pretty_report.slow` and `@pretty_report.slow()` work too.

### Failing tests that are too fast or too slow

```python
@pretty_report.slow(runtime=timedelta(minutes=2),
                    min_runtime=timedelta(seconds=30),
                    max_runtime=timedelta(minutes=5))
def test_big_import(): ...
```

`min_runtime` and `max_runtime` turn the test into a failure when its body
ran for less than `min_runtime` or longer than `max_runtime` (`test ran for
12s, below the minimum of 30s`). Only the test body is timed: slow fixtures
don't count. By default the check happens after the test finishes. It never
overrides a test that already failed or an xfail, and works with and without
`--pretty`.

### Interrupting tests that run too long

Pass `--enforce-max-runtime` (or set `enforce_max_runtime = true` in the ini
file) to interrupt a test as soon as it runs past its `max_runtime`. It fails
with `test interrupted after 5m 00s: exceeded the maximum of 5m 00s`, and its
fixtures are still torn down normally.

The interruption uses `SIGALRM`, so it needs a POSIX platform and the main
thread; elsewhere a warning is emitted and the test runs to completion. Like
any signal-based timeout it cannot break out of a blocking C call that never
returns to the interpreter, and a test that swallows exceptions can swallow the
interruption.

## Development

```
uv venv && uv pip install -e . pytest
.venv/bin/python -m pytest
```

## Asking the user for input

Request the `pretty_input` fixture to block the test until the user types an
answer:

```python
def test_flash_board(pretty_input):
    board = pretty_input('Board name? ', default='rpi4')
    token = pretty_input('API token? ', secret=True)  # not echoed
    assert pretty_input('Is the LED blinking? [y/N] ').lower() == 'y'
```

The answer is returned as a string; an empty answer gives `default` (or `''`).
The live line is hidden while the prompt is shown, and capture is suspended so
you can type even without `-s`. When there is no terminal on stdin (CI, a
pipe) the test is skipped with `no terminal available for user input`. Time
spent waiting does not count towards `min_runtime`/`max_runtime`, and the
`--enforce-max-runtime` timer is paused meanwhile. The final `took ...` figure
does include it.

## Editing the live progress line

Request the `pretty_progress` fixture to show a status message and/or a
progress bar under the running test:

```python
def test_import(pretty_progress):
    pretty_progress.update(total=len(files))
    for f in files:
        pretty_progress.advance(message=f'importing {f.name}')
        do_import(f)
```

- `update(message=None, completed=None, total=None)` sets any of the fields
  and keeps the ones left out.
- `advance(step=1, message=None)` moves the bar forward.
- `message`, `completed` and `total` can be read back.

With `--no-pretty` (or any run without the pretty reporter) the fixture keeps
the same state but draws nothing, so tests don't need to care.

## End-of-run report

The rich reporter reproduces pytest's end-of-run output: failure tracebacks
with captured stdout/stderr/log (`--show-capture`), the warnings summary,
sections added by other plugins through `pytest_terminal_summary`
(`--durations`, coverage, ...) and the `short test summary info` driven by
`-r`.

## Known limitations

- `-q`/`-qq` and xdist output are not specially handled yet.
- `pytest_report_header` and other header sections are not printed.
