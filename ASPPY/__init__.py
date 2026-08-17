"""ASPPY - Classic ASP/VBScript runtime for Python.

Run legacy Classic ASP (VBScript) pages on Windows, Linux and macOS without
IIS or COM. See https://github.com/PieterCooreman/ASPPY for documentation.

Quick start::

    python -m ASPPY 0.0.0.0 8080 www

Submodules are imported lazily: importing ``ASPPY`` itself is cheap and pulls
in nothing but this docstring, so tools that only need ``__version__`` (build
backends, ``pip show``, packaging metadata) do not pay for the whole runtime.
"""

__version__ = "0.1.1"

__all__ = ["__version__"]
