
import dis
import re
import types
from pprint import pprint
import subprocess
import os
import sys

from . import steps as _steps_module

# The tag that marks a statement for step tracing: a '#' followed by 'steps',
# optionally preceded by 'print'. Case-insensitive, and any amount of whitespace --
# or none -- is allowed between '#', 'print' and 'steps' (the two words may also be
# joined by a hyphen), so '#steps', '# STEPS', '# PRINT STEPS', '#print-steps' and
# '#    pRint    steps' are all the same tag. The trailing \b keeps a word that
# merely starts with the tag (e.g. '# stepsize') from triggering a trace.
_TAG_RE = re.compile(r'#\s*(?:print\s*-?\s*)?steps\b', re.IGNORECASE)

# A sample of recognized spellings, for documentation and for the test suite to pin.
# `_TAG_RE` -- not this list -- is what `_find_tagged_statement` matches against, and
# it recognizes infinitely many spellings (any whitespace run), so this is examples
# only, never an exhaustive enumeration.
_EXAMPLE_TAGS = [
    '# STEPS', '#STEPS', '# steps', '#steps', '#   Steps',
    '# PRINT STEPS', '#PRINT STEPS', '# PRINTSTEPS', '#PRINTSTEPS', '# PRINT-STEPS', '#PRINT-STEPS',
    '# print steps', '#print steps', '# printsteps', '#printsteps', '# print-steps', '#print-steps',
    '#    pRint    steps', '# print - steps',
    ]


def _find_tagged_statement(line):
    """If `line` carries a `# steps`/`# PRINT STEPS`-style tag (see `_TAG_RE`), return
    `(indent, statement)` for the code preceding the tag. Returns None if there is no
    tag, or the tag sits inside a comment (no code precedes it on the line)."""
    match = _TAG_RE.search(line)
    if not match:
        return None
    code = line[:match.start()]
    indent = ' ' * (len(code) - len(code.lstrip()))
    statement = code.strip()
    if statement and not statement.startswith('#'):
        return indent, statement
    return None


def _build_steps_exec_oneliner():
    """Encode the whole of steps.py as a single `exec(...)` line (source on one physical
    line), so injecting it ahead of instrumented code doesn't shift that code's line numbers."""
    with open(_steps_module.__file__) as f:
        steps_code = f.read()
    escaped = steps_code.translate(str.maketrans({"\\": r"\\", "\n": r"\n", "\'": r"\'", '\"': r'\"'}))
    return f'exec("""{escaped}""")'


# computed once; shared by run_student_file() and steps_widget.widget
_STEPS_EXEC_ONELINER = _build_steps_exec_oneliner()


def run_student_file():

    file_name = sys.argv[1]

    p = subprocess.run([sys.executable, file_name], capture_output=True)
    if p.returncode:
        print("""
Your encountered an errors. bphelp only works on code that runs.
See the error by running you code like this: python your_file.py
Fix that before you use bphelp.
""")
        sys.exit()

    dir_name = os.path.dirname(file_name)
    if not dir_name:
        dir_name = '.'
    tmpname = os.path.join(dir_name, '._' + os.path.basename(file_name))

    with open(file_name) as i:
        with open(tmpname, 'w') as o:

            print(_STEPS_EXEC_ONELINER, file=o)

            for lineno, line in enumerate(i):
                tagged = _find_tagged_statement(line)
                if tagged:
                    indent, expr = tagged
                    line = indent + f'print("Line ", sys._getframe().f_lineno - 1, " in {os.path.basename(file_name)}:", sep="", file=sys.stderr) ; _steps("""{expr}""", _print_steps=True) ; ' + line
                o.write(line)

    subprocess.run([sys.executable, tmpname], stdout=subprocess.DEVNULL)
    os.remove(tmpname)
