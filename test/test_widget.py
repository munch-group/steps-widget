"""Headless tests for ``StepsWidget``.

Passing an explicit ``namespace=`` skips the live-kernel ``ip.run_cell`` path (see
``steps_widget.widget._run_traced``), so the trace can be asserted on without a
running Jupyter kernel -- the same headless pattern used by the sibling
turtle-widget/codelens-widget test suites.
"""
from steps_widget import StepsWidget
from steps_widget.widget import register_steps_magic


def test_steps_widget_traces_tagged_statement():
    code = "x = 7\ny = 5\nz = x * y + 4  # PRINT STEPS\n"
    w = StepsWidget(code, namespace={})

    assert len(w.sections) == 1
    section = w.sections[0]
    assert section["line"] == 3
    assert section["code"] == "z = x * y + 4"

    labels = [step["label"] for step in section["steps"]]
    assert labels[0] == "As written"
    assert "Reduction" in labels
    # the final step re-attaches the "z = " assignment prefix
    assert section["steps"][-1]["text"] == "z = 39"


def test_steps_widget_multiple_tagged_lines_and_persistence():
    code = "x = 7\ny = 5\nz = x * y + 4  # PRINT STEPS\nk = z * 42  # PRINT STEPS\n"
    ns = {}
    w = StepsWidget(code, namespace=ns)

    assert len(w.sections) == 2
    # assignments in the traced code persist into the caller's namespace
    assert ns["z"] == 39
    assert ns["k"] == 39 * 42


def test_steps_widget_no_tagged_lines_yields_no_sections():
    w = StepsWidget("a = 1\nb = 2\n", namespace={})
    assert w.sections == []


def test_register_steps_magic_without_a_live_shell_returns_false():
    assert register_steps_magic(ipython=None) is False
