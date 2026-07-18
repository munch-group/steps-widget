"""Headless tests for the ``_steps`` expression stepper.

``_steps`` dispatches on the live values of whatever module it is exec'd/defined
in -- variable substitution reads/writes ``steps_widget.steps``'s own module
globals (see the ``_load_name``/``_load_attr`` dispatch functions), so tests that
need substitution set attributes directly on the ``steps`` module rather than on
local variables in this test module.
"""
import pytest

from steps_widget import steps as steps_module

_steps = steps_module._steps


def test_reduction_simple():
    # a literal expression like "1 + 2" is constant-folded away by the compiler
    # before _steps ever sees a BINARY_ADD to trace, so use a builtin call --
    # never folded -- to get an actual runtime reduction step.
    result = _steps("abs(-3) + 2")
    assert result[0] == "abs(-3) + 2"
    assert result[-1] == "5"


def test_with_labels_marks_written_and_reduction():
    result = _steps("abs(-3) + 2", _with_labels=True)
    labels = [label for label, _ in result]
    texts = [text for _, text in result]
    assert labels[0] == "As written"
    assert texts[0] == "abs(-3) + 2"
    assert labels[-1] == "Reduction"
    assert texts[-1] == "5"


def test_variable_substitution_and_reduction():
    steps_module.x = 7
    steps_module.y = 5
    try:
        result = _steps("x * y + 4", _with_labels=True)
    finally:
        del steps_module.x
        del steps_module.y

    labels = [label for label, _ in result]
    texts = [text for _, text in result]
    assert texts[0] == "x * y + 4"
    assert texts[-1] == "39"
    assert "Substitution" in labels
    assert "Reduction" in labels


def test_logic_short_circuit_and():
    steps_module.x = 0
    try:
        result = _steps("x and 1 / 0", _with_labels=True)
    finally:
        del steps_module.x
    # short-circuits on the falsy left side; the right side (which would raise)
    # is never evaluated -- the last step documents why.
    last_label, last_text = result[-1]
    assert last_label == "Logic"
    assert "bool(0) is False" in last_text
    assert "0 as result" in last_text


def test_method_call_and_attribute_access():
    steps_module.s = "hello"
    try:
        result = _steps("s.upper()")
    finally:
        del steps_module.s
    assert result[-1] == "'HELLO'"


def test_guards_against_python_311_and_later(monkeypatch):
    monkeypatch.setattr(steps_module.sys, "version_info", (3, 11, 0, "final", 0))
    with pytest.raises(RuntimeError):
        _steps("1 + 1")
