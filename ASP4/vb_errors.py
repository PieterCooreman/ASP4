"""Centralized VBScript Error Definitions for ASP4.

Distinguishes between Compilation Errors (syntax, parsing) and Runtime Errors.
"""

from dataclasses import dataclass

@dataclass
class ErrorDef:
    number: int  # Standard decimal number (e.g. 13 for Type mismatch)
    hex_code: str # The 800Axxxx code
    description: str

# -----------------------------------------------------------------------------
# Compilation Errors (Syntax, Parser)
# -----------------------------------------------------------------------------
COMPILATION_ERRORS = {
    'SYNTAX_ERROR': ErrorDef(1002, '800A0400', "Syntax error"),
    'EXPECTED_EOS': ErrorDef(1003, '800A0401', "Expected end of statement"), # Missing : or newline
    'EXPECTED_INTEGER': ErrorDef(1004, '800A0402', "Expected integer constant"),
    'INVALID_CHARACTER': ErrorDef(1010, '800A0408', "Invalid character"),
    'UNTERMINATED_STRING': ErrorDef(1011, '800A0409', "Unterminated string constant"),
    'NAME_REDEFINED': ErrorDef(1013, '800A0411', "Name redefined"), # Dim x, x
    'CANNOT_USE_PARENS': ErrorDef(1016, '800A0414', "Cannot use parentheses when calling a Sub"),
    'EXPECTED_IDENTIFIER': ErrorDef(1017, '800A0415', "Expected identifier"),
    'EXPECTED_ASSIGN': ErrorDef(1018, '800A0416', "Expected '='"),
    'INVALID_ME': ErrorDef(1019, '800A0417', "Invalid use of Me keyword"),
    'INVALID_PROPERTY': ErrorDef(1020, '800A0418', "Invalid use of property"),
    
    # Specific block closers
    'EXPECTED_NEXT': ErrorDef(1026, '800A03F6', "Expected 'Next'"),
    'EXPECTED_LOOP': ErrorDef(1027, '800A03F7', "Expected 'Loop'"),
    'EXPECTED_WEND': ErrorDef(1028, '800A03F8', "Expected 'Wend'"),
    'EXPECTED_END': ErrorDef(1029, '800A03F9', "Expected 'End'"), # End If, End Sub, etc.
    'EXPECTED_END_SELECT': ErrorDef(1029, '800A03F9', "Expected 'End Select'"),
    
    # Query/String specific
    'QUERY_SYNTAX': ErrorDef(1002, '800A03EA', "Syntax error in string in query expression"),
    
    # General fallback
    'COMPILATION_UNKNOWN': ErrorDef(0, '800A0400', "Compilation error"),
}

# -----------------------------------------------------------------------------
# Runtime Errors (Execution)
# -----------------------------------------------------------------------------
RUNTIME_ERRORS = {
    'INVALID_PROC_CALL': ErrorDef(5, '800A0005', "Invalid procedure call or argument"),
    'SUBSCRIPT_OUT_OF_RANGE': ErrorDef(9, '800A0009', "Subscript out of range"),
    'TYPE_MISMATCH': ErrorDef(13, '800A000D', "Type mismatch"),
    'FILE_NOT_FOUND': ErrorDef(53, '800A0035', "File not found"),
    'PERMISSION_DENIED': ErrorDef(70, '800A0046', "Permission denied"),
    'OBJECT_REQUIRED': ErrorDef(424, '800A01A8', "Object required"),
    'COMPONENT_CANT_CREATE': ErrorDef(429, '800A01AD', "ActiveX component can't create object"),
    'OBJECT_NOT_SUPPORT': ErrorDef(438, '800A01B6', "Object doesn't support this property or method"),
    'WRONG_NUM_ARGS': ErrorDef(450, '800A01C2', "Wrong number of arguments or invalid property assignment"),
    'VAR_UNDEFINED': ErrorDef(500, '800A01F4', "Variable is undefined"), # Needs dynamic message
    
    # ADO / Database specific
    'ADO_ARGS_WRONG_TYPE': ErrorDef(3001, '800A0BB9', "Arguments are of the wrong type, are out of acceptable range, or are in conflict with one another"),
    'ADO_BOF_EOF': ErrorDef(3021, '800A0BCD', "Either BOF or EOF is True, or the current record has been deleted. Requested operation requires a current record."),
    'ADO_OBJECT_CLOSED': ErrorDef(3704, '800A0E7A', "Operation is not allowed when the object is closed"),
    'ADO_UNSPECIFIED': ErrorDef(-2147467259, '80004005', "Unspecified error"),
}

class VBScriptError(Exception):
    def __init__(self, def_or_key, extra_info=None, source_ctx=None):
        """
        def_or_key: ErrorDef object OR string key from definitions
        extra_info: Optional string to append/replace description (e.g. variable name)
        """
        self.error_def = None
        if isinstance(def_or_key, ErrorDef):
            self.error_def = def_or_key
        elif isinstance(def_or_key, str):
            # Look in compilation first, then runtime
            self.error_def = COMPILATION_ERRORS.get(def_or_key) or RUNTIME_ERRORS.get(def_or_key)
        
        if self.error_def is None:
            self.error_def = ErrorDef(0, '8000FFFF', str(def_or_key))

        self.description = self.error_def.description
        if extra_info:
            if "%s" in self.description:
                self.description = self.description % extra_info
            else:
                # If specific known errors, append info formatted
                if self.error_def.hex_code == '800A01F4': # Var undefined
                    self.description = f"Variable is undefined: '{extra_info}'"
                else:
                    self.description = f"{self.description}: {extra_info}"

        # Location info (populated by runtime/parser)
        self.file = ""
        self.line = 0
        self.col = 0
        self.source_line = ""
        self.source_snippet = ""
        
        super().__init__(self.description)

class VBScriptCompilationError(VBScriptError):
    pass

class VBScriptRuntimeError(VBScriptError):
    pass

def raise_runtime(key, extra=None):
    raise VBScriptRuntimeError(key, extra)

def raise_compilation(key, extra=None):
    raise VBScriptCompilationError(key, extra)
