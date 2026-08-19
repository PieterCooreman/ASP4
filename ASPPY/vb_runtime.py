"""Tiny VBScript runtime helpers (type conversions, formatting)."""

from __future__ import annotations

import datetime as _dt
import locale as _locale
import math as _math
import re as _re
import threading as _threading
from decimal import Decimal as _Decimal

# NOTE: do NOT call locale.setlocale(LC_NUMERIC, '') here.
#
# All VBScript-visible number/date formatting is driven by this runtime's own
# LCID tables in ASPPY.vb_locale (see _decimal_sep below), so the process-wide
# C locale is never consulted for correctness. Setting it, however, breaks
# other libraries: pyodbc reads the C decimal separator once, at import time,
# and builds its Decimal parser from it. On a machine whose regional format
# uses ',' (e.g. Dutch/German/French Windows) that made every Currency/Decimal
# column raise "sub() missing 1 required positional argument: 'string'" the
# moment a row was fetched, so any page touching such a column died with
# ASP 0115 / 80004005.
_ = _locale  # kept imported for the helpers below


_fmt_tls = _threading.local()


def vbs_set_lcid(value):
    try:
        _fmt_tls.lcid = int(value)
    except Exception:
        _fmt_tls.lcid = 0


def vbs_get_lcid():
    return getattr(_fmt_tls, 'lcid', 0)


def _decimal_sep():
    """Decimal separator for the current thread's LCID.

    Imported lazily so that vb_locale (stdlib-only) stays independent of the
    runtime's import order.
    """
    from . import vb_locale
    return vb_locale.decimal_separator(vbs_get_lcid())


def vbs_get_lcid_info(lcid=None):
    """Deprecated compatibility shim.

    Superseded by :mod:`ASPPY.vb_locale`, which is driven by the full NLS table
    in locale_data.json (60 locales) rather than the 8 hand-written entries this
    used to hold. Retained so any external caller keeps working.
    """
    from . import vb_locale
    L = vb_locale.get(vbs_get_lcid() if lcid is None else lcid)
    return {
        "decimal":    L['numberDecimalSeparator'],
        "thousands":  L['numberGroupSeparator'],
        "currency":   L['currencySymbol'],
        "date_short": L['shortDatePattern'],
        "date_long":  L['longDatePattern'],
        "time_short": L['shortTimePattern'],
        "time_long":  L['longTimePattern'],
    }


try:
    from .vm.values import VBEmpty, VBNull, VBNothing
except Exception:  # pragma: no cover
    VBEmpty = object()
    VBNull = object()
    VBNothing = object()


class VBSingle(float):
    """Marker type for VBScript Single (CSng): VarType 4, TypeName "Single",
    CStr with 7 significant digits. Arithmetic promotes to plain float
    (Double), which is close enough for ASP compatibility purposes."""
    __slots__ = ()


class VBLong(int):
    """Marker type for VBScript Long (VarType 3, TypeName "Long").

    ASPPY normally infers Integer vs Long from an int's magnitude, but some
    APIs return a Long even for small values -- Len(), .Count, CLng() and the
    '\\' operator all report "Long" on IIS. Subclassing int keeps every
    arithmetic and comparison operation working unchanged."""
    __slots__ = ()


class VBByte(int):
    """Marker type for VBScript Byte (VarType 17, TypeName "Byte").

    CByte() and AscB() report "Byte" on IIS, where magnitude alone would make
    ASPPY infer "Integer". Subclasses int so arithmetic keeps working."""
    __slots__ = ()


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


def vbs_default_value(value):
    """Read a host object's DEFAULT property, the way VBScript does.

    VBScript never uses an object reference where a value is expected: it calls
    the object's default property first (Err -> Err.Number, ADODB.Field ->
    .Value, Request.Cookies -> its raw string). Objects that declare
    __vbs_default__ opt into that here; everything else is returned unchanged
    so callers keep their existing behaviour.
    """
    dname = getattr(value.__class__, '__vbs_default__', None)
    if dname:
        try:
            return getattr(value, dname)
        except Exception:
            return value
    return value


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
    # An object in a string context renders its default property, so
    # CStr(Err) is "0" on IIS rather than a type name or a Python repr.
    _dv = vbs_default_value(value)
    if _dv is not value:
        return vbs_cstr(_dv)
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
    if isinstance(value, _Decimal):
        # Decimal is ASPPY's Currency subtype (VarType 6). VBScript renders
        # Currency in plain fixed-point (never scientific), trimming trailing
        # zeros: CStr(CCur(123.45)) => "123.45", CStr(CCur(123)) => "123".
        s = format(value, 'f')
        if '.' in s:
            s = s.rstrip('0').rstrip('.')
        if s in ('', '-', '-0'):
            s = '0'
        return s.replace('.', _decimal_sep())
    if isinstance(value, float):
        # VBScript CStr renders a Double with up to 15 significant digits
        # (CStr(1/3) => "0.333333333333333"); a Single (CSng) uses 7.
        # Scientific notation kicks in below 1E-4, like VBScript.
        if value == 0.0:
            return "0"

        digits = 7 if isinstance(value, VBSingle) else 15
        av = abs(value)
        # VBScript keeps plain decimal notation for small magnitudes far
        # longer than most languages: CStr(0.000001) = "0.000001" and even
        # CStr(0.00000001) = "0.00000001". Scientific notation only kicks in
        # once the exponent drops below -19 (verified against IIS).
        if av < 1e-19:
            # scientific notation: mantissa with (digits-1) decimals, trimmed
            exp = int(_math.floor(_math.log10(av)))
            mant = value / (10 ** exp)
            s = f"{mant:.{digits - 1}f}"
            # Trim trailing zeros like VBScript tends to
            if '.' in s:
                s = s.rstrip('0').rstrip('.')
            s = f"{s}E{exp:+03d}"
        else:
            s = format(value, f'.{digits}g')
            if 'e' in s or 'E' in s:
                # Python switches to exponent form much earlier than VBScript.
                # For small magnitudes (down to 1E-19) VBScript prints plain
                # decimals, so re-render those without an exponent.
                exp10 = int(_math.floor(_math.log10(av)))
                if exp10 < 0:
                    dec = (digits - 1) - exp10
                    s = f"{value:.{dec}f}"
                    if '.' in s:
                        s = s.rstrip('0').rstrip('.')
                else:
                    s = s.replace('e', 'E')
                    m = _re.match(r"^(.*)E([+-]?)(\d+)$", s)
                    if m:
                        mant, sign, exp2 = m.group(1), m.group(2) or '+', m.group(3)
                        s = mant + 'E' + sign + exp2.zfill(2)

        return s.replace('.', _decimal_sep())
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        # VBScript prints date-only when the time part is midnight and time-only
        # when the value is a pure time (OA zero date).
        if isinstance(value, _dt.datetime):
            has_date = (value.year, value.month, value.day) != (1899, 12, 30)
            has_time = (value.hour, value.minute, value.second, value.microsecond) != (0, 0, 0, 0)
            dt_value = value
        elif isinstance(value, _dt.date):
            has_date, has_time = True, False
            dt_value = _dt.datetime(value.year, value.month, value.day)
        else:
            has_date, has_time = False, True
            dt_value = _dt.datetime(1899, 12, 30, value.hour, value.minute,
                                    value.second, value.microsecond)
        if not has_date and not has_time:
            has_time = True

        # Under IIS this always follows the locale. ASPPY keeps its ISO output
        # while no locale has been chosen (LCID 0) so that apps which never
        # localise - and commonly concatenate dates straight into SQL - are not
        # silently broken, and switches to full IIS parity as soon as the app
        # opts in via Session.LCID / SetLocale / <%@ LCID %>. See README
        # "Character encoding" for the same deterministic-default reasoning.
        if vbs_get_lcid():
            from . import vb_locale
            return vb_locale.general_date(dt_value, vbs_get_lcid(), has_date, has_time)

        if has_date and has_time:
            return dt_value.strftime("%Y-%m-%d %H:%M:%S")
        if has_date:
            return dt_value.strftime("%Y-%m-%d")
        return dt_value.strftime("%H:%M:%S")
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
                    msg = f"[ASPPY] _UserProc rendered to string: {proc_name}"
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
    """Lenient Boolean coercion, as used for implicit truthiness.

    `If "abc" Then` does not raise on IIS, so this never raises. The CBool()
    BUILTIN is stricter (Type mismatch on an unconvertible string) - see
    vb_builtins.CBool.
    """
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
    if isinstance(v, _Decimal):
        # Currency: convert to float so mixed Currency/Double arithmetic and
        # comparisons behave numerically (Decimal==float is exact in Python
        # and would wrongly report CCur(123.45) <> 123.45).
        return float(v)
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