"""Execution context for a single ASP request."""

from __future__ import annotations

from ASP4.vb_err import VBErr
from ASP4.vm.values import VBEmpty
from typing import Any


class ExecutionContext:
    def __init__(self, response, request=None, server=None, session=None, application=None, err=None):
        self.Response = response
        self.Request = request
        self.Server = server
        self.Session = session
        self.Application = application
        self.Err = err if err is not None else VBErr()
        self.Interpreter: Any = None

    def _getref(self, name):
        n = str(name).upper() # explicit call, ensure upper
        interp = getattr(self, 'Interpreter', None)
        if interp is None:
            return VBEmpty
        try:
            # Fallback to global proc table; include current frame to pick up
            # ASP-page-level function declarations.
            if hasattr(interp, '_procs') and n in interp._procs:
                return interp._procs[n]
            try:
                proc = interp._get_proc(n)
                if proc is not None:
                    return proc
            except Exception:
                pass
            return interp._get_var_raw(n)
        except Exception:
            return VBEmpty
