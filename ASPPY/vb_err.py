"""VBScript Err object (minimal)."""

from __future__ import annotations


class VBErr:
    def __init__(self):
        self.Clear()

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
