# Add InStrRev to vb_builtins.py
from __future__ import annotations

import datetime as _dt
import math as _math
import random as _random
from decimal import Decimal, ROUND_HALF_EVEN

from .vb_errors import raise_runtime
from .vb_runtime import vbs_cbool, vbs_cstr
from .vm.values import VBEmpty, VBNull, VBNothing
from .vb_builtins import _to_int

def InStrRev(string1, string2, start=-1, compare=0):

    if string1 is VBNull or string2 is VBNull:
        return VBNull
        
    s1 = vbs_cstr(string1)
    s2 = vbs_cstr(string2)
    st = int(_to_int(start))
    
    if st == 0:
        return 0
        
    if s1 == "":
        return 0
    if s2 == "":
        return st if st != -1 else len(s1)
        
    if st == -1:
        st = len(s1)
        
    if st > len(s1):
        st = len(s1) # Or invalid? VBScript clamps or errors?
        # Docs say: If start > Len(string1), 0 is returned (actually inconsistent docs).
        # Let's clamp to len(s1)
        st = len(s1)
        
    # Search backwards from st
    
    if int(_to_int(compare)) == 1:
        s1 = s1.lower()
        s2 = s2.lower()
        
    # Python rfind searches in [0, end). 
    # VBScript InStrRev searches from 'start' backwards.
    # In python: s1.rfind(s2, 0, st)
    
    idx = s1.rfind(s2, 0, st)
    return 0 if idx < 0 else (idx + 1)

# ... (Rest of file)
