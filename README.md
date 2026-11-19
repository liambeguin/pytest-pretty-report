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

## Development

```
uv venv && uv pip install -e . pytest
.venv/bin/python -m pytest
```

## End-of-run report

The rich reporter reproduces pytest's end-of-run output: failure tracebacks
with captured stdout/stderr/log (`--show-capture`), the warnings summary,
sections added by other plugins through `pytest_terminal_summary`
(`--durations`, coverage, ...) and the `short test summary info` driven by
`-r`.

## Known limitations

- `-q`/`-qq` and xdist output are not specially handled yet.
- `pytest_report_header` and other header sections are not printed.
