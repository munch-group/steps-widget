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


def test_bare_constant_expression_does_not_crash():
    # a *lone* literal (nothing for _wrap_literals to hang a BinOp/UnaryOp
    # wrap on) still constant-folds all the way through. On 3.12+ that
    # disassembles to a lone RETURN_CONST (no LOAD_CONST/BINARY_OP at all --
    # the whole computation happens at compile time), a distinct opcode from
    # the LOAD_CONST+RETURN_VALUE pair pre-3.12 emits for the same case;
    # regression test for a KeyError on RETURN_CONST.
    result = _steps("42")
    assert result == ["42"]


def test_literal_arithmetic_respects_operator_precedence():
    # _wrap_literals defeats the compiler's constant folding of pure-literal
    # sub-expressions (see the module docstring's "Constant folding hides
    # steps" note) by wrapping each numeric literal in an opaque __lit(...)
    # call, so this now traces through real BINARY_OP instructions instead
    # of disassembling straight to a single folded "20". Operator precedence
    # itself was never the problem -- the compiler already bakes it into the
    # *nesting* of the emitted instructions -- so multiplication (higher
    # precedence) reduces before either addition, and the additions then
    # apply left-to-right.
    result = _steps("3 + 2 * 4 + 9")
    assert result == ["3 + 2 * 4 + 9", "3 + 8 + 9", "11 + 9", "20"]


def test_literal_unary_negative_and_invert():
    # -3/~5 constant-fold to a bare LOAD_CONST too (confirmed empirically --
    # dis never emits UNARY_NEGATIVE/UNARY_INVERT for a literal operand), so
    # _wrap_literals wrapping the operand is what first exercises these two
    # dispatch handlers at all.
    assert _steps("-3 * 4") == ["-3 * 4", "-12"]
    assert _steps("~5 & 3") == ["~5 & 3", "-6 & 3", "2"]


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
