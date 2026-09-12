
# steps-widget

Jupyter widget and CLI that trace Python expression evaluation step by step.

- `%%steps` -- a cell magic (registered by `import steps_widget`) that renders the
  substitution/reduction trace of any `# steps`-tagged statement as a widget
  below the cell.
- `print-steps` -- the command-line equivalent: `print-steps student_script.py`
  prints the same trace to stderr for every tagged line in a script.

Tag convention: append `# steps` (or `# PRINT STEPS`, `#PRINT-STEPS`,
`# printsteps`, ...) to a statement to have it evaluated one operation at a time
instead of all at once. The tag is case-insensitive and the whitespace in it is
free -- `#steps`, `# STEPS` and `#    pRint    steps` all work; see
`steps_widget.print_steps._TAG_RE` for the exact pattern.

```python
import steps_widget

%%steps
x = 7
y = 5
z = x * y + 4  # steps
```

Requires **Python 3.10 through 3.13** -- the stepper dispatches on CPython
bytecode opcode names, which change across these versions; each is handled by
its own dispatch table (see `CLAUDE.md`).

```bash
pip install steps-widget
# or
conda install -c munch-group steps-widget
```

See the [docs](https://munch-group.org/steps-widget) for more.

## Initial set up

```bash
pixi run init
```

## Get updates to upstream fork

Add upstream if not already added

```bash
git remote add upstream https://github.com/munch-group/steps-widget.git
```

Fetch upstream changes

```bash
git fetch upstream
```

Either rebase your changes on top of upstream (cleaner history)

```bash
git rebase upstream/main
```

Or, merge upstream into your fork (preserves history)

```bash
git merge upstream/main
```

If you want to see what's changed upstream before applying:

```bash
git log HEAD..upstream/main
```

See the actual diff

```bash
git diff HEAD...upstream/main
```

Then push your updated fork:

```bash
git push origin main
```

If you rebased and need to force push
    
```bash
git push origin main --force-with-lease
```
