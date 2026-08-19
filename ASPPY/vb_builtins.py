# vb_builtins.py - Fix missing exports
from __future__ import annotations

import datetime as _dt
import math as _math
import random as _random
from decimal import Decimal, ROUND_HALF_EVEN, InvalidOperation

import struct as _struct

from .vb_errors import raise_runtime
from .vb_runtime import VBSingle, VBLong, VBByte, vbs_cbool, vbs_cstr, vbs_get_lcid, vbs_set_lcid
from . import vb_locale
from .vm.values import VBEmpty, VBNull, VBNothing

# Re-implement core functions to guarantee they exist in this module scope

def Len(expression):
    # VBScript Len() returns a Long (TypeName(Len("")) = "Long").
    if expression is VBNull: return VBNull
    if expression is VBEmpty or expression is VBNothing: return VBLong(0)
    if isinstance(expression, (bytes, bytearray)):
        # Len() counts CHARACTERS, and a binary string holds 2 bytes per
        # character: Len(ChrB(65)) = 0 on IIS (use LenB for the byte count).
        return VBLong(len(expression) // 2)
    if isinstance(expression, str): return VBLong(len(expression))
    return VBLong(len(vbs_cstr(expression)))

def UCase(string):
    if string is VBNull: return VBNull
    return vbs_cstr(string).upper()

def LCase(string):
    if string is VBNull: return VBNull
    return vbs_cstr(string).lower()

def Trim(string):
    if string is VBNull: return VBNull
    return vbs_cstr(string).strip()

def LTrim(string):
    if string is VBNull: return VBNull
    return vbs_cstr(string).lstrip()

def RTrim(string):
    if string is VBNull: return VBNull
    return vbs_cstr(string).rstrip()

def StrReverse(string):
    # IIS raises Invalid use of Null here rather than propagating Null, unlike
    # Left/Right/Mid/Trim/LCase which all return Null. Verified against IIS.
    if string is VBNull: raise_runtime('INVALID_USE_OF_NULL')
    return vbs_cstr(string)[::-1]

def StrComp(string1, string2, compare=0):
    # StrComp does propagate Null (verified against IIS).
    if string1 is VBNull or string2 is VBNull: return VBNull
    s1 = vbs_cstr(string1)
    s2 = vbs_cstr(string2)
    cmp = int(_to_int(compare))
    if cmp == 1:
        # vbTextCompare is a locale collation, not a lowercase byte compare:
        # "strasse" equals "stra<sharp-s>e" and accents act as a tiebreak.
        return vb_locale.compare_text(s1, s2)
    if s1 < s2: return -1
    if s1 > s2: return 1
    return 0

def Split(expression, delimiter=" ", count=-1, compare=0):
    # IIS rejects Null in either position with Invalid use of Null (94); it does
    # not propagate Null and does not return an empty array. Verified against
    # IIS for Split(Null), Split(Null, ",") and Split("a,b", Null).
    if expression is VBNull or delimiter is VBNull:
        raise_runtime('INVALID_USE_OF_NULL')
    s = vbs_cstr(expression)
    d = vbs_cstr(delimiter)
    from .vm.values import VBArray
    # VBScript: Split("") returns an EMPTY array (UBound = -1).
    if s == "": return VBArray([-1], allocated=True, dynamic=True)
    if d == "": return VBArray([0], allocated=True, dynamic=True)
    cnt = int(_to_int(count))
    if cnt < 0:
        parts = s.split(d)
    else:
        if cnt == 0: return VBArray([-1], allocated=True, dynamic=True)
        parts = s.split(d, cnt - 1)
    arr = VBArray(len(parts)-1, allocated=True, dynamic=True)
    for i, p in enumerate(parts):
        arr._items[i] = p
    return arr

def Join(list_var, delimiter=" "):
    from .vm.values import VBArray
    # Invalid use of Null (94) on IIS, not Null propagation.
    if list_var is VBNull or delimiter is VBNull:
        raise_runtime('INVALID_USE_OF_NULL')
    if not isinstance(list_var, (VBArray, list, tuple)): raise_runtime('TYPE_MISMATCH')
    items = list_var._items if isinstance(list_var, VBArray) else list_var
    d = vbs_cstr(delimiter)
    return d.join([vbs_cstr(i) for i in items])


def Escape(string=""):
    s = vbs_cstr(string)
    safe = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@*_+-./"
    out = []
    for ch in s:
        if ch in safe:
            out.append(ch)
            continue
        cp = ord(ch)
        if cp <= 0xFF:
            out.append("%" + format(cp, "02X"))
            continue
        b = ch.encode('utf-16-be', errors='surrogatepass')
        for i in range(0, len(b), 2):
            unit = (b[i] << 8) | b[i + 1]
            out.append("%u" + format(unit, "04X"))
    return "".join(out)


def Unescape(string):
    s = vbs_cstr(string)
    n = len(s)
    i = 0
    out = []
    while i < n:
        ch = s[i]
        if ch != '%':
            out.append(ch)
            i += 1
            continue

        if i + 5 < n and s[i + 1] in ('u', 'U'):
            h = s[i + 2:i + 6]
            if all(c in '0123456789abcdefABCDEF' for c in h):
                out.append(chr(int(h, 16)))
                i += 6
                continue

        if i + 2 < n:
            h = s[i + 1:i + 3]
            if all(c in '0123456789abcdefABCDEF' for c in h):
                out.append(chr(int(h, 16)))
                i += 3
                continue

        out.append('%')
        i += 1

    return "".join(out)

def UBound(arrayname, dimension=1):
    # VBScript fixes this function's return SUBTYPE at Long (VarType 3)
    # regardless of magnitude - TypeName is "Long" even for 0 or 1.
    # Verified on IIS 10. ASPPY otherwise infers Integer from the value,
    # which changes TypeName/VarType results and any arithmetic that
    # overflows an Integer.
    from .vb_runtime import VBLong
    return VBLong(_ubound_raw(arrayname, dimension))

def _ubound_raw(arrayname, dimension=1):
    from .vm.values import VBArray
    if isinstance(arrayname, VBArray):
        try: return arrayname.ubound(dimension)
        except IndexError as e: raise_runtime('SUBSCRIPT_OUT_OF_RANGE', str(e))
    # bytes/bytearray model a Byte() SafeArray (responseBody, BinaryRead).
    if isinstance(arrayname, (list, tuple, bytes, bytearray)):
        if int(dimension) != 1:
            raise_runtime('SUBSCRIPT_OUT_OF_RANGE',
                f"UBound dimension {dimension} requested but array is 1-dimensional")
        return len(arrayname) - 1
    raise_runtime('TYPE_MISMATCH')

def LBound(arrayname, dimension=1):
    # VBScript fixes this function's return SUBTYPE at Long (VarType 3)
    # regardless of magnitude - TypeName is "Long" even for 0 or 1.
    # Verified on IIS 10. ASPPY otherwise infers Integer from the value,
    # which changes TypeName/VarType results and any arithmetic that
    # overflows an Integer.
    from .vb_runtime import VBLong
    return VBLong(_lbound_raw(arrayname, dimension))

def _lbound_raw(arrayname, dimension=1):
    from .vm.values import VBArray
    if isinstance(arrayname, VBArray):
        try: return arrayname.lbound(dimension)
        except IndexError as e: raise_runtime('SUBSCRIPT_OUT_OF_RANGE', str(e))
    if isinstance(arrayname, (list, tuple, bytes, bytearray)):
        if int(dimension) != 1:
            raise_runtime('SUBSCRIPT_OUT_OF_RANGE',
                f"LBound dimension {dimension} requested but array is 1-dimensional")
        return 0
    raise_runtime('TYPE_MISMATCH')

def IsArray(varname):
    from .vm.values import VBArray
    # bytes/bytearray represent a Byte() SafeArray - what IIS hands back from
    # ServerXMLHTTP.responseBody and Request.BinaryRead. Verified on IIS 10:
    # IsArray = True, TypeName = "Byte()", VarType = 8209, IsObject = False.
    return isinstance(varname, (VBArray, list, tuple, bytes, bytearray))

def IsDate(expression):
    if expression is VBNull: return False
    if isinstance(expression, (_dt.datetime, _dt.date)): return True
    s = vbs_cstr(expression)
    if not s: return False
    try:
        from .vb_datetime import CDate
        CDate(s)
        return True
    except: return False

def IsEmpty(expression):
    # A missing Request key coerces to Empty through its default property,
    # so IsEmpty(Request.Form("nope")) is True on IIS.
    return _scalarize(expression) is VBEmpty

def IsNull(expression):
    return _scalarize(expression) is VBNull

def IsNumeric(expression):
    expression = _scalarize(expression)
    if expression is VBNull: return False
    # VBScript: IsNumeric(Empty) = True (Empty coerces to 0).
    if expression is VBEmpty: return True
    if isinstance(expression, (int, float, Decimal, bool)): return True
    if isinstance(expression, _dt.datetime): return False
    s = vbs_cstr(expression)
    if not s: return False
    try:
        _to_number(expression)
        return True
    except: return False

def IsObject(expression):
    if expression is VBNothing: return True
    if expression in (VBEmpty, VBNull): return False
    from .vm.interpreter import VBClassInstance
    from .adodb import ADOConnection, ADORecordset, ADOCommand
    if isinstance(expression, (VBClassInstance, ADOConnection, ADORecordset, ADOCommand)): return True
    if expression is None: return False
    if isinstance(expression, (str, int, float, bool, Decimal, _dt.date, _dt.datetime)): return False
    # A Byte() SafeArray is an array, not an object (IsObject = False on IIS).
    if isinstance(expression, (bytes, bytearray)): return False
    from .vm.values import VBArray
    if isinstance(expression, VBArray): return False
    return True

def TypeName(varname):
    v = varname
    # NOTE: TypeName does NOT go through the default property -- IIS reports
    # "IStringList" for Request values even when the key is missing (verified
    # against IIS), unlike VarType/IsEmpty which report Empty/0.
    if v is VBEmpty or v is None: return "Empty"
    if v is VBNull: return "Null"
    if v is VBNothing: return "Nothing"
    if isinstance(v, bool): return "Boolean"
    if isinstance(v, VBByte): return "Byte"
    if isinstance(v, VBLong): return "Long"
    # VBScript quirk (verified on IIS): -32768 reports as Long even though it
    # fits in an Integer, because the literal is negated from a Long.
    if isinstance(v, int): return "Integer" if -32767 <= v <= 32767 else "Long"
    if isinstance(v, VBSingle): return "Single"
    if isinstance(v, float): return "Double"
    if isinstance(v, Decimal): return "Currency"
    tn_hook = getattr(v, '__vbs_typename__', None)
    if tn_hook is not None:
        try: return tn_hook()
        except Exception: pass
    if isinstance(v, str): return "String"
    # Binary payloads are a Byte() SafeArray on IIS, not an opaque object.
    if isinstance(v, (bytes, bytearray)): return "Byte()"
    if isinstance(v, (_dt.datetime, _dt.date, _dt.time)): return "Date"
    from .vm.values import VBArray
    if isinstance(v, VBArray): return "Variant()"
    if hasattr(v, '_cls'):
        try: return str(getattr(getattr(v, '_cls'), 'name'))
        except: pass
    from .adodb import TypeName as ADOTypeName
    tn = ADOTypeName(v)
    if tn != type(v).__name__: return tn
    tn = type(v).__name__
    if tn == 'ScriptingDictionary': return 'Dictionary'
    if tn == '_Sentinel': return 'Object'
    # The built-in ASP objects report their COM interface name on IIS.
    asp_iface = {
        'Request': 'IRequest',
        'Response': 'IResponse',
        'ServerObject': 'IServer',
        'Server': 'IServer',
        'Session': 'ISessionObject',
        'Application': 'IApplicationObject',
        'ScriptingContext': 'IScriptingContext',
    }.get(tn)
    if asp_iface is not None: return asp_iface
    return "Object"

def VarType(varname):
    v = _scalarize(varname)
    if v is VBEmpty or v is None: return 0
    if v is VBNull: return 1
    if isinstance(v, bool): return 11
    if isinstance(v, VBByte): return 17  # vbByte
    if isinstance(v, VBLong): return 3
    # vbInteger (2) for values in Integer range, vbLong (3) beyond - keep
    # consistent with TypeName so VarType(42) = 2 like IIS (including the
    # -32768 => Long quirk).
    if isinstance(v, int): return 2 if -32767 <= v <= 32767 else 3
    if isinstance(v, VBSingle): return 4
    if isinstance(v, float): return 5
    if isinstance(v, Decimal): return 6
    if isinstance(v, str): return 8
    if isinstance(v, (_dt.datetime, _dt.date, _dt.time)): return 7
    # vbArray (8192) + vbByte (17) = 8209, what IIS reports for responseBody.
    if isinstance(v, (bytes, bytearray)): return 8209
    from .vm.values import VBArray
    if isinstance(v, VBArray): return 8204
    if v is VBNothing: return 9
    return 9

def Array(*args):
    from .vm.values import VBArray
    if not args: return VBArray([-1], allocated=True, dynamic=True)
    arr = VBArray([len(args)-1], allocated=True, dynamic=True)
    for i, val in enumerate(args):
        arr._items[i] = val
    return arr

def Filter(inputstrings, value, include=True, compare=0):
    from .vm.values import VBArray
    # A Null array/value is Invalid use of Null (94) on IIS, not Type mismatch.
    if inputstrings is VBNull or value is VBNull:
        raise_runtime('INVALID_USE_OF_NULL')
    if not IsArray(inputstrings): raise_runtime('TYPE_MISMATCH')
    arr = inputstrings
    # dynamic=True throughout: arrays returned by Split/Filter are resizable in
    # VBScript, so a later ReDim Preserve on the result must not raise error 10.
    if not arr._allocated: return VBArray([-1], allocated=True, dynamic=True)
    res = []
    val_s = vbs_cstr(value)
    inc = vbs_cbool(include)
    for item in arr._items:
        s = vbs_cstr(item)
        match = (val_s.lower() in s.lower()) if int(_to_int(compare)) == 1 else (val_s in s)
        if match == inc: res.append(item)
    out = VBArray([len(res)-1] if res else [-1], allocated=True, dynamic=True)
    for i, r in enumerate(res): out._items[i] = r
    return out

def Asc(s):
    # Null is Invalid use of Null (94); only an *empty string* is Invalid
    # procedure call (5). Verified against IIS.
    if s is VBNull: raise_runtime('INVALID_USE_OF_NULL')
    t = vbs_cstr(s)
    if t == "": raise_runtime('INVALID_PROC_CALL')
    return ord(t[0])

def AscW(s):
    t = vbs_cstr(s)
    if t == "": raise_runtime('INVALID_PROC_CALL')
    cp = ord(t[0])
    # AscW returns a VBScript Integer, which is SIGNED 16-bit, so every code
    # point above U+7FFF comes back negative: AscW(ChrW(&HFFFF)) is -1, not
    # 65535 (verified on IIS 10). That covers most non-Latin scripts - CJK,
    # Hangul, and the U+8000+ range generally - so scripts doing
    # `If AscW(c) > &H7FF Then` or round-tripping through ChrW() need the wrap.
    # ChrW() already accepts the negative form, so the pair stays symmetric.
    if cp > 0x7FFF:
        cp -= 0x10000
    return cp

def AscB(s):
    # AscB yields a Byte (TypeName "Byte", VarType 17) on IIS, not an
    # Integer. Verified on IIS 10.
    if s is VBNull:
        return VBNull
    b = bytes(s) if isinstance(s, (bytes, bytearray)) else vbs_cstr(s).encode('utf-16le')
    if len(b) == 0:
        raise_runtime('INVALID_PROC_CALL')
    from .vb_runtime import VBByte
    return VBByte(b[0])

def Chr(charcode):
    n = int(_to_int(charcode))
    if n < 0 or n > 255: raise_runtime('INVALID_PROC_CALL')
    return chr(n)

def ChrW(charcode):
    n = int(_to_int(charcode))
    if n < -32768 or n > 65535: raise_runtime('INVALID_PROC_CALL')
    if n < 0: n = n & 0xFFFF
    return chr(n)

def ChrB(charcode):
    n = int(_to_int(charcode))
    if n < 0 or n > 255: raise_runtime('INVALID_PROC_CALL')
    return bytes([n])

def CByte(expr):
    if expr is VBNull: raise_runtime('INVALID_USE_OF_NULL')
    n = int(_to_int(expr))
    if n < 0 or n > 255: raise_runtime('OVERFLOW')
    return n

# VBScript Currency range: +/- 922,337,203,685,477.5807 (64-bit scaled int).
_CUR_MAX = Decimal('922337203685477.5807')


def CCur(expr):
    if expr is VBNull: raise_runtime('INVALID_USE_OF_NULL')
    if isinstance(expr, bool): return Decimal('-1.0000') if expr else Decimal('0.0000')
    d = _to_decimal(expr).quantize(Decimal('0.0000'), rounding=ROUND_HALF_EVEN)
    if d < -_CUR_MAX or d > _CUR_MAX: raise_runtime('OVERFLOW')
    return d

def CDbl(expr):
    if expr is VBNull: raise_runtime('INVALID_USE_OF_NULL')
    return float(_to_number(expr))

def CSng(expr):
    if expr is VBNull: raise_runtime('INVALID_USE_OF_NULL')
    f = float(_to_number(expr))
    # Reduce to real 32-bit float precision, like VBScript Single.
    f32 = _struct.unpack('f', _struct.pack('f', f))[0]
    if _math.isinf(f32) and not _math.isinf(f):
        raise_runtime('OVERFLOW')
    return VBSingle(f32)

def CInt(expr):
    if expr is VBNull: raise_runtime('INVALID_USE_OF_NULL')
    if isinstance(expr, bool): return -1 if expr else 0
    result = int(_round_bankers(_to_decimal(expr)))
    if result < -32768 or result > 32767:
        raise_runtime('OVERFLOW')
    return result

def CLng(expr):
    if _scalarize(expr) is VBNull: raise_runtime('INVALID_USE_OF_NULL')
    if isinstance(_scalarize(expr), bool): return VBLong(-1 if _scalarize(expr) else 0)
    result = int(_round_bankers(_to_decimal(expr)))
    # VBScript Long is 32-bit: CLng(2147483648) => Overflow (error 6).
    if result < -2147483648 or result > 2147483647:
        raise_runtime('OVERFLOW')
    # CLng always yields the Long subtype, even for small values.
    return VBLong(result)

def CStr(expr):
    if expr is VBNull: raise_runtime('INVALID_USE_OF_NULL')
    return vbs_cstr(expr)

def CBool(expr):
    if expr is VBNull: raise_runtime('INVALID_USE_OF_NULL')
    # IIS parity: CBool is stricter than implicit truthiness. A string is
    # accepted only as True/False or as a number; anything else - including
    # the EMPTY string - is Type mismatch (13). `If "abc" Then` still does not
    # raise, because that path goes through the lenient vbs_cbool().
    e = _scalarize(expr)
    if isinstance(e, str) and not isinstance(e, bool):
        v = e.strip().lower()
        if v in ("true", "false"):
            return v == "true"
        try:
            return _to_decimal(e) != 0
        except Exception:
            raise_runtime('TYPE_MISMATCH')
    return vbs_cbool(expr)

def Hex(number):
    if _scalarize(number) is VBNull: return VBNull
    # VBScript rounds (banker's) before converting: Hex(15.7) => "10".
    n = int(_round_bankers(_to_decimal(number)))
    if n < 0: n = n & _neg_mask(number, n)
    return format(n, 'X')

def _neg_mask(original, n):
    """Two's-complement width VBScript uses when formatting a negative number.

    The width follows the value's SUBTYPE, verified against IIS:
        Hex(-1)             = "FFFF"      (Integer)
        Hex(True)           = "FFFF"      (Boolean behaves as Integer -1)
        Hex(CLng(-1))       = "FFFFFFFF"  (Long, even though it fits 16 bits)
        Hex(-32768)         = "FFFF8000"  (Long: -32768 is not an Integer)
        Hex(CLng(-70000))   = "FFFEEE90"  (Long by magnitude)
    """
    orig = _scalarize(original)
    if isinstance(orig, bool): return 0xFFFF
    # An explicit Long (CLng/Len/...) always uses the 32-bit width.
    if isinstance(orig, VBLong): return 0xFFFFFFFF
    # Integer subtype is -32767..32767 here: -32768 reports as Long on IIS
    # (same quirk as TypeName), so it takes the 32-bit width.
    if isinstance(orig, int) and -32767 <= orig <= 32767: return 0xFFFF
    if isinstance(orig, (float, Decimal)) and -32767 <= n <= 32767: return 0xFFFF
    return 0xFFFFFFFF

def LenB(expr):
    # Like Len(), LenB() returns a Long on IIS.
    v = expr
    if v is VBNull: return VBNull
    if v is VBEmpty or v is VBNothing or v is None: return VBLong(0)
    if isinstance(v, (bytes, bytearray)): return VBLong(len(v))
    s = vbs_cstr(v)
    try: return VBLong(len(s.encode('utf-16le')))
    except: return VBLong(len(s))

def LeftB(string, length):
    if string is VBNull: return VBNull
    s = vbs_cstr(string)
    b = s.encode('utf-16le')
    n = int(_to_int(length))
    if n < 0: raise_runtime('INVALID_PROC_CALL')
    if n == 0: return b""
    return b[:n]

def RightB(string, length):
    if string is VBNull: return VBNull
    s = vbs_cstr(string)
    b = s.encode('utf-16le')
    n = int(_to_int(length))
    if n < 0: raise_runtime('INVALID_PROC_CALL')
    if n == 0: return b""
    return b[-n:]

def MidB(expr, start, length=None):
    if expr is VBNull: return VBNull
    b = bytes(expr) if isinstance(expr, (bytes, bytearray)) else vbs_cstr(expr).encode('utf-16le')
    st = int(_to_int(start))
    if st <= 0: raise_runtime('INVALID_PROC_CALL')
    i = st - 1
    if length is None: return b[i:]
    ln = int(_to_int(length))
    if ln < 0: raise_runtime('INVALID_PROC_CALL')
    if ln == 0: return b""
    return b[i:i + ln]

def InStr(*args):
    # InStr/InStrRev return Long on IIS (TypeName "Long", VarType 3),
    # even for 0 or 1. Verified on IIS 10.
    from .vb_runtime import VBLong
    return VBLong(_instr_raw(*args))

def _instr_raw(*args):
    start = 1
    compare = 0
    s1 = None
    s2 = None
    if len(args) == 2:
        s1, s2 = args
    elif len(args) == 3:
        try:
            float(_to_number(args[0]))
            is_num = True
        except: is_num = False
        if is_num: start, s1, s2 = args
        else: start, s1, s2 = args
    elif len(args) == 4:
        start, s1, s2, compare = args
    else: raise_runtime('WRONG_NUM_ARGS')
    
    if s1 is None or s2 is None: raise_runtime('WRONG_NUM_ARGS')
    if s1 is VBNull or s2 is VBNull: return VBNull
    
    ts1 = vbs_cstr(s1)
    ts2 = vbs_cstr(s2)
    if ts1 == "": return 0
    if ts2 == "": return int(_to_int(start))
    
    st = int(_to_int(start))
    if st <= 0: raise_runtime('INVALID_PROC_CALL')
    
    if int(_to_int(compare)) == 1:
        ts1 = ts1.lower()
        ts2 = ts2.lower()
    
    idx = ts1.find(ts2, st - 1)
    return 0 if idx < 0 else (idx + 1)

def InStrB(*args):
    start = 1
    s1 = None
    s2 = None
    if len(args) == 2:
        s1, s2 = args
    elif len(args) == 3:
        # InStrB(start, string1, string2)
        start, s1, s2 = args
    else:
        raise_runtime('WRONG_NUM_ARGS')
        
    if s1 is VBNull or s2 is VBNull: return VBNull
    
    def _to_bytes(v):
        if isinstance(v, (bytes, bytearray)): return bytes(v)
        return vbs_cstr(v).encode('utf-16le')
        
    b1 = _to_bytes(s1)
    b2 = _to_bytes(s2)
    
    st = int(_to_int(start))
    if st <= 0: raise_runtime('INVALID_PROC_CALL')
    
    idx = b1.find(b2, st - 1)
    return 0 if idx < 0 else (idx + 1)

def Oct(number):
    if _scalarize(number) is VBNull: return VBNull
    # VBScript rounds (banker's) before converting, like Hex.
    n = int(_round_bankers(_to_decimal(number)))
    if n < 0: n = n & _neg_mask(number, n)
    return format(n, 'o')

def Abs(number):
    # VBScript: Abs(Null) = Null (documented, no error).
    if _scalarize(number) is VBNull: return VBNull
    x = _to_number(number)
    return -x if x < 0 else x

def Atn(number):
    return _math.atan(float(_to_number(number)))

def Cos(number):
    return _math.cos(float(_to_number(number)))

def Exp(number):
    return _math.exp(float(_to_number(number)))

def Int(number):
    # VBScript: Int(Null) = Null (no error).
    if number is VBNull: return VBNull
    return _math.floor(float(_to_number(number)))

def Fix(number):
    # VBScript: Fix(Null) = Null (no error).
    if number is VBNull: return VBNull
    x = float(_to_number(number))
    return int(x)

def _date_to_oaserial(v):
    # OLE Automation date: days since 1899-12-30. A VBScript Date IS a Double.
    if isinstance(v, _dt.datetime):
        d = v
    else:  # _dt.date
        d = _dt.datetime(v.year, v.month, v.day)
    return (d - _dt.datetime(1899, 12, 30)).total_seconds() / 86400.0

def _scalarize(v):
    """Invoke a wrapped value's default-scalar hook (IStringList etc.).

    IIS coerces such COM objects through their default property before any
    conversion; an empty IStringList (missing Request key) becomes Empty."""
    hook = getattr(v.__class__, '__vbs_scalar__', None)
    if hook is not None:
        return hook(v)
    return v

def _to_number(v):
    v = _scalarize(v)
    if v is VBNull: raise_runtime('INVALID_USE_OF_NULL')
    # VBScript: True is -1, False is 0 (CDbl(True) = -1, Hex(True) = "FFFF").
    if isinstance(v, bool): return -1 if v else 0
    if isinstance(v, (int, float)): return v
    if isinstance(v, Decimal): return float(v)
    if isinstance(v, (_dt.datetime, _dt.date)): return _date_to_oaserial(v)
    if v is VBEmpty: return 0
    s = vbs_cstr(v).strip()
    # VBScript: CInt("")/CDbl("") is a Type Mismatch; only Empty converts to 0.
    if s == "": raise_runtime('TYPE_MISMATCH')
    if len(s) >= 2 and s[0] == '&' and s[1] in ('H', 'h', 'O', 'o'):
        try: return int(s.replace('&H','0x').replace('&h','0x').replace('&O','0o').replace('&o','0o'), 0)
        except: raise_runtime('TYPE_MISMATCH')
    # Numeric strings are interpreted in the current locale, which is what makes
    # CDbl("1,5") 15 under en-US (comma = group separator) but 1.5 under nl-BE,
    # and makes fr-FR reject "1.5" outright. The locale reading is authoritative:
    # falling back to a plain float() here would wrongly accept separators the
    # locale does not define. Scientific notation ("1e5") is handled by the
    # normaliser, so it keeps working at every locale.
    norm = vb_locale.normalize_number_string(s, vbs_get_lcid())
    if norm is None:
        raise_runtime('TYPE_MISMATCH')
    try: return int(norm)
    except ValueError: pass
    try: return float(norm)
    except ValueError: raise_runtime('TYPE_MISMATCH')

def _to_int(v):
    return int(_to_number(v))

def _to_decimal(v) -> Decimal:
    v = _scalarize(v)
    if v is VBNull: raise_runtime('INVALID_USE_OF_NULL')
    if isinstance(v, Decimal): return v
    # VBScript: True is -1, False is 0.
    if isinstance(v, bool): return Decimal(-1 if v else 0)
    if isinstance(v, (int, float)): return Decimal(str(v))
    if isinstance(v, (_dt.datetime, _dt.date)): return Decimal(str(_date_to_oaserial(v)))
    if v is VBEmpty: return Decimal(0)
    s = vbs_cstr(v).strip()
    # VBScript: CInt("")/CLng("") is a Type Mismatch; only Empty converts to 0.
    if s == "": raise_runtime('TYPE_MISMATCH')
    if len(s) >= 2 and s[0] == '&' and s[1] in ('H', 'h', 'O', 'o'):
        # VBScript hex/octal strings ("&HFF", "&O77") are valid input to
        # CLng/CInt/CCur etc. Keep behavior identical to _to_number.
        try: return Decimal(int(s.replace('&H','0x').replace('&h','0x').replace('&O','0o').replace('&o','0o'), 0))
        except: raise_runtime('TYPE_MISMATCH')
    # Same locale reading as _to_number, so CCur agrees with CDbl.
    norm = vb_locale.normalize_number_string(s, vbs_get_lcid())
    if norm is None: raise_runtime('TYPE_MISMATCH')
    try: return Decimal(norm)
    except: raise_runtime('TYPE_MISMATCH')

def _round_bankers(d: Decimal) -> Decimal:
    return d.quantize(Decimal('1'), rounding=ROUND_HALF_EVEN)

def _group_thousands(s: str, sep: str = ',') -> str:
    if s == "": return ""
    out = []
    n = len(s)
    for i, ch in enumerate(s):
        out.append(ch)
        left = n - i - 1
        if left > 0 and (left % 3) == 0: out.append(sep)
    return ''.join(out)

def Log(number):
    x = float(_to_number(number))
    if x <= 0: raise_runtime('INVALID_PROC_CALL')
    return _math.log(x)

def Sqr(number):
    x = float(_to_number(number))
    if x < 0: raise_runtime('INVALID_PROC_CALL')
    return _math.sqrt(x)

def Left(string, length):
    if string is VBNull: return VBNull
    s = vbs_cstr(string)
    n = int(_to_int(length))
    if n < 0: raise_runtime('INVALID_PROC_CALL')
    if n == 0: return ""
    return s[:n]

def Right(string, length):
    if string is VBNull: return VBNull
    s = vbs_cstr(string)
    n = int(_to_int(length))
    if n < 0: raise_runtime('INVALID_PROC_CALL')
    if n == 0: return ""
    return s[-n:]

def Mid(string, start, length=None):
    if string is VBNull: return VBNull
    s = vbs_cstr(string)
    st = int(_to_int(start))
    if st < 1: raise_runtime('INVALID_PROC_CALL')
    if length is None: return s[st-1:]
    ln = int(_to_int(length))
    if ln < 0: raise_runtime('INVALID_PROC_CALL')
    return s[st-1:st-1+ln]

def Replace(expression, find, replace, start=1, count=-1, compare=0):
    # VBScript: Replace(Null, ...) raises error 94 (it does NOT return Null).
    expr_v = _scalarize(expression)
    if expr_v is VBNull: raise_runtime('INVALID_USE_OF_NULL')
    find_v = _scalarize(find)
    if find_v is VBNull: raise_runtime('INVALID_USE_OF_NULL')
    if _scalarize(replace) is VBNull: raise_runtime('INVALID_USE_OF_NULL')
    expr_s = vbs_cstr(expression)
    find_s = vbs_cstr(find)
    repl_s = vbs_cstr(replace)
    # A zero-length search string means "nothing to find": return unchanged.
    # (Empty must be handled here too; the sentinel is not == "".)
    if find_s == "": return expr_s
    st = int(_to_int(start))
    cnt = int(_to_int(count))
    cmp = int(_to_int(compare))
    if st < 1: raise_runtime('INVALID_PROC_CALL')
    working = expr_s[st-1:]
    # count = 0 means "replace nothing"; only a negative count means "all".
    if cnt == 0: return working
    if cmp == 1:
        import re
        pat = re.escape(find_s)
        flags = re.IGNORECASE
        # re.sub(count=0) means unlimited, so map "all" explicitly.
        n = 0 if cnt < 0 else cnt
        return re.sub(pat, lambda m: repl_s, working, count=n, flags=flags)
    else:
        if cnt < 0: return working.replace(find_s, repl_s)
        return working.replace(find_s, repl_s, cnt)

def Space(number):
    n = int(_to_int(number))
    if n < 0: raise_runtime('INVALID_PROC_CALL')
    return " " * n

def String(number, character):
    # VBScript raises error 94 for Null in either argument, and the character
    # check comes first (String(3, Null) errors rather than returning Null).
    if _scalarize(number) is VBNull: raise_runtime('INVALID_USE_OF_NULL')
    char_v = _scalarize(character)
    if character is None or char_v is VBNull: raise_runtime('INVALID_USE_OF_NULL')
    n = int(_to_int(number))
    if n < 0: raise_runtime('INVALID_PROC_CALL')
    c = ""
    if isinstance(character, int): c = chr(character)
    else:
        s = vbs_cstr(character)
        if len(s) > 0: c = s[0]
    return c * n

def RGB(red, green, blue):
    try:
        r, g, b = int(_to_int(red)), int(_to_int(green)), int(_to_int(blue))
    except: raise_runtime('TYPE_MISMATCH')
    if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255): raise_runtime('INVALID_PROC_CALL')
    return r | (g << 8) | (b << 16)

def Round(expression, numdecimalplaces=0):
    # VBScript quirk: unlike Int/Fix, Round(Null) raises error 94.
    expr = _scalarize(expression)
    if expr is VBNull: raise_runtime('INVALID_USE_OF_NULL')
    # VBScript preserves the Boolean subtype: Round(True) => True.
    if isinstance(expr, bool): return expr
    n = _to_decimal(expression)
    dp = int(_to_int(numdecimalplaces))
    if dp < 0: raise_runtime('INVALID_PROC_CALL')
    quant = Decimal("1")
    if dp > 0: quant = Decimal("0." + ("0" * dp))
    try:
        return float(n.quantize(quant, rounding=ROUND_HALF_EVEN))
    except InvalidOperation:
        # Values beyond the Decimal context precision (e.g. 1E30) have no
        # fractional part left to round; IIS just returns them unchanged.
        return float(n)

def _format_args(numdigitsafterdecimal, includeleadingdigit,
                 useparensfornegativenumbers, groupdigits):
    """Normalise the four shared Format* arguments.

    An OMITTED argument (FormatNumber(n, 2, , , True)) arrives as Python None.
    VBScript treats such a gap as "use the system default", exactly like
    vbUseDefault (-2), so restore each parameter's default here rather than
    letting None reach _to_int (which would be a Type Mismatch).
    """
    if numdigitsafterdecimal is None: numdigitsafterdecimal = -1
    if includeleadingdigit is None: includeleadingdigit = -2
    if useparensfornegativenumbers is None: useparensfornegativenumbers = -2
    if groupdigits is None: groupdigits = -2
    nd = int(_to_int(numdigitsafterdecimal))
    if nd < -1:
        raise_runtime('INVALID_PROC_CALL')
    return (nd,
            int(_to_int(includeleadingdigit)),
            int(_to_int(useparensfornegativenumbers)),
            int(_to_int(groupdigits)))


def FormatNumber(expression, numdigitsafterdecimal=-1, includeleadingdigit=-2, useparensfornegativenumbers=-2, groupdigits=-2):
    # The Format* family does NOT propagate Null: IIS raises Type mismatch (13),
    # not Invalid use of Null and not a Null result. Verified against IIS.
    if expression is VBNull: raise_runtime('TYPE_MISMATCH')
    nd, lead, parens, group = _format_args(
        numdigitsafterdecimal, includeleadingdigit,
        useparensfornegativenumbers, groupdigits)
    return vb_locale.format_number(_to_number(expression), nd, lead, parens,
                                   group, lcid=vbs_get_lcid())


def FormatCurrency(expression, numdigitsafterdecimal=-1, includeleadingdigit=-2, useparensfornegativenumbers=-2, groupdigits=-2):
    if expression is VBNull: raise_runtime('TYPE_MISMATCH')
    nd, lead, parens, group = _format_args(
        numdigitsafterdecimal, includeleadingdigit,
        useparensfornegativenumbers, groupdigits)
    return vb_locale.format_currency(_to_number(expression), nd, lead, parens,
                                     group, lcid=vbs_get_lcid())


def FormatPercent(expression, numdigitsafterdecimal=-1, includeleadingdigit=-2, useparensfornegativenumbers=-2, groupdigits=-2):
    if expression is VBNull: raise_runtime('TYPE_MISMATCH')
    nd, lead, parens, group = _format_args(
        numdigitsafterdecimal, includeleadingdigit,
        useparensfornegativenumbers, groupdigits)
    return vb_locale.format_percent(_to_number(expression), nd, lead, parens,
                                    group, lcid=vbs_get_lcid())


# -----------------------------------------------------------------------------
# Locale functions: GetLocale / SetLocale
#
# VBScript stores the current locale per script engine (per thread in IIS).
# ASPPY already keeps a thread-local LCID in vb_runtime (used by Response.LCID,
# Session.LCID and all locale-aware formatting via vb_locale), so these builtins
# simply read/write that same state.
# -----------------------------------------------------------------------------

# Default LCID when nothing was set. LCID 0 means "system default"; ASPPY
# resolves it deterministically to en-US rather than inheriting the host locale.
_DEFAULT_LCID = vb_locale.DEFAULT_LCID

# Curated VBScript locale short-name -> LCID map. This takes precedence over the
# generated table in locale_data.json because it pins the conventional default
# sub-language for bare language codes ("pt" -> pt-PT, "zh" -> zh-CN) and covers
# a few names that have no formatting record of their own (en-nz, en-ie, en-za,
# zh-sg). Anything not listed here is resolved from locale_data.json, which
# covers all 60 supported locales.
_LOCALE_NAME_TO_LCID = {
    'ar': 1025, 'ar-sa': 1025,
    'cs': 1029, 'cs-cz': 1029,
    'da': 1030, 'da-dk': 1030,
    'de': 1031, 'de-de': 1031, 'de-ch': 2055, 'de-at': 3079,
    'el': 1032, 'el-gr': 1032,
    'en': 1033, 'en-us': 1033, 'en-gb': 2057, 'en-au': 3081,
    'en-ca': 4105, 'en-nz': 5129, 'en-ie': 6153, 'en-za': 7177,
    'es': 1034, 'es-es': 1034, 'es-mx': 2058,
    'fi': 1035, 'fi-fi': 1035,
    'fr': 1036, 'fr-fr': 1036, 'fr-be': 2060, 'fr-ca': 3084, 'fr-ch': 4108,
    'he': 1037, 'he-il': 1037,
    'hi': 1081, 'hi-in': 1081,
    'hu': 1038, 'hu-hu': 1038,
    'id': 1057, 'id-id': 1057,
    'it': 1040, 'it-it': 1040, 'it-ch': 2064,
    'ja': 1041, 'ja-jp': 1041,
    'ko': 1042, 'ko-kr': 1042,
    'nb': 1044, 'nb-no': 1044, 'nn-no': 2068, 'no': 1044,
    'nl': 1043, 'nl-nl': 1043, 'nl-be': 2067,
    'pl': 1045, 'pl-pl': 1045,
    'pt': 2070, 'pt-pt': 2070, 'pt-br': 1046,
    'ru': 1049, 'ru-ru': 1049,
    'sv': 1053, 'sv-se': 1053,
    'th': 1054, 'th-th': 1054,
    'tr': 1055, 'tr-tr': 1055,
    'uk': 1058, 'uk-ua': 1058,
    'vi': 1066, 'vi-vn': 1066,
    'zh': 2052, 'zh-cn': 2052, 'zh-tw': 1028, 'zh-hk': 3076, 'zh-sg': 4100,
}


def GetLocale():
    """VBScript GetLocale(): return the current locale ID (LCID) as a Long."""
    lcid = vbs_get_lcid()
    return int(lcid) if lcid else _DEFAULT_LCID


def SetLocale(lcid=0):
    """VBScript SetLocale(lcid): set the current locale, return previous LCID.

    Accepts a numeric LCID (e.g. 1033), a short locale string (e.g. "en-gb",
    "de", "zh-cn"), or 0 / "" / 1024 / 2048 for the system default locale.
    """
    prev = GetLocale()

    if lcid is VBNull:
        raise_runtime('INVALID_USE_OF_NULL')
    if lcid is VBEmpty or lcid is None:
        lcid = 0

    if isinstance(lcid, str):
        name = lcid.strip().lower().replace('_', '-')
        if name == '':
            new_lcid = 0  # system default
        elif name in _LOCALE_NAME_TO_LCID:
            new_lcid = _LOCALE_NAME_TO_LCID[name]
        elif vb_locale.lcid_for_name(name) is not None:
            new_lcid = vb_locale.lcid_for_name(name)
        else:
            # Allow numeric LCIDs passed as strings ("1033").
            try:
                new_lcid = int(name)
            except Exception:
                raise_runtime('INVALID_PROC_CALL', 'SetLocale')
    else:
        try:
            new_lcid = int(_to_int(lcid))
        except Exception:
            raise_runtime('TYPE_MISMATCH', 'SetLocale')

    # LOCALE_USER_DEFAULT (1024) / LOCALE_SYSTEM_DEFAULT (2048) -> default.
    if new_lcid in (1024, 2048):
        new_lcid = 0
    if new_lcid < 0:
        raise_runtime('INVALID_PROC_CALL', 'SetLocale')

    vbs_set_lcid(new_lcid)
    return prev
