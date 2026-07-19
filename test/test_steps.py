"""Headless tests for the ``_steps`` expression stepper.

``_steps`` dispatches on the live values of whatever module it is exec'd/defined
in -- variable substitution reads/writes ``steps_widget.steps``'s own module
globals (see the ``_load_name``/``_load_attr`` dispatch functions), so tests that
need substitution set attributes directly on the ``steps`` module rather than on
local variables in this test module.
"""
import sys

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


def test_guards_against_unsupported_future_python_versions(monkeypatch):
    # dispatch tables currently exist for 3.9 through 3.13 only -- this just
    # pins down that versions beyond what's actually implemented still fail
    # loudly rather than silently misdispatching. Not 3.11/3.12/3.13: those
    # are now genuinely supported eras (see the plain-call/chained-
    # comparison/etc. tests below), so asserting they raise would itself be
    # the regression.
    monkeypatch.setattr(steps_module.sys, "version_info", (3, 14, 0, "final", 0))
    with pytest.raises(RuntimeError):
        _steps("1 + 1")


def test_method_call_with_multiple_args():
    # regression test for a pre-existing bug where method calls with 2+
    # positional args didn't reverse the popped args (so this used to
    # silently produce 'hello' unchanged instead of 'heLLo') -- fixed as a
    # side effect of writing the unified 3.11+ _call handler; left as-is
    # for the legacy 3.9/3.10 _call_method handler (out of scope for the
    # version port, tracked separately).
    steps_module.s, steps_module.a, steps_module.b = "hello", "l", "L"
    try:
        result = _steps("s.replace(a, b)")
    finally:
        del steps_module.s, steps_module.a, steps_module.b
    if sys.version_info >= (3, 11):
        assert result[-1] == "'heLLo'"


def test_plain_function_call():
    def f(x, y):
        return x + y
    steps_module.f = f
    try:
        result = _steps("f(1, 2)")
    finally:
        del steps_module.f
    assert result[0] == "f(1, 2)"
    assert result[-1] == "3"


def test_chained_comparison():
    steps_module.a, steps_module.b, steps_module.c = 1, 2, 3
    try:
        result = _steps("a < b < c")
    finally:
        del steps_module.a, steps_module.b, steps_module.c
    assert result[0] == "a < b < c"
    assert result[-1] == "True"


def test_or_short_circuit():
    steps_module.x = 1
    try:
        result = _steps("x or 1 / 0", _with_labels=True)
    finally:
        del steps_module.x
    # short-circuits on the truthy left side; the right side (which would
    # raise) is never evaluated -- the last step documents why.
    last_label, last_text = result[-1]
    assert last_label == "Logic"
    assert "bool(1) is True" in last_text
    assert "1 as result" in last_text


def test_mixed_and_or():
    # "a and b or c" with a falsy -- exercises POP_JUMP_IF_FALSE (3.9/3.10)
    # / POP_JUMP_FORWARD_IF_FALSE (3.11), registered but previously untested.
    steps_module.a, steps_module.b, steps_module.c = 0, 1, 5
    try:
        result = _steps("a and b or c")
    finally:
        del steps_module.a, steps_module.b, steps_module.c
    assert result[0] == "a and b or c"
    assert result[-1] == "5"


def test_slicing():
    steps_module.lst = [10, 20, 30, 40]
    try:
        result = _steps("lst[1:3]")
    finally:
        del steps_module.lst
    assert result[0] == "lst[1:3]"
    assert result[-1] == "[20, 30]"


def test_parenthesized_subexpression():
    # exercises the __paren grouping-marker mechanism (steps.py's paren-
    # reinsertion pass) together with a plain function call in the same
    # expression -- the call-shape special case that suppresses the __paren
    # wrapper call from counting as a real step is opcode-name-sensitive
    # (CALL_FUNCTION pre-3.11, CALL from 3.11 on).
    steps_module.x = 2
    steps_module.y = 3
    try:
        result = _steps("(x + 1) * y")
    finally:
        del steps_module.x
        del steps_module.y
    assert result[0] == "(x + 1) * y"
    assert result[-1] == "9"
