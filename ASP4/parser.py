"""A minimal recursive-descent parser for a tiny VBScript subset."""

from .ast_nodes import (
    StringLit,
    NumberLit,
    DateLit,
    Ident,
    BoolLit,
    Call,
    Member,
    Index,
    CallExpr,
    Concat,
    UnaryOp,
    BinaryOp,
    ResponseWrite,
    ResponseEnd,
    ResponseClear,
    ResponseFlush,
    ResponseSetProperty,
    ResponseCall,
    ResponseCookiesSet,
    ExprStmt,
    Assign,
    SetAssign,
    IfStmt,
    WhileStmt,
    DoWhileStmt,
    DoLoopStmt,
    ForStmt,
    ForEachStmt,
    CaseClause,
    SelectCaseStmt,
    ExitForStmt,
    ExitDoStmt,
    ExitSelectStmt,
    ExitFunctionStmt,
    ExitSubStmt,
    ExitPropertyStmt,
    ParamDecl,
    SubDef,
    FuncDef,
    PropertyDef,
    ClassVarDecl,
    ClassDef,
    NewExpr,
    OptionExplicitStmt,
    OnErrorResumeNextStmt,
    OnErrorGoto0Stmt,
    RandomizeStmt,
    ConstStmt,
    EndIfStmt,
    ExecuteStmt,
    DimDecl,
    DimStmt,
    ReDimStmt,
    EraseStmt,
)
from .lexer import Lexer, LexerError


from .vb_errors import VBScriptCompilationError

class ParseError(Exception):
    # Deprecated, mapped to VBScriptCompilationError internally via wrapper or updated code
    pass


_RESERVED_DIM_NAMES = {
    'AND', 'CALL', 'CASE', 'CLASS', 'CONST', 'DEFAULT', 'DIM', 'DO',
    'EACH', 'ELSE', 'ELSEIF', 'EMPTY', 'END', 'ERASE', 'ERR', 'EXIT',
    'EXPLICIT', 'FALSE', 'FOR', 'FUNCTION', 'GET', 'GOTO', 'IF', 'IN',
    'IS', 'LET', 'LOOP', 'ME', 'MOD', 'NEW', 'NEXT', 'NOT', 'NOTHING',
    'NULL', 'ON', 'OPTION', 'OR', 'PRESERVE', 'PRIVATE', 'PROPERTY',
    'PUBLIC', 'REDIM', 'REM', 'RESUME', 'SELECT', 'SET', 'STEP', 'STOP',
    'SUB', 'THEN', 'TO', 'TRUE', 'UNTIL', 'WHILE', 'WEND', 'WITH', 'XOR',
}


class Parser:
    def __init__(self, text: str):
        self.lexer = Lexer(text)
        self.tok = self.lexer.next_token()
        self._peeked = None
        self._with_counter = 0
        self._with_target_stack = []

    def _raise_c(self, key, extra=None):
        e = VBScriptCompilationError(key, extra)
        # Attach position info directly to the exception instance
        e.vbs_pos = self.tok.pos
        raise e

    def _new_with_name(self) -> str:
        self._with_counter += 1
        return f"__asp_py_with_{self._with_counter}"

    def _current_with_target(self):
        if self._with_target_stack:
            return self._with_target_stack[-1]
        return None

    def _peek(self):
        if self._peeked is None:
            self._peeked = self.lexer.next_token()
        return self._peeked

    def _eat(self, kind: str):
        if self.tok.kind != kind:
            # Map common syntax errors
            if kind == "END":
                self._raise_c('EXPECTED_END')
            if kind == "NEXT":
                self._raise_c('EXPECTED_NEXT')
            if kind == "LOOP":
                self._raise_c('EXPECTED_LOOP')
            if kind == "WEND":
                self._raise_c('EXPECTED_WEND')
            if kind == "THEN":
                self._raise_c('SYNTAX_ERROR', f"Expected 'Then', got {self.tok.kind}")
            if kind == "IDENT":
                self._raise_c('EXPECTED_IDENTIFIER')
            if kind == "EQ":
                self._raise_c('EXPECTED_ASSIGN')
            if kind in ("NEWLINE", "COLON", "EOF"):
                self._raise_c('EXPECTED_EOS')
            
            self._raise_c('SYNTAX_ERROR', f"Expected {kind}, got {self.tok.kind}")
            
        if self._peeked is not None:
            self.tok = self._peeked
            self._peeked = None
        else:
            self.tok = self.lexer.next_token()

    def _require_not_reserved_ident(self, name: str, context: str):
        if name.upper() in _RESERVED_DIM_NAMES:
            self._raise_c('SYNTAX_ERROR', f"Invalid {context} identifier: {name}")

    def _require_eos(self, what: str = "end of statement"):
        # Some declarations must end the statement immediately.
        if self.tok.kind not in ("NEWLINE", "COLON", "EOF"):
            self._raise_c('EXPECTED_EOS', f"Expected {what}")

    def _mark(self):
        return (self.lexer.i, self.tok, self._peeked)

    def _reset(self, mark):
        (i, tok, peeked) = mark
        self.lexer.i = i
        self.tok = tok
        self._peeked = peeked

    def _match_ident(self, expected_upper: str) -> bool:
        # Match either a plain identifier or a keyword token with the same text.
        if self.tok.kind == expected_upper:
            return True
        return self.tok.kind == "IDENT" and self.tok.value.upper() == expected_upper

    def parse(self):
        """Parse a program (one or more statements)."""
        return self.parse_program()

    def parse_program(self):
        try:
            stmts = []
            while True:
                self._skip_seps()
                if self.tok.kind == "EOF":
                    break
                start_pos = self.tok.pos
                stmt = self._parse_stmt(with_target=None)
                try:
                    setattr(stmt, "_pos", start_pos)
                except Exception:
                    pass
                stmts.append(stmt)
        except LexerError as e:
            if "Unterminated string" in str(e):
                self._raise_c('UNTERMINATED_STRING')
            self._raise_c('INVALID_CHARACTER', str(e))
        return stmts

    def _skip_seps(self):
        while self.tok.kind in ("NEWLINE", "COLON"):
            self._eat(self.tok.kind)

    def _skip_newlines(self):
        while self.tok.kind == "NEWLINE":
            self._eat("NEWLINE")

    def parse_expression(self):
        """Parse a single expression (used for ASP shorthand: <%= ... %>)."""
        try:
            expr = self._parse_expr()
        except LexerError as e:
            self._raise_c('INVALID_CHARACTER', str(e))
        if self.tok.kind != "EOF":
            self._raise_c('SYNTAX_ERROR', f"Unexpected token {self.tok.kind}")
        return expr

    def _parse_args(self):
        # Parse arguments for a method call. Supports:
        #   Method(arg1, arg2)
        #   Method arg1, arg2
        args = []
        if self.tok.kind == "LPAREN":
            self._eat("LPAREN")
            self._skip_newlines()
            if self.tok.kind != "RPAREN":
                while True:
                    if self.tok.kind == "COMMA":
                        # Missing argument => Empty
                        args.append(Ident("EMPTY")) # ensure upper
                        self._eat("COMMA")
                        self._skip_newlines()
                        if self.tok.kind == "RPAREN":
                            break
                        continue
                    if self.tok.kind == "RPAREN":
                        break
                    args.append(self._parse_expr())
                    self._skip_newlines()
                    if self.tok.kind == "COMMA":
                        self._eat("COMMA")
                        self._skip_newlines()
                        if self.tok.kind == "RPAREN":
                            args.append(Ident("EMPTY")) # ensure upper
                            break
                        continue
                    break
            self._eat("RPAREN")
            return args

        # Without parentheses: if next token starts an expression, parse it and any comma-separated extras.
        if self.tok.kind in ("STRING", "NUMBER", "IDENT", "DEFAULT"):
            args.append(self._parse_expr())
            while self.tok.kind == "COMMA":
                self._eat("COMMA")
                # Missing argument => Empty (e.g. Call Foo(a,,b))
                if self.tok.kind in ("COMMA", "NEWLINE", "COLON", "EOF"):
                    args.append(Ident("EMPTY")) # ensure upper
                    continue
                args.append(self._parse_expr())
        return args

    def _parse_stmt(self, with_target=None):
        self._skip_seps()

        # Stray END IF (some code uses: If cond Then ... : End If)
        if self.tok.kind == "END" and self._peek().kind == "IF":
            self._eat("END")
            self._eat("IF")
            return EndIfStmt()

        # OPTION EXPLICIT
        if self.tok.kind == "OPTION":
            self._eat("OPTION")
            if self.tok.kind != "EXPLICIT":
                self._raise_c('SYNTAX_ERROR', "Expected EXPLICIT after OPTION")
            self._eat("EXPLICIT")
            return OptionExplicitStmt()

        # ON ERROR RESUME NEXT / ON ERROR GOTO 0
        if self._match_ident("ON"):
            self._eat("IDENT")
            if not self._match_ident("ERROR"):
                self._raise_c('SYNTAX_ERROR', "Expected ERROR after ON")
            self._eat("IDENT")
            if self._match_ident("RESUME"):
                self._eat("IDENT")
                if self.tok.kind != "NEXT":
                    self._raise_c('EXPECTED_NEXT', "Expected NEXT after RESUME")
                self._eat("NEXT")
                return OnErrorResumeNextStmt()
            if self._match_ident("GOTO"):
                self._eat("IDENT")
                # Only support '0' for now
                if self.tok.kind != "NUMBER" or self.tok.value != "0":
                    self._raise_c('SYNTAX_ERROR', "Only 'On Error GoTo 0' is supported")
                self._eat("NUMBER")
                return OnErrorGoto0Stmt()
            self._raise_c('SYNTAX_ERROR', "Expected RESUME or GOTO")

        # RANDOMIZE [seed]
        if self._match_ident("RANDOMIZE") and self._peek().kind != "LPAREN":
            self._eat("IDENT")
            # seed can be omitted
            if self.tok.kind in ("NEWLINE", "COLON", "EOF"):
                return RandomizeStmt(None)
            return RandomizeStmt(self._parse_expr())

        # EXECUTE / EXECUTEGLOBAL
        if self._match_ident("EXECUTE"):
            self._eat("IDENT")
            return ExecuteStmt(self._parse_expr(), is_global=False)
        if self._match_ident("EXECUTEGLOBAL"):
            self._eat("IDENT")
            return ExecuteStmt(self._parse_expr(), is_global=True)

        # CONST a = 1, b = 2
        if self.tok.kind == "CONST":
            self._eat("CONST")
            items = []
            while True:
                if self.tok.kind != "IDENT":
                    self._raise_c('EXPECTED_IDENTIFIER', "Expected identifier after Const")
                name = self.tok.value.upper()
                self._require_not_reserved_ident(name, "Const")
                self._eat("IDENT")
                if self.tok.kind != "EQ":
                    self._raise_c('EXPECTED_ASSIGN', "Expected '=' in Const")
                self._eat("EQ")
                expr = self._parse_expr()
                items.append((name, expr))
                if self.tok.kind == "COMMA":
                    self._eat("COMMA")
                    continue
                break
            return ConstStmt(items)

        # Optional PUBLIC/PRIVATE before SUB/FUNCTION/PROPERTY (top-level)
        if self.tok.kind in ("PUBLIC", "PRIVATE") and self._peek().kind in ("SUB", "FUNCTION", "PROPERTY"):
            vis = self.tok.kind
            self._eat(self.tok.kind)
            if self.tok.kind == "SUB":
                return self._parse_sub_def()
            if self.tok.kind == "FUNCTION":
                return self._parse_func_def()
            if self.tok.kind == "PROPERTY":
                return self._parse_property_def(default_visibility=vis)

        # PUBLIC/PRIVATE variable declarations (top-level)
        if self.tok.kind in ("PUBLIC", "PRIVATE"):
            if self._peek().kind == "DIM":
                self._eat(self.tok.kind)
                return self._parse_dim()
            if self._peek().kind == "IDENT":
                self._eat(self.tok.kind)
                decls = []
                while True:
                    if self.tok.kind != "IDENT":
                        self._raise_c('EXPECTED_IDENTIFIER', "Expected identifier after Public/Private")
                    name = self.tok.value.upper()
                    self._eat("IDENT")
                    bounds = None
                    if self.tok.kind == "LPAREN":
                        self._eat("LPAREN")
                        if self.tok.kind == "RPAREN":
                            self._eat("RPAREN")
                            bounds = []
                        else:
                            bounds = [self._parse_expr()]
                            while self.tok.kind == "COMMA":
                                self._eat("COMMA")
                                bounds.append(self._parse_expr())
                            self._eat("RPAREN")
                    decls.append(DimDecl(name, bounds))
                    if self.tok.kind == "COMMA":
                        self._eat("COMMA")
                        continue
                    break
                return DimStmt(decls)

        # CLASS definitions
        if self.tok.kind == "CLASS":
            return self._parse_class_def()

        # SUB/FUNCTION definitions (top-level procedures)
        if self.tok.kind == "SUB":
            return self._parse_sub_def()
        if self.tok.kind == "FUNCTION":
            return self._parse_func_def()

        # PROPERTY definitions (only meaningful inside classes, but parse anyway)
        if self.tok.kind == "PROPERTY":
            return self._parse_property_def(default_visibility="PUBLIC")

        # CALL statement: Call Foo(arg1, arg2) or Call obj.Method(arg1, arg2)
        if self.tok.kind == "CALL":
            self._eat("CALL")
            if self.tok.kind != "IDENT":
                self._raise_c('EXPECTED_IDENTIFIER', "Expected procedure name after Call")
            name = self.tok.value.upper()
            self._eat("IDENT")
            expr = self._parse_postfix(Ident(name), lvalue=False)
            # If postfix already produced a call, use it directly.
            if isinstance(expr, CallExpr):
                return ExprStmt(expr)
            # Call requires parentheses in VBScript, but allow no-arg call.
            if self.tok.kind == "LPAREN":
                args = self._parse_args()
                return ExprStmt(CallExpr(expr, args))
            # VBScript commonly allows: Call Foo (with no args). Be permissive.
            return ExprStmt(CallExpr(expr, []))

        # SET <lvalue> = <expr>
        if self.tok.kind == "SET":
            self._eat("SET")
            lv = self._parse_lvalue()
            if self.tok.kind != "EQ":
                self._raise_c('EXPECTED_ASSIGN', "Expected '=' after Set target")
            self._eat("EQ")
            rhs = self._parse_expr()
            return SetAssign(lv, rhs)

        # EXIT FOR / EXIT DO / EXIT SELECT / EXIT FUNCTION / EXIT SUB / EXIT PROPERTY
        if self.tok.kind == "EXIT":
            self._eat("EXIT")
            if self.tok.kind == "FOR":
                self._eat("FOR")
                return ExitForStmt()
            if self.tok.kind == "DO":
                self._eat("DO")
                return ExitDoStmt()
            if self.tok.kind == "SELECT":
                self._eat("SELECT")
                return ExitSelectStmt()
            if self.tok.kind == "FUNCTION":
                self._eat("FUNCTION")
                return ExitFunctionStmt()
            if self.tok.kind == "SUB":
                self._eat("SUB")
                return ExitSubStmt()
            if self.tok.kind == "PROPERTY":
                self._eat("PROPERTY")
                return ExitPropertyStmt()
            self._raise_c('SYNTAX_ERROR', "Expected FOR, DO, SELECT, FUNCTION, SUB, or PROPERTY after EXIT")

        # DIM
        if self.tok.kind == "DIM":
            return self._parse_dim()

        # REDIM [PRESERVE] name(bounds)
        if self.tok.kind == "REDIM":
            return self._parse_redim()

        # ERASE name
        if self.tok.kind == "ERASE":
            return self._parse_erase()

        # IF ... THEN ... END IF
        if self.tok.kind == "IF":
            return self._parse_if()

        # SELECT CASE ... END SELECT
        if self.tok.kind == "SELECT":
            return self._parse_select_case()

        # DO WHILE ... LOOP
        if self.tok.kind == "DO":
            return self._parse_do_loop()

        # WHILE ... WEND
        if self.tok.kind == "WHILE":
            return self._parse_while_wend()

        # FOR ... NEXT
        if self.tok.kind == "FOR":
            return self._parse_for()

        # With <expr> ... End With
        if self.tok.kind == "WITH":
            self._eat("WITH")
            target_expr = self._parse_expr()
            target = None
            prefix = []
            if isinstance(target_expr, Ident) and target_expr.name.upper() == "RESPONSE":
                target = "RESPONSE"
            else:
                tmp_name = self._new_with_name()
                target = tmp_name
                prefix = [DimStmt([DimDecl(tmp_name)]), Assign(Ident(tmp_name), target_expr)]

            from .ast_nodes import Block
            body = []
            self._with_target_stack.append(target)
            while True:
                self._skip_seps()
                if self.tok.kind == "END":
                    self._eat("END")
                    if self.tok.kind != "WITH":
                        self._raise_c('SYNTAX_ERROR', "Expected WITH after END")
                    self._eat("WITH")
                    break
                body.append(self._parse_stmt(with_target=target))
            self._with_target_stack.pop()
            return Block(prefix + body)

        # Dot form inside With: .Write/.End/.Clear/.Flush/.Buffer = ...
        if with_target is not None and self.tok.kind == "DOT":
            # Currently only valid for With Response
            if str(with_target).upper() != "RESPONSE":
                mark = self._mark()
                base = Ident(with_target)
                try:
                    lv = self._parse_postfix(base, lvalue=True)
                    if self.tok.kind == "EQ":
                        self._eat("EQ")
                        rhs = self._parse_expr()
                        return Assign(lv, rhs)
                except Exception:
                    pass
                self._reset(mark)
                expr = self._parse_postfix(base, lvalue=False)

                if self.tok.kind in ("STRING", "NUMBER", "IDENT", "LPAREN"):
                    args = [self._parse_expr()]
                    while self.tok.kind == "COMMA":
                        self._eat("COMMA")
                        args.append(self._parse_expr())
                    expr = CallExpr(expr, args)

                return ExprStmt(expr)
            self._eat("DOT")
            if self.tok.kind in ("EOF", "NEWLINE", "COLON"):
                self._raise_c('EXPECTED_IDENTIFIER', "Expected member name after '.'")
            member = self.tok.value.upper()
            self._eat(self.tok.kind)

            if member == "WRITE":
                if self.tok.kind == "LPAREN":
                    mark = self._mark()
                    self._eat("LPAREN")
                    if self.tok.kind == "RPAREN":
                        self._eat("RPAREN")
                        expr = StringLit("")
                    else:
                        self._reset(mark)
                        expr = self._parse_expr()
                else:
                    expr = self._parse_expr()
                return ResponseWrite(expr)

            if member == "END":
                if self.tok.kind == "LPAREN":
                    self._eat("LPAREN")
                    self._eat("RPAREN")
                return ResponseEnd()
            if member == "CLEAR":
                if self.tok.kind == "LPAREN":
                    self._eat("LPAREN")
                    self._eat("RPAREN")
                return ResponseClear()
            if member == "FLUSH":
                if self.tok.kind == "LPAREN":
                    self._eat("LPAREN")
                    self._eat("RPAREN")
                return ResponseFlush()

            if member == "COOKIES":
                mark = self._mark()
                if self.tok.kind == "LPAREN":
                    self._eat("LPAREN")
                    cookie_name_expr = self._parse_expr()
                    self._eat("RPAREN")
                    if self.tok.kind == "LPAREN":
                        self._eat("LPAREN")
                        subkey_expr = self._parse_expr()
                        self._eat("RPAREN")
                        if self.tok.kind == "EQ":
                            self._eat("EQ")
                            value_expr = self._parse_expr()
                            return ResponseCookiesSet(cookie_name_expr, value_expr, subkey_expr=subkey_expr)
                    if self.tok.kind == "EQ":
                        self._eat("EQ")
                        value_expr = self._parse_expr()
                        return ResponseCookiesSet(cookie_name_expr, value_expr)

                    if self.tok.kind == "DOT":
                        self._eat("DOT")
                        if self.tok.kind in ("EOF", "NEWLINE", "COLON"):
                            self._raise_c('EXPECTED_IDENTIFIER', "Expected cookie property name")
                        prop = self.tok.value
                        self._eat(self.tok.kind)
                        target = Member(Index(Member(Ident("RESPONSE"), "Cookies"), [cookie_name_expr]), prop)
                        if self.tok.kind != "EQ":
                            self._raise_c('EXPECTED_ASSIGN', "Expected '=' after cookie property")
                        self._eat("EQ")
                        rhs = self._parse_expr()
                        return Assign(target, rhs)

                if self.tok.kind == "DOT":
                    self._eat("DOT")
                    if self.tok.kind in ("EOF", "NEWLINE", "COLON"):
                        self._raise_c('EXPECTED_IDENTIFIER', "Expected cookie member name")
                    member_name = self.tok.value
                    self._eat(self.tok.kind)
                    if str(member_name).upper() == "ITEM":
                        if self.tok.kind != "LPAREN":
                            self._raise_c('SYNTAX_ERROR', "Expected '(' after Cookies.Item")
                        self._eat("LPAREN")
                        cookie_name_expr = self._parse_expr()
                        self._eat("RPAREN")
                        if self.tok.kind == "LPAREN":
                            self._eat("LPAREN")
                            subkey_expr = self._parse_expr()
                            self._eat("RPAREN")
                            if self.tok.kind == "EQ":
                                self._eat("EQ")
                                value_expr = self._parse_expr()
                                return ResponseCookiesSet(cookie_name_expr, value_expr, subkey_expr=subkey_expr)
                        if self.tok.kind == "EQ":
                            self._eat("EQ")
                            value_expr = self._parse_expr()
                            return ResponseCookiesSet(cookie_name_expr, value_expr)
                        if self.tok.kind == "DOT":
                            self._eat("DOT")
                            if self.tok.kind in ("EOF", "NEWLINE", "COLON"):
                                self._raise_c('EXPECTED_IDENTIFIER', "Expected cookie property name")
                            prop = self.tok.value
                            self._eat(self.tok.kind)
                            target = Member(Index(Member(Ident("RESPONSE"), "Cookies"), [cookie_name_expr]), prop)
                            if self.tok.kind != "EQ":
                                self._raise_c('EXPECTED_ASSIGN', "Expected '=' after cookie property")
                            self._eat("EQ")
                            rhs = self._parse_expr()
                            return Assign(target, rhs)
                self._reset(mark)
                return self._parse_generic_stmt()

            # Property assignment
            if self.tok.kind == "EQ":
                self._eat("EQ")
                expr = self._parse_expr()
                return ResponseSetProperty(member, expr)

            # Method call
            args = self._parse_args()
            return ResponseCall(member, args)

            self._raise_c('SYNTAX_ERROR', "Unsupported Response member inside With")

        # Response.<member>
        if not self._match_ident("RESPONSE"):
            return self._parse_generic_stmt()
        self._eat("IDENT")
        self._eat("DOT")

        if self.tok.kind in ("EOF", "NEWLINE", "COLON"):
            self._raise_c('EXPECTED_IDENTIFIER', "Expected Response member name")
        member = self.tok.value.upper()
        self._eat(self.tok.kind)

        if member == "WRITE":
            if self.tok.kind == "LPAREN":
                mark = self._mark()
                self._eat("LPAREN")
                if self.tok.kind == "RPAREN":
                    self._eat("RPAREN")
                    expr = StringLit("")
                else:
                    self._reset(mark)
                    expr = self._parse_expr()
            else:
                expr = self._parse_expr()
            if self.tok.kind not in ("NEWLINE", "COLON", "EOF", "ELSE", "END"):
                self._raise_c('EXPECTED_EOS', "Expected operator between expressions")
            return ResponseWrite(expr)

        if member == "END":
            if self.tok.kind == "LPAREN":
                self._eat("LPAREN")
                self._eat("RPAREN")
            return ResponseEnd()
        if member == "CLEAR":
            if self.tok.kind == "LPAREN":
                self._eat("LPAREN")
                self._eat("RPAREN")
            return ResponseClear()
        if member == "FLUSH":
            if self.tok.kind == "LPAREN":
                self._eat("LPAREN")
                self._eat("RPAREN")
            return ResponseFlush()

        if member == "COOKIES":
            mark = self._mark()
            if self.tok.kind == "LPAREN":
                self._eat("LPAREN")
                cookie_name_expr = self._parse_expr()
                self._eat("RPAREN")
                if self.tok.kind == "LPAREN":
                    self._eat("LPAREN")
                    subkey_expr = self._parse_expr()
                    self._eat("RPAREN")
                    if self.tok.kind == "EQ":
                        self._eat("EQ")
                        value_expr = self._parse_expr()
                        return ResponseCookiesSet(cookie_name_expr, value_expr, subkey_expr=subkey_expr)
                if self.tok.kind == "EQ":
                    self._eat("EQ")
                    value_expr = self._parse_expr()
                    return ResponseCookiesSet(cookie_name_expr, value_expr)

                if self.tok.kind == "DOT":
                    self._eat("DOT")
                    if self.tok.kind in ("EOF", "NEWLINE", "COLON"):
                        self._raise_c('EXPECTED_IDENTIFIER', "Expected cookie property name")
                    prop = self.tok.value
                    self._eat(self.tok.kind)
                    target = Member(Index(Member(Ident("RESPONSE"), "Cookies"), [cookie_name_expr]), prop)
                    if self.tok.kind != "EQ":
                        self._raise_c('EXPECTED_ASSIGN', "Expected '=' after cookie property")
                    self._eat("EQ")
                    rhs = self._parse_expr()
                    return Assign(target, rhs)

            if self.tok.kind == "DOT":
                self._eat("DOT")
                if self.tok.kind in ("EOF", "NEWLINE", "COLON"):
                    self._raise_c('EXPECTED_IDENTIFIER', "Expected cookie member name")
                member_name = self.tok.value
                self._eat(self.tok.kind)
                if str(member_name).upper() == "ITEM":
                    if self.tok.kind != "LPAREN":
                        self._raise_c('SYNTAX_ERROR', "Expected '(' after Cookies.Item")
                    self._eat("LPAREN")
                    cookie_name_expr = self._parse_expr()
                    self._eat("RPAREN")
                    if self.tok.kind == "LPAREN":
                        self._eat("LPAREN")
                        subkey_expr = self._parse_expr()
                        self._eat("RPAREN")
                        if self.tok.kind == "EQ":
                            self._eat("EQ")
                            value_expr = self._parse_expr()
                            return ResponseCookiesSet(cookie_name_expr, value_expr, subkey_expr=subkey_expr)
                    if self.tok.kind == "EQ":
                        self._eat("EQ")
                        value_expr = self._parse_expr()
                        return ResponseCookiesSet(cookie_name_expr, value_expr)
                    if self.tok.kind == "DOT":
                        self._eat("DOT")
                        if self.tok.kind in ("EOF", "NEWLINE", "COLON"):
                            self._raise_c('EXPECTED_IDENTIFIER', "Expected cookie property name")
                        prop = self.tok.value
                        self._eat(self.tok.kind)
                        target = Member(Index(Member(Ident("RESPONSE"), "Cookies"), [cookie_name_expr]), prop)
                        if self.tok.kind != "EQ":
                            self._raise_c('EXPECTED_ASSIGN', "Expected '=' after cookie property")
                        self._eat("EQ")
                        rhs = self._parse_expr()
                        return Assign(target, rhs)
            self._reset(mark)
            return self._parse_generic_stmt()

        # Property assignment
        if self.tok.kind == "EQ":
            self._eat("EQ")
            expr = self._parse_expr()
            return ResponseSetProperty(member, expr)

        # Method call
        args = self._parse_args()
        return ResponseCall(member, args)

        # (unreachable)


    def _parse_generic_stmt(self):

        # VBScript uses '=' for both assignment and comparison. At statement level,
        # "<lvalue> = <expr>" is always assignment.
        mark = self._mark()
        try:
            lv = self._parse_lvalue()
            if self.tok.kind == "EQ":
                self._eat("EQ")
                rhs = self._parse_expr()
                return Assign(lv, rhs)
        except (ParseError, VBScriptCompilationError):
            pass
        self._reset(mark)
        expr = self._parse_expr()

        # Support VBScript call syntax without parentheses:
        #   obj.Method arg1, arg2
        # Only if the callee is a simple identifier/member/index and the next
        # token begins an expression on the same statement.
        if self.tok.kind in ("STRING", "NUMBER", "IDENT", "DEFAULT", "LPAREN"):
            if isinstance(expr, (Ident, Member, Index)):
                args = [self._parse_expr()]
                while self.tok.kind == "COMMA":
                    self._eat("COMMA")
                    # Missing argument => Empty
                    if self.tok.kind in ("COMMA", "NEWLINE", "COLON", "EOF"):
                        args.append(Ident("EMPTY")) # ensure upper
                        continue
                    args.append(self._parse_expr())
                expr = CallExpr(expr, args)
            else:
                raise ParseError("Expected operator between expressions")

        # After parsing a statement expression, require statement terminator.
        if self.tok.kind not in ("NEWLINE", "COLON", "EOF", "ELSE", "END"):
            raise ParseError("Expected operator between expressions")
        return ExprStmt(expr)

    def _parse_lvalue(self):
        # lvalue: Ident (postfix member/index)
        if self.tok.kind not in ("IDENT", "DEFAULT"):
            self._raise_c('EXPECTED_IDENTIFIER')
        name = self.tok.value.upper()
        self._eat(self.tok.kind)
        expr = Ident(name)
        expr = self._parse_postfix(expr, lvalue=True)
        if isinstance(expr, (Ident, Member, Index)):
            return expr
        self._raise_c('SYNTAX_ERROR', "Invalid assignment target")

    def _parse_if(self):
        # IF <expr> THEN <block> [ELSEIF <expr> THEN <block>]* [ELSE <block>] END IF
        self._eat("IF")
        cond = self._parse_expr()
        if self.tok.kind != "THEN":
            raise ParseError(f"Expected THEN at position {self.tok.pos}")
        self._eat("THEN")

        # Single-line THEN: IF cond THEN stmt [: stmt ...] [ELSE stmt [: stmt ...]]
        if self.tok.kind not in ("NEWLINE", "COLON", "EOF"):
            then_block = []
            then_pos = self.tok.pos
            then_stmt = self._parse_stmt(with_target=None)
            try:
                setattr(then_stmt, "_pos", then_pos)
            except Exception:
                pass
            then_block.append(then_stmt)

            while self.tok.kind == "COLON":
                self._eat("COLON")
                if self.tok.kind in ("NEWLINE", "EOF", "ELSE"):
                    break
                stmt_pos = self.tok.pos
                stmt = self._parse_stmt(with_target=None)
                try:
                    setattr(stmt, "_pos", stmt_pos)
                except Exception:
                    pass
                then_block.append(stmt)

            else_block = None
            if self.tok.kind == "ELSE":
                self._eat("ELSE")
                else_block = []
                if self.tok.kind not in ("NEWLINE", "COLON", "EOF"):
                    else_pos = self.tok.pos
                    else_stmt = self._parse_stmt(with_target=None)
                    try:
                        setattr(else_stmt, "_pos", else_pos)
                    except Exception:
                        pass
                    else_block.append(else_stmt)
                while self.tok.kind == "COLON":
                    self._eat("COLON")
                    if self.tok.kind in ("NEWLINE", "EOF"):
                        break
                    stmt_pos = self.tok.pos
                    stmt = self._parse_stmt(with_target=None)
                    try:
                        setattr(stmt, "_pos", stmt_pos)
                    except Exception:
                        pass
                    else_block.append(stmt)
                if else_block == []:
                    else_block = None

            # Allow single-line IF ... THEN ... END IF on same line
            if self.tok.kind == "END":
                self._eat("END")
                if self.tok.kind == "IF":
                    self._eat("IF")
                if self.tok.kind not in ("NEWLINE", "COLON", "EOF", "ELSE", "END"):
                    raise ParseError("Expected operator between expressions")
            return IfStmt(cond, then_block, [], else_block)

        self._skip_seps()
        then_block = self._parse_block_until({"ELSE", "ELSEIF", "END"})

        elseif_parts = []
        while self.tok.kind == "ELSEIF":
            self._eat("ELSEIF")
            ec = self._parse_expr()
            if self.tok.kind != "THEN":
                raise ParseError(f"Expected THEN at position {self.tok.pos}")
            self._eat("THEN")
            self._skip_seps()
            eb = self._parse_block_until({"ELSE", "ELSEIF", "END"})
            elseif_parts.append((ec, eb))

        else_block = None
        if self.tok.kind == "ELSE":
            self._eat("ELSE")
            self._skip_seps()
            else_block = self._parse_block_until({"END"})

        # END IF
        if self.tok.kind != "END":
            raise ParseError("Expected END IF")
        self._eat("END")
        if self.tok.kind != "IF":
            raise ParseError("Expected IF after END")
        self._eat("IF")
        return IfStmt(cond, then_block, elseif_parts, else_block)

    def _parse_select_case(self):
        # SELECT CASE <expr> NEWLINE { CASE ... } END SELECT
        self._eat("SELECT")
        if self.tok.kind != "CASE":
            raise ParseError("Expected CASE after SELECT")
        self._eat("CASE")
        expr = self._parse_expr()
        self._skip_seps()

        cases = []
        else_block = None
        while self.tok.kind == "CASE":
            self._eat("CASE")
            if self.tok.kind == "ELSE":
                self._eat("ELSE")
                self._skip_seps()
                else_block = self._parse_block_until({"END", "CASE"})
                continue

            patterns = [self._parse_expr()]
            while self.tok.kind == "COMMA":
                self._eat("COMMA")
                patterns.append(self._parse_expr())
            self._skip_seps()
            body = self._parse_block_until({"CASE", "END"})
            cases.append(CaseClause(patterns, body))

        if self.tok.kind != "END":
            raise ParseError("Expected END SELECT")
        self._eat("END")
        if self.tok.kind != "SELECT":
            raise ParseError("Expected SELECT after END")
        self._eat("SELECT")
        return SelectCaseStmt(expr, cases, else_block)

    def _parse_do_loop(self):
        # DO [WHILE|UNTIL <expr>] ... LOOP [WHILE|UNTIL <expr>]
        self._eat("DO")
        pre_kind = None
        if self.tok.kind in ("WHILE", "UNTIL") or self._match_ident("UNTIL"):
            pre_kind = self.tok.kind if self.tok.kind in ("WHILE", "UNTIL") else "UNTIL"
            self._eat(self.tok.kind)
            cond = self._parse_expr()
            self._skip_seps()
            body = self._parse_block_until({"LOOP"})
            if self.tok.kind != "LOOP":
                raise ParseError("Expected LOOP")
            self._eat("LOOP")
            return DoLoopStmt(cond, is_until=(pre_kind == "UNTIL"), post_test=False, body=body)

        self._skip_seps()
        body = self._parse_block_until({"LOOP"})
        if self.tok.kind != "LOOP":
            raise ParseError("Expected LOOP")
        self._eat("LOOP")
        if self.tok.kind in ("WHILE", "UNTIL") or self._match_ident("UNTIL"):
            post_kind = self.tok.kind if self.tok.kind in ("WHILE", "UNTIL") else "UNTIL"
            self._eat(self.tok.kind)
            cond = self._parse_expr()
            return DoLoopStmt(cond, is_until=(post_kind == "UNTIL"), post_test=True, body=body)
        return DoLoopStmt(None, is_until=False, post_test=True, body=body)

    def _parse_while_wend(self):
        # WHILE <expr> ... WEND
        self._eat("WHILE")
        cond = self._parse_expr()
        self._skip_seps()
        body = self._parse_block_until({"WEND"})
        if self.tok.kind != "WEND":
            raise ParseError("Expected WEND")
        self._eat("WEND")
        return WhileStmt(cond, body)

    def _parse_for(self):
        # FOR EACH x IN expr ... NEXT
        # FOR x = start TO end [STEP step] ... NEXT
        self._eat("FOR")
        if self.tok.kind == "EACH":
            self._eat("EACH")
            if self.tok.kind != "IDENT":
                raise ParseError("Expected loop variable")
            var = self.tok.value.upper()
            self._eat("IDENT")
            if self.tok.kind != "IN":
                raise ParseError("Expected IN")
            self._eat("IN")
            iterable = self._parse_expr()
            self._skip_seps()
            body = self._parse_block_until({"NEXT"})
            if self.tok.kind != "NEXT":
                raise ParseError("Expected NEXT")
            self._eat("NEXT")
            return ForEachStmt(var, iterable, body)

        if self.tok.kind != "IDENT":
            raise ParseError("Expected loop variable")
        var = self.tok.value.upper()
        self._eat("IDENT")
        if self.tok.kind != "EQ":
            raise ParseError("Expected '=' in FOR")
        self._eat("EQ")
        start = self._parse_expr()
        if self.tok.kind != "TO":
            raise ParseError("Expected TO")
        self._eat("TO")
        end = self._parse_expr()
        step = NumberLit(1)
        if self.tok.kind == "STEP":
            self._eat("STEP")
            step = self._parse_expr()
        self._skip_seps()
        body = self._parse_block_until({"NEXT"})
        if self.tok.kind != "NEXT":
            raise ParseError("Expected NEXT")
        self._eat("NEXT")
        return ForStmt(var, start, end, step, body)

    def _parse_block_until(self, end_kinds: set):
        stmts = []
        while True:
            self._skip_seps()
            if self.tok.kind == "EOF":
                break
            if self.tok.kind in end_kinds:
                break
            # END <something>
            if self.tok.kind == "END" and "END" in end_kinds:
                break
            start_pos = self.tok.pos
            stmt = self._parse_stmt(with_target=None)
            try:
                setattr(stmt, "_pos", start_pos)
            except Exception:
                pass
            stmts.append(stmt)
        return stmts

    def _parse_dim(self):
        # DIM a, b(2)
        self._eat("DIM")
        decls = []
        while True:
            if self.tok.kind != "IDENT":
                raise ParseError("Expected identifier after Dim")
            name = self.tok.value.upper()
            self._require_not_reserved_ident(name, "Dim")
            self._eat("IDENT")
            bounds = None
            if self.tok.kind == "LPAREN":
                self._eat("LPAREN")
                # Dim a() => dynamic array
                if self.tok.kind == "RPAREN":
                    self._eat("RPAREN")
                    bounds = []
                else:
                    bounds = [self._parse_expr()]
                    while self.tok.kind == "COMMA":
                        self._eat("COMMA")
                        bounds.append(self._parse_expr())
                    self._eat("RPAREN")
            decls.append(DimDecl(name, bounds))
            if self.tok.kind == "COMMA":
                self._eat("COMMA")
                continue
            break
        return DimStmt(decls)

    def _parse_redim(self):
        self._eat("REDIM")
        preserve = False
        if self.tok.kind == "PRESERVE":
            self._eat("PRESERVE")
            preserve = True
        if self.tok.kind != "IDENT":
            raise ParseError("Expected identifier after ReDim")
        name = self.tok.value.upper()
        self._eat("IDENT")
        if self.tok.kind != "LPAREN":
            raise ParseError("Expected '(' in ReDim")
        self._eat("LPAREN")
        bounds = []
        if self.tok.kind != "RPAREN":
            bounds.append(self._parse_expr())
            while self.tok.kind == "COMMA":
                self._eat("COMMA")
                bounds.append(self._parse_expr())
        self._eat("RPAREN")
        if not bounds:
            raise ParseError("ReDim requires at least one dimension")
        return ReDimStmt(name, bounds, preserve=preserve)

    def _parse_erase(self):
        self._eat("ERASE")
        if self.tok.kind != "IDENT":
            raise ParseError("Expected identifier after Erase")
        name = self.tok.value.upper()
        self._eat("IDENT")
        return EraseStmt(name)

    def _parse_expr(self):
        return self._parse_imp()

    def _parse_imp(self):
        left = self._parse_eqv()
        while self.tok.kind == "IDENT" and self.tok.value.upper() == "IMP":
            self._eat("IDENT")
            right = self._parse_eqv()
            left = BinaryOp("IMP", left, right)
        return left

    def _parse_eqv(self):
        left = self._parse_xor()
        while self.tok.kind == "IDENT" and self.tok.value.upper() == "EQV":
            self._eat("IDENT")
            right = self._parse_xor()
            left = BinaryOp("EQV", left, right)
        return left

    def _parse_xor(self):
        left = self._parse_or()
        while self.tok.kind == "IDENT" and self.tok.value.upper() == "XOR":
            self._eat("IDENT")
            right = self._parse_or()
            left = BinaryOp("XOR", left, right)
        return left

    def _parse_or(self):
        left = self._parse_and()
        while self.tok.kind == "IDENT" and self.tok.value.upper() == "OR":
            self._eat("IDENT")
            right = self._parse_and()
            left = BinaryOp("OR", left, right)
        return left

    def _parse_and(self):
        left = self._parse_compare()
        while self.tok.kind == "IDENT" and self.tok.value.upper() == "AND":
            self._eat("IDENT")
            right = self._parse_compare()
            left = BinaryOp("AND", left, right)
        return left

    def _parse_compare(self):
        left = self._parse_concat()
        while True:
            # Object identity comparison: a Is b / a Is Not b
            if self._match_ident("IS"):
                self._eat(self.tok.kind)
                op = "IS"
                if self._match_ident("NOT"):
                    self._eat(self.tok.kind)
                    op = "IS NOT"
                right = self._parse_concat()
                left = BinaryOp(op, left, right)
                continue

            if self.tok.kind in ("EQ", "NE", "LT", "LE", "GT", "GE"):
                op_map = {
                    "EQ": "=",
                    "NE": "<>",
                    "LT": "<",
                    "LE": "<=",
                    "GT": ">",
                    "GE": ">=",
                }
                op = op_map[self.tok.kind]
                self._eat(self.tok.kind)
                right = self._parse_concat()
                left = BinaryOp(op, left, right)
                continue
            break
        return left

    def _parse_concat(self):
        # VBScript operator precedence: '&' has LOWER precedence than '+' and '-'.
        # Example: "a" & 1 + 1 & "b"  =>  "a" & (1+1) & "b".
        left = self._parse_add()
        while self.tok.kind == "AMP":
            self._eat("AMP")
            right = self._parse_add()
            left = Concat(left, '&', right)
        return left

    def _parse_add(self):
        left = self._parse_mul()
        while self.tok.kind in ("PLUS", "MINUS"):
            if self.tok.kind == "PLUS":
                self._eat("PLUS")
                right = self._parse_mul()
                left = Concat(left, '+', right)
                continue
            self._eat("MINUS")
            right = self._parse_mul()
            left = BinaryOp("-", left, right)
        return left

    def _parse_mul(self):
        left = self._parse_unary()
        while self.tok.kind in ("STAR", "SLASH", "BSLASH") or (self.tok.kind == "IDENT" and self.tok.value.upper() == "MOD"):
            if self.tok.kind == "STAR":
                self._eat("STAR")
                right = self._parse_unary()
                left = BinaryOp("*", left, right)
                continue
            if self.tok.kind == "IDENT" and self.tok.value.upper() == "MOD":
                self._eat("IDENT")
                right = self._parse_unary()
                left = BinaryOp("MOD", left, right)
                continue
            if self.tok.kind == "SLASH":
                self._eat("SLASH")
                right = self._parse_unary()
                left = BinaryOp("/", left, right)
                continue
            self._eat("BSLASH")
            right = self._parse_unary()
            left = BinaryOp("\\", left, right)
        return left

    def _parse_unary(self):
        if self.tok.kind == "MINUS":
            self._eat("MINUS")
            return UnaryOp("-", self._parse_unary())
        if self.tok.kind == "IDENT" and self.tok.value.upper() == "NOT":
            self._eat("IDENT")
            return UnaryOp("NOT", self._parse_unary())
        return self._parse_pow()

    def _parse_pow(self):
        left = self._parse_term()
        if self.tok.kind == "CARET":
            self._eat("CARET")
            right = self._parse_pow()
            return BinaryOp("^", left, right)
        return left

    def _parse_term(self):
        # primary
        if self.tok.kind == "DOT":
            with_target = self._current_with_target()
            if with_target is None:
                raise ParseError(f"Expected expression at position {self.tok.pos}")
            base = Ident(with_target)
            return self._parse_postfix(base)
        if self.tok.kind == "STRING":
            val = self.tok.value
            self._eat("STRING")
            expr = StringLit(val)
            return self._parse_postfix(expr)

        if self.tok.kind == "NUMBER":
            val_s = self.tok.value
            val = float(val_s) if '.' in val_s else int(val_s)
            self._eat("NUMBER")
            expr = NumberLit(val)
            return self._parse_postfix(expr)

        if self.tok.kind == "DATE":
            val = self.tok.value
            self._eat("DATE")
            expr = DateLit(val)
            return self._parse_postfix(expr)

        if self.tok.kind in ("IDENT", "DEFAULT"):
            name = self.tok.value.upper()
            upper = name # already upper
            self._eat(self.tok.kind)
            if upper == "TRUE":
                expr = BoolLit(True)
            elif upper == "FALSE":
                expr = BoolLit(False)
            else:
                # Support common no-parentheses functions:
                # - Date/time: Now, Date, Time, Timer
                # - Random: Rnd
                # Only when not immediately followed by parentheses (to avoid double-call on Now()).
                if upper in ("NOW", "DATE", "TIME", "TIMER", "RND") and self.tok.kind != "LPAREN":
                    expr = CallExpr(Ident(name), [])
                else:
                    expr = Ident(name)
            return self._parse_postfix(expr)

        if self.tok.kind == "ME":
            self._eat("ME")
            return self._parse_postfix(Ident("ME"))

        if self.tok.kind == "NEW":
            self._eat("NEW")
            if self.tok.kind != "IDENT":
                raise ParseError("Expected class name after New")
            nm = self.tok.value
            self._eat("IDENT")
            return self._parse_postfix(NewExpr(nm))

        if self.tok.kind == "LPAREN":
            self._eat("LPAREN")
            self._skip_newlines()
            expr = self._parse_expr()
            self._skip_newlines()
            self._eat("RPAREN")
            return self._parse_postfix(expr)

        raise ParseError(f"Expected expression at position {self.tok.pos}")

    def _parse_postfix(self, expr, lvalue: bool = False):
        # postfix: .ident and (args)
        while True:
            if self.tok.kind == "DOT":
                self._eat("DOT")
                if self.tok.kind in ("EOF", "NEWLINE", "COLON"):
                    raise ParseError("Expected identifier after '.'")
                # Allow keywords as member names (e.g. obj.To)
                if self.tok.kind == "IDENT":
                    name = self.tok.value.upper()
                    self._eat("IDENT")
                else:
                    if not (self.tok.value and str(self.tok.value)[0].isalpha()):
                        raise ParseError("Expected identifier after '.'")
                    name = self.tok.value.upper()
                    self._eat(self.tok.kind)
                expr = Member(expr, name)
                continue

            if self.tok.kind == "LPAREN":
                if lvalue:
                    # Allow indexing as an lvalue (arrays, collections, default members).
                    pass
                # Parse args
                self._eat("LPAREN")
                self._skip_newlines()
                args = []
                if self.tok.kind != "RPAREN":
                    if self.tok.kind == "COMMA":
                        args.append(None)
                    else:
                        args.append(self._parse_expr())
                    while self.tok.kind == "COMMA":
                        self._eat("COMMA")
                        self._skip_newlines()
                        if self.tok.kind == "RPAREN":
                            args.append(None)
                            break
                        elif self.tok.kind == "COMMA":
                            args.append(None)
                        else:
                            args.append(self._parse_expr())
                    self._skip_newlines()
                self._eat("RPAREN")

                # Heuristic:
                # - Session/Request/Application default member is indexable: Session("k")
                # - Some collection-like properties are indexable: Request.QueryString("k")
                # - Otherwise, treat as a call: obj.Method(args)
                if lvalue:
                    expr = Index(expr, args)
                else:
                    # Heuristic:
                    # - Session/Request/Application default member is indexable: Session("k")
                    # - Some collection-like properties are indexable: Request.QueryString("k")
                    # - Otherwise, treat as a call: obj.Method(args)
                    if isinstance(expr, Ident) and expr.name.upper() in ("SESSION", "REQUEST", "APPLICATION"):
                        expr = Index(expr, args)
                    elif isinstance(expr, Member):
                        member_up = expr.name.upper()
                        base = expr.obj
                        if isinstance(base, Ident):
                            base_up = base.name.upper()
                            if base_up == "REQUEST" and member_up in ("QUERYSTRING", "FORM", "COOKIES", "SERVERVARIABLES"):
                                expr = Index(expr, args)
                            elif base_up in ("SESSION", "APPLICATION") and member_up == "CONTENTS":
                                expr = Index(expr, args)
                            else:
                                expr = CallExpr(expr, args)
                        else:
                            expr = CallExpr(expr, args)
                    elif isinstance(expr, Index):
                        # Nested indexing: Request.Cookies(x)(y)
                        expr = Index(expr, args)
                    else:
                        expr = CallExpr(expr, args)
                continue

            break

        return expr


    def _parse_param_list(self):
        params = []
        if self.tok.kind != "LPAREN":
            return params
        self._eat("LPAREN")
        if self.tok.kind == "RPAREN":
            self._eat("RPAREN")
            return params

        while True:
            byval = False
            if self.tok.kind == "BYVAL":
                self._eat("BYVAL")
                byval = True
            elif self.tok.kind == "BYREF":
                self._eat("BYREF")
                byval = False

            if self.tok.kind != "IDENT":
                raise ParseError("Expected parameter name")
            nm = self.tok.value.upper()
            self._eat("IDENT")
            params.append(ParamDecl(nm, byval=byval))
            if self.tok.kind == "COMMA":
                self._eat("COMMA")
                continue
            break
        self._eat("RPAREN")
        return params


    def _parse_proc_body_until_end(self, end_kind: str):
        body = []
        while True:
            self._skip_seps()
            if self.tok.kind == "EOF":
                raise ParseError(f"Expected END {end_kind}")
            if self.tok.kind == "END" and self._peek().kind == end_kind:
                break
            start_pos = self.tok.pos
            stmt = self._parse_stmt(with_target=None)
            try:
                setattr(stmt, "_pos", start_pos)
            except Exception:
                pass
            body.append(stmt)
        self._eat("END")
        self._eat(end_kind)
        return body


    def _parse_property_def(self, default_visibility: str = "PUBLIC"):
        # PROPERTY GET/LET/SET Name(params) ... END PROPERTY
        self._eat("PROPERTY")
        if self.tok.kind not in ("GET", "LET", "SET"):
            raise ParseError("Expected GET, LET, or SET after Property")
        kind = self.tok.kind
        self._eat(self.tok.kind)
        if self.tok.kind == "IDENT":
            name = self.tok.value.upper()
            self._eat("IDENT")
        elif self.tok.kind == "DEFAULT":
            name = "DEFAULT"
            self._eat("DEFAULT")
        else:
            raise ParseError("Expected property name")
        params = self._parse_param_list()
        self._require_eos("end of Property statement")
        body = self._parse_proc_body_until_end("PROPERTY")
        return PropertyDef(kind, name, params, body, visibility=default_visibility)


    def _parse_class_def(self):
        # CLASS Name ... END CLASS
        self._eat("CLASS")
        if self.tok.kind != "IDENT":
            raise ParseError("Expected Class name")
        original_name = self.tok.value
        name = self.tok.value.upper()
        self._require_not_reserved_ident(name, "Class")
        self._eat("IDENT")
        self._require_eos("end of Class statement")
        members = []
        while True:
            self._skip_seps()
            if self.tok.kind == "EOF":
                raise ParseError("Expected END CLASS")
            if self.tok.kind == "END" and self._peek().kind == "CLASS":
                break

            visibility = "PUBLIC"
            is_default = False
            while True:
                if self.tok.kind in ("PUBLIC", "PRIVATE"):
                    visibility = self.tok.kind
                    self._eat(self.tok.kind)
                    self._skip_seps()
                    continue
                if self.tok.kind == "DEFAULT":
                    self._eat("DEFAULT")
                    self._skip_seps()
                    is_default = True
                    continue
                break

            # Variable declaration: Private x, y(30), z()
            if self.tok.kind == "IDENT":
                while True:
                    if self.tok.kind != "IDENT":
                        raise ParseError("Expected identifier")
                    nm = self.tok.value.upper()
                    self._eat("IDENT")
                    # Optional bounds like x(30)
                    bounds = None
                    if self.tok.kind == "LPAREN":
                        self._eat("LPAREN")
                        # x() => dynamic array
                        if self.tok.kind == "RPAREN":
                            bounds = []
                        else:
                            bounds = [self._parse_expr()]
                            while self.tok.kind == "COMMA":
                                self._eat("COMMA")
                                bounds.append(self._parse_expr())
                        self._eat("RPAREN")
                    members.append(ClassVarDecl(nm, visibility=visibility, bounds=bounds))
                    if self.tok.kind == "COMMA":
                        self._eat("COMMA")
                        continue
                    break
                continue

            if self.tok.kind == "DIM":
                dim = self._parse_dim()
                for d in dim.decls:
                    members.append(ClassVarDecl(d.name, visibility=visibility))
                continue

            if self.tok.kind == "SUB":
                sub = self._parse_sub_def()
                sub.visibility = visibility  # attach dynamically
                sub.is_default = bool(is_default)
                members.append(sub)
                continue

            if self.tok.kind == "FUNCTION":
                fn = self._parse_func_def()
                fn.visibility = visibility
                fn.is_default = bool(is_default)
                members.append(fn)
                continue

            if self.tok.kind == "PROPERTY":
                p = self._parse_property_def(default_visibility=visibility)
                p.is_default = bool(is_default)
                members.append(p)
                continue

            raise ParseError("Unsupported statement in Class block")

        self._eat("END")
        self._eat("CLASS")
        return ClassDef(name, members, original_name=original_name)


    def _parse_sub_def(self):
        self._eat("SUB")
        if self.tok.kind != "IDENT":
            raise ParseError("Expected Sub name")
        name = self.tok.value.upper()
        self._require_not_reserved_ident(name, "Sub")
        self._eat("IDENT")
        params = self._parse_param_list()
        self._require_eos("end of Sub statement")
        body = self._parse_proc_body_until_end("SUB")
        return SubDef(name, params, body)


    def _parse_func_def(self):
        self._eat("FUNCTION")
        if self.tok.kind != "IDENT":
            raise ParseError("Expected Function name")
        name = self.tok.value.upper()
        self._require_not_reserved_ident(name, "Function")
        self._eat("IDENT")
        params = self._parse_param_list()
        self._require_eos("end of Function statement")
        body = self._parse_proc_body_until_end("FUNCTION")
        return FuncDef(name, params, body)


def parse_expression(text: str):
    return Parser(text).parse_expression()
