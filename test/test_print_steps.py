import sys

import pytest

from steps_widget.print_steps import (
    _EXAMPLE_TAGS,
    _STEPS_EXEC_ONELINER,
    _find_tagged_statement,
    run_student_file,
)


@pytest.mark.parametrize("tag", _EXAMPLE_TAGS)
def test_find_tagged_statement_recognizes_every_example_spelling(tag):
    indent, statement = _find_tagged_statement(f"    z = x + 1 {tag}\n")
    assert indent == "    "
    assert statement == "z = x + 1"


@pytest.mark.parametrize("tag", ["#steps", "# steps", "#\tsteps", "#     STEPS", "#stEpS"])
def test_find_tagged_statement_recognizes_the_short_steps_tag(tag):
    """`# steps` is the short spelling of the tag -- same case-insensitivity, and the
    same free (or absent) whitespace after the '#', as the `print steps` spellings."""
    assert _find_tagged_statement(f"z = x + 1  {tag}\n") == ("", "z = x + 1")


@pytest.mark.parametrize(
    "tag", ["#print steps", "#    pRint    steps", "#PRINT-STEPS", "# print - steps", "#printsteps"]
)
def test_find_tagged_statement_allows_free_whitespace_in_the_print_spelling(tag):
    assert _find_tagged_statement(f"z = x + 1  {tag}\n") == ("", "z = x + 1")


@pytest.mark.parametrize(
    "comment", ["# stepsize is 2", "# printstepsize", "# step", "# steppes", "# print"]
)
def test_find_tagged_statement_ignores_words_merely_starting_with_the_tag(comment):
    """The tag ends on a word boundary, so an ordinary trailing comment that happens to
    begin with 'step...' does not silently turn into a traced statement."""
    assert _find_tagged_statement(f"z = x + 1  {comment}\n") is None


@pytest.mark.parametrize("tag", ["# PRINT STEPS", "# steps"])
def test_find_tagged_statement_ignores_tag_inside_a_comment(tag):
    assert _find_tagged_statement(f"# a comment mentioning {tag}\n") is None


def test_find_tagged_statement_no_tag():
    assert _find_tagged_statement("x = 1\n") is None


def test_steps_exec_oneliner_is_valid_single_line_python():
    assert "\n" not in _STEPS_EXEC_ONELINER
    ns = {}
    exec(_STEPS_EXEC_ONELINER, ns)
    assert "_steps" in ns
    # "1 + 1" would be constant-folded away before _steps ever sees a step to
    # trace; abs(-1) + 1 forces an actual runtime reduction.
    result = ns["_steps"]("abs(-1) + 1")
    assert result[0] == "abs(-1) + 1"
    assert result[-1] == "2"


@pytest.mark.parametrize("tag", ["# PRINT STEPS", "# steps"])
def test_run_student_file_traces_tagged_lines(tmp_path, monkeypatch, capfd, tag):
    script = tmp_path / "student.py"
    script.write_text(
        "x = 7\n"
        "y = 5\n"
        f"z = x * y + 4  {tag}\n"
    )
    monkeypatch.setattr(sys, "argv", ["print-steps", str(script)])

    run_student_file()

    captured = capfd.readouterr()
    assert "As written:" in captured.err
    assert "z = x * y + 4" in captured.err
    assert "39" in captured.err
    # the shadow file is cleaned up afterwards
    assert not (tmp_path / "._student.py").exists()


def test_run_student_file_reports_broken_student_scripts(tmp_path, monkeypatch, capsys):
    script = tmp_path / "broken.py"
    script.write_text("1 / 0  # PRINT STEPS\n")
    monkeypatch.setattr(sys, "argv", ["print-steps", str(script)])

    with pytest.raises(SystemExit):
        run_student_file()

    captured = capsys.readouterr()
    assert "only works on code that runs" in captured.out
