# vb_builtins.py - Fix missing exports
from __future__ import annotations

import datetime as _dt
import math as _math
import random as _random
from decimal import Decimal, ROUND_HALF_EVEN

from .vb_errors import raise_runtime
from .vb_runtime import vbs_cbool, vbs_cstr, vbs_get_lcid, vbs_set_lcid
from .vm.values import VBEmpty, VBNull, VBNothing

# Re-implement core functions to guarantee they exist in this module scope

def Len(expression):
    if expression is VBNull: return VBNull
    if expression is VBEmpty or expression is VBNothing: return 0
    if isinstance(expression, (str, bytes, bytearray)): return len(expression)
    return len(vbs_cstr(expression))

def UCase(string):
    return vbs_cstr(string).upper()

def LCase(string):
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
    if string is VBNull: return VBNull
    return vbs_cstr(string)[::-1]

def StrComp(string1, string2, compare=0):
    s1 = vbs_cstr(string1)
    s2 = vbs_cstr(string2)
    cmp = int(_to_int(compare))
    if cmp == 1:
        s1 = s1.lower()
        s2 = s2.lower()
    if s1 < s2: return -1
    if s1 > s2: return 1
    return 0

def Split(expression, delimiter=" ", count=-1, compare=0):
    if expression is VBNull: return VBNull
    s = vbs_cstr(expression)
    d = vbs_cstr(delimiter)
    from .vm.values import VBArray
    if d == "": return VBArray([0], allocated=True, dynamic=True)
    cnt = int(_to_int(count))
    if cnt < 0:
        parts = s.split(d)
    else:
        if cnt == 0: return VBArray([-1])
        parts = s.split(d, cnt - 1)
    arr = VBArray(len(parts)-1, allocated=True, dynamic=True)
    for i, p in enumerate(parts):
        arr._items[i] = p
    return arr

def Join(list_var, delimiter=" "):
    from .vm.values import VBArray
    if list_var is VBNull: return VBNull
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
    from .vm.values import VBArray
    if isinstance(arrayname, VBArray):
        try: return arrayname.ubound(dimension)
        except IndexError as e: raise_runtime('SUBSCRIPT_OUT_OF_RANGE', str(e))
    if isinstance(arrayname, (list, tuple)):
        if int(dimension) != 1:
            raise_runtime('SUBSCRIPT_OUT_OF_RANGE',
                f"UBound dimension {dimension} requested but array is 1-dimensional")
        return len(arrayname) - 1
    raise_runtime('TYPE_MISMATCH')

def LBound(arrayname, dimension=1):
    from .vm.values import VBArray
    if isinstance(arrayname, VBArray):
        try: return arrayname.lbound(dimension)
        except IndexError as e: raise_runtime('SUBSCRIPT_OUT_OF_RANGE', str(e))
    if isinstance(arrayname, (list, tuple)):
        if int(dimension) != 1:
            raise_runtime('SUBSCRIPT_OUT_OF_RANGE',
                f"LBound dimension {dimension} requested but array is 1-dimensional")
        return 0
    raise_runtime('TYPE_MISMATCH')

def IsArray(varname):
    from .vm.values import VBArray
    return isinstance(varname, (VBArray, list, tuple))

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
    return expression is VBEmpty

def IsNull(expression):
    return expression is VBNull

def IsNumeric(expression):
    if expression is VBNull: return False
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
    from .vm.values import VBArray
    if isinstance(expression, VBArray): return False
    return True

def TypeName(varname):
    v = varname
    if v is VBEmpty or v is None: return "Empty"
    if v is VBNull: return "Null"
    if v is VBNothing: return "Nothing"
    if isinstance(v, bool): return "Boolean"
    if isinstance(v, int): return "Integer" if -32768 <= v <= 32767 else "Long"
    if isinstance(v, float): return "Double"
    if isinstance(v, Decimal): return "Currency"
    if isinstance(v, str): return "String"
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
    return "Object"

def VarType(varname):
    v = varname
    if v is VBEmpty or v is None: return 0
    if v is VBNull: return 1
    if isinstance(v, bool): return 11
    if isinstance(v, int): return 3
    if isinstance(v, float): return 5
    if isinstance(v, Decimal): return 6
    if isinstance(v, str): return 8
    if isinstance(v, (_dt.datetime, _dt.date)): return 7
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
    if not IsArray(inputstrings): raise_runtime('TYPE_MISMATCH')
    arr = inputstrings
    if not arr._allocated: return VBArray([-1])
    res = []
    val_s = vbs_cstr(value)
    inc = vbs_cbool(include)
    for item in arr._items:
        s = vbs_cstr(item)
        match = (val_s.lower() in s.lower()) if int(_to_int(compare)) == 1 else (val_s in s)
        if match == inc: res.append(item)
    out = VBArray([len(res)-1] if res else [-1])
    for i, r in enumerate(res): out._items[i] = r
    return out

def Asc(s):
    t = vbs_cstr(s)
    if t == "": raise_runtime('INVALID_PROC_CALL')
    return ord(t[0])

def AscW(s):
    t = vbs_cstr(s)
    if t == "": raise_runtime('INVALID_PROC_CALL')
    return ord(t[0])

def AscB(s):
    if s is VBNull:
        return VBNull
    b = bytes(s) if isinstance(s, (bytes, bytearray)) else vbs_cstr(s).encode('utf-16le')
    if len(b) == 0:
        raise_runtime('INVALID_PROC_CALL')
    return b[0]

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
    return float(_to_number(expr))

def CInt(expr):
    if expr is VBNull: raise_runtime('INVALID_USE_OF_NULL')
    if isinstance(expr, bool): return -1 if expr else 0
    result = int(_round_bankers(_to_decimal(expr)))
    if result < -32768 or result > 32767:
        raise_runtime('OVERFLOW')
    return result

def CLng(expr):
    if expr is VBNull: raise_runtime('INVALID_USE_OF_NULL')
    if isinstance(expr, bool): return -1 if expr else 0
    return int(_round_bankers(_to_decimal(expr)))

def CStr(expr):
    if expr is VBNull: raise_runtime('INVALID_USE_OF_NULL')
    return vbs_cstr(expr)

def CBool(expr):
    if expr is VBNull: raise_runtime('INVALID_USE_OF_NULL')
    return vbs_cbool(expr)

def Hex(number):
    n = int(_to_int(number))
    if n < 0: n = n & 0xFFFFFFFF
    return format(n, 'X')

def LenB(expr):
    v = expr
    if v is VBNull: return VBNull
    if v is VBEmpty or v is VBNothing or v is None: return 0
    if isinstance(v, (bytes, bytearray)): return len(v)
    s = vbs_cstr(v)
    try: return len(s.encode('utf-16le'))
    except: return len(s)

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
    n = int(_to_int(number))
    if n < 0: n = n & 0xFFFFFFFF
    return format(n, 'o')

def Abs(number):
    x = _to_number(number)
    return -x if x < 0 else x

def Atn(number):
    return _math.atan(float(_to_number(number)))

def Cos(number):
    return _math.cos(float(_to_number(number)))

def Exp(number):
    return _math.exp(float(_to_number(number)))

def Int(number):
    return _math.floor(float(_to_number(number)))

def Fix(number):
    x = float(_to_number(number))
    return int(x)

def _date_to_oaserial(v):
    # OLE Automation date: days since 1899-12-30. A VBScript Date IS a Double.
    if isinstance(v, _dt.datetime):
        d = v
    else:  # _dt.date
        d = _dt.datetime(v.year, v.month, v.day)
    return (d - _dt.datetime(1899, 12, 30)).total_seconds() / 86400.0

def _to_number(v):
    if v is VBNull: raise_runtime('INVALID_USE_OF_NULL')
    if isinstance(v, bool): return 1 if v else 0
    if isinstance(v, (int, float)): return v
    if isinstance(v, Decimal): return float(v)
    if isinstance(v, (_dt.datetime, _dt.date)): return _date_to_oaserial(v)
    s = vbs_cstr(v).strip()
    if s == "": return 0
    if len(s) >= 2 and s[0] == '&' and s[1] in ('H', 'h', 'O', 'o'):
        try: return int(s.replace('&H','0x').replace('&h','0x').replace('&O','0o').replace('&o','0o'), 0)
        except: raise_runtime('TYPE_MISMATCH')
    try: return float(s) if '.' in s else int(s)
    except: raise_runtime('TYPE_MISMATCH')

def _to_int(v):
    return int(_to_number(v))

def _to_decimal(v) -> Decimal:
    if v is VBNull: raise_runtime('INVALID_USE_OF_NULL')
    if isinstance(v, Decimal): return v
    if isinstance(v, bool): return Decimal(1 if v else 0)
    if isinstance(v, (int, float)): return Decimal(str(v))
    if isinstance(v, (_dt.datetime, _dt.date)): return Decimal(str(_date_to_oaserial(v)))
    s = vbs_cstr(v).strip()
    if s == "": return Decimal(0)
    try: return Decimal(s)
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
    if expression is VBNull: return VBNull
    if find is VBNull or find == "": return vbs_cstr(expression)
    if replace is VBNull: replace = ""
    expr_s = vbs_cstr(expression)
    find_s = vbs_cstr(find)
    repl_s = vbs_cstr(replace)
    st = int(_to_int(start))
    cnt = int(_to_int(count))
    cmp = int(_to_int(compare))
    if st < 1: raise_runtime('INVALID_PROC_CALL')
    working = expr_s[st-1:]
    if cmp == 1:
        import re
        pat = re.escape(find_s)
        flags = re.IGNORECASE
        if cnt < 0: cnt = 0
        return re.sub(pat, lambda m: repl_s, working, count=cnt, flags=flags)
    else:
        if cnt < 0: return working.replace(find_s, repl_s)
        return working.replace(find_s, repl_s, cnt)

def Space(number):
    n = int(_to_int(number))
    if n < 0: raise_runtime('INVALID_PROC_CALL')
    return " " * n

def String(number, character):
    n = int(_to_int(number))
    if n < 0: raise_runtime('INVALID_PROC_CALL')
    if character is None or character is VBNull: return VBNull
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
    if expression is VBNull: return VBNull
    n = _to_decimal(expression)
    dp = int(_to_int(numdecimalplaces))
    if dp < 0: raise_runtime('INVALID_PROC_CALL')
    quant = Decimal("1")
    if dp > 0: quant = Decimal("0." + ("0" * dp))
    return float(n.quantize(quant, rounding=ROUND_HALF_EVEN))

def FormatNumber(expression, numdigitsafterdecimal=2, includeleadingdigit=True, useparensfornegativenumbers=False, groupdigits=True):
    if expression is VBNull: return VBNull
    n = _to_number(expression)
    
    # Handle Default (-1) for arguments
    nd = int(_to_int(numdigitsafterdecimal))
    if nd == -1: nd = 2
    
    if nd < 0: raise_runtime('INVALID_PROC_CALL')
        
    fmt = f"{{:.{nd}f}}"
    s = fmt.format(n)
    
    # Defaults for tristate args: -2 (Default) -> True or False
    # VBScript defaults: LeadingDigit=True, Parens=False, Group=True usually
    
    inc_lead = int(_to_int(includeleadingdigit))
    if inc_lead == -2: inc_lead = -1 # True
    
    use_parens = int(_to_int(useparensfornegativenumbers))
    if use_parens == -2: use_parens = 0 # False
    
    use_group = int(_to_int(groupdigits))
    if use_group == -2: use_group = -1 # True

    if use_group and use_group != 0:
        parts = s.split('.')
        parts[0] = _group_thousands(parts[0])
        s = '.'.join(parts)
        
    if inc_lead == 0: 
        if s.startswith('0.'): s = s[1:]
        elif s.startswith('-0.'): s = '-' + s[2:]
            
    if use_parens and use_parens != 0 and n < 0:
        s = f"({s.replace('-', '')})"
        
    return s

def FormatCurrency(expression, numdigitsafterdecimal=-1, includeleadingdigit=-2, useparensfornegativenumbers=-2, groupdigits=-2):
    s = FormatNumber(expression, numdigitsafterdecimal, includeleadingdigit, useparensfornegativenumbers, groupdigits)
    # Simple hardcoded symbol for now, as user doesn't want full locale support but expects currency-like output.
    # Check for parens (negative)
    if s.startswith('(') and s.endswith(')'):
        return f"(${s[1:-1]})"
    return f"${s}"

def FormatPercent(expression, numdigitsafterdecimal=-1, includeleadingdigit=-2, useparensfornegativenumbers=-2, groupdigits=-2):
    try:
        val = float(_to_number(expression)) * 100.0
    except:
        val = 0.0
    s = FormatNumber(val, numdigitsafterdecimal, includeleadingdigit, useparensfornegativenumbers, groupdigits)
    return s + "%"


# -----------------------------------------------------------------------------
# Locale functions: GetLocale / SetLocale
#
# VBScript stores the current locale per script engine (per thread in IIS).
# ASPPY already keeps a thread-local LCID in vb_runtime (used by Response.LCID
# and locale-aware formatting via vbs_get_lcid_info), so these builtins simply
# read/write that same state.
# -----------------------------------------------------------------------------

# Default LCID when nothing was set. The runtime treats LCID 0 as "system
# default" and formats as en-US (see vb_runtime.vbs_get_lcid_info), so the
# deterministic default reported to scripts is 1033 (en-US), matching typical
# IIS installs.
_DEFAULT_LCID = 1033

# Common VBScript locale short-name -> LCID map (SetLocale accepts either a
# numeric LCID or a short string like "en-gb", "de", "zh-cn").
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
