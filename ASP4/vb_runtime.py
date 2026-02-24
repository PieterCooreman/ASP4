"""Tiny VBScript runtime helpers (type conversions, formatting)."""

from __future__ import annotations

import datetime as _dt
import locale as _locale
import math as _math
import re as _re
import threading as _threading

try:
    _locale.setlocale(_locale.LC_NUMERIC, '')
except Exception:
    pass


_fmt_tls = _threading.local()


def vbs_set_lcid(value):
    try:
        _fmt_tls.lcid = int(value)
    except Exception:
        _fmt_tls.lcid = 0


def vbs_get_lcid():
    return getattr(_fmt_tls, 'lcid', 0)


_LCID_INFO = {
    1033: {"decimal": ".", "thousands": ",", "currency": "USD", "date_short": "%m/%d/%Y", "date_long": "%A, %B %d, %Y", "time_short": "%H:%M", "time_long": "%H:%M:%S"},
    1041: {"decimal": ".", "thousands": ",", "currency": "JPY", "date_short": "%Y/%m/%d", "date_long": "%Y %B %d", "time_short": "%H:%M", "time_long": "%H:%M:%S"},
    1049: {"decimal": ",", "thousands": " ", "currency": "RUB", "date_short": "%d.%m.%Y", "date_long": "%d %B %Y", "time_short": "%H:%M", "time_long": "%H:%M:%S"},
    1031: {"decimal": ",", "thousands": ".", "currency": "EUR", "date_short": "%d.%m.%Y", "date_long": "%d. %B %Y", "time_short": "%H:%M", "time_long": "%H:%M:%S"},
    1025: {"decimal": ".", "thousands": ",", "currency": "SAR", "date_short": "%d/%m/%Y", "date_long": "%d %B %Y", "time_short": "%H:%M", "time_long": "%H:%M:%S"},
    1081: {"decimal": ".", "thousands": ",", "currency": "INR", "date_short": "%d-%m-%Y", "date_long": "%d %B %Y", "time_short": "%H:%M", "time_long": "%H:%M:%S"},
    2052: {"decimal": ".", "thousands": ",", "currency": "CNY", "date_short": "%Y-%m-%d", "date_long": "%Y %B %d", "time_short": "%H:%M", "time_long": "%H:%M:%S"},
    1042: {"decimal": ".", "thousands": ",", "currency": "KRW", "date_short": "%Y-%m-%d", "date_long": "%Y %B %d", "time_short": "%H:%M", "time_long": "%H:%M:%S"},
}


def vbs_get_lcid_info(lcid=None):
    if lcid is None:
        lcid = vbs_get_lcid()
    try:
        lcid = int(lcid)
    except Exception:
        lcid = 0
    return _LCID_INFO.get(lcid, _LCID_INFO.get(1033))


try:
    from .vm.values import VBEmpty, VBNull, VBNothing
except Exception:  # pragma: no cover
    VBEmpty = object()
    VBNull = object()
    VBNothing = object()


class VBScriptRuntimeError(Exception):
    pass


class VBScriptCOMError(VBScriptRuntimeError):
    """Represents a COM-style runtime error with an HRESULT-like number.

    Used so On Error Resume Next can populate Err.Number/Description with more
    accurate values than the generic 0x80004005.
    """

    def __init__(self, number: int, description: str = "", source: str = ""):
        super().__init__(description or str(number))
        self.number = int(number)
        self.description = str(description or "")
        self.source = str(source or "")


def vbs_cstr(value) -> str:
    """Best-effort VBScript-like CStr.

    Note: VBScript formats dates according to system locale. For cross-platform
    determinism this runtime uses ISO-like formats.
    """
    if value is None:
        return ""
    if value is VBEmpty or value is VBNothing or value is VBNull:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (bytes, bytearray)):
        # Treat binary strings as latin-1 to preserve 0-255 values.
        try:
            return bytes(value).decode('latin-1', errors='replace')
        except Exception:
            return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        # VBScript numeric string formatting is locale-dependent.
        # Approximate Single formatting: 7 significant digits, and IIS/VBScript
        # tends to emit scientific notation for values < 0.1.
        if value == 0.0:
            return "0"

        av = abs(value)
        if av < 0.1:
            # scientific with 6 decimals in mantissa (total ~7 sig digits)
            exp = int(_math.floor(_math.log10(av)))
            mant = value / (10 ** exp)
            s = f"{mant:.6f}"
            # Trim trailing zeros like VBScript tends to
            if '.' in s:
                s = s.rstrip('0').rstrip('.')
            s = f"{s}E{exp:+03d}"
        else:
            s = format(value, '.7g')
            if 'e' in s or 'E' in s:
                s = s.replace('e', 'E')
                m = _re.match(r"^(.*)E([+-]?)(\d+)$", s)
                if m:
                    mant, sign, exp2 = m.group(1), m.group(2) or '+', m.group(3)
                    s = mant + 'E' + sign + exp2.zfill(2)

        return s
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        if isinstance(value, _dt.datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, _dt.date):
            return value.strftime("%Y-%m-%d")
        return value.strftime("%H:%M:%S")
    # Only do the expensive _UserProc check if the object looks like one,
    # avoiding costly imports and getattr chains on every unrecognised type.
    if hasattr(value, 'kind') and hasattr(value, 'params'):
        try:
            from .vm import interpreter as _interp
            _UserProc = getattr(_interp, '_UserProc', None)
            if _UserProc is not None and isinstance(value, _UserProc):
                try:
                    interp = getattr(getattr(_interp, '_debug_tls', None), 'current', None)
                    if interp is not None and value.kind == 'FUNCTION' and len(value.params) == 0:
                        try:
                            res = interp._invoke_user_proc(value, [])
                            return vbs_cstr(res)
                        except Exception:
                            pass
                    proc_name = getattr(value, 'name', 'UnknownProc')
                    msg = f"[asp.py] _UserProc rendered to string: {proc_name}"
                    try:
                        pos = getattr(interp, '_last_stmt_pos', None) if interp is not None else None
                        src = getattr(interp, '_current_vbs_src', '') if interp is not None else ''
                        path = getattr(interp, '_current_asp_path', '') if interp is not None else ''
                        if pos is not None and src:
                            line = src.count("\n", 0, pos) + 1
                            last_nl = src.rfind("\n", 0, pos)
                            col = pos + 1 if last_nl == -1 else pos - last_nl
                            line_start = 0 if last_nl == -1 else last_nl + 1
                            line_end = src.find("\n", pos)
                            if line_end == -1:
                                line_end = len(src)
                            src_line = src[line_start:line_end]
                            msg += f" at {path or 'ASP'} line {line} col {col}: {src_line.strip()}"
                    except Exception:
                        pass
                    try:
                        print(msg)
                    except Exception:
                        pass
                    return ""
                except Exception:
                    pass
        except Exception:
            pass
    return str(value)


def vbs_cbool(value) -> bool:
    if value is VBEmpty or value is VBNull or value is VBNothing or value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "yes", "1"):
            return True
        if v in ("false", "no", "0", ""):
            return False
    return bool(value)


def _vbs_to_int32(v: int) -> int:
    v = int(v) & 0xFFFFFFFF
    return v - 0x100000000 if (v & 0x80000000) else v


def _vbs_try_number(v):
    if v is VBEmpty or v is VBNothing:
        return 0
    if v is VBNull:
        return None
    if isinstance(v, bool):
        return -1 if v else 0
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        s = v.strip()
        if s == "":
            return 0
        try:
            if '.' in s:
                return float(s)
            return int(s)
        except Exception:
            return None
    return None


def _vbs_try_truthy(v):
    if v is VBEmpty or v is VBNull or v is VBNothing or v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v != ""
    return bool(v)


def _vbs_compare(op: str, a, b):
    if a is VBNull or b is VBNull:
        return VBNull
    a_is_empty_str = isinstance(a, str) and a.strip() == ""
    b_is_empty_str = isinstance(b, str) and b.strip() == ""
    an = None if a_is_empty_str else _vbs_try_number(a)
    bn = None if b_is_empty_str else _vbs_try_number(b)
    if an is not None and bn is not None:
        if op == '=':
            return an == bn
        if op == '<>':
            return an != bn
        if op == '<':
            return an < bn
        if op == '<=':
            return an <= bn
        if op == '>':
            return an > bn
        if op == '>=':
            return an >= bn
    sa = vbs_cstr(a)
    sb = vbs_cstr(b)
    # VBScript uses case-insensitive string comparisons by default
    sa_cmp = sa.lower()
    sb_cmp = sb.lower()
    if op == '=':
        return sa_cmp == sb_cmp
    if op == '<>':
        return sa_cmp != sb_cmp
    if op == '<':
        return sa_cmp < sb_cmp
    if op == '<=':
        return sa_cmp <= sb_cmp
    if op == '>':
        return sa_cmp > sb_cmp
    if op == '>=':
        return sa_cmp >= sb_cmp
    raise VBScriptRuntimeError("Unknown compare op")


def vbs_not(value):
    if isinstance(value, bool):
        return not value
    n = _vbs_try_number(value)
    if n is not None:
        return _vbs_to_int32(~int(n))
    return not bool(_vbs_try_truthy(value))


def vbs_and(left, right):
    if isinstance(left, bool) or isinstance(right, bool):
        return bool(_vbs_try_truthy(left)) and bool(_vbs_try_truthy(right))
    ln = _vbs_try_number(left)
    rn = _vbs_try_number(right)
    if ln is not None and rn is not None:
        li = _vbs_to_int32(int(ln))
        ri = _vbs_to_int32(int(rn))
        return _vbs_to_int32(li & ri)
    return bool(_vbs_try_truthy(left)) and bool(_vbs_try_truthy(right))


def vbs_or(left, right):
    if isinstance(left, bool) or isinstance(right, bool):
        return bool(_vbs_try_truthy(left)) or bool(_vbs_try_truthy(right))
    ln = _vbs_try_number(left)
    rn = _vbs_try_number(right)
    if ln is not None and rn is not None:
        li = _vbs_to_int32(int(ln))
        ri = _vbs_to_int32(int(rn))
        return _vbs_to_int32(li | ri)
    return bool(_vbs_try_truthy(left)) or bool(_vbs_try_truthy(right))


def vbs_xor(left, right):
    if isinstance(left, bool) or isinstance(right, bool):
        lb = bool(_vbs_try_truthy(left))
        rb = bool(_vbs_try_truthy(right))
        return (lb and (not rb)) or ((not lb) and rb)
    ln = _vbs_try_number(left)
    rn = _vbs_try_number(right)
    if ln is not None and rn is not None:
        li = _vbs_to_int32(int(ln))
        ri = _vbs_to_int32(int(rn))
        return _vbs_to_int32(li ^ ri)
    lb = bool(_vbs_try_truthy(left))
    rb = bool(_vbs_try_truthy(right))
    return (lb and (not rb)) or ((not lb) and rb)


def vbs_eqv(left, right):
    if isinstance(left, bool) or isinstance(right, bool):
        lb = bool(_vbs_try_truthy(left))
        rb = bool(_vbs_try_truthy(right))
        return (lb and rb) or ((not lb) and (not rb))
    ln = _vbs_try_number(left)
    rn = _vbs_try_number(right)
    if ln is not None and rn is not None:
        li = _vbs_to_int32(int(ln))
        ri = _vbs_to_int32(int(rn))
        return _vbs_to_int32(~(li ^ ri))
    lb = bool(_vbs_try_truthy(left))
    rb = bool(_vbs_try_truthy(right))
    return (lb and rb) or ((not lb) and (not rb))


def vbs_imp(left, right):
    if isinstance(left, bool) or isinstance(right, bool):
        lb = bool(_vbs_try_truthy(left))
        rb = bool(_vbs_try_truthy(right))
        return (not lb) or rb
    ln = _vbs_try_number(left)
    rn = _vbs_try_number(right)
    if ln is not None and rn is not None:
        li = _vbs_to_int32(int(ln))
        ri = _vbs_to_int32(int(rn))
        return _vbs_to_int32((~li) | ri)
    lb = bool(_vbs_try_truthy(left))
    rb = bool(_vbs_try_truthy(right))
    return (not lb) or rb


def vbs_eq(left, right):
    return _vbs_compare('=', left, right)


def vbs_neq(left, right):
    return _vbs_compare('<>', left, right)


def vbs_lt(left, right):
    return _vbs_compare('<', left, right)


def vbs_lte(left, right):
    return _vbs_compare('<=', left, right)


def vbs_gt(left, right):
    return _vbs_compare('>', left, right)


def vbs_gte(left, right):
    return _vbs_compare('>=', left, right)