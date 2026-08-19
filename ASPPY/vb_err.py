"""VBScript Err object (minimal)."""

from __future__ import annotations


class VBErr:
    # The Err object's DEFAULT property is Number, so bare `Err` reads as the
    # error code. Verified on IIS 10: CStr(Err) is "0", (Err = 0) is True and
    # Err + 5 is 5 on a clean Err. Legacy code relies on this constantly:
    #     Conn.Open ConnStr
    #     If Err Then ...            ' i.e. If Err.Number <> 0
    __vbs_default__ = 'Number'

    # ... and that default property is WRITABLE, so `Err = 0` is a property-put
    # that clears only Number (Description/Source survive - it is not
    # Err.Clear), leaving Err an Object. Verified on IIS 10. Without this the
    # name would be rebound to the Integer 0, destroying the intrinsic Err for
    # the rest of the page and silently breaking every later
    # `If Err.Number <> 0` check.
    __vbs_default_put__ = 'Number'

    def __init__(self):
        self.Clear()

    # Err.Number and Err.HelpContext are declared Long on the COM interface, so
    # their subtype never depends on the value: TypeName(Err.Number) is "Long"
    # and VarType(Err.Number) is 3 (vbLong) even for 0 or 6, where ASPPY would
    # otherwise infer "Integer" from the magnitude. Verified on IIS 10. Scripts
    # that branch on VarType/TypeName of an error code need this.
    @property
    def Number(self):
        from .vb_runtime import VBLong
        return VBLong(self._number)

    @Number.setter
    def Number(self, value):
        try:
            self._number = int(value)
        except (TypeError, ValueError):
            self._number = 0

    @property
    def HelpContext(self):
        from .vb_runtime import VBLong
        return VBLong(self._helpcontext)

    @HelpContext.setter
    def HelpContext(self, value):
        try:
            self._helpcontext = int(value)
        except (TypeError, ValueError):
            self._helpcontext = 0

    def Clear(self):
        self.Number = 0
        self.Description = ""
        self.Source = ""
        self.HelpFile = ""
        self.HelpContext = 0

    def Raise(self, number=0, source="", description="", helpfile="", helpcontext=0):
        # Err.Number is a signed 32-bit Long on IIS, so Err.Raise &H80004005
        # must report -2147467259 rather than 2147500037.
        n = int(number) & 0xFFFFFFFF
        self.Number = n - 0x100000000 if (n & 0x80000000) else n
        self.Source = str(source)
        self.Description = str(description)
        self.HelpFile = str(helpfile)
        self.HelpContext = int(helpcontext)
        # Raising a VBScript runtime error is handled by the interpreter.
        from .vb_errors import VBScriptRuntimeError, ErrorDef
        
        # If no description provided, try to find standard one
        desc = self.Description
        code = self.Number
        
        # Convert VB error code to hex if needed or pass as is
        # Note: Err.Raise arguments are raw.
        # Construct a custom ErrorDef on the fly
        hex_code = f"{code & 0xFFFFFFFF:08X}"
        err_def = ErrorDef(code, hex_code, desc or f"Runtime error {code}")
        
        raise VBScriptRuntimeError(err_def)
