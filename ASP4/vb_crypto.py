"""Crypto utility shim for VBScript (bcrypt)."""

from __future__ import annotations

try:
    import bcrypt as _bcrypt
except Exception:  # pragma: no cover
    _bcrypt = None

from .vb_runtime import VBScriptRuntimeError, vbs_cstr
from .vm.values import VBEmpty, VBNull, VBNothing


def _require_bcrypt():
    global _bcrypt
    if _bcrypt is None:
        try:
            import bcrypt as _bcrypt
        except Exception:
            import sys
            exe = getattr(sys, "executable", "python")
            raise VBScriptRuntimeError(
                "bcrypt is not available. Install with: "
                + exe
                + " -m pip install bcrypt"
            )


class CryptoShim:
    def Hash(self, password, rounds=12):
        _require_bcrypt()
        if password is VBEmpty or password is VBNull or password is VBNothing or password is None:
            raise VBScriptRuntimeError("Crypto.Hash: password is required")
        pw = vbs_cstr(password)
        if pw == "":
            raise VBScriptRuntimeError("Crypto.Hash: password is required")
        try:
            r = int(rounds)
        except Exception:
            raise VBScriptRuntimeError("Crypto.Hash: invalid rounds")
        if r < 4 or r > 31:
            raise VBScriptRuntimeError("Crypto.Hash: rounds must be 4..31")
        salt = _bcrypt.gensalt(rounds=r)
        h = _bcrypt.hashpw(pw.encode("utf-8"), salt)
        return h.decode("utf-8")

    def Verify(self, password, hashed):
        _require_bcrypt()
        if password is VBEmpty or password is VBNull or password is VBNothing or password is None:
            return False
        if hashed is VBEmpty or hashed is VBNull or hashed is VBNothing or hashed is None:
            return False
        pw = vbs_cstr(password)
        h = vbs_cstr(hashed)
        if pw == "" or h == "":
            return False
        try:
            return bool(_bcrypt.checkpw(pw.encode("utf-8"), h.encode("utf-8")))
        except Exception:
            return False


ASP4_CRYPTO = CryptoShim()
