# CLAUDE.md

Project context for `steps-widget` -- a Jupyter widget + CLI that trace Python
expression evaluation step by step (substitution, then reduction), built on
[anywidget](https://anywidget.dev).

## What this is

`steps-widget` is the new home for the `%%steps` cell magic and `print-steps`
console script that used to live in the `bp-help` teaching-tool repo (a course
package for an introductory Python programming class). The code was ported over
close to verbatim -- the stepper engine (`steps.py`) and the `# PRINT STEPS` tag
convention (`print_steps.py`) are unchanged; only import paths, entry points, and
packaging were adapted to this repo's `munch-group` template layout. `bp-help`
also shipped a `myiagi` TUI trainer (`textual`-based) that was **not** ported --
this repo covers only the notebook widget and the `print-steps` CLI.

The repo was scaffolded from the `munch-group` Python-library template (pixi
environment, quartodoc docs, conda/PyPI release automation) -- the same template
`turtle-widget` and `codelens-widget` use.

## Package layout

The package is `steps_widget` under `src/`:

- `src/steps_widget/steps.py` -- the stepper engine. `_steps(expr)` disassembles a
  Python expression string with `dis`, walks the CPython bytecode instructions one
  at a time through `_inst_map` (a dispatch table keyed by opcode name, e.g.
  `BINARY_ADD`, `CALL_FUNCTION`, `LOAD_ATTR`), and reconstructs the expression as a
  string after each operation -- producing a list of intermediate "steps" that
  mirror Python's actual evaluation order (substitution of variable/attribute/call
  loads, then reduction of each binary/unary op, with `and`/`or`/comparison chains
  surfaced as separate "Logic" steps to show short-circuiting). Pass
  `_with_labels=True` to get `(label, text)` pairs instead of bare strings --
  `label` is `"As written"` for the first entry, then whichever of
  `"Substitution"`/`"Reduction"`/`"Logic"` produced that step.
- `src/steps_widget/print_steps.py` -- `run_student_file()` (the `print-steps`
  entry point) takes a student `.py` file as `argv[1]`: first runs it unmodified
  to confirm it's error-free, then writes a shadow copy (`._<filename>`) with the
  entirety of `steps.py`'s source `exec()`'d (escaped onto one line via
  `_STEPS_EXEC_ONELINER`, so the shadow file's line numbers stay in sync with the
  original) at the top, and every line containing a `# PRINT STEPS`-style comment
  rewritten to call `_steps(expr, _print_steps=True)` before executing that line,
  printing each step to stderr. Runs the shadow file as a subprocess (via
  `sys.executable`, not a hardcoded `python` + `shell=True`, so it also works on
  Windows), then deletes it. The tag convention itself -- the recognized comment
  spellings (`_COMMENT_TAGS`) and the per-line detection (`_find_tagged_statement`,
  returning the indent and bare statement preceding the tag) -- lives here so
  `widget.py` can reuse the exact same tagging logic rather than re-implementing it.
- `src/steps_widget/widget.py` -- the `%%steps` cell magic and `StepsWidget`
  (an `anywidget.AnyWidget`). `_instrument_cell()` reuses `print_steps.py`'s
  `_find_tagged_statement`/`_STEPS_EXEC_ONELINER` to rewrite tagged statements so
  each one appends its `_steps(expr, _with_labels=True)` result to a collector list
  before running -- same tag convention, same one-physical-line injection trick as
  the CLI tool. Execution goes through `ip.run_cell()` (not a bare `exec()`) so the
  cell behaves like any other notebook cell -- exceptions display inline,
  assignments persist into the notebook's real `ip.user_ns` -- with the collector
  list popped back out afterward. Passing an explicit `namespace=` (instead of
  `None`) skips `ip.run_cell()` and `exec()`s into that dict directly, which is how
  the widget is tested headlessly (see Testing below). `StepsWidget` renders one
  card per tagged statement; `register_steps_magic()` runs at import time
  (wrapped in `try/except` so plain-Python imports don't fail outside IPython).
- `src/steps_widget/__init__.py` -- re-exports `StepsWidget`/`register_steps_magic`
  from `widget.py` (mirrors `turtle_widget`'s `from .widget import Turtle`).
  Importing `steps_widget` therefore both exposes the public API and registers the
  cell magic as a side effect.
- `test/` -- headless pytest suite (`test_steps.py`, `test_print_steps.py`,
  `test_widget.py`) + `conftest.py` that puts `src/` on `sys.path`.
- `docs/` -- Quarto + quartodoc site (`docs/pages/*.ipynb` prose, `docs/api/*.qmd`
  API ref -- the checked-in `.qmd` files are placeholders; run `pixi run api` to
  regenerate them from the live docstrings).
- `pyproject.toml` -- packaging metadata **and** the pixi workspace (deps + task
  runner).
- `conda-build/`, `.github/workflows/` -- conda/PyPI release on tag push, for
  macOS, Linux, and Windows.
- `scripts/` -- version-bump / docs-build / release helpers invoked by pixi tasks.

## Critical constraint: Python 3.9/3.10 only

`steps.py`'s dispatch table (`_inst_map`) is keyed by CPython 3.9/3.10 bytecode
opcode names (`BINARY_ADD`, `CALL_FUNCTION`, `LOAD_METHOD`/`CALL_METHOD`, ...).
Python 3.11 restructured many of these (`BINARY_ADD` and friends collapsed into
`BINARY_OP`; `CALL_FUNCTION`/`CALL_METHOD` replaced by `PRECALL`/`CALL`), so this
code cannot work unmodified on 3.11+. This is enforced two ways:

- `pyproject.toml` pins `requires-python = ">=3.9,<3.11"`, so `pip`/`conda` refuse
  to install the package on a newer interpreter.
- `_steps()` itself raises a `RuntimeError` with a clear message if
  `sys.version_info >= (3, 11)`, as a safety net for anyone who installs anyway
  (e.g. `pip install --ignore-requires-python`) -- without it the failure mode is a
  confusing `KeyError` on the missing opcode name.

Both the conda recipe (`conda-build/meta.yaml`) and the pixi workspace
(`[tool.pixi.dependencies]` in `pyproject.toml`) mirror this cap. **Do not** widen
`requires-python` without first reworking `steps.py`'s dispatch table for the
newer opcode set (see `bp-help`'s `CLAUDE.md` for the same note against its
`myiagi` TUI, which has the identical constraint and was never fixed).

## The `# PRINT STEPS` tag convention

Any of these spellings, trailing a statement, marks it for step tracing (see
`_COMMENT_TAGS` in `print_steps.py`): `# PRINT STEPS`, `#PRINT STEPS`,
`# PRINTSTEPS`, `#PRINTSTEPS`, `# PRINT-STEPS`, `#PRINT-STEPS`, and the lowercase
equivalents. A tag inside a comment-only line (nothing but `#...` before the tag)
is ignored, not traced.

## Environment & commands

Pixi-managed (config in `pyproject.toml` under `[tool.pixi.*]`; channels
`conda-forge` + `munch-group`; platforms `osx-arm64`, `linux-64`, `win-64`).
Python is pinned `>=3.9,<3.11` for the reason above -- pixi will fetch a 3.10
interpreter from conda-forge regardless of the system Python.

- Dev install: `pixi run install-dev` (editable, no build isolation).
- Run tests: `pixi run test` (== `pytest test/`).
- Try the CLI: `pixi run print-steps some_script.py` (or, after
  `install-dev`, plain `print-steps some_script.py`).
- Try the widget: open a notebook, `import steps_widget`, then use `%%steps`.
- Build docs: `pixi run api` (quartodoc API pages), then `pixi run docs` (execute
  the doc notebooks in place).
- Release: `pixi run bump` / `release` / `version` drive `scripts/bump_version.py`
  + a tag push, which triggers the conda/PyPI workflows.

## Distribution

Both `.github/workflows/conda-release.yml` and `pypi-release.yml` trigger on
version tag pushes (`vX.Y[.Z][.rcN]`):

- **conda**: builds natively on `macOS-latest`, `ubuntu-latest`, and
  `windows-latest` (matrix in `conda-release.yml`), using
  `conda-build/meta.yaml` -- which pins `python` (host and run) to
  `pyproject.toml`'s `requires-python` via Jinja
  (`load_file_data("../pyproject.toml", ...)`), so it never drifts from the
  Python cap above. Uploaded to the `munch-group` Anaconda.org channel.
- **pip**: pure-Python universal wheel (`build-wheel` job, no compiled
  extensions), published to PyPI. A single wheel installs on all three platforms;
  `pip` itself enforces the `requires-python` cap at install time.

## Gotchas

- **Constant folding hides steps.** CPython folds literal arithmetic like `1 + 2`
  at compile time, so `_steps("1 + 2")` disassembles straight to `LOAD_CONST 3` --
  there is no `BINARY_ADD` left to trace, and the result is just the one "As
  written" entry, unchanged. Always demo/test with a variable (`x + 1`) or a
  builtin call (`abs(-3) + 2`, never folded) to actually exercise a reduction step.
- The final step of a traced **assignment** statement re-attaches the `lhs = `
  prefix (e.g. `z = 39`), even though every intermediate substitution/reduction
  step shows the bare right-hand-side value (`39`). Expected -- don't "fix" the
  prefix-stripping regex in `_steps()` to strip it from the last step too.

## Testing approach

- `_steps()` operates on the **module globals of `steps_widget.steps` itself**
  (the dispatch functions call bare `globals()`), not on the caller's locals --
  tests that need variable substitution must set attributes on the `steps` module
  directly (`steps_module.x = 7`), not on local variables. This is also why every
  entry point historically `exec()`'d `steps.py`'s source into a shared namespace
  rather than `import`ing it: the bytecode dispatch needs `_steps` and the
  student's variables to live in the same `globals()`.
- `StepsWidget(code, namespace={})` (or any dict) skips the live-kernel
  `ip.run_cell()` path and `exec()`s into that dict instead -- this is how the
  widget is tested without a running Jupyter kernel (`test/test_widget.py`).
- `run_student_file()` is tested end-to-end (`test/test_print_steps.py`): it's
  driven via `monkeypatch.setattr(sys, "argv", ...)` on a real temp script, and
  since it shells out to a subprocess, output is captured with pytest's `capfd`
  (file-descriptor level), not `capsys`.
