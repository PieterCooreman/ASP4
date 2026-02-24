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
        self.Number = int(number)
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
        hex_code = f"{code:08X}"
        err_def = ErrorDef(code, hex_code, desc or f"Runtime error {code}")
        
        raise VBScriptRuntimeError(err_def)
