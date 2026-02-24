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
from . import vb_zip
from . import vb_image
from . import vb_crypto
from . import vb_pdf


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


class ASP4Shim:
    def __init__(self):
        self.json = JsonShim()
        self.zip = vb_zip.ZipShim()
        self.image = vb_image.ASP4_IMAGE
        self.crypto = vb_crypto.ASP4_CRYPTO
        self.pdf = vb_pdf.ASP4_PDF


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


ASP4 = ASP4Shim()
