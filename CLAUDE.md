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
also shipped a `myiagi` TUI trainer (`textual`-based); it was **not** ported
here -- this repo covers only the notebook widget and the `print-steps`
CLI -- but was later ported separately to
[`myiagi-widget`](https://github.com/munch-group/myiagi-widget), which
depends on this package for `steps_widget.steps._steps()` rather than
vendoring its own copy of the stepper.

The repo was scaffolded from the `munch-group` Python-library template (pixi
environment, quartodoc docs, conda/PyPI release automation) -- the same template
`turtle-widget` and `codelens-widget` use.

## Package layout

The package is `steps_widget` under `src/`:

- `src/steps_widget/steps.py` -- the stepper engine. `_steps(expr)` disassembles a
  Python expression string with `dis`, walks the CPython bytecode instructions one
  at a time (by list index, not raw byte offset) through one of three
  version-specific dispatch tables keyed by opcode name (e.g. `BINARY_ADD`,
  `CALL_FUNCTION`, `LOAD_ATTR` on 3.9/3.10; see "Multi-era bytecode dispatch"
  below for the 3.11/3.12/3.13 tables), and reconstructs the expression as a
  string after each operation -- producing a list of intermediate "steps" that
  mirror Python's actual evaluation order (substitution of variable/attribute/call
  loads, then reduction of each binary/unary op, with `and`/`or`/comparison chains
  surfaced as separate "Logic" steps to show short-circuiting). Pass
  `_with_labels=True` to get `(label, text)` pairs instead of bare strings --
  `label` is `"As written"` for the first entry, then whichever of
  `"Substitution"`/`"Reduction"`/`"Logic"` produced that step. Before
  disassembly, `_wrap_literals()` AST-rewrites numeric literals in arithmetic
  position into `__lit(...)` calls so operator-precedence chains like
  `3 + 2 * 4 + 9` step through their real reduction order instead of
  disassembling straight to a compiler-folded constant -- see "Constant
  folding hides steps" under Gotchas.
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
  `test_widget.py`) + `conftest.py` that puts `src/` on `sys.path`. Every test
  runs unmodified under whichever interpreter invokes pytest -- multi-version
  coverage comes from running the same suite under different real
  interpreters (see `.github/workflows/test.yml`'s matrix), not from
  version-conditional tests.
- `docs/` -- Quarto + quartodoc site (`docs/pages/*.ipynb` prose, `docs/api/*.qmd`
  API ref -- the checked-in `.qmd` files are placeholders; run `pixi run api` to
  regenerate them from the live docstrings).
- `pyproject.toml` -- packaging metadata **and** the pixi workspace (deps + task
  runner).
- `conda-build/`, `.github/workflows/` -- conda/PyPI release on tag push, for
  macOS, Linux, and Windows.
- `scripts/` -- version-bump / docs-build / release helpers invoked by pixi tasks.

## Multi-era bytecode dispatch: Python 3.10-3.13

`steps.py` disassembles expressions with `dis` and walks the resulting
instructions by **list index**, not raw byte offset: CPython 3.11+'s adaptive
interpreter inserts `CACHE` pseudo-instructions that `dis.get_instructions()`
hides from iteration by default but which still occupy real byte-offset space,
so `offset // 2`-style indexing (valid on 3.9/3.10, where every instruction is
exactly 2 bytes) silently breaks on 3.11+ independent of any opcode renaming.
`_offset_to_index()` resolves jump targets (byte offsets in `argval`) to list
positions by matching `.offset`, and every handler returns/consumes indices,
not offsets.

On top of that index-based walk, opcode *names* and *shapes* genuinely change
across CPython versions, so there are **three dispatch table pairs**
(`_inst_map`/`_inst_type` + era suffix), selected once near the top of
`_steps()` by `sys.version_info`:

- **`_inst_map`/`_inst_type`** (no suffix) -- Python 3.9/3.10. The original
  table; e.g. `BINARY_ADD`, `CALL_FUNCTION`, `CALL_METHOD`, `DUP_TOP`/`ROT_TWO`/
  `ROT_THREE`, `JUMP_IF_FALSE_OR_POP`/`JUMP_IF_TRUE_OR_POP`/`POP_JUMP_IF_FALSE`.
- **`_inst_map_311`/`_inst_type_311`** -- Python 3.11. Built as `dict(_inst_map)`
  plus overrides: `RESUME`/`PUSH_NULL`/`PRECALL` (no-ops), a generic
  `_binary_op` (all the `BINARY_*` opcodes collapse into `BINARY_OP`, keyed by
  `argrepr`'s operator symbol), a unified `_call` (`CALL_FUNCTION`/`CALL_METHOD`
  collapse into `CALL`), and generalized `_copy`/`_swap` (`DUP_TOP`/`ROT_TWO`/
  `ROT_THREE` collapse into `COPY(n)`/`SWAP(n)`). `JUMP_IF_FALSE_OR_POP`/
  `JUMP_IF_TRUE_OR_POP` are unchanged; `POP_JUMP_IF_FALSE` is renamed
  `POP_JUMP_FORWARD_IF_FALSE` (jumps became direction-qualified).
- **`_inst_map_312`/`_inst_type_312`** (plus a two-entry `_inst_map_313`/
  `_inst_type_313` diff for `TO_BOOL`) -- Python 3.12/3.13. `LOAD_METHOD` is
  folded into `LOAD_ATTR` (`_load_attr_312` detects the method-call shape via
  `argrepr != argval`, never parses `argrepr`'s "NULL|self" decoration, whose
  word order even flips between 3.12 and 3.13). `PRECALL` is gone. 2-argument
  slicing gets its own `BINARY_SLICE` opcode (3-argument slicing still routes
  through `BUILD_SLICE`+`BINARY_SUBSCR` on every version). Biggest change:
  `JUMP_IF_FALSE_OR_POP`/`JUMP_IF_TRUE_OR_POP` are retired entirely --
  `COPY(1)` [+ `TO_BOOL` on 3.13] + `POP_JUMP_IF_FALSE`/`POP_JUMP_IF_TRUE` +
  `POP_TOP` now implements *every* and/or/chained-comparison short-circuit
  shape uniformly, so `_pop_jump_if_false_312`/`_pop_jump_if_true_312`'s
  narrative text is deliberately role-agnostic rather than claiming "moves to
  right side of and/or" -- the same opcode now plays roles that used to be
  split across different opcodes with different narratives. They check
  whether the jump target is `RETURN_VALUE` to decide whether to use the
  precise pre-3.12 "terminates logic sequence" wording (genuinely terminal,
  e.g. isolated `and`/`or`) or the generic "short-circuits here" wording
  (jump lands on more logic-checking code, e.g. mixed `and`-then-`or`).
  3.12+ also peephole-collapses a plain `LOAD_CONST c; RETURN_VALUE` tail
  into one `RETURN_CONST` when the returned value is itself a literal --
  verified this only fires when the *entire* expression constant-folds to a
  single value (e.g. a bare `_steps("42")` disassembles to just
  `RESUME`+`RETURN_CONST`, no `BINARY_OP` left to trace, previously an
  unhandled `KeyError`); an and/or/comparison jump target that returns a
  literal still emits a genuine `RETURN_VALUE` reading off the stack
  (confirmed empirically for `x and 5`), so `_return_const` never interacts
  with the `POP_JUMP_IF_FALSE`/`POP_JUMP_IF_TRUE` jump-target checks above --
  it's the exact same "constant folding hides steps" case the Gotchas section
  documents, just 3.12+'s opcode spelling of it. `_wrap_literals` (see
  Gotchas) means this now only actually fires for a *lone* literal with
  nothing for it to wrap (a bare `_steps("42")`, or a non-numeric literal
  like a string) -- `_steps("3 + 2 * 4 + 9")` no longer takes this path at
  all on any version, `_return_const` is not dead code, just rarer.

`_call` (used by all three of 3.11/3.12/3.13) resolves the plain-call vs.
method-call shape by checking **both** of the two non-arg popped stack items
for identity against a `_NULL_SENTINEL` object, rather than assuming a fixed
pop position -- `PUSH_NULL`'s position relative to the callable genuinely
flips between 3.11/3.12 and 3.13 (verified empirically), and a fixed-position
assumption would silently swap the receiver and method name for one of the
three eras instead of crashing.

Each table's era also gets its own `_era_non_oprations` list (opcodes that
never get their own reveal step) and `_era_logic_opnames` list (which opcodes
`_is_not_logic_expr` treats as evidence of and/or/comparison logic, used to
suppress a spurious first "Sub-expression" step for non-logic expressions).
**When adding a new opcode to any era's table, always add pure-plumbing
opcodes to that era's `_era_non_oprations` too** -- `_inst_type[opname] = ''`
alone does *not* suppress the opcode name from leaking into the UI as a raw
label (the check at `_op_performed = _era_inst_type[_op_performed]` only
replaces a *truthy* mapped value, and `''` is falsy), which is exactly what
happened pre-fix with `DUP_TOP`/`ROT_TWO`/`ROT_THREE`/`POP_TOP`/`JUMP_FORWARD`
on 3.9/3.10 (confirmed live, e.g. `[DUP_TOP] 2 < c` instead of a blank label)
and would happen again for any new silent opcode that's declared only in
`_inst_type`.

This is enforced two ways:

- `pyproject.toml` pins `requires-python = ">=3.10,<3.14"`. The floor is
  3.10, not 3.9, even though `_steps()`'s dispatch logic itself still works
  fine on 3.9 (verified) -- `anywidget>=0.11,<0.12`, this package's own
  runtime dependency, requires Python `>=3.10` on both PyPI and conda-forge,
  so the package as a whole was never actually installable on 3.9 regardless
  of the stepper. The ceiling is 3.14 because that's as far as the dispatch
  tables above have been built and verified against real interpreters --
  nothing about CPython 3.14 has been checked.
- `_steps()` itself raises a `RuntimeError` with a clear message outside
  `[3.10, 3.14)`, as a safety net for anyone who installs anyway (e.g.
  `pip install --ignore-requires-python`) -- without it the failure mode
  would be a confusing `KeyError` on a missing opcode name.

The conda recipe (`conda-build/meta.yaml`) derives its Python pin from
`pyproject.toml`'s `requires-python` via Jinja, so it never needs a separate
manual edit when this cap changes. **Do not** widen `requires-python` past
3.14 without first repeating the empirical verification this range required:
`dis`-disassemble this tool's supported expression grammar (binary/bitwise
ops, comparisons incl. chained, `and`/`or` incl. mixed, method/function
calls, slicing, list/dict literals) under a real interpreter of the new
version and diff against what the nearest existing era table assumes --
CPython has restructured this bytecode at every 3.11/3.12/3.13 boundary so
far, there's no reason to expect 3.14 won't too. `myiagi-widget` now depends
on this package for exactly this dispatch table rather than vendoring its own
copy (as `bp-help`'s original `myiagi` TUI did, permanently pinned to
3.9/3.10 as a result) -- widening the cap here is what would let
`myiagi-widget` follow suit, so re-verify with that consumer in mind too.

**Known pre-existing gaps, out of scope for the dispatch tables above** (not
introduced by the multi-era port, not fixed by it either):
- `_call_method` (the 3.9/3.10-only handler for method calls) doesn't reverse
  popped args, so a 2+-arg method call silently uses the wrong argument order
  on 3.9/3.10 specifically (e.g. `"hello".replace("l", "L")` traced via
  `_call_method` produces `'hello'` unchanged instead of `'heLLo'`) -- fixed
  for 3.11+ as a side effect of writing the unified `_call` handler correctly,
  never backported to `_call_method` itself.
- List/dict comprehensions, lambdas, `for`-loops, user-defined function bodies
  (`MAKE_FUNCTION`/`LOAD_FAST`/`FOR_ITER`/`GET_ITER` etc.) and dict literals
  with non-constant keys (`{a: b}`, compiles to `BUILD_MAP`) all `KeyError`
  today on every supported version -- never implemented (abandoned partial
  attempts exist commented-out in `steps.py`), not a version-compatibility gap.

## The `# PRINT STEPS` tag convention

Any of these spellings, trailing a statement, marks it for step tracing (see
`_COMMENT_TAGS` in `print_steps.py`): `# PRINT STEPS`, `#PRINT STEPS`,
`# PRINTSTEPS`, `#PRINTSTEPS`, `# PRINT-STEPS`, `#PRINT-STEPS`, and the lowercase
equivalents. A tag inside a comment-only line (nothing but `#...` before the tag)
is ignored, not traced.

## Environment & commands

Pixi-managed (config in `pyproject.toml` under `[tool.pixi.*]`; channels
`conda-forge` + `munch-group`; platforms `osx-arm64`, `linux-64`, `win-64`).
Python is pinned `>=3.10,<3.14` for the reason above -- pixi will fetch a
matching interpreter from conda-forge regardless of the system Python (a
single environment/solve-group, currently resolving to 3.10; the wider
`3.10-3.13` range is exercised in CI via `.github/workflows/test.yml`'s
matrix, not via multiple local pixi environments).

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

- **Constant folding hides steps -- fixed for arithmetic via `_wrap_literals`.**
  CPython folds literal arithmetic like `1 + 2` at compile time, so disassembling
  `"1 + 2"` directly would go straight to `LOAD_CONST 3` -- no `BINARY_ADD` left
  to trace. `_steps()` now works around this: right after the assignment prefix
  is stripped, `_wrap_literals()` walks the expression's AST and rewrites every
  numeric literal (`int`/`float`/`complex`, not `bool`) that is an immediate
  operand of a `BinOp` or a `UnaryOp(USub|Invert)` into an opaque `__lit(...)`
  call (the same invisible-wrapper trick `__paren` already used for a different
  purpose -- see below) before the first `dis.Bytecode()` call. A call result
  can't be constant-folded, so the real `BINARY_OP`/`UNARY_*` instructions
  survive -- in precedence order, since precedence was never actually the
  problem: the compiler already bakes it into the *nesting* of the emitted
  instructions regardless of whether operands are constants or names. So
  `_steps("3 + 2 * 4 + 9")` now walks `"3 + 2 * 4 + 9"` -> `"3 + 8 + 9"` ->
  `"11 + 9"` -> `"20"` instead of jumping straight to `"20"`. `__lit`-wrapped
  literals never get a step of their own -- `_param_lit_call` (mirroring the
  existing `_param_fun_call` check for `__paren`) excludes their `CALL` from
  operation counting *and* forces `_evl=True` for it unconditionally, so a
  literal always resolves to its wrapped value immediately regardless of which
  operation index the current pass is revealing up to (unlike `__paren`, which
  intentionally stays symbolic until genuinely reached).

  Scope, and why: only `BinOp`/`UnaryOp(USub|Invert)` operands are wrapped --
  not list/dict/set/tuple elements, slice bounds, comparison/boolop operands, or
  plain call arguments. Those compile through opcodes (`LIST_EXTEND`'s
  single-constant-tuple optimization, `BUILD_SLICE`, the chained-comparison
  `COPY`/`SWAP`/`POP_JUMP` idiom, `CALL`) whose bytecode *shape* wrapping would
  silently change -- e.g. a constant-only list display normally folds its
  elements into one tuple constant fed to `LIST_EXTEND`; wrapped elements would
  produce a per-element `LOAD`/`CALL` shape `_list_extend` doesn't expect.
  `UnaryOp(UAdd)` (`+3`) is also deliberately excluded: unlike `-x`/`~x`, unary
  positive compiles to `CALL_INTRINSIC_1` (`INTRINSIC_UNARY_POSITIVE`) on 3.12+
  rather than a stable per-version opcode (confirmed empirically) -- wrapping it
  would raise `KeyError` there instead of producing a step. String literals
  aren't wrapped either (out of scope for this fix; `"a" + "b"` still folds).
  Wrapping a `-x`/`~x` literal operand also newly exposes genuine
  `UNARY_NEGATIVE`/`UNARY_INVERT` instructions that constant folding always
  hid before (e.g. `-3` alone still disassembles straight to `LOAD_CONST -3`,
  no unary opcode at all) -- both got dispatch handlers added to the base
  `_inst_map`/`_inst_type` table, inherited by all three era tables via the
  `dict(...)` copy chain since their opcode names don't change across
  3.9-3.13, unlike the `BINARY_*` family `BINARY_OP` superseded on 3.11+.
- The `lhs = ` prefix on a traced **assignment** statement's steps is reattached
  by whichever dispatch handler happens to produce that particular step's text
  -- it is not simply "final step only." `_return_value`/`_return_const` (the
  handlers that actually return the expression's value) reattach it every
  single time they fire, and for a plain substitution/reduction chain that's
  *every* step, since each iteration's walk independently re-terminates at
  `RETURN_VALUE`/`RETURN_CONST` (confirmed empirically, e.g. `_steps("z = x +
  1")` with `x = 7` gives `["z = x + 1", "z = 7 + 1", "z = 8"]` -- the prefix
  on the middle step too, not just the last). The prefix is genuinely *absent*
  only from steps produced by the and/or/chained-comparison jump handlers
  (`_jump_if_false_or_pop`, `_jump_if_true_or_pop`, `_pop_jump_if_false[_312]`,
  `_pop_jump_if_true_312`), which never thread `_prefix` through at all -- so a
  short-circuiting `Logic` step, or an intermediate chained-comparison
  `Reduction` step riding on one of those same jump opcodes, shows the bare
  sub-expression value inside a traced assignment, and the prefix reappears on
  whichever later step next comes from `_return_value`/`_return_const` (e.g.
  `_steps("z = a < b < c")` with `a,b,c = 1,2,3` includes a bare `"True"`
  reduction step for the `1 < 2` sub-comparison, then `"z = True"` once back at
  `RETURN_VALUE`). Don't "fix" the prefix-stripping regex in `_steps()` over
  this -- it's inherent to which handler produced a given step, not a bug.
- **Widget state must ship in `comm_open`, not a follow-up `update`.**
  `StepsWidget.__init__` computes the trace *before* `super().__init__()` and passes
  it in as a `sections=` constructor kwarg. This is load-bearing, not style:
  `ipywidgets.Widget.__init__` applies kwargs to the traits and only then calls
  `open()`, which publishes `comm_open` carrying `get_state()`. Assigning
  `self.sections` after `super().__init__()` instead (as the code originally did)
  leaves `comm_open` advertising the empty default and pushes the real trace as a
  separate `update` comm message -- which the frontend drops for the *first*
  anywidget of a browser session, while it is still asynchronously loading the
  anywidget package and this widget's `_esm`: the comm's message handler is not
  attached until that load resolves. The view then renders the "No '# PRINT
  STEPS'-tagged lines found" placeholder off the empty default and never recovers,
  because no `change:sections` event follows for `render()`'s listener to catch.
  Symptom was version-independent and Python-side-invisible: the first `%%steps`
  cell in a freshly opened notebook came up empty, every later run in that browser
  session worked, and a kernel restart also "fixed" it (a restart does not clear
  the browser's module cache). Confirmed by driving a real kernel over
  `jupyter_client` and reading the iopub comm traffic -- the trace itself was
  byte-identical on runs 1/2/3, only the message it rode in on differed.
  `test_sections_are_populated_before_the_comm_opens` pins this by spying on
  `open()` and asserting `get_state()["sections"]` is already complete there.
  Any future synced traitlet holding cell output belongs in the same initial
  state for the same reason.
- **The VS Code "Widget load failure ... @jupyter-widgets/base" log line is
  cosmetic -- do not "fix" it by emptying `jupyter.widgetScriptSources`.**
  VS Code's Jupyter extension tries its widget script-source providers in order --
  CDN first, then local -- and stops at the first that returns a script
  (`ipyWidgetScriptSourceProvider.ts`), so with the default-off CDN list turned on
  it fetches `@jupyter-widgets/base` and `anywidget` from jsdelivr/unpkg even
  though both are installed in the env. A failed fetch logs `Widget load failure`
  to the Jupyter output channel, but `@jupyter-widgets/base` only supplies the
  `layout` sub-widget (styling), and since the `comm_open` fix above the trace
  arrives in the widget's initial state -- so the steps still render regardless of
  whether, or how slowly, that fetch resolves. Setting `widgetScriptSources` to
  `[]` *would* make the CDN provider return with no network request at all
  (`cdnWidgetScriptSourceProvider.ts`) and fall through to the local provider,
  which reads `<sysPrefix>/share/jupyter/nbextensions/*/extension.js` and pulls
  module names out of each one's `require.config` map; both modules this package
  needs do resolve that way in a pixi env (`@jupyter-widgets/base` ->
  `jupyter-js-widgets/extension.js` from widgetsnbextension, `anywidget` ->
  `anywidget/index.js`). It was still rejected: the setting applies to *every*
  widget in scope, the local provider reads only `nbextensions`, and widget
  libraries that ship a labextension and no nbextension would lose their only
  fallback -- a repo-wide constraint on unrelated widgets in exchange for
  suppressing a log line that costs nothing. Fix the network path instead if it
  ever becomes a real failure. (If anyone does emulate the local lookup: anywidget's
  entry point writes `window.requirejs?.config({`, and the extension's
  `REQUIRE_PATTERNS` covers that optional-chaining spelling -- searching only for
  plain `requirejs.config` wrongly reports anywidget as unresolvable.)

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
