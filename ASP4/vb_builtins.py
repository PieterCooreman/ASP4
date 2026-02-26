# vb_builtins.py - Fix missing exports
from __future__ import annotations

import datetime as _dt
import math as _math
import random as _random
from decimal import Decimal, ROUND_HALF_EVEN

from .vb_errors import raise_runtime
from .vb_runtime import vbs_cbool, vbs_cstr
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

def UBound(arrayname, dimension=1):
    from .vm.values import VBArray
    if isinstance(arrayname, VBArray):
        try: return arrayname.ubound(dimension)
        except IndexError: raise_runtime('SUBSCRIPT_OUT_OF_RANGE')
    if isinstance(arrayname, (list, tuple)):
        if int(dimension) != 1: raise_runtime('SUBSCRIPT_OUT_OF_RANGE')
        return len(arrayname) - 1
    raise_runtime('TYPE_MISMATCH')

def LBound(arrayname, dimension=1):
    from .vm.values import VBArray
    if isinstance(arrayname, VBArray):
        try: return arrayname.lbound(dimension)
        except IndexError: raise_runtime('SUBSCRIPT_OUT_OF_RANGE')
    if isinstance(arrayname, (list, tuple)):
        if int(dimension) != 1: raise_runtime('SUBSCRIPT_OUT_OF_RANGE')
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
    t = vbs_cstr(s)
    if t == "": raise_runtime('INVALID_PROC_CALL')
    return ord(t[0])

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
    return chr(n)

def CByte(expr):
    n = int(_to_int(expr))
    if n < 0 or n > 255: raise_runtime('OVERFLOW')
    return n

def CCur(expr):
    d = _to_decimal(expr)
    return d.quantize(Decimal('0.0000'), rounding=ROUND_HALF_EVEN)

def CDbl(expr):
    return float(_to_number(expr))

def CSng(expr):
    return float(_to_number(expr))

def CInt(expr):
    return int(_round_bankers(_to_decimal(expr)))

def CLng(expr):
    return int(_round_bankers(_to_decimal(expr)))

def CStr(expr):
    return vbs_cstr(expr)

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
    try: return len(s.encode('latin-1', errors='replace'))
    except: return len(s)

def LeftB(string, length):
    if string is VBNull: return VBNull
    s = vbs_cstr(string)
    # Approximation of BSTR bytes (latin-1)
    b = s.encode('latin-1', errors='replace')
    n = int(_to_int(length))
    if n < 0: raise_runtime('INVALID_PROC_CALL')
    if n == 0: return b""
    return b[:n]

def RightB(string, length):
    if string is VBNull: return VBNull
    s = vbs_cstr(string)
    b = s.encode('latin-1', errors='replace')
    n = int(_to_int(length))
    if n < 0: raise_runtime('INVALID_PROC_CALL')
    if n == 0: return b""
    return b[-n:]

def MidB(expr, start, length=None):
    if expr is VBNull: return VBNull
    b = bytes(expr) if isinstance(expr, (bytes, bytearray)) else vbs_cstr(expr).encode('latin-1', errors='replace')
    st = int(_to_int(start))
    if st <= 0: return b""
    i = st - 1
    if length is None: return b[i:]
    ln = int(_to_int(length))
    if ln <= 0: return b""
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
    
    # Force byte conversion (latin-1 or utf-8? VBScript uses BSTR bytes)
    # Since we use Python str, let's treat it as bytes.
    # VBScript InStrB treats strings as byte arrays.
    
    def _to_bytes(v):
        if isinstance(v, (bytes, bytearray)): return bytes(v)
        return vbs_cstr(v).encode('latin-1', errors='replace') # Approximation
        
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

def _to_number(v):
    if isinstance(v, bool): return 1 if v else 0
    if isinstance(v, (int, float)): return v
    if isinstance(v, Decimal): return float(v)
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
    if isinstance(v, Decimal): return v
    if isinstance(v, bool): return Decimal(1 if v else 0)
    if isinstance(v, (int, float)): return Decimal(str(v))
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
