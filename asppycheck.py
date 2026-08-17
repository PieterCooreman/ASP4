"""asppycheck.py - source-checkout shim for ASPPY.check.

The implementation lives in ASPPY/check.py so that it ships inside the
installed package and is exposed as the ``asppy-check`` console script.
This wrapper keeps the historical, documented invocation working when you
run ASPPY straight from a git checkout, without installing anything:

    python asppycheck.py www_test
    python asppycheck.py www --exclude drafts

Equivalent once ASPPY is pip-installed:

    asppy-check www_test
"""
import os
import sys

# Allow running from the repo root (or anywhere) without installing anything.
_project_root = os.path.abspath(os.path.dirname(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from ASPPY.check import find_asp_files, main  # noqa: E402

__all__ = ["find_asp_files", "main"]

if __name__ == "__main__":
    sys.exit(main())
