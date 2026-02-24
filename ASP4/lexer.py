"""A minimal lexer for a growing VBScript subset.

Scope (current):
- Identifiers + a small keyword set (IF/THEN/..., FOR/NEXT, SELECT/CASE, ...)
- String literals: "..." with VBScript escaping via ""
- Numbers (ints)
- Symbols: . ( ) ,
- Statement separators: : and NEWLINE
- Operators: & + - * / \\ < > <= >= <>
"""


class Token:
    def __init__(self, kind: str, value: str, pos: int):
        self.kind = kind
        self.value = value
        self.pos = pos

    def __repr__(self):
        return f"Token({self.kind!r}, {self.value!r}, pos={self.pos})"


class LexerError(Exception):
    pass


_KEYWORDS = {
    # control flow
    "IF",
    "THEN",
    "ELSE",
    "ELSEIF",
    "END",
    "SELECT",
    "CASE",
    "DO",
    "LOOP",
    "WHILE",
    "UNTIL",
    "WEND",
    "FOR",
    "EACH",
    "IN",
    "TO",
    "STEP",
    "NEXT",
    "WITH",
    "EXIT",
    "DIM",
    "REDIM",
    "PRESERVE",
    "ERASE",
    "SET",
    "IS",
    "SUB",
    "FUNCTION",
    "CALL",
    "BYVAL",
    "OPTIONAL",
    "BYREF",
    "PROPERTY",
    "GET",
    "LET",
    # SET already included above
    "CLASS",
    "PUBLIC",
    "PRIVATE",
    "DEFAULT",
    "NEW",
    "ME",
    "OPTION",
    "EXPLICIT",
    "CONST",
    # Treat "On/Error/Resume/Goto/Randomize" as identifiers to avoid
    # breaking valid VBScript variable names like "Dim error".
    # Same for "RESPONSE", "REQUEST", "SERVER", "SESSION", "APPLICATION", "ERR" - 
    # these are just standard identifiers in global scope, not keywords.
}


class Lexer:
    def __init__(self, text: str):
        self.text = text
        self.i = 0
        self.n = len(text)

    def _peek(self) -> str:
        if self.i >= self.n:
            return ""
        return self.text[self.i]

    def _take(self) -> str:
        if self.i >= self.n:
            return ""
        ch = self.text[self.i]
        self.i += 1
        return ch

    def _skip_ws(self):
        # Skip spaces/tabs and apostrophe comments, but DO NOT consume newlines.
        while self.i < self.n:
            ch = self.text[self.i]
            if ch in ("\r", "\n"):
                return
            if ch.isspace():
                self.i += 1
                continue
            if ch == "'":
                while self.i < self.n and self.text[self.i] not in ("\r", "\n"):
                    self.i += 1
                continue
            return

    def next_token(self) -> Token:
        self._skip_ws()
        pos = self.i
        if self.i >= self.n:
            return Token("EOF", "", pos)

        ch = self._take()

        # Line continuation: space-underscore at end of line
        if ch == '_':
            j = self.i
            while j < self.n and self.text[j] not in ("\r", "\n"):
                if not self.text[j].isspace():
                    break
                j += 1
            if j == self.n or self.text[j] in ("\r", "\n"):
                # consume to end of line and the newline itself
                self.i = j
                if self.i < self.n and self.text[self.i] == "\r":
                    self.i += 1
                if self.i < self.n and self.text[self.i] == "\n":
                    self.i += 1
                return self.next_token()

        # Bracketed identifier: [foo bar] - used to escape keywords.
        if ch == '[':
            buf = []
            start = self.i
            while self.i < self.n:
                c2 = self._take()
                if c2 == ']':
                    name = "".join(buf).strip()
                    if name == "":
                        raise LexerError(f"Empty bracketed identifier at position {start}")
                    return Token("IDENT", name, pos)
                buf.append(c2)
            raise LexerError(f"Unterminated bracketed identifier at position {start}")

        # Date literal: #...#
        if ch == '#':
            buf = []
            start = self.i
            while self.i < self.n:
                c2 = self._take()
                if c2 == '#':
                    return Token("DATE", "".join(buf), pos)
                buf.append(c2)
            raise LexerError(f"Unterminated date literal at position {start}")

        # Line continuation: underscore at end of line
        if ch == '_':
            j = self.i
            while j < self.n and self.text[j] not in ("\r", "\n"):
                if self.text[j].isspace():
                    j += 1
                    continue
                # allow comment after underscore
                if self.text[j] == "'":
                    while j < self.n and self.text[j] not in ("\r", "\n"):
                        j += 1
                    break
                # not a line continuation
                j = -1
                break
            if j != -1:
                # consume to end-of-line + newline
                self.i = j
                if self.i < self.n and self.text[self.i] == "\r":
                    self.i += 1
                    if self.i < self.n and self.text[self.i] == "\n":
                        self.i += 1
                elif self.i < self.n and self.text[self.i] == "\n":
                    self.i += 1
                return self.next_token()

        # Newlines
        if ch == "\r":
            if self.i < self.n and self.text[self.i] == "\n":
                self.i += 1
            return Token("NEWLINE", "\n", pos)
        if ch == "\n":
            return Token("NEWLINE", "\n", pos)

        # Single-char tokens
        if ch == '.':
            return Token("DOT", ch, pos)
        if ch == '(':
            return Token("LPAREN", ch, pos)
        if ch == ')':
            return Token("RPAREN", ch, pos)
        if ch == ',':
            return Token("COMMA", ch, pos)
        if ch == ':':
            return Token("COLON", ch, pos)
        if ch == '=':
            # Some legacy VBScript code uses =< and => as <= and >=.
            if self.i < self.n and self.text[self.i] == '<':
                self.i += 1
                return Token("LE", "=<", pos)
            if self.i < self.n and self.text[self.i] == '>':
                self.i += 1
                return Token("GE", "=>", pos)
            return Token("EQ", ch, pos)
        if ch == '&':
            # Hex/Oct literal: &HFF / &O377
            if self.i < self.n and self.text[self.i] in ('H', 'h', 'O', 'o'):
                base_ch = self.text[self.i]
                base = 16 if base_ch in ('H', 'h') else 8
                j = self.i + 1
                if j < self.n:
                    c3 = self.text[j]
                    if c3.isdigit() or (base == 16 and c3.lower() in 'abcdef'):
                        self.i += 1
                        digits = []
                        while self.i < self.n:
                            c4 = self.text[self.i]
                            if c4.isdigit() or (base == 16 and c4.lower() in 'abcdef'):
                                digits.append(c4)
                                self.i += 1
                                continue
                            break
                        n = int(''.join(digits), base)
                        return Token("NUMBER", str(n), pos)
            return Token("AMP", ch, pos)
        if ch == '+':
            return Token("PLUS", ch, pos)
        if ch == '-':
            return Token("MINUS", ch, pos)
        if ch == '*':
            return Token("STAR", ch, pos)
        if ch == '^':
            return Token("CARET", ch, pos)
        if ch == '/':
            return Token("SLASH", ch, pos)
        if ch == '\\':
            return Token("BSLASH", ch, pos)
        if ch == '<':
            if self.i < self.n and self.text[self.i] == '=':
                self.i += 1
                return Token("LE", "<=", pos)
            if self.i < self.n and self.text[self.i] == '>':
                self.i += 1
                return Token("NE", "<>", pos)
            return Token("LT", "<", pos)
        if ch == '>':
            if self.i < self.n and self.text[self.i] == '=':
                self.i += 1
                return Token("GE", ">=", pos)
            return Token("GT", ">", pos)

        # Number (int or simple float)
        if ch.isdigit():
            buf = [ch]
            while self.i < self.n and self.text[self.i].isdigit():
                buf.append(self.text[self.i])
                self.i += 1
            # optional fractional part
            if self.i + 1 < self.n and self.text[self.i] == '.' and self.text[self.i + 1].isdigit():
                buf.append('.')
                self.i += 1
                while self.i < self.n and self.text[self.i].isdigit():
                    buf.append(self.text[self.i])
                    self.i += 1
            return Token("NUMBER", "".join(buf), pos)

        # Identifier / keyword
        if ch.isalpha() or ch == '_':
            buf = [ch]
            while self.i < self.n:
                c2 = self.text[self.i]
                if c2.isalnum() or c2 == '_':
                    buf.append(c2)
                    self.i += 1
                else:
                    break
            ident = "".join(buf)
            u = ident.upper()
            if u in _KEYWORDS:
                return Token(u, ident, pos)
            return Token("IDENT", ident, pos)

        # String literal
        if ch == '"':
            buf = []
            while self.i < self.n:
                c2 = self._take()
                if c2 == '"':
                    # VBScript escapes quotes by doubling them: ""
                    if self.i < self.n and self.text[self.i] == '"':
                        self.i += 1
                        buf.append('"')
                        continue
                    return Token("STRING", "".join(buf), pos)
                buf.append(c2)
            raise LexerError(f"Unterminated string literal at position {pos}")

        raise LexerError(f"Unexpected character {ch!r} at position {pos}")
