"""JSON utility shim for VBScript.

Provides JSON.Encode(value) and JSON.Decode(json) with basic VBScript-friendly
type conversions.
"""

from __future__ import annotations

import json as _json
from typing import Any

from .vm.values import VBArray, VBEmpty, VBNull, VBNothing
from .vb_runtime import VBScriptRuntimeError
from .server_object import ScriptingDictionary

# NOTE: the zip/image/crypto/pdf/pop3/imap shims are intentionally imported
# lazily inside ASPPYShim below (not at module level), because they pull in
# optional third-party packages (Pillow, bcrypt, fpdf2) and heavy stdlib
# modules (email, poplib, imaplib) that most pages never use.


class JsonShim:
    def Encode(self, value, pretty=False):
        try:
            payload = _to_json_value(value)
        except Exception as e:
            raise VBScriptRuntimeError(f"JSON.Encode failed: {e}")
        if bool(pretty):
            return _json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)
        return _json.dumps(payload, ensure_ascii=True, separators=(",", ":"))

    def Decode(self, s):
        try:
            raw = _json.loads(str(s))
        except Exception as e:
            raise VBScriptRuntimeError(f"JSON.Decode failed: {e}")
        return _from_json_value(raw)


class ASPPYShim:
    _LAZY_ATTRS = ("zip", "image", "crypto", "pdf")

    def __init__(self):
        self.json = JsonShim()

    def __dir__(self):
        # Keep the lazily-provided shims visible to dir()-based (including
        # case-insensitive) attribute resolution in the VBScript VM.
        return sorted(set(super().__dir__()) | set(self._LAZY_ATTRS))

    def __getattr__(self, name):
        # Called only when normal attribute lookup fails. The result is
        # cached as a plain instance attribute, so the lazy import runs at
        # most once per attribute per shim instance.
        if name == "zip":
            from . import vb_zip
            value = vb_zip.ZipShim()
        elif name == "image":
            from . import vb_image
            value = vb_image.ASPPY_IMAGE
        elif name == "crypto":
            from . import vb_crypto
            value = vb_crypto.ASPPY_CRYPTO
        elif name == "pdf":
            from . import vb_pdf
            value = vb_pdf.ASPPY_PDF
        else:
            raise AttributeError(name)
        setattr(self, name, value)
        return value

    # NOTE: `code`/`path` are deliberately REQUIRED positional parameters. The
    # VM invokes zero-arg host callables on bare member access
    # (_maybe_invoke_zero_arg), so a default value here would make merely
    # *naming* ASPPY.ExecutePython spawn a Python subprocess. `args` and
    # `timeout` may safely default because the first parameter still makes a
    # bare zero-arg call raise TypeError.
    def ExecutePython(self, code, args=None, timeout=None):
        from . import vb_python
        return vb_python.ExecutePython(code, args, timeout)

    def ExecutePythonFile(self, path, args=None, timeout=None):
        from . import vb_python
        return vb_python.ExecutePythonFile(path, args, timeout)

    def pop3(self):
        from . import pop3 as vb_pop3
        return vb_pop3.ASPPYPOP3()

    def imap(self):
        from . import imap as vb_imap
        return vb_imap.ASPPYIMAP()


def _to_json_value(value: Any):
    if value is None or value is VBNull or value is VBEmpty or value is VBNothing:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, VBArray):
        return _vbarray_to_list(value)
    if isinstance(value, ScriptingDictionary):
        return _dict_to_obj(value)
    if isinstance(value, dict):
        return {str(k): _to_json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_value(v) for v in value]
    raise VBScriptRuntimeError(f"Unsupported JSON value type: {type(value).__name__}")


def _from_json_value(value: Any):
    if value is None:
        return VBNull
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return _list_to_vbarray(value)
    if isinstance(value, dict):
        d = ScriptingDictionary()
        for k, v in value.items():
            d.__vbs_index_set__(k, _from_json_value(v))
        return d
    return value


def _vbarray_to_list(arr: VBArray):
    if arr.dims() == 1:
        return [_to_json_value(arr.__vbs_index_get__(i)) for i in range(arr.ubound(1) + 1)]
    return _vbarray_to_nested(arr, 1, [])


def _vbarray_to_nested(arr: VBArray, dim: int, idxs):
    ub = arr.ubound(dim)
    out = []
    for i in range(ub + 1):
        idxs.append(i)
        if dim == arr.dims():
            out.append(_to_json_value(arr.__vbs_index_get__(idxs)))
        else:
            out.append(_vbarray_to_nested(arr, dim + 1, idxs))
        idxs.pop()
    return out


def _list_to_vbarray(items: list[Any]) -> VBArray:
    a = VBArray(len(items) - 1, allocated=True, dynamic=True)
    for i, v in enumerate(items):
        a.__vbs_index_set__(i, _from_json_value(v))
    return a


def _dict_to_obj(d: ScriptingDictionary):
    out = {}
    for k, v in d._d.values():
        out[str(k)] = _to_json_value(v)
    return out


ASPPY = ASPPYShim()
