"""asppycli.py - source-checkout shim for ASPPY.cli.

The implementation lives in ASPPY/cli.py so that it ships inside the
installed package and is exposed as the ``asppy-render`` console script.
This wrapper keeps the historical, documented invocation working when you
run ASPPY straight from a git checkout, without installing anything:

    python asppycli.py www_test/index.asp
    python asppycli.py www_test/01-basics.asp -o out.html

Equivalent once ASPPY is pip-installed:

    asppy-render www_test/index.asp

Importing this module also re-exports render_file / parse_session_var, so
`from asppycli import render_file` keeps working in existing scripts.
"""
import os
import sys

# Allow running from the repo root (or anywhere) without installing the package.
_project_root = os.path.abspath(os.path.dirname(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from ASPPY.cli import main, parse_session_var, render_file  # noqa: E402

__all__ = ["main", "parse_session_var", "render_file"]

if __name__ == "__main__":
    sys.exit(main())
