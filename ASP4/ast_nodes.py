"""AST node definitions for the tiny VBScript subset we compile."""

from typing import Optional


class Node:
    pass


class Expr(Node):
    pass


class Stmt(Node):
    pass


class ExprStmt(Stmt):
    def __init__(self, expr: Expr):
        self.expr = expr


class Assign(Stmt):
    def __init__(self, target: Expr, expr: Expr):
        self.target = target
        self.expr = expr


class SetAssign(Stmt):
    def __init__(self, target: Expr, expr: Expr):
        self.target = target
        self.expr = expr


class StringLit(Expr):
    def __init__(self, value: str):
        self.value = value


class NumberLit(Expr):
    def __init__(self, value):
        self.value = value


class DateLit(Expr):
    def __init__(self, value: str):
        self.value = value


class Ident(Expr):
    def __init__(self, name: str):
        self.name = name


class Member(Expr):
    def __init__(self, obj: Expr, name: str):
        self.obj = obj
        self.name = name


class Index(Expr):
    def __init__(self, obj: Expr, args):
        self.obj = obj
        self.args = args


class CallExpr(Expr):
    def __init__(self, callee: Expr, args):
        self.callee = callee
        self.args = args


class BoolLit(Expr):
    def __init__(self, value: bool):
        self.value = bool(value)


class Call(Expr):
    def __init__(self, name: str, args):
        self.name = name
        self.args = args


class Concat(Expr):
    def __init__(self, left: Expr, op: str, right: Expr):
        self.left = left
        self.op = op  # '&' or '+'
        self.right = right


class UnaryOp(Expr):
    def __init__(self, op: str, expr: Expr):
        self.op = op
        self.expr = expr


class BinaryOp(Expr):
    def __init__(self, op: str, left: Expr, right: Expr):
        self.op = op
        self.left = left
        self.right = right


class IfStmt(Stmt):
    def __init__(self, cond: Expr, then_block, elseif_parts, else_block):
        self.cond = cond
        self.then_block = then_block
        self.elseif_parts = elseif_parts  # list[(cond, block)]
        self.else_block = else_block


class WhileStmt(Stmt):
    def __init__(self, cond: Expr, body):
        self.cond = cond
        self.body = body


class DoWhileStmt(Stmt):
    def __init__(self, cond: Expr, body):
        self.cond = cond
        self.body = body


class DoLoopStmt(Stmt):
    def __init__(self, cond: Optional[Expr], is_until: bool, post_test: bool, body):
        self.cond = cond
        self.is_until = bool(is_until)
        self.post_test = bool(post_test)
        self.body = body


class ForStmt(Stmt):
    def __init__(self, var_name: str, start: Expr, end: Expr, step: Expr, body):
        self.var_name = var_name
        self.start = start
        self.end = end
        self.step = step
        self.body = body


class ForEachStmt(Stmt):
    def __init__(self, var_name: str, iterable: Expr, body):
        self.var_name = var_name
        self.iterable = iterable
        self.body = body


class CaseClause(Node):
    def __init__(self, patterns, body):
        self.patterns = patterns  # list[Expr] (minimal)
        self.body = body


class SelectCaseStmt(Stmt):
    def __init__(self, expr: Expr, cases, else_block):
        self.expr = expr
        self.cases = cases  # list[CaseClause]
        self.else_block = else_block


class ExitForStmt(Stmt):
    pass


class ExitDoStmt(Stmt):
    pass


class ExitSelectStmt(Stmt):
    pass


class ExitFunctionStmt(Stmt):
    pass


class ExitSubStmt(Stmt):
    pass


class ExitPropertyStmt(Stmt):
    pass


class ParamDecl(Node):
    def __init__(self, name: str, byval: bool = False):
        self.name = name
        self.byval = bool(byval)


class SubDef(Stmt):
    def __init__(self, name: str, params, body):
        self.name = name
        self.params = params  # list[ParamDecl]
        self.body = body
        self.visibility = "PUBLIC"
        self.is_default = False


class FuncDef(Stmt):
    def __init__(self, name: str, params, body):
        self.name = name
        self.params = params  # list[ParamDecl]
        self.body = body
        self.visibility = "PUBLIC"
        self.is_default = False


class PropertyDef(Stmt):
    def __init__(self, kind: str, name: str, params, body, visibility: str = "PUBLIC"):
        self.kind = kind  # GET / LET / SET
        self.name = name
        self.params = params  # list[ParamDecl]
        self.body = body
        self.visibility = visibility
        self.is_default = False


class ClassVarDecl(Node):
    def __init__(self, name: str, visibility: str = "PUBLIC", bounds=None):
        self.name = name
        self.visibility = visibility
        # bounds semantics match DimDecl.bounds:
        # - None => scalar var
        # - [] => dynamic array (unallocated)
        # - [Expr, Expr, ...] => array upper bounds per dimension
        self.bounds = bounds


class ClassDef(Stmt):
    def __init__(self, name: str, members, original_name: Optional[str] = None):
        self.name = name
        self.members = members
        self.original_name = original_name or name


class NewExpr(Expr):
    def __init__(self, class_name: str):
        self.class_name = class_name


class OptionExplicitStmt(Stmt):
    pass


class OnErrorResumeNextStmt(Stmt):
    pass


class OnErrorGoto0Stmt(Stmt):
    pass


class RandomizeStmt(Stmt):
    def __init__(self, seed_expr=None):
        self.seed_expr = seed_expr


class ConstStmt(Stmt):
    def __init__(self, items):
        # items: list[tuple[str, Expr]]
        self.items = items


class EndIfStmt(Stmt):
    pass


class ExecuteStmt(Stmt):
    def __init__(self, expr, is_global: bool):
        self.expr = expr
        self.is_global = bool(is_global)


class DimDecl(Node):
    def __init__(self, name: str, bounds=None):
        self.name = name
        # bounds:
        # - None => scalar var
        # - [] => dynamic array (unallocated)
        # - [Expr, Expr, ...] => array upper bounds per dimension
        self.bounds = bounds


class DimStmt(Stmt):
    def __init__(self, decls):
        self.decls = decls  # list[DimDecl]


class ReDimStmt(Stmt):
    def __init__(self, name: str, bounds, preserve: bool = False):
        self.name = name
        self.bounds = bounds  # list[Expr]
        self.preserve = preserve


class EraseStmt(Stmt):
    def __init__(self, name: str):
        self.name = name


class ResponseWrite(Stmt):
    def __init__(self, expr: Expr):
        self.expr = expr


class ResponseEnd(Stmt):
    pass


class ResponseClear(Stmt):
    pass


class ResponseFlush(Stmt):
    pass


class ResponseSetProperty(Stmt):
    def __init__(self, name: str, expr: Expr):
        self.name = name
        self.expr = expr


class ResponseCall(Stmt):
    def __init__(self, name: str, args):
        self.name = name
        self.args = args


class ResponseCookiesSet(Stmt):
    def __init__(self, cookie_name_expr: Expr, value_expr: Expr, subkey_expr: Optional[Expr] = None):
        self.cookie_name_expr = cookie_name_expr
        self.value_expr = value_expr
        self.subkey_expr = subkey_expr


class Block(Stmt):
    def __init__(self, stmts):
        self.stmts = stmts
