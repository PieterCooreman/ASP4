"""AST-walk interpreter for our current VBScript subset.

This interpreter executes the existing VBScript AST nodes produced by
ASPPY/parser.py and ASPPY/ast_nodes.py.
"""

from __future__ import annotations

from typing import Any, Dict, cast

from ..ast_nodes import (
    StringLit,
    NumberLit,
    DateLit,
    BoolLit,
    Ident,
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
    SubDef,
    FuncDef,
    SelectCaseStmt,
    CaseClause,
    CaseIsPattern,
    CaseToPattern,
    ExitForStmt,
    ExitDoStmt,
    ExitSelectStmt,
    DimStmt,
    DimDecl,
    ReDimStmt,
    EraseStmt,
    Block,
    ClassDef,
    ClassVarDecl,
    PropertyDef,
    NewExpr,
    OptionExplicitStmt,
    OnErrorResumeNextStmt,
    OnErrorGoto0Stmt,
    RandomizeStmt,
    ConstStmt,
    EndIfStmt,
    ExecuteStmt,
)
from ..vb_runtime import vbs_cstr, VBScriptCOMError
from .. import vb_datetime
import datetime as _dt
from decimal import Decimal as _Decimal
import math
import struct
import time
import threading
import types as _types
# Plain Python callables used to back VBScript built-in functions (Sin, CStr,
# Len, ...). These are never user procs, bound methods, class instances or
# indexable host objects, so when a CallExpr's callee resolves to one of these
# we can invoke it directly and skip the full dispatch cascade. This is the hot
# path for CPU-bound scripts that call many built-ins inside tight loops.
_PLAIN_CALLABLE_TYPES = (
    _types.FunctionType,
    _types.BuiltinFunctionType,
    _types.MethodType,
    _types.BuiltinMethodType,
)
from .values import VBArray, VBEmpty, VBNull, VBNothing, _Sentinel
from ..vb_errors import raise_runtime, VBScriptRuntimeError, VBScriptError
from ..http_response import ResponseEndException
from ..server_object import ServerTransferException
from ..parser import Parser
from ..ast_nodes import ExitFunctionStmt, ExitSubStmt, ExitPropertyStmt


# Case-insensitive attribute lookup cache: type(obj) -> {UPPER_NAME: real_name}
_icase_attr_cache = {}

_ICASE_MISSING = object()  # sentinel for "attribute not found"

def _icase_getattr(obj, name_upper):
    """Resolve a case-insensitive attribute name on obj using a cached mapping.
    Returns _ICASE_MISSING if the attribute does not exist (not None, since
    None is a valid attribute value)."""
    cls = type(obj)
    cache_key = id(cls)
    if cache_key not in _icase_attr_cache:
        mapping = {}
        for attr in dir(obj):
            mapping[attr.upper()] = attr
        _icase_attr_cache[cache_key] = mapping
    mapping = _icase_attr_cache[cache_key]
    real_name = mapping.get(name_upper)
    if real_name is not None:
        return getattr(obj, real_name, _ICASE_MISSING)
    # Instance might have dynamic attrs not in type cache
    for attr in dir(obj):
        if attr.upper() == name_upper:
            _icase_attr_cache[cache_key][name_upper] = attr
            return getattr(obj, attr, _ICASE_MISSING)
    return _ICASE_MISSING

def _icase_real_name(obj, name_upper):
    """Return the real (correctly-cased) attribute name, or None."""
    cls = type(obj)
    cache_key = id(cls)
    if cache_key not in _icase_attr_cache:
        mapping = {}
        for attr in dir(obj):
            mapping[attr.upper()] = attr
        _icase_attr_cache[cache_key] = mapping
    return _icase_attr_cache[cache_key].get(name_upper)


def _maybe_attr(obj: Any, name: str):
    return getattr(obj, name, None)


def _maybe_invoke_zero_arg(callable_obj):
    """VBScript treats many zero-arg functions like properties.

    For host (Python) objects, if a member resolves to a callable and the
    script references it without parentheses, VBScript will typically invoke it.
    """
    if not callable(callable_obj):
        return callable_obj
    try:
        return callable_obj()
    except TypeError:
        return callable_obj


def _to_int32(v: int) -> int:
    v = int(v) & 0xFFFFFFFF
    return v - 0x100000000 if (v & 0x80000000) else v






# VBScriptRuntimeError is imported from vb_errors (line 69) — do not redefine here.


class _ExitFor(Exception):
    pass


class _ExitDo(Exception):
    pass


class _ExitSelect(Exception):
    pass


class _ExitFunction(Exception):
    pass


class _ExitSub(Exception):
    pass


class _ExitProperty(Exception):
    pass


class _ByRef:
    def __init__(self, getter, setter):
        self._get = getter
        self._set = setter

    def get(self):
        return self._get()

    def set(self, v):
        return self._set(v)


class _UserProc:
    def __init__(self, name: str, kind: str, params, body):
        self.name = name
        self.kind = kind  # 'SUB' or 'FUNCTION'
        self.params = params
        self.body = body
        # ASP source location where this proc was defined (set by runner_vm)
        self.asp_file = None   # virtual path of the ASP file
        self.asp_line = None   # ASP line number of the <% block
        self.asp_src = None    # VBScript source of the <% block

    def invoke(self, interp: 'VBInterpreter', arg_exprs):
        return interp._invoke_user_proc(self, arg_exprs)


class VBClassDef:
    def __init__(self, name: str):
        # Keep display name as written; interpreter uses an uppercased key.
        self.name = name
        self.public_fields: set[str] = set()
        self.private_fields: set[str] = set()
        self.all_fields: set[str] = set()  # union of public + private; kept in sync
        # Field arrays: name -> DimDecl-style bounds (None / [] / [Expr...])
        self.field_bounds: dict[str, Any] = {}
        self.public_methods: dict[str, _UserProc] = {}
        self.private_methods: dict[str, _UserProc] = {}
        # property name -> kind -> proc
        self.public_props: dict[str, dict[str, _UserProc]] = {}
        self.private_props: dict[str, dict[str, _UserProc]] = {}
        self.default_method: _UserProc | None = None
        self.default_prop_get: _UserProc | None = None
        # Default parameterised Property Let/Set (e.g. obj(key) = value).
        # Records the property name marked Default so the matching Let/Set can
        # be resolved even though VBScript only allows the Default keyword on Get.
        self.default_prop_name: str | None = None

    def new_instance(self, interp: Any) -> 'VBClassInstance':
        inst = VBClassInstance(self)
        # initialize declared fields to Empty
        for f in self.all_fields:
            b = self.field_bounds.get(f)
            if b is None:
                inst._fields[f] = VBEmpty
                continue
            # Array field
            if b == []:
                inst._fields[f] = VBArray(0, allocated=False, dynamic=True)
                continue
            try:
                ubs = [int(interp.eval_expr(ex)) for ex in b]
            except Exception:
                ubs = [0]
            inst._fields[f] = VBArray(ubs, allocated=True, dynamic=True)
        # call Class_Initialize if present
        init_name = 'CLASS_INITIALIZE'
        proc = self.private_methods.get(init_name) or self.public_methods.get(init_name)
        if proc is not None:
            interp._invoke_class_proc(inst, proc, [])
        return inst

    def terminate_instance(self, interp: Any, inst: 'VBClassInstance'):
        if getattr(inst, '_terminated', False):
            return
        term_name = 'CLASS_TERMINATE'
        proc = self.private_methods.get(term_name) or self.public_methods.get(term_name)
        if proc is None:
            return
        try:
            inst._terminated = True
            interp._invoke_class_proc(inst, proc, [])
        except Exception:
            # VBScript ignores terminate failures in many cases.
            return


class VBClassInstance:
    def __init__(self, cls: VBClassDef):
        self._cls = cls
        self._fields: dict[str, Any] = {}
        self._terminated = False

    def _can_access_private(self, interp: Any) -> bool:
        return bool(interp._this_stack) and interp._this_stack[-1] is self

    def _vbs_get_member_raw(self, interp: Any, name: str):
        up = name # parser ensures upper (or caller does)

        # Properties
        if up in self._cls.public_props or up in self._cls.private_props:
            procs = self._cls.public_props.get(up)
            if procs is None and self._can_access_private(interp):
                procs = self._cls.private_props.get(up)
            if procs is None:
                raise VBScriptRuntimeError(f"Unknown member: {name}")
            getp = procs.get('GET')
            if getp is None:
                raise VBScriptRuntimeError("Property get not defined")
            if len(getp.params) > 0:
                return _BoundMethod(self, getp)
            return interp._invoke_class_proc(self, getp, [])

        # Methods
        if up in self._cls.public_methods:
            proc = self._cls.public_methods[up]
            return _BoundMethod(self, proc)
        if self._can_access_private(interp) and up in self._cls.private_methods:
            proc = self._cls.private_methods[up]
            return _BoundMethod(self, proc)

        # Fields
        if up in self._fields:
            if up in self._cls.private_fields and not self._can_access_private(interp):
                raise VBScriptRuntimeError("Object doesn't support this property or method")
            return self._fields.get(up, VBEmpty)

        raise VBScriptRuntimeError(f"Unknown member: {name}")

    def vbs_get_member(self, interp: Any, name: str):
        """Get a member value.

        VBScript treats zero-arg Functions like value properties when referenced
        without parentheses (e.g. `x = obj.Foo` calls `Foo` if it is a Function).
        """
        m = self._vbs_get_member_raw(interp, name)
        if isinstance(m, _BoundMethod) and m._kind == 'FUNCTION' and m._param_count == 0:
            return m.__vbs_invoke__(interp, [])
        return m

    def vbs_set_member(self, interp: Any, name: str, value, is_set: bool = False):
        up = name # parser ensures upper

        # Property Let/Set
        if up in self._cls.public_props or up in self._cls.private_props:
            procs = self._cls.public_props.get(up)
            if procs is None and self._can_access_private(interp):
                procs = self._cls.private_props.get(up)
            if procs is None:
                raise VBScriptRuntimeError(f"Unknown member: {name}")

            k = 'SET' if is_set else 'LET'
            p = procs.get(k)
            if p is None:
                # fall back: allow LET for SET in this minimal runtime
                p = procs.get('LET')
            if p is None:
                raise VBScriptRuntimeError("Property let/set not defined")
            interp._invoke_class_proc(self, p, [value], by_value_args=True)
            return

        # Field
        if up in self._cls.all_fields:
            if up in self._cls.private_fields and not self._can_access_private(interp):
                raise VBScriptRuntimeError("Object doesn't support this property or method")
            self._fields[up] = value
            return

        raise VBScriptRuntimeError(f"Unknown member: {name}")


class _BoundMethod:
    def __init__(self, inst: VBClassInstance, proc: _UserProc):
        self._inst = inst
        self._proc = proc

    def __call__(self, *args):
        # Called via eval_expr(CallExpr) for host callables only.
        # We don't support this route for VBScript class methods.
        raise VBScriptRuntimeError("Internal: bound method must be invoked via CallExpr")

    def __vbs_invoke__(self, interp: Any, arg_exprs):
        return interp._invoke_class_proc(self._inst, self._proc, arg_exprs)

    @property
    def _kind(self):
        return getattr(self._proc, 'kind', '')

    @property
    def _param_count(self):
        try:
            return len(getattr(self._proc, 'params', []) or [])
        except Exception:
            return 0


class VBInterpreter:
    def __init__(self, ctx, globals_env: Dict[str, Any]):
        self.ctx = ctx
        self.env = globals_env
        self._locals_stack: list[dict[str, Any]] = []
        self._procs: dict[str, _UserProc] = {}
        self._classes: dict[str, 'VBClassDef'] = {}
        self._this_stack: list['VBClassInstance'] = []
        self._proc_name_stack: list[str] = []
        self.option_explicit = False
        self.on_error_resume_next = False
        self._consts: set[str] = set()

        # VBScript RNG state (for Rnd/Randomize)
        self._rnd_state = 0
        self._rnd_last = 0.0
        self._rnd_last_auto_seed = None
        self._rnd_auto_nonce = 0
        self.env['RND'] = self._vbs_rnd
        self.env['RANDOMIZE'] = self._vbs_randomize

        # Built-ins that need interpreter context.
        self.env['CREATEOBJECT'] = lambda progid: self.ctx.Server.CreateObject(progid)
        self.env['EVAL'] = self._eval_from_string

    def _eval_from_string(self, s):
        expr = Parser(str(s)).parse_expression()
        return self.eval_expr(expr)

    def eval_expr(self, expr):
        # Fast type-based dispatch for the hottest node types.
        #
        # The branches in _eval_expr_slow form an ordered isinstance() cascade.
        # In CPU-heavy scripts the overwhelming majority of evaluations are
        # Ident / CallExpr / Concat / BinaryOp, yet CallExpr / Concat / BinaryOp
        # sit deep in that cascade, so each evaluation wasted up to a dozen
        # failed isinstance() checks before reaching the right branch.
        #
        # Every dispatched AST expr node is a *leaf* subclass of Expr (no node
        # type inherits from another dispatched node type), so an exact-type
        # dict lookup keyed on `expr.__class__` is behaviorally identical to the
        # isinstance cascade but turns the linear scan into a single O(1) hash
        # lookup. Unknown / rare node types fall through to the full cascade.
        handler = self._EXPR_DISPATCH.get(expr.__class__)
        if handler is not None:
            return handler(self, expr)
        return self._eval_expr_slow(expr)

    def _eval_expr_slow(self, expr):
        if isinstance(expr, StringLit):
            return expr.value
        if isinstance(expr, NumberLit):
            return expr.value

        if isinstance(expr, DateLit):
            return vb_datetime.CDate(expr.value)
        if isinstance(expr, BoolLit):
            return expr.value
        if isinstance(expr, Ident):
            name = expr.name
            up = name  # parser ensures upper
            return self._get_var(up)

        if isinstance(expr, NewExpr):
            nm = str(expr.class_name).upper()
            # VBScript ships RegExp as a built-in COM class that can be created via
            # either `New RegExp` or `CreateObject("VBScript.RegExp")`.
            if nm == 'REGEXP':
                return self.ctx.Server.CreateObject('VBScript.RegExp')
            if nm not in self._classes:
                raise_runtime('VAR_UNDEFINED', str(expr.class_name))
            return self._classes[nm].new_instance(self)
        if isinstance(expr, Member):
            # ADO Recordset Field-object access: `rs("field").Member` needs the
            # Field object. Only special-case a SIMPLE identifier base so we never
            # re-evaluate a side-effecting call chain (which must run exactly once).
            obj = None
            rs_base_expr = None
            rs_args = None
            if isinstance(expr.obj, (CallExpr, Index)):
                inner = expr.obj.callee if isinstance(expr.obj, CallExpr) else expr.obj.obj
                if isinstance(inner, Ident):
                    rs_base_expr = inner
                    rs_args = expr.obj.args
            if rs_base_expr is not None:
                try:
                    base = self._get_var_raw(rs_base_expr.name)
                    if isinstance(base, _ByRef):
                        base = base.get()
                    if getattr(base, '__class__', None) is not None and base.__class__.__name__ == 'ADORecordset':
                        args = [self.eval_expr(a) for a in rs_args]
                        if len(args) == 1:
                            obj = base.Fields.Item(args[0])
                except Exception:
                    obj = None
            if obj is None:
                obj = self.eval_expr(expr.obj)
            if isinstance(obj, _ByRef):
                obj = obj.get()
            if obj is VBNothing:
                raise VBScriptCOMError(424, "Object required")
            if obj in (VBEmpty, VBNull):
                return VBEmpty
            # VBScript allows chaining off zero-arg functions without parentheses:
            #   obj.Method.Prop  =>  obj.Method().Prop
            if isinstance(obj, _BoundMethod) and obj._kind == 'FUNCTION' and obj._param_count == 0:
                obj = obj.__vbs_invoke__(self, [])
            if isinstance(obj, VBClassInstance):
                return obj.vbs_get_member(self, expr.name)
            obj_any = cast(Any, obj)
            get_prop = _maybe_attr(obj_any, 'vbs_get_prop')
            if get_prop is not None:
                return _maybe_invoke_zero_arg(get_prop(expr.name))
            # Basic Python attribute fallback (only for explicit host objects)
            if hasattr(obj, expr.name):
                return _maybe_invoke_zero_arg(getattr(obj, expr.name))
            # Case-insensitive
            _icase_val = _icase_getattr(obj, expr.name.upper())
            if _icase_val is not _ICASE_MISSING:
                return _maybe_invoke_zero_arg(_icase_val)
            raise_runtime('OBJECT_NOT_SUPPORT', f"Unknown member: {expr.name} on {type(obj).__name__}")
        if isinstance(expr, Index):
            obj = self.eval_expr(expr.obj)
            if isinstance(obj, _ByRef):
                obj = obj.get()
            if isinstance(obj, _BoundMethod) and obj._kind == 'FUNCTION' and obj._param_count == 0:
                obj = obj.__vbs_invoke__(self, [])
            # Default parameterised Property Get on a class instance:
            #   x = store("colour")  parsed as an Index in some lvalue contexts.
            if isinstance(obj, VBClassInstance):
                if obj._cls.default_method is not None:
                    return self._invoke_class_proc(obj, obj._cls.default_method, expr.args)
                if obj._cls.default_prop_get is not None:
                    return self._invoke_class_proc(obj, obj._cls.default_prop_get, expr.args)
            args = [self.eval_expr(a) for a in expr.args]
            obj_any = cast(Any, obj)
            # Resolve the variable name from the AST for better error messages
            _idx_varname = getattr(expr.obj, 'name', None) or '(expression)'
            idx_get = _maybe_attr(obj_any, '__vbs_index_get__')
            if idx_get is not None:
                try:
                    if len(args) == 1:
                        return idx_get(args[0])
                    return idx_get(args)
                except IndexError as _ie:
                    _ub = getattr(obj, 'ubound', None)
                    _ub_str = ''
                    if _ub is not None:
                        try: _ub_str = f', UBound = {_ub()}'
                        except Exception: _ub_str = ', array unallocated'
                    raise_runtime('SUBSCRIPT_OUT_OF_RANGE',
                        f"{_idx_varname}({', '.join(str(a) for a in args)}){_ub_str}")
            # Python list/tuple support for arrays
            if isinstance(obj, (list, tuple)):
                if len(args) != 1:
                    raise_runtime('SUBSCRIPT_OUT_OF_RANGE',
                        f"{_idx_varname}({', '.join(str(a) for a in args)}) — expected 1 index, got {len(args)}")
                _req_idx = int(args[0])
                try:
                    return obj[_req_idx]
                except IndexError:
                    raise_runtime('SUBSCRIPT_OUT_OF_RANGE',
                        f"{_idx_varname}({_req_idx}), but UBound is {len(obj) - 1}")
            
            # Robustness: Handle Index on Empty (common in VBScript On Error Resume Next scenarios)
            # instead of crashing with _Sentinel
            if obj in (VBEmpty, VBNull, VBNothing, None):
                # VBScript typically raises "Type mismatch" or "Object required" here.
                # Since we want to avoid crashing the runner with internal python errors:
                raise_runtime('TYPE_MISMATCH')
                
            raise_runtime('OBJECT_NOT_SUPPORT', f"Object is not indexable: {type(obj).__name__}")
        if isinstance(expr, CallExpr):
            # When calling `obj.Member(...)`, do not auto-invoke a zero-arg
            # Function on Member lookup; the call itself will invoke it.
            if isinstance(expr.callee, Ident):
                name_up = expr.callee.name  # parser ensures upper
                callee = None
                if self._locals_stack and name_up in self._locals_stack[-1]:
                    v = self._locals_stack[-1][name_up]
                    v = v.get() if isinstance(v, _ByRef) else v
                    is_current_proc = bool(self._proc_name_stack) and name_up == self._proc_name_stack[-1]
                    prefer_proc = (v is VBEmpty) or is_current_proc
                    # If this is a function return variable (or a non-callable)
                    # and we're in a class context, prefer the class member for recursion.
                    if prefer_proc and self._this_stack:
                        try:
                            callee = self._this_stack[-1]._vbs_get_member_raw(self, name_up)
                        except VBScriptRuntimeError as e:
                            if str(e).startswith('Unknown member:'):
                                callee = None
                            else:
                                raise
                    if callee is None:
                        if prefer_proc and name_up in self._procs:
                            callee = self._procs[name_up]
                        else:
                            callee = v
                if callee is VBEmpty and name_up in self._procs:
                    callee = self._procs[name_up]
                if callee is None:
                    # Check registered procedures before falling back to
                    # _get_var_raw which only searches locals/env and would
                    # return VBEmpty for procedure names stored in _procs.
                    if name_up in self._procs:
                        callee = self._procs[name_up]
                    else:
                        callee = self._get_var_raw(name_up)
            elif isinstance(expr.callee, Member):
                callee = self._eval_member_ref(expr.callee)
            else:
                callee = self.eval_expr(expr.callee)
            # User-defined procedures need access to the raw arg expressions (ByRef).
            if isinstance(callee, _UserProc):
                return callee.invoke(self, expr.args)
            if isinstance(callee, _BoundMethod):
                return callee.__vbs_invoke__(self, expr.args)
            if isinstance(callee, VBClassInstance) and callee._cls.default_method is not None:
                return self._invoke_class_proc(callee, callee._cls.default_method, expr.args)
            # Default parameterised Property Get: store(key) reads via the
            # class's Default Property Get (e.g. KeyValueStore.Item).
            if isinstance(callee, VBClassInstance) and callee._cls.default_prop_get is not None:
                return self._invoke_class_proc(callee, callee._cls.default_prop_get, expr.args)

            # Default member indexing (e.g., rs("field")) for non-callable objects.
            if callee is not None and not callable(callee):
                idx_get = _maybe_attr(callee, '__vbs_index_get__')
                if idx_get is not None:
                    args = []
                    for a in expr.args:
                        if a is None: args.append(None)
                        else: args.append(self.eval_expr(a))
                    try:
                        if len(args) == 1:
                            return idx_get(args[0])
                        return idx_get(args)
                    except IndexError:
                        _call_varname = getattr(expr.callee, 'name', None) or '(expression)'
                        _ub = getattr(callee, 'ubound', None)
                        _ub_str = ''
                        if _ub is not None:
                            try: _ub_str = f', UBound = {_ub()}'
                            except Exception: _ub_str = ', array unallocated'
                        raise_runtime('SUBSCRIPT_OUT_OF_RANGE',
                            f"{_call_varname}({', '.join(str(a) for a in args)}){_ub_str}")

            # Special-case: legacy upload scripts may rely on Request.BinaryRead
            # updating the requested byte count (ByRef-like behavior).
            if isinstance(expr.callee, Member) and str(expr.callee.name).upper() == 'BINARYREAD':
                try:
                    obj = self.eval_expr(expr.callee.obj)
                    if isinstance(obj, _ByRef):
                        obj = obj.get()
                    if obj.__class__.__name__ == 'Request' and len(expr.args) == 1 and isinstance(expr.args[0], Ident):
                        br = self._make_byref(expr.args[0])
                        if callable(callee):
                            return callee(br)
                except Exception:
                    pass

            args = []
            for a in expr.args:
                if a is None: args.append(None)
                else: args.append(self.eval_expr(a))
            # Array indexing can look like a call in VBScript: a(0)
            callee_any = cast(Any, callee)
            idx_get = getattr(callee_any, '__vbs_index_get__', None)
            if idx_get is not None:
                try:
                    if len(args) == 1:
                        return idx_get(args[0])
                    return idx_get(args)
                except IndexError:
                    _call_varname2 = getattr(expr.callee, 'name', None) or '(expression)'
                    _ub2 = getattr(callee, 'ubound', None)
                    _ub_str2 = ''
                    if _ub2 is not None:
                        try: _ub_str2 = f', UBound = {_ub2()}'
                        except Exception: _ub_str2 = ', array unallocated'
                    raise_runtime('SUBSCRIPT_OUT_OF_RANGE',
                        f"{_call_varname2}({', '.join(str(a) for a in args)}){_ub_str2}")
            if callable(callee):
                return callee(*args)
            # Provide a helpful message; this bubbles into aspLite's Err.Description.
            callee_hint = type(callee).__name__
            try:
                if isinstance(expr.callee, Ident):
                    callee_hint = f"{expr.callee.name} ({callee_hint})"
                elif isinstance(expr.callee, Member):
                    callee_hint = f"{expr.callee.name} member ({callee_hint})"
            except Exception:
                pass
            raise_runtime('OBJECT_NOT_SUPPORT', f"Not callable: {callee_hint}")
        if isinstance(expr, Call):
            fn = self._get_var_raw(expr.name)  # parser ensures upper
            args = []
            for a in expr.args:
                if a is None: args.append(None)
                else: args.append(self.eval_expr(a))
            if isinstance(fn, _UserProc):
                return fn.invoke(self, expr.args)
            if isinstance(fn, _BoundMethod):
                return fn.__vbs_invoke__(self, expr.args)
            if callable(fn):
                return fn(*args)
            raise_runtime('OBJECT_NOT_SUPPORT', f"Not callable: {expr.name}")
        if isinstance(expr, Concat):
            left = self.eval_expr(expr.left)
            right = self.eval_expr(expr.right)
            if expr.op == '&':
                if isinstance(left, (bytes, bytearray)) or isinstance(right, (bytes, bytearray)):
                    lb = left if isinstance(left, (bytes, bytearray)) else vbs_cstr(left).encode('latin-1', errors='replace')
                    rb = right if isinstance(right, (bytes, bytearray)) else vbs_cstr(right).encode('latin-1', errors='replace')
                    return bytes(lb) + bytes(rb)
                # VBScript: Null & "x" => "x" (& ignores Null, treats as "")
                ls = "" if left is VBNull else vbs_cstr(left)
                rs = "" if right is VBNull else vbs_cstr(right)
                return ls + rs
            # VBScript: any arithmetic with Null propagates Null
            if left is VBNull or right is VBNull:
                return VBNull
            # '+' in VBScript is numeric add if possible, else string concat.
            # Date arithmetic: date + number => add days.
            if isinstance(left, (_dt.datetime, _dt.date)) and isinstance(right, (int, float)):
                ld = left if isinstance(left, _dt.datetime) else _dt.datetime(left.year, left.month, left.day)
                return ld + _dt.timedelta(days=float(right))
            if isinstance(right, (_dt.datetime, _dt.date)) and isinstance(left, (int, float)):
                rd = right if isinstance(right, _dt.datetime) else _dt.datetime(right.year, right.month, right.day)
                return rd + _dt.timedelta(days=float(left))
            ln = _try_number(left)
            rn = _try_number(right)
            if ln is not None and rn is not None:
                return ln + rn
            return vbs_cstr(left) + vbs_cstr(right)
        if isinstance(expr, UnaryOp):
            v = self.eval_expr(expr.expr)
            if expr.op == '-':
                n = _try_number(v)
                if n is None:
                    raise_runtime('TYPE_MISMATCH')
                return -n
            if expr.op.upper() == 'NOT':
                if isinstance(v, bool):
                    return not v
                n = _try_number(v)
                if n is not None:
                    return _to_int32(~int(n))
                return not bool(_try_truthy(v))
            raise_runtime('INVALID_PROC_CALL') # Unsupported unary op
        if isinstance(expr, BinaryOp):
            op = expr.op.upper()
            if op in ('AND', 'OR', 'XOR', 'EQV', 'IMP'):
                l = self.eval_expr(expr.left)
                r = self.eval_expr(expr.right)
                # VBScript And/Or/Xor/Eqv/Imp are ALWAYS bitwise.
                # True = -1, False = 0.  Track whether BOTH operands
                # were boolean so the result type is correct:
                # bool AND bool => bool, anything else => integer.
                both_bool = isinstance(l, bool) and isinstance(r, bool)
                if isinstance(l, bool):
                    l = -1 if l else 0
                if isinstance(r, bool):
                    r = -1 if r else 0

                ln = _try_number(l)
                rn = _try_number(r)
                if ln is not None and rn is not None:
                    li = _to_int32(int(ln))
                    ri = _to_int32(int(rn))
                    result_i = 0
                    if op == 'AND':
                        result_i = _to_int32(li & ri)
                    elif op == 'OR':
                        result_i = _to_int32(li | ri)
                    elif op == 'XOR':
                        result_i = _to_int32(li ^ ri)
                    elif op == 'EQV':
                        result_i = _to_int32(~(li ^ ri))
                    else:  # IMP
                        result_i = _to_int32((~li) | ri)
                    # Return boolean only when both operands were boolean
                    if both_bool:
                        return result_i != 0
                    return result_i
                # Fallback for non-numeric: treat as boolean
                lb = bool(_try_truthy(l))
                rb = bool(_try_truthy(r))
                li2 = -1 if lb else 0
                ri2 = -1 if rb else 0
                result_i2 = 0
                if op == 'AND':
                    result_i2 = li2 & ri2
                elif op == 'OR':
                    result_i2 = li2 | ri2
                elif op == 'XOR':
                    result_i2 = li2 ^ ri2
                elif op == 'EQV':
                    result_i2 = ~(li2 ^ ri2)
                else:
                    result_i2 = (~li2) | ri2
                return result_i2 == -1

            if op == 'IS':
                l = self.eval_expr(expr.left)
                r = self.eval_expr(expr.right)
                # VBScript's Is operator only works with object references.
                # Non-object values (Empty, Null, scalars) raise Type Mismatch.
                if l is VBEmpty or l is VBNull or isinstance(l, (int, float, str, bool)):
                    raise_runtime('TYPE_MISMATCH')
                if r is VBEmpty or r is VBNull or isinstance(r, (int, float, str, bool)):
                    raise_runtime('TYPE_MISMATCH')
                return l is r

            l = self.eval_expr(expr.left)
            r = self.eval_expr(expr.right)
            if expr.op in ('=', '<>', '<', '<=', '>', '>='):
                return _compare(expr.op, l, r)
            if expr.op == '-':
                # Date arithmetic: date - number => subtract days; date - date => days diff
                if isinstance(l, (_dt.datetime, _dt.date)) and isinstance(r, (int, float)):
                    ld = l if isinstance(l, _dt.datetime) else _dt.datetime(l.year, l.month, l.day)
                    return ld - _dt.timedelta(days=float(r))
                if isinstance(l, (_dt.datetime, _dt.date)) and isinstance(r, (_dt.datetime, _dt.date)):
                    ld = l if isinstance(l, _dt.datetime) else _dt.datetime(l.year, l.month, l.day)
                    rd = r if isinstance(r, _dt.datetime) else _dt.datetime(r.year, r.month, r.day)
                    return (ld - rd).total_seconds() / 86400.0
                ln = _try_number(l)
                rn = _try_number(r)
                if ln is None or rn is None:
                    raise_runtime('TYPE_MISMATCH')
                return ln - rn
            if expr.op == '*':
                ln = _try_number(l)
                rn = _try_number(r)
                if ln is None or rn is None:
                    raise_runtime('TYPE_MISMATCH')
                return ln * rn
            if expr.op == '^':
                ln = _try_number(l)
                rn = _try_number(r)
                if ln is None or rn is None:
                    raise_runtime('TYPE_MISMATCH')
                return ln ** rn
            if expr.op == '/':
                ln = _try_number(l)
                rn = _try_number(r)
                if ln is None or rn is None:
                    raise_runtime('TYPE_MISMATCH')
                if rn == 0:
                    raise_runtime('DIVISION_BY_ZERO')
                return ln / rn
            if expr.op == '\\':
                ln = _try_number(l)
                rn = _try_number(r)
                if ln is None or rn is None:
                    raise_runtime('TYPE_MISMATCH')
                if rn == 0:
                    raise_runtime('DIVISION_BY_ZERO')
                # VBScript integer division: round operands to int first
                # (banker's rounding), then truncate toward zero (like C).
                li_d = int(round(ln))
                ri_d = int(round(rn))
                return int(math.trunc(li_d / ri_d))
            if op == 'MOD' or expr.op.upper() == 'MOD':
                ln = _try_number(l)
                rn = _try_number(r)
                if ln is None or rn is None:
                    raise_runtime('TYPE_MISMATCH')
                if rn == 0:
                    raise_runtime('DIVISION_BY_ZERO')
                # VBScript Mod: result has sign of dividend (not divisor).
                # Operands are rounded to integers first.
                li_m = int(round(ln))
                ri_m = int(round(rn))
                return int(math.fmod(li_m, ri_m))
            raise_runtime('INVALID_PROC_CALL') # Unsupported binary op
        raise_runtime('INVALID_PROC_CALL') # Unsupported expr

    # ==================================================================
    # Auto-extracted eval_expr branch handlers (see eval_expr docstring).
    # Each method body is a verbatim extraction of the matching branch
    # in _eval_expr_slow; _eval_expr_slow is retained as a fallback.
    # ==================================================================

    def _eval_stringlit(self, expr):
        return expr.value

    def _eval_numberlit(self, expr):
        return expr.value


    def _eval_datelit(self, expr):
        return vb_datetime.CDate(expr.value)

    def _eval_boollit(self, expr):
        return expr.value

    def _eval_ident(self, expr):
        name = expr.name
        up = name  # parser ensures upper
        return self._get_var(up)


    def _eval_newexpr(self, expr):
        nm = str(expr.class_name).upper()
        # VBScript ships RegExp as a built-in COM class that can be created via
        # either `New RegExp` or `CreateObject("VBScript.RegExp")`.
        if nm == 'REGEXP':
            return self.ctx.Server.CreateObject('VBScript.RegExp')
        if nm not in self._classes:
            raise_runtime('VAR_UNDEFINED', str(expr.class_name))
        return self._classes[nm].new_instance(self)

    def _eval_member(self, expr):
        # ADO Recordset Field-object access: `rs("field").Member` needs the
        # Field object. Only special-case a SIMPLE identifier base so we never
        # re-evaluate a side-effecting call chain (which must run exactly once).
        obj = None
        rs_base_expr = None
        rs_args = None
        if isinstance(expr.obj, (CallExpr, Index)):
            inner = expr.obj.callee if isinstance(expr.obj, CallExpr) else expr.obj.obj
            if isinstance(inner, Ident):
                rs_base_expr = inner
                rs_args = expr.obj.args
        if rs_base_expr is not None:
            try:
                base = self._get_var_raw(rs_base_expr.name)
                if isinstance(base, _ByRef):
                    base = base.get()
                if getattr(base, '__class__', None) is not None and base.__class__.__name__ == 'ADORecordset':
                    args = [self.eval_expr(a) for a in rs_args]
                    if len(args) == 1:
                        obj = base.Fields.Item(args[0])
            except Exception:
                obj = None
        if obj is None:
            obj = self.eval_expr(expr.obj)
        if isinstance(obj, _ByRef):
            obj = obj.get()
        if obj is VBNothing:
            raise VBScriptCOMError(424, "Object required")
        if obj in (VBEmpty, VBNull):
            return VBEmpty
        # VBScript allows chaining off zero-arg functions without parentheses:
        #   obj.Method.Prop  =>  obj.Method().Prop
        if isinstance(obj, _BoundMethod) and obj._kind == 'FUNCTION' and obj._param_count == 0:
            obj = obj.__vbs_invoke__(self, [])
        if isinstance(obj, VBClassInstance):
            return obj.vbs_get_member(self, expr.name)
        obj_any = cast(Any, obj)
        get_prop = _maybe_attr(obj_any, 'vbs_get_prop')
        if get_prop is not None:
            return _maybe_invoke_zero_arg(get_prop(expr.name))
        # Basic Python attribute fallback (only for explicit host objects)
        if hasattr(obj, expr.name):
            return _maybe_invoke_zero_arg(getattr(obj, expr.name))
        # Case-insensitive
        _icase_val = _icase_getattr(obj, expr.name.upper())
        if _icase_val is not _ICASE_MISSING:
            return _maybe_invoke_zero_arg(_icase_val)
        raise_runtime('OBJECT_NOT_SUPPORT', f"Unknown member: {expr.name} on {type(obj).__name__}")

    def _eval_index(self, expr):
        obj = self.eval_expr(expr.obj)
        if isinstance(obj, _ByRef):
            obj = obj.get()
        if isinstance(obj, _BoundMethod) and obj._kind == 'FUNCTION' and obj._param_count == 0:
            obj = obj.__vbs_invoke__(self, [])
        # Default parameterised Property Get on a class instance:
        #   x = store("colour")  parsed as an Index in some lvalue contexts.
        if isinstance(obj, VBClassInstance):
            if obj._cls.default_method is not None:
                return self._invoke_class_proc(obj, obj._cls.default_method, expr.args)
            if obj._cls.default_prop_get is not None:
                return self._invoke_class_proc(obj, obj._cls.default_prop_get, expr.args)
        args = [self.eval_expr(a) for a in expr.args]
        obj_any = cast(Any, obj)
        # Resolve the variable name from the AST for better error messages
        _idx_varname = getattr(expr.obj, 'name', None) or '(expression)'
        idx_get = _maybe_attr(obj_any, '__vbs_index_get__')
        if idx_get is not None:
            try:
                if len(args) == 1:
                    return idx_get(args[0])
                return idx_get(args)
            except IndexError as _ie:
                _ub = getattr(obj, 'ubound', None)
                _ub_str = ''
                if _ub is not None:
                    try: _ub_str = f', UBound = {_ub()}'
                    except Exception: _ub_str = ', array unallocated'
                raise_runtime('SUBSCRIPT_OUT_OF_RANGE',
                    f"{_idx_varname}({', '.join(str(a) for a in args)}){_ub_str}")
        # Python list/tuple support for arrays
        if isinstance(obj, (list, tuple)):
            if len(args) != 1:
                raise_runtime('SUBSCRIPT_OUT_OF_RANGE',
                    f"{_idx_varname}({', '.join(str(a) for a in args)}) — expected 1 index, got {len(args)}")
            _req_idx = int(args[0])
            try:
                return obj[_req_idx]
            except IndexError:
                raise_runtime('SUBSCRIPT_OUT_OF_RANGE',
                    f"{_idx_varname}({_req_idx}), but UBound is {len(obj) - 1}")

        # Robustness: Handle Index on Empty (common in VBScript On Error Resume Next scenarios)
        # instead of crashing with _Sentinel
        if obj in (VBEmpty, VBNull, VBNothing, None):
            # VBScript typically raises "Type mismatch" or "Object required" here.
            # Since we want to avoid crashing the runner with internal python errors:
            raise_runtime('TYPE_MISMATCH')

        raise_runtime('OBJECT_NOT_SUPPORT', f"Object is not indexable: {type(obj).__name__}")

    def _eval_callexpr(self, expr):
        # When calling `obj.Member(...)`, do not auto-invoke a zero-arg
        # Function on Member lookup; the call itself will invoke it.
        callee_from_ident = False
        if isinstance(expr.callee, Ident):
            callee_from_ident = True
            name_up = expr.callee.name  # parser ensures upper
            callee = None
            if self._locals_stack and name_up in self._locals_stack[-1]:
                v = self._locals_stack[-1][name_up]
                v = v.get() if isinstance(v, _ByRef) else v
                is_current_proc = bool(self._proc_name_stack) and name_up == self._proc_name_stack[-1]
                prefer_proc = (v is VBEmpty) or is_current_proc
                # If this is a function return variable (or a non-callable)
                # and we're in a class context, prefer the class member for recursion.
                if prefer_proc and self._this_stack:
                    try:
                        callee = self._this_stack[-1]._vbs_get_member_raw(self, name_up)
                    except VBScriptRuntimeError as e:
                        if str(e).startswith('Unknown member:'):
                            callee = None
                        else:
                            raise
                if callee is None:
                    if prefer_proc and name_up in self._procs:
                        callee = self._procs[name_up]
                    else:
                        callee = v
            if callee is VBEmpty and name_up in self._procs:
                callee = self._procs[name_up]
            if callee is None:
                # Check registered procedures before falling back to
                # _get_var_raw which only searches locals/env and would
                # return VBEmpty for procedure names stored in _procs.
                if name_up in self._procs:
                    callee = self._procs[name_up]
                else:
                    callee = self._get_var_raw(name_up)
        elif isinstance(expr.callee, Member):
            callee = self._eval_member_ref(expr.callee)
        else:
            callee = self.eval_expr(expr.callee)

        # Fast path: a built-in resolved from an Ident callee (Sin, CStr, Len,
        # Round, ...). Plain Python functions are never user procs / bound
        # methods / class instances / indexable host objects, so we can skip the
        # entire dispatch cascade below and invoke directly. This is the dominant
        # case for CPU-bound scripts calling many built-ins in tight loops.
        if callee_from_ident and type(callee) in _PLAIN_CALLABLE_TYPES:
            ca = expr.args
            if not ca:
                return callee()
            args = [None if a is None else self.eval_expr(a) for a in ca]
            return callee(*args)

        # User-defined procedures need access to the raw arg expressions (ByRef).
        if isinstance(callee, _UserProc):
            return callee.invoke(self, expr.args)
        if isinstance(callee, _BoundMethod):
            return callee.__vbs_invoke__(self, expr.args)
        if isinstance(callee, VBClassInstance) and callee._cls.default_method is not None:
            return self._invoke_class_proc(callee, callee._cls.default_method, expr.args)
        # Default parameterised Property Get: store(key) reads via the
        # class's Default Property Get (e.g. KeyValueStore.Item).
        if isinstance(callee, VBClassInstance) and callee._cls.default_prop_get is not None:
            return self._invoke_class_proc(callee, callee._cls.default_prop_get, expr.args)

        # Default member indexing (e.g., rs("field")) for non-callable objects.
        if callee is not None and not callable(callee):
            idx_get = _maybe_attr(callee, '__vbs_index_get__')
            if idx_get is not None:
                args = []
                for a in expr.args:
                    if a is None: args.append(None)
                    else: args.append(self.eval_expr(a))
                try:
                    if len(args) == 1:
                        return idx_get(args[0])
                    return idx_get(args)
                except IndexError:
                    _call_varname = getattr(expr.callee, 'name', None) or '(expression)'
                    _ub = getattr(callee, 'ubound', None)
                    _ub_str = ''
                    if _ub is not None:
                        try: _ub_str = f', UBound = {_ub()}'
                        except Exception: _ub_str = ', array unallocated'
                    raise_runtime('SUBSCRIPT_OUT_OF_RANGE',
                        f"{_call_varname}({', '.join(str(a) for a in args)}){_ub_str}")

        # Special-case: legacy upload scripts may rely on Request.BinaryRead
        # updating the requested byte count (ByRef-like behavior).
        if isinstance(expr.callee, Member) and str(expr.callee.name).upper() == 'BINARYREAD':
            try:
                obj = self.eval_expr(expr.callee.obj)
                if isinstance(obj, _ByRef):
                    obj = obj.get()
                if obj.__class__.__name__ == 'Request' and len(expr.args) == 1 and isinstance(expr.args[0], Ident):
                    br = self._make_byref(expr.args[0])
                    if callable(callee):
                        return callee(br)
            except Exception:
                pass

        args = []
        for a in expr.args:
            if a is None: args.append(None)
            else: args.append(self.eval_expr(a))
        # Array indexing can look like a call in VBScript: a(0)
        # `cast(Any, ...)` is a typing-only no-op at runtime; calling it here on
        # every invocation added a measurable per-call function-call overhead.
        idx_get = getattr(callee, '__vbs_index_get__', None)
        if idx_get is not None:
            try:
                if len(args) == 1:
                    return idx_get(args[0])
                return idx_get(args)
            except IndexError:
                _call_varname2 = getattr(expr.callee, 'name', None) or '(expression)'
                _ub2 = getattr(callee, 'ubound', None)
                _ub_str2 = ''
                if _ub2 is not None:
                    try: _ub_str2 = f', UBound = {_ub2()}'
                    except Exception: _ub_str2 = ', array unallocated'
                raise_runtime('SUBSCRIPT_OUT_OF_RANGE',
                    f"{_call_varname2}({', '.join(str(a) for a in args)}){_ub_str2}")
        if callable(callee):
            return callee(*args)
        # Provide a helpful message; this bubbles into aspLite's Err.Description.
        callee_hint = type(callee).__name__
        try:
            if isinstance(expr.callee, Ident):
                callee_hint = f"{expr.callee.name} ({callee_hint})"
            elif isinstance(expr.callee, Member):
                callee_hint = f"{expr.callee.name} member ({callee_hint})"
        except Exception:
            pass
        raise_runtime('OBJECT_NOT_SUPPORT', f"Not callable: {callee_hint}")

    def _eval_call(self, expr):
        fn = self._get_var_raw(expr.name)  # parser ensures upper
        args = []
        for a in expr.args:
            if a is None: args.append(None)
            else: args.append(self.eval_expr(a))
        if isinstance(fn, _UserProc):
            return fn.invoke(self, expr.args)
        if isinstance(fn, _BoundMethod):
            return fn.__vbs_invoke__(self, expr.args)
        if callable(fn):
            return fn(*args)
        raise_runtime('OBJECT_NOT_SUPPORT', f"Not callable: {expr.name}")

    def _eval_concat(self, expr):
        left = self.eval_expr(expr.left)
        right = self.eval_expr(expr.right)
        if expr.op == '&':
            if isinstance(left, (bytes, bytearray)) or isinstance(right, (bytes, bytearray)):
                lb = left if isinstance(left, (bytes, bytearray)) else vbs_cstr(left).encode('latin-1', errors='replace')
                rb = right if isinstance(right, (bytes, bytearray)) else vbs_cstr(right).encode('latin-1', errors='replace')
                return bytes(lb) + bytes(rb)
            # VBScript: Null & "x" => "x" (& ignores Null, treats as "")
            ls = "" if left is VBNull else vbs_cstr(left)
            rs = "" if right is VBNull else vbs_cstr(right)
            return ls + rs
        # VBScript: any arithmetic with Null propagates Null
        if left is VBNull or right is VBNull:
            return VBNull
        # '+' in VBScript is numeric add if possible, else string concat.
        # Date arithmetic: date + number => add days.
        if isinstance(left, (_dt.datetime, _dt.date)) and isinstance(right, (int, float)):
            ld = left if isinstance(left, _dt.datetime) else _dt.datetime(left.year, left.month, left.day)
            return ld + _dt.timedelta(days=float(right))
        if isinstance(right, (_dt.datetime, _dt.date)) and isinstance(left, (int, float)):
            rd = right if isinstance(right, _dt.datetime) else _dt.datetime(right.year, right.month, right.day)
            return rd + _dt.timedelta(days=float(left))
        ln = _try_number(left)
        rn = _try_number(right)
        if ln is not None and rn is not None:
            return ln + rn
        return vbs_cstr(left) + vbs_cstr(right)

    def _eval_unaryop(self, expr):
        v = self.eval_expr(expr.expr)
        if expr.op == '-':
            n = _try_number(v)
            if n is None:
                raise_runtime('TYPE_MISMATCH')
            return -n
        if expr.op.upper() == 'NOT':
            if isinstance(v, bool):
                return not v
            n = _try_number(v)
            if n is not None:
                return _to_int32(~int(n))
            return not bool(_try_truthy(v))
        raise_runtime('INVALID_PROC_CALL') # Unsupported unary op

    def _eval_binaryop(self, expr):
        op = expr.op.upper()
        if op in ('AND', 'OR', 'XOR', 'EQV', 'IMP'):
            l = self.eval_expr(expr.left)
            r = self.eval_expr(expr.right)
            # VBScript And/Or/Xor/Eqv/Imp are ALWAYS bitwise.
            # True = -1, False = 0.  Track whether BOTH operands
            # were boolean so the result type is correct:
            # bool AND bool => bool, anything else => integer.
            both_bool = isinstance(l, bool) and isinstance(r, bool)
            if isinstance(l, bool):
                l = -1 if l else 0
            if isinstance(r, bool):
                r = -1 if r else 0

            ln = _try_number(l)
            rn = _try_number(r)
            if ln is not None and rn is not None:
                li = _to_int32(int(ln))
                ri = _to_int32(int(rn))
                result_i = 0
                if op == 'AND':
                    result_i = _to_int32(li & ri)
                elif op == 'OR':
                    result_i = _to_int32(li | ri)
                elif op == 'XOR':
                    result_i = _to_int32(li ^ ri)
                elif op == 'EQV':
                    result_i = _to_int32(~(li ^ ri))
                else:  # IMP
                    result_i = _to_int32((~li) | ri)
                # Return boolean only when both operands were boolean
                if both_bool:
                    return result_i != 0
                return result_i
            # Fallback for non-numeric: treat as boolean
            lb = bool(_try_truthy(l))
            rb = bool(_try_truthy(r))
            li2 = -1 if lb else 0
            ri2 = -1 if rb else 0
            result_i2 = 0
            if op == 'AND':
                result_i2 = li2 & ri2
            elif op == 'OR':
                result_i2 = li2 | ri2
            elif op == 'XOR':
                result_i2 = li2 ^ ri2
            elif op == 'EQV':
                result_i2 = ~(li2 ^ ri2)
            else:
                result_i2 = (~li2) | ri2
            return result_i2 == -1

        if op == 'IS':
            l = self.eval_expr(expr.left)
            r = self.eval_expr(expr.right)
            # VBScript's Is operator only works with object references.
            # Non-object values (Empty, Null, scalars) raise Type Mismatch.
            if l is VBEmpty or l is VBNull or isinstance(l, (int, float, str, bool)):
                raise_runtime('TYPE_MISMATCH')
            if r is VBEmpty or r is VBNull or isinstance(r, (int, float, str, bool)):
                raise_runtime('TYPE_MISMATCH')
            return l is r

        l = self.eval_expr(expr.left)
        r = self.eval_expr(expr.right)
        if expr.op in ('=', '<>', '<', '<=', '>', '>='):
            return _compare(expr.op, l, r)
        if expr.op == '-':
            # Date arithmetic: date - number => subtract days; date - date => days diff
            if isinstance(l, (_dt.datetime, _dt.date)) and isinstance(r, (int, float)):
                ld = l if isinstance(l, _dt.datetime) else _dt.datetime(l.year, l.month, l.day)
                return ld - _dt.timedelta(days=float(r))
            if isinstance(l, (_dt.datetime, _dt.date)) and isinstance(r, (_dt.datetime, _dt.date)):
                ld = l if isinstance(l, _dt.datetime) else _dt.datetime(l.year, l.month, l.day)
                rd = r if isinstance(r, _dt.datetime) else _dt.datetime(r.year, r.month, r.day)
                return (ld - rd).total_seconds() / 86400.0
            ln = _try_number(l)
            rn = _try_number(r)
            if ln is None or rn is None:
                raise_runtime('TYPE_MISMATCH')
            return ln - rn
        if expr.op == '*':
            ln = _try_number(l)
            rn = _try_number(r)
            if ln is None or rn is None:
                raise_runtime('TYPE_MISMATCH')
            return ln * rn
        if expr.op == '^':
            ln = _try_number(l)
            rn = _try_number(r)
            if ln is None or rn is None:
                raise_runtime('TYPE_MISMATCH')
            return ln ** rn
        if expr.op == '/':
            ln = _try_number(l)
            rn = _try_number(r)
            if ln is None or rn is None:
                raise_runtime('TYPE_MISMATCH')
            if rn == 0:
                raise_runtime('DIVISION_BY_ZERO')
            return ln / rn
        if expr.op == '\\':
            ln = _try_number(l)
            rn = _try_number(r)
            if ln is None or rn is None:
                raise_runtime('TYPE_MISMATCH')
            if rn == 0:
                raise_runtime('DIVISION_BY_ZERO')
            # VBScript integer division: round operands to int first
            # (banker's rounding), then truncate toward zero (like C).
            li_d = int(round(ln))
            ri_d = int(round(rn))
            return int(math.trunc(li_d / ri_d))
        if op == 'MOD' or expr.op.upper() == 'MOD':
            ln = _try_number(l)
            rn = _try_number(r)
            if ln is None or rn is None:
                raise_runtime('TYPE_MISMATCH')
            if rn == 0:
                raise_runtime('DIVISION_BY_ZERO')
            # VBScript Mod: result has sign of dividend (not divisor).
            # Operands are rounded to integers first.
            li_m = int(round(ln))
            ri_m = int(round(rn))
            return int(math.fmod(li_m, ri_m))
        raise_runtime('INVALID_PROC_CALL') # Unsupported binary op

    def _eval_member_ref(self, expr: Member):
        """Evaluate a Member expression as a callable reference.

        This differs from normal Member evaluation by NOT auto-invoking
        zero-arg Function members.
        """
        # ADO Recordset Field-object access: when `expr.obj` is `rs("field")`
        # and `rs` is an ADORecordset, member access (e.g. rs("f").Value) needs
        # the Field object rather than the field's default value. Only handle the
        # case where the base is a SIMPLE identifier so we never re-evaluate a
        # side-effecting call chain such as `a.Add(1).Add(2)` (which must invoke
        # Add() exactly once per call).
        obj = None
        rs_base_expr = None
        rs_args = None
        if isinstance(expr.obj, (CallExpr, Index)):
            inner = expr.obj.callee if isinstance(expr.obj, CallExpr) else expr.obj.obj
            if isinstance(inner, Ident):
                rs_base_expr = inner
                rs_args = expr.obj.args
        if rs_base_expr is not None:
            try:
                base = self._get_var_raw(rs_base_expr.name)
                if isinstance(base, _ByRef):
                    base = base.get()
                if getattr(base, '__class__', None) is not None and base.__class__.__name__ == 'ADORecordset':
                    args = [self.eval_expr(a) if a is not None else None for a in rs_args]
                    if len(args) == 1:
                        obj = base.Fields.Item(args[0])
            except Exception:
                obj = None
        if obj is None:
            obj = self.eval_expr(expr.obj)
        if isinstance(obj, _ByRef):
            obj = obj.get()
        # Allow chaining off zero-arg functions without parentheses:
        #   obj.Method.Prop  =>  obj.Method().Prop
        if isinstance(obj, _BoundMethod) and obj._kind == 'FUNCTION' and obj._param_count == 0:
            obj = obj.__vbs_invoke__(self, [])
        if isinstance(obj, VBClassInstance):
            # For call syntax `obj.Member(...)`, we need the callable reference,
            # not the VBScript "value" behavior of zero-arg Functions.
            return obj._vbs_get_member_raw(self, expr.name) # expr.name is upper from parser
        obj_any = cast(Any, obj)
        get_prop = _maybe_attr(obj_any, 'vbs_get_prop')
        if get_prop is not None:
            return get_prop(expr.name)
        if hasattr(obj, expr.name):
            return getattr(obj, expr.name)
        # case-insensitive fallback if exact match not found
        _icase_val = _icase_getattr(obj, expr.name)
        if _icase_val is not _ICASE_MISSING:
            return _icase_val
        raise VBScriptRuntimeError(f"Unknown member: {expr.name} on {type(obj).__name__}")

    def exec_stmt(self, stmt):
        # Error suppression wrapper (On Error Resume Next)
        try:
            _debug_tls.current = self
            _debug_tls.last_stmt = stmt
        except Exception:
            pass
        try:
            try:
                self._last_stmt_pos = getattr(stmt, '_pos', None)
            except Exception:
                self._last_stmt_pos = None
            return self._exec_stmt_inner(stmt)
        except Exception as e:
            # Always propagate control-flow exceptions.
            if isinstance(e, (ResponseEndException, ServerTransferException, _ExitFor, _ExitDo, _ExitSelect, _ExitFunction, _ExitSub, _ExitProperty)):
                raise

            if self.on_error_resume_next:
                if getattr(self.ctx, 'Err', None) is not None:
                    try:
                        # Map known error types to Err object
                        number = 5 # default to invalid proc call
                        desc = str(e)
                        src = ""
                        
                        if isinstance(e, VBScriptError) and e.error_def:
                            number = e.error_def.number
                            desc = e.description
                            src = getattr(e, 'source_snippet', '')
                        elif isinstance(e, VBScriptCOMError):
                            number = int(getattr(e, 'number', 2147500037))
                            desc = str(getattr(e, 'description', str(e)))
                            src = str(getattr(e, 'source', ''))
                        else:
                            # Generic python exception map
                            number = 2147500037 # Unspecified
                            desc = str(e)

                        self.ctx.Err.Number = number
                        self.ctx.Err.Description = desc
                        if src:
                            self.ctx.Err.Source = src
                    except Exception:
                        pass
                return
            try:
                if getattr(e, 'vbs_pos', None) is None:
                    setattr(e, 'vbs_pos', getattr(self, '_last_stmt_pos', None))
            except Exception:
                pass
            raise

    def _exec_stmt_inner(self, stmt):
        if isinstance(stmt, OptionExplicitStmt):
            self.option_explicit = True
            return

        if isinstance(stmt, OnErrorResumeNextStmt):
            self.on_error_resume_next = True
            return

        if isinstance(stmt, OnErrorGoto0Stmt):
            self.on_error_resume_next = False
            # VBScript behavior: turning off error handling also resets Err.
            try:
                if getattr(self.ctx, 'Err', None) is not None:
                    self.ctx.Err.Clear()
            except Exception:
                pass
            return

        if isinstance(stmt, RandomizeStmt):
            seed = None
            if stmt.seed_expr is not None:
                seed = self.eval_expr(stmt.seed_expr)
            return self._vbs_randomize(seed)

        if isinstance(stmt, ConstStmt):
            for (nm, ex) in stmt.items:
                up = str(nm).upper()
                val = self.eval_expr(ex)
                # Const declares the name even under Option Explicit.
                if self._locals_stack:
                    self._locals_stack[-1][up] = val
                else:
                    self.env[up] = val
                self._consts.add(up)
            return

        if isinstance(stmt, EndIfStmt):
            return

        if isinstance(stmt, ExecuteStmt):
            code = vbs_cstr(self.eval_expr(stmt.expr))
            return self._vbs_execute(code, is_global=bool(stmt.is_global))
        R = self.ctx.Response
        if isinstance(stmt, Block):
            for s in stmt.stmts:
                self.exec_stmt(s)
            return

        if isinstance(stmt, ResponseWrite):
            v = self.eval_expr(stmt.expr)
            if isinstance(v, VBClassInstance) and v._cls.default_prop_get is not None:
                v = self._invoke_class_proc(v, v._cls.default_prop_get, [])
            R.Write(v)
            return
        if isinstance(stmt, ResponseClear):
            R.Clear()
            return
        if isinstance(stmt, ResponseFlush):
            R.Flush()
            return
        if isinstance(stmt, ResponseEnd):
            R.End()
            return
        if isinstance(stmt, ResponseSetProperty):
            name = stmt.name
            val = self.eval_expr(stmt.expr)
            if name.upper() == 'BUFFER':
                R.Buffer = bool(val)
            else:
                R.SetProperty(name, val)
            return
        if isinstance(stmt, ResponseCookiesSet):
            cname = self.eval_expr(stmt.cookie_name_expr)
            cval = self.eval_expr(stmt.value_expr)
            if getattr(stmt, 'subkey_expr', None) is not None:
                sk = self.eval_expr(stmt.subkey_expr)
                R.SetCookieKey(cname, sk, cval)
            else:
                R.SetCookie(cname, cval)
            return
        if isinstance(stmt, ResponseCall):
            args = [self.eval_expr(a) for a in stmt.args]
            if str(stmt.name).upper() == 'WRITE' and args:
                v = args[0]
                if isinstance(v, VBClassInstance) and v._cls.default_prop_get is not None:
                    args[0] = self._invoke_class_proc(v, v._cls.default_prop_get, [])
            name_up = str(stmt.name).upper()
            if name_up == 'WRITE':
                if len(args) != 1:
                    raise Exception("Response.Write expects 1 argument")
                R.Write(args[0])
                return
            R.Call(stmt.name, *args)
            return

        if isinstance(stmt, ExprStmt):
            v = self.eval_expr(stmt.expr)
            # VBScript: a bare procedure name or member can be used as a statement call.
            if isinstance(v, _BoundMethod):
                v.__vbs_invoke__(self, [])
                return
            if isinstance(v, _UserProc):
                self._invoke_user_proc(v, [])
                return
            # Host objects: allow `obj.Method` (no parentheses) as a statement call.
            # This is required for common COM/VBScript patterns like:
            #   oxmlhttp.send
            #   dom.Load url
            try:
                # IMPORTANT: VBEmpty/VBNull are callables (sentinels) but should NOT be called here.
                # If 'v' is VBEmpty (bare variable), we should just ignore it (no-op), not crash.
                if callable(v) and not isinstance(v, _Sentinel) and isinstance(stmt.expr, (Ident, Member)):
                    v()
                    return
            except Exception:
                # Let normal error handling apply in exec_stmt wrapper.
                raise
            return

        if isinstance(stmt, Assign):
            val = self.eval_expr(stmt.expr)
            tgt = stmt.target
            if isinstance(tgt, Ident):
                self._set_ident(tgt.name, val, is_set=False)  # parser ensures upper
                return
            if isinstance(tgt, Member):
                obj = self.eval_expr(tgt.obj)
                if isinstance(obj, _ByRef):
                    obj = obj.get()
                if isinstance(obj, VBClassInstance):
                    obj.vbs_set_member(self, tgt.name, val, is_set=False)
                    return
                if hasattr(obj, 'vbs_set_prop'):
                    obj.vbs_set_prop(tgt.name, val)
                    return
                # case-insensitive setattr for host objects
                _real_name = _icase_real_name(obj, tgt.name.upper())
                if _real_name is not None:
                    setattr(obj, _real_name, val)
                    return
                setattr(obj, tgt.name, val)
                return
            if isinstance(tgt, Index):
                if isinstance(tgt.obj, Member):
                    base = self.eval_expr(tgt.obj.obj)
                    if isinstance(base, _ByRef):
                        base = base.get()
                    if isinstance(base, VBClassInstance):
                        name_up = str(tgt.obj.name).upper()
                        procs = base._cls.public_props.get(name_up)
                        if procs is None and base._can_access_private(self):
                            procs = base._cls.private_props.get(name_up)
                        if procs:
                            p = procs.get('LET') or procs.get('SET')
                            if p is not None:
                                args = [self.eval_expr(a) for a in tgt.args]
                                self._invoke_class_proc(base, p, args + [val], by_value_args=True)
                                return
                obj = self.eval_expr(tgt.obj)
                if isinstance(obj, _ByRef):
                    obj = obj.get()
                # Default parameterised property: store(key) = value
                # invokes the class's default Property Let/Set.
                if isinstance(obj, VBClassInstance):
                    p = self._resolve_default_prop_let(obj, prefer='LET')
                    if p is not None:
                        args = [self.eval_expr(a) for a in tgt.args]
                        self._invoke_class_proc(obj, p, args + [val], by_value_args=True)
                        return
                args = [self.eval_expr(a) for a in tgt.args]
                if hasattr(obj, '__vbs_index_set__'):
                    if len(args) == 1:
                        obj.__vbs_index_set__(args[0], val)
                    else:
                        obj.__vbs_index_set__(args, val)
                    return
                if isinstance(obj, list):
                    if len(args) != 1:
                        raise VBScriptRuntimeError("Index assignment expects 1 argument")
                    obj[int(args[0])] = val
                    return
                raise VBScriptRuntimeError("Target is not index-assignable")
            raise VBScriptRuntimeError("Unsupported assignment target")

        if isinstance(stmt, SetAssign):
            # For now, Set behaves like normal assignment but is required for
            # object references in VBScript.
            val = self.eval_expr(stmt.expr)
            tgt = stmt.target
            if isinstance(tgt, Ident):
                self._set_ident(tgt.name, val, is_set=True) # parser ensures upper
                return
            if isinstance(tgt, Member):
                obj = self.eval_expr(tgt.obj)
                if isinstance(obj, _ByRef):
                    obj = obj.get()
                if isinstance(obj, VBClassInstance):
                    obj.vbs_set_member(self, tgt.name, val, is_set=True)
                    return
                if hasattr(obj, 'vbs_set_prop'):
                    obj.vbs_set_prop(tgt.name, val)
                    return
                _real_name2 = _icase_real_name(obj, tgt.name.upper())
                if _real_name2 is not None:
                    setattr(obj, _real_name2, val)
                    return
                setattr(obj, tgt.name, val)
                return
            if isinstance(tgt, Index):
                if isinstance(tgt.obj, Member):
                    base = self.eval_expr(tgt.obj.obj)
                    if isinstance(base, _ByRef):
                        base = base.get()
                    if isinstance(base, VBClassInstance):
                        name_up = str(tgt.obj.name).upper()
                        procs = base._cls.public_props.get(name_up)
                        if procs is None and base._can_access_private(self):
                            procs = base._cls.private_props.get(name_up)
                        if procs:
                            p = procs.get('SET') or procs.get('LET')
                            if p is not None:
                                args = [self.eval_expr(a) for a in tgt.args]
                                self._invoke_class_proc(base, p, args + [val], by_value_args=True)
                                return
                obj = self.eval_expr(tgt.obj)
                if isinstance(obj, _ByRef):
                    obj = obj.get()
                # Default parameterised property: Set store(key) = obj
                # invokes the class's default Property Set/Let.
                if isinstance(obj, VBClassInstance):
                    p = self._resolve_default_prop_let(obj, prefer='SET')
                    if p is not None:
                        args = [self.eval_expr(a) for a in tgt.args]
                        self._invoke_class_proc(obj, p, args + [val], by_value_args=True)
                        return
                args = [self.eval_expr(a) for a in tgt.args]
                if hasattr(obj, '__vbs_index_set__'):
                    if len(args) == 1:
                        obj.__vbs_index_set__(args[0], val)
                    else:
                        obj.__vbs_index_set__(args, val)
                    return
                raise VBScriptRuntimeError("Target is not index-assignable")
            raise VBScriptRuntimeError("Unsupported Set assignment target")

        if isinstance(stmt, DimStmt):
            for d in stmt.decls:
                name = d.name # parser ensures upper
                if d.bounds is None:
                    # VBScript: Dim inside a procedure creates a local that can hide globals.
                    if self._locals_stack:
                        if name not in self._locals_stack[-1]:
                            self._locals_stack[-1][name] = VBEmpty
                    else:
                        if name not in self.env:
                            self.env[name] = VBEmpty
                    continue
                # array decl
                if len(d.bounds) == 0:
                    # dynamic unallocated (1-D default)
                    if self._locals_stack:
                        if name not in self._locals_stack[-1]:
                            self._locals_stack[-1][name] = VBArray([-1], allocated=False, dynamic=True)
                    else:
                        if name not in self.env:
                            self.env[name] = VBArray([-1], allocated=False, dynamic=True)
                    continue
                ubs = []
                for b in d.bounds:
                    ub = _try_number(self.eval_expr(b))
                    if ub is None:
                        raise VBScriptRuntimeError("Dim array bound must be numeric")
                    ubs.append(int(ub))
                if self._locals_stack:
                    if name not in self._locals_stack[-1]:
                        self._locals_stack[-1][name] = VBArray(ubs, allocated=True, dynamic=False)
                else:
                    if name not in self.env:
                        self.env[name] = VBArray(ubs, allocated=True, dynamic=False)
            return

        if isinstance(stmt, ReDimStmt):
            key = stmt.name # parser ensures upper
            cur = None
            if self._locals_stack and key in self._locals_stack[-1]:
                cur = self._locals_stack[-1][key]
            elif key in self.env:
                cur = self.env[key]

            if isinstance(cur, _ByRef):
                cur_val = cur.get()
                if not isinstance(cur_val, VBArray):
                    cur.set(VBArray([-1], allocated=False, dynamic=True))
            elif isinstance(cur, VBArray):
                pass
            else:
                # If variable doesn't exist, create it in current scope.
                if self._locals_stack:
                    self._locals_stack[-1][key] = VBArray([-1], allocated=False, dynamic=True)
                else:
                    self.env[key] = VBArray([-1], allocated=False, dynamic=True)
            arr = cast(VBArray, self._get_var(key))
            ubs = []
            for b in stmt.bounds:
                ub = _try_number(self.eval_expr(b))
                if ub is None:
                    raise VBScriptRuntimeError("ReDim bound must be numeric")
                ubs.append(int(ub))
            arr.redim(ubs, preserve=bool(stmt.preserve))
            return

        if isinstance(stmt, EraseStmt):
            key = stmt.name # parser ensures upper
            v = self._get_var(key)
            if isinstance(v, VBArray):
                v.erase()
            else:
                # Erase on non-array: ignore (pragmatic)
                pass
            return

        if isinstance(stmt, IfStmt):
            if bool(_try_truthy(self.eval_expr(stmt.cond))):
                for s in stmt.then_block:
                    self.exec_stmt(s)
                return
            for (c, b) in stmt.elseif_parts:
                if bool(_try_truthy(self.eval_expr(c))):
                    for s in b:
                        self.exec_stmt(s)
                    return
            if stmt.else_block is not None:
                for s in stmt.else_block:
                    self.exec_stmt(s)
            return

        if isinstance(stmt, WhileStmt):
            while bool(_try_truthy(self.eval_expr(stmt.cond))):
                try:
                    for s in stmt.body:
                        self.exec_stmt(s)
                except _ExitDo:
                    break
            return

        if isinstance(stmt, DoWhileStmt):
            while bool(_try_truthy(self.eval_expr(stmt.cond))):
                try:
                    for s in stmt.body:
                        self.exec_stmt(s)
                except _ExitDo:
                    break
            return

        if isinstance(stmt, DoLoopStmt):
            def _cond_ok():
                if stmt.cond is None:
                    return True
                v = bool(_try_truthy(self.eval_expr(stmt.cond)))
                return (not v) if stmt.is_until else v

            if not stmt.post_test:
                while _cond_ok():
                    try:
                        for s in stmt.body:
                            self.exec_stmt(s)
                    except _ExitDo:
                        break
                return

            # post-test: execute at least once if unconditional or condition holds after body
            while True:
                try:
                    for s in stmt.body:
                        self.exec_stmt(s)
                except _ExitDo:
                    break
                if stmt.cond is None:
                    continue
                if not _cond_ok():
                    break
            return

        if isinstance(stmt, ForStmt):
            start = _try_number(self.eval_expr(stmt.start))
            end = _try_number(self.eval_expr(stmt.end))
            step = _try_number(self.eval_expr(stmt.step))
            if start is None or end is None or step is None:
                raise VBScriptRuntimeError("For requires numeric bounds")
            i = start
            var_key = stmt.var_name # parser ensures upper
            self._set_ident(var_key, i, is_set=False)
            if step == 0:
                raise VBScriptRuntimeError("For Step cannot be 0")
            if step > 0:
                cond = lambda v: v <= end
            else:
                cond = lambda v: v >= end
            while cond(i):
                self._set_ident(var_key, i, is_set=False)
                try:
                    for s in stmt.body:
                        self.exec_stmt(s)
                except _ExitFor:
                    break
                # Read the counter back from the VBS variable system
                # before applying the step, so user modifications are respected.
                i = _try_number(self._get_var(var_key))
                if i is None:
                    break
                i = i + step
            return

        if isinstance(stmt, ForEachStmt):
            it = self.eval_expr(stmt.iterable)
            if hasattr(it, '__iter__'):
                var_key = stmt.var_name # parser ensures upper
                for v in it:
                    self._set_ident(var_key, v, is_set=False)
                    try:
                        for s in stmt.body:
                            self.exec_stmt(s)
                    except _ExitFor:
                        break
                return
            raise VBScriptRuntimeError(f"For Each target is not iterable: {type(it).__name__}")

        if isinstance(stmt, SelectCaseStmt):
            sel = self.eval_expr(stmt.expr)
            matched = False
            for c in stmt.cases:
                for p in c.patterns:
                    pattern_matched = False
                    if isinstance(p, CaseIsPattern):
                        pv = self.eval_expr(p.expr)
                        result = _compare(p.op, sel, pv)
                        pattern_matched = (result is True)
                    elif isinstance(p, CaseToPattern):
                        lo = self.eval_expr(p.lower)
                        hi = self.eval_expr(p.upper)
                        r1 = _compare('>=', sel, lo)
                        r2 = _compare('<=', sel, hi)
                        pattern_matched = (r1 is True) and (r2 is True)
                    else:
                        pv = self.eval_expr(p)
                        pattern_matched = (_compare('=', sel, pv) is True)
                    if pattern_matched:
                        for s in c.body:
                            try:
                                self.exec_stmt(s)
                            except _ExitSelect:
                                return
                        matched = True
                        break
                if matched:
                    break
            if (not matched) and (stmt.else_block is not None):
                for s in stmt.else_block:
                    try:
                        self.exec_stmt(s)
                    except _ExitSelect:
                        return
            return

        if isinstance(stmt, ExitForStmt):
            raise _ExitFor()

        if isinstance(stmt, ExitDoStmt):
            raise _ExitDo()

        if isinstance(stmt, ExitSelectStmt):
            raise _ExitSelect()

        if isinstance(stmt, SubDef):
            self._register_proc(stmt.name, 'SUB', stmt.params, stmt.body)
            return

        if isinstance(stmt, FuncDef):
            self._register_proc(stmt.name, 'FUNCTION', stmt.params, stmt.body)
            return

        if isinstance(stmt, ClassDef):
            self._register_class(stmt)
            return

        if isinstance(stmt, ExitFunctionStmt):
            raise _ExitFunction()

        if isinstance(stmt, ExitSubStmt):
            raise _ExitSub()

        if isinstance(stmt, ExitPropertyStmt):
            raise _ExitProperty()

        raise VBScriptRuntimeError("Unsupported statement")


    def _vbs_execute(self, code: str, is_global: bool):
        # Execute/ExecuteGlobal behaves like a separate compilation unit.
        prev_opt = self.option_explicit
        prev_onerr = self.on_error_resume_next
        prev_locals = self._locals_stack
        prev_this = self._this_stack
        prev_src = getattr(self, '_current_vbs_src', '')
        prev_path = getattr(self, '_current_asp_path', '')
        try:
            try:
                self._current_vbs_src = str(code)
                self._current_asp_path = 'EXECUTE'
            except Exception:
                pass
            # ExecuteGlobal runs in the global namespace (cannot see procedure locals)
            # and should not inherit an implicit class `Me` context.
            if is_global:
                self._locals_stack = []
                self._this_stack = []

            self.option_explicit = False
            self.on_error_resume_next = False
            prog = Parser(str(code)).parse_program()
            for s in prog:
                if isinstance(s, OptionExplicitStmt):
                    self.exec_stmt(s)
                    break
            if self.option_explicit:
                decls = []
                self._collect_dim_decls(prog, decls)
                # ExecuteGlobal declares into globals; Execute declares into current locals.
                if is_global or (not self._locals_stack):
                    self._predeclare_dim_decls(self.env, decls)
                else:
                    self._predeclare_dim_decls(self._locals_stack[-1], decls)

            # Register defs first (including those in nested blocks)
            defs = []
            self._collect_proc_defs(prog, defs)
            for s in defs:
                if isinstance(s, (ClassDef, SubDef, FuncDef)):
                    self.exec_stmt(s)
            # Execute rest
            for s in prog:
                if isinstance(s, (OptionExplicitStmt, ClassDef, SubDef, FuncDef)):
                    continue
                self.exec_stmt(s)
        finally:
            self._locals_stack = prev_locals
            self._this_stack = prev_this
            self.option_explicit = prev_opt
            self.on_error_resume_next = prev_onerr
            try:
                self._current_vbs_src = prev_src
                self._current_asp_path = prev_path
            except Exception:
                pass
        return VBEmpty


    def _vbs_randomize(self, number=None):
        # VBScript Randomize
        if number is None or number == "":
            # Use high-resolution clock sources and a per-interpreter nonce so
            # rapid back-to-back calls do not reuse the same seed.
            try:
                timer_seed = int(float(vb_datetime.Timer()) * 1000000.0)
                seed = int(timer_seed + (time.time_ns() & 0xFFFFFF) + (time.perf_counter_ns() & 0xFFFFFF))
            except Exception:
                seed = int(time.time() * 1000000.0)
            self._rnd_auto_nonce = (int(self._rnd_auto_nonce) + 1) & 0xFFFFFFFF
            seed = int(seed + self._rnd_auto_nonce)
            seed24 = int(seed) % 16777216
            if self._rnd_last_auto_seed is not None and int(seed24) == int(self._rnd_last_auto_seed):
                seed24 = (int(seed24) + 1) % 16777216
            self._rnd_last_auto_seed = int(seed24)
            seed = int(seed24)
        else:
            try:
                seed = int(float(number) * 1000000)
            except Exception:
                seed = int(time.time() * 1000)
        self._rnd_state = seed % 16777216
        self._rnd_last = self._rnd_state / 16777216.0
        return VBEmpty


    def _vbs_rnd(self, number=None):
        # VBScript-like Rnd semantics (24-bit LCG).
        # - number < 0: seed from number, return first value for that seed
        # - number = 0: return last value
        # - number > 0 or omitted: advance and return next

        MOD = 16777216
        A = 1140671485
        C = 12820163

        n = None
        if number is not None:
            try:
                n = float(number)
            except Exception:
                n = 0.0

        if n is not None and n < 0:
            # VBScript quirk: Rnd(negative) reseeds based on the Single bits.
            # It returns a deterministic value for a given input.
            b = struct.pack('<f', float(n))
            bits = struct.unpack('<I', b)[0]
            seed24 = (bits & 0xFFFFFF) | ((bits >> 24) & 0xFF)
            self._rnd_state = int(seed24) % MOD
            # Advance once; this value is returned for the negative argument.
            self._rnd_state = (self._rnd_state * A + C) % MOD
            self._rnd_last = self._rnd_state / float(MOD)
            return self._rnd_last

        if n is not None and n == 0:
            return self._rnd_last

        self._rnd_state = (self._rnd_state * A + C) % MOD
        self._rnd_last = self._rnd_state / float(MOD)
        return self._rnd_last


    def _has_var(self, up: str) -> bool:
        # VBScript has procedure-level scope (no closures). Only the current
        # stack frame is visible, plus globals.
        if self._locals_stack and up in self._locals_stack[-1]:
            return True
        return up in self.env


    def _get_var(self, up: str):
        # Locals (current procedure frame) first.
        # up is already upper from parser or internal call
        if self._locals_stack and up in self._locals_stack[-1]:
            v = self._locals_stack[-1][up]
            v = v.get() if isinstance(v, _ByRef) else v
            if isinstance(v, _UserProc) and v.kind == 'FUNCTION' and len(v.params) == 0:
                return self._invoke_user_proc(v, [])
            return v

        # Inside class procedures, VBScript allows calling members without `Me.`.
        # Prefer class members over global built-ins when names collide (e.g. aspLite's
        # `[isEmpty]` helper vs VBScript IsEmpty()).
        if self._this_stack:
            try:
                inst = self._this_stack[-1]
                return inst.vbs_get_member(self, up)
            except VBScriptRuntimeError as e:
                # Only fall back to globals if the name truly isn't a member.
                # Do not hide exceptions thrown *by* member execution.
                if str(e).startswith('Unknown member:'):
                    pass
                else:
                    raise

        # Globals/env
        if up in self.env:
            v = self.env[up]
            # Fast path: plain scalar values (the common case for loop counters
            # and accumulators) are never _ByRef wrappers or zero-arg user
            # functions, so skip those isinstance checks entirely.
            vt = v.__class__
            if vt is int or vt is float or vt is str:
                return v
            v = v.get() if isinstance(v, _ByRef) else v
            if isinstance(v, _UserProc) and v.kind == 'FUNCTION' and len(v.params) == 0:
                return self._invoke_user_proc(v, [])
            return v

        if self.option_explicit:
            raise VBScriptRuntimeError(f"Variable is undefined: '{up}'")
        # VBScript default: undeclared vars default to Empty.
        return VBEmpty

    def _get_var_raw(self, up: str):
        """Like _get_var, but do not auto-invoke zero-arg class functions.

        This is used when resolving a CallExpr callee (e.g. getConn()).
        """
        if self._locals_stack and up in self._locals_stack[-1]:
            v = self._locals_stack[-1][up]
            return v.get() if isinstance(v, _ByRef) else v

        if self._this_stack:
            try:
                inst = self._this_stack[-1]
                return inst._vbs_get_member_raw(self, up)
            except VBScriptRuntimeError as e:
                if str(e).startswith('Unknown member:'):
                    pass
                else:
                    raise

        if up in self.env:
            v = self.env[up]
            return v.get() if isinstance(v, _ByRef) else v

        if self.option_explicit:
            raise VBScriptRuntimeError(f"Variable is undefined: '{up}'")
        return VBEmpty


    def _declare_var(self, up: str, value):
        if self._locals_stack:
            self._locals_stack[-1][up] = value
        else:
            self.env[up] = value


    def _terminate_frame_objects(self, frame: dict[str, Any], keep=None):
        """Best-effort: call Class_Terminate for objects that go out of scope.

        Important: Do not terminate the object that is being returned from a
        Function/Property Get. In VBScript, returning an object does not
        destroy it.
        """
        pass


    def end_request_cleanup(self, keep: set[int] | None = None):
        # Best-effort cleanup at end of request: terminate remaining class instances
        # that are not part of the keep set (Application/Session/Request/Response/Server).
        keep_ids = keep or set()

        def _collect(obj, seen: set[int]) -> None:
            if obj is None:
                return
            oid = id(obj)
            if oid in seen:
                return
            seen.add(oid)
            if isinstance(obj, VBClassInstance):
                keep_ids.add(oid)
                for fv in obj._fields.values():
                    _collect(fv, seen)
                return
            if isinstance(obj, _ByRef):
                try:
                    _collect(obj.get(), seen)
                except Exception:
                    pass
                return
            if isinstance(obj, VBArray):
                try:
                    for it in obj:
                        _collect(it, seen)
                except Exception:
                    pass
                return
            if isinstance(obj, dict):
                for it in obj.values():
                    _collect(it, seen)
                return
            if isinstance(obj, (list, tuple, set)):
                for it in obj:
                    _collect(it, seen)
                return

        # Build keep set from core context
        try:
            ctx = self.ctx
            _collect(getattr(ctx, 'Application', None), set())
            _collect(getattr(ctx, 'Session', None), set())
            _collect(getattr(ctx, 'Request', None), set())
            _collect(getattr(ctx, 'Response', None), set())
            _collect(getattr(ctx, 'Server', None), set())
        except Exception:
            pass

        # Collect candidates from globals and local frames
        candidates: list[VBClassInstance] = []
        def _gather(obj, seen: set[int]):
            if obj is None:
                return
            oid = id(obj)
            if oid in seen:
                return
            seen.add(oid)
            if isinstance(obj, VBClassInstance):
                candidates.append(obj)
                for fv in obj._fields.values():
                    _gather(fv, seen)
                return
            if isinstance(obj, _ByRef):
                try:
                    _gather(obj.get(), seen)
                except Exception:
                    pass
                return
            if isinstance(obj, VBArray):
                try:
                    for it in obj:
                        _gather(it, seen)
                except Exception:
                    pass
                return
            if isinstance(obj, dict):
                for it in obj.values():
                    _gather(it, seen)
                return
            if isinstance(obj, (list, tuple, set)):
                for it in obj:
                    _gather(it, seen)
                return

        seen: set[int] = set()
        for v in self.env.values():
            _gather(v, seen)
        for frame in self._locals_stack:
            for v in frame.values():
                _gather(v, seen)
        for inst in self._this_stack or []:
            _gather(inst, seen)

        # Terminate anything not in keep_ids
        for inst in candidates:
            if id(inst) in keep_ids:
                continue
            try:
                inst._cls.terminate_instance(self, inst)
            except Exception:
                pass


    def _collect_dim_decls(self, stmts, out: list):
        # Collect DimStmt decls recursively (for Option Explicit predecl).
        for s in stmts or []:
            if isinstance(s, DimStmt):
                out.extend(s.decls)
                continue
            if isinstance(s, Block):
                self._collect_dim_decls(s.stmts, out)
                continue
            if isinstance(s, IfStmt):
                self._collect_dim_decls(s.then_block, out)
                for (_c, b) in s.elseif_parts:
                    self._collect_dim_decls(b, out)
                self._collect_dim_decls(s.else_block, out)
                continue
            if isinstance(s, WhileStmt):
                self._collect_dim_decls(s.body, out)
                continue
            if isinstance(s, DoWhileStmt):
                self._collect_dim_decls(s.body, out)
                continue
            if isinstance(s, DoLoopStmt):
                self._collect_dim_decls(s.body, out)
                continue
            if isinstance(s, ForStmt):
                self._collect_dim_decls(s.body, out)
                continue
            if isinstance(s, ForEachStmt):
                self._collect_dim_decls(s.body, out)
                continue
            if isinstance(s, SelectCaseStmt):
                for cc in s.cases:
                    self._collect_dim_decls(cc.body, out)
                self._collect_dim_decls(s.else_block, out)
                continue


    def _collect_proc_defs(self, stmts, out: list):
        for s in stmts or []:
            if isinstance(s, (ClassDef, SubDef, FuncDef)):
                out.append(s)
                continue
            if isinstance(s, Block):
                self._collect_proc_defs(s.stmts, out)
                continue
            if isinstance(s, IfStmt):
                self._collect_proc_defs(s.then_block, out)
                for (_c, b) in s.elseif_parts:
                    self._collect_proc_defs(b, out)
                self._collect_proc_defs(s.else_block, out)
                continue
            if isinstance(s, WhileStmt):
                self._collect_proc_defs(s.body, out)
                continue
            if isinstance(s, DoWhileStmt):
                self._collect_proc_defs(s.body, out)
                continue
            if isinstance(s, DoLoopStmt):
                self._collect_proc_defs(s.body, out)
                continue
            if isinstance(s, ForStmt):
                self._collect_proc_defs(s.body, out)
                continue
            if isinstance(s, ForEachStmt):
                self._collect_proc_defs(s.body, out)
                continue
            if isinstance(s, SelectCaseStmt):
                for cc in s.cases:
                    self._collect_proc_defs(cc.body, out)
                self._collect_proc_defs(s.else_block, out)
                continue


    def _predeclare_dim_decls(self, frame: dict[str, Any], decls):
        # Create declared names in frame/env with Empty/arrays.
        for d in decls or []:
            if not isinstance(d, DimDecl):
                continue
            nm = d.name # parser ensures upper
            if nm in frame:
                continue
            if d.bounds is None:
                frame[nm] = VBEmpty
                continue
            if d.bounds == []:
                frame[nm] = VBArray([-1], allocated=False, dynamic=True)
                continue
            ubs = []
            for b in d.bounds:
                try:
                    ub = _try_number(self.eval_expr(b))
                except Exception:
                    ub = 0
                if ub is None:
                    ub = 0
                ubs.append(int(ub))
            frame[nm] = VBArray(ubs, allocated=True, dynamic=False)


    def _set_ident(self, up: str, value, *, is_set: bool = False):
        if not is_set and isinstance(value, VBArray):
            value = value.clone()
        # Inside class procedures, assignment to a declared field should update
        # the instance field (not create a local).
        if self._this_stack:
            try:
                inst = self._this_stack[-1]
                if isinstance(inst, VBClassInstance) and up in inst._cls.all_fields:
                    inst._fields[up] = value
                    return
            except Exception:
                pass

        if up in self._consts:
            raise VBScriptRuntimeError("Assignment to constant")
        # If ident exists in current local frame, assign there (respect ByRef).
        if self._locals_stack and up in self._locals_stack[-1]:
            frame = self._locals_stack[-1]
            cur = frame[up]
            if isinstance(cur, _ByRef):
                cur.set(value)
            else:
                frame[up] = value
            return

        # Inside class procedures, assignment to a property should invoke Let/Set
        if self._this_stack:
            try:
                inst = self._this_stack[-1]
                if isinstance(inst, VBClassInstance) and (up in inst._cls.public_props or up in inst._cls.private_props):
                    inst.vbs_set_member(self, up, value, is_set=False)
                    return
            except Exception:
                pass
        if up in self.env:
            cur = self.env[up]
            if isinstance(cur, _ByRef):
                cur.set(value)
            else:
                self.env[up] = value
            return
        if self.option_explicit:
            raise VBScriptRuntimeError(f"Variable is undefined: '{up}'")

        # New var: create in current scope.
        if self._locals_stack:
            self._locals_stack[-1][up] = value
        else:
            self.env[up] = value

        # New binding overwrote nothing; no terminate.


    def _register_proc(self, name: str, kind: str, params, body):
        up = name # parser ensures upper
        proc = _UserProc(name, kind, params, body)
        self._procs[up] = proc
        # Expose in env as callable.
        self.env[up] = proc


    def _register_class(self, cls_def: ClassDef):
        c = VBClassDef(str(cls_def.original_name))
        prop_names: set[str] = set()
        var_names: set[str] = set()
        proc_names: set[str] = set()
        for m in cls_def.members:
            if isinstance(m, ClassVarDecl):
                nm = m.name # parser ensures upper
                if nm in prop_names or nm in var_names or nm in proc_names:
                    raise VBScriptRuntimeError("Name redefined")
                var_names.add(nm)
                vis = str(getattr(m, 'visibility', 'PUBLIC')).upper()
                # Remember array bounds for declared array fields.
                try:
                    b = getattr(m, 'bounds', None)
                    if b is not None:
                        c.field_bounds[nm] = b
                except Exception:
                    pass
                if vis == 'PRIVATE':
                    c.private_fields.add(nm)
                else:
                    c.public_fields.add(nm)
                c.all_fields.add(nm)
                continue

            if isinstance(m, SubDef):
                vis = str(getattr(m, 'visibility', 'PUBLIC')).upper()
                nm = m.name # parser ensures upper
                if nm in var_names or nm in proc_names:
                    raise VBScriptRuntimeError("Name redefined")
                proc_names.add(nm)
                proc = _UserProc(m.name, 'SUB', m.params, m.body)
                if bool(getattr(m, 'is_default', False)) and vis != 'PRIVATE':
                    c.default_method = proc
                if vis == 'PRIVATE':
                    c.private_methods[nm] = proc
                else:
                    c.public_methods[nm] = proc
                continue

            if isinstance(m, FuncDef):
                vis = str(getattr(m, 'visibility', 'PUBLIC')).upper()
                nm = m.name # parser ensures upper
                if nm in var_names or nm in proc_names:
                    raise VBScriptRuntimeError("Name redefined")
                proc_names.add(nm)
                proc = _UserProc(m.name, 'FUNCTION', m.params, m.body)
                if bool(getattr(m, 'is_default', False)) and vis != 'PRIVATE':
                    c.default_method = proc
                if vis == 'PRIVATE':
                    c.private_methods[nm] = proc
                else:
                    c.public_methods[nm] = proc
                continue

            if isinstance(m, PropertyDef):
                vis = str(getattr(m, 'visibility', 'PUBLIC')).upper()
                nm = m.name # parser ensures upper
                if nm in var_names:
                    raise VBScriptRuntimeError("Name redefined")
                prop_names.add(nm)
                kind = str(m.kind).upper()
                # Property Get behaves like a Function returning property name.
                proc_kind = 'FUNCTION' if kind == 'GET' else 'SUB'
                proc = _UserProc(m.name, proc_kind, m.params, m.body)
                props = c.private_props if vis == 'PRIVATE' else c.public_props
                if nm not in props:
                    props[nm] = {}
                props[nm][kind] = proc

                if bool(getattr(m, 'is_default', False)) and vis != 'PRIVATE' and kind == 'GET':
                    c.default_prop_get = proc
                    c.default_prop_name = nm
                continue

        up = str(cls_def.name).upper() # Class name itself (internal uppercase key)
        self._classes[up] = c
        # Expose class name in env for convenience (VBScript treats it as type name).
        self.env[up] = c


    def _resolve_default_prop_let(self, inst: VBClassInstance, prefer: str = 'LET'):
        """Resolve the Property Let/Set for a class's Default parameterised
        property, used by  obj(key) = value  /  Set obj(key) = value.

        `prefer` selects which accessor to try first ('LET' for value
        assignment, 'SET' for object assignment); VBScript falls back to the
        other accessor when only one is defined.
        """
        cls = inst._cls
        name_up = cls.default_prop_name
        if name_up is None:
            return None
        procs = cls.public_props.get(name_up)
        if procs is None and inst._can_access_private(self):
            procs = cls.private_props.get(name_up)
        if not procs:
            return None
        if prefer == 'SET':
            return procs.get('SET') or procs.get('LET')
        return procs.get('LET') or procs.get('SET')


    def _invoke_class_proc(self, inst: VBClassInstance, proc: _UserProc, arg_items, by_value_args: bool = False):
        # arg_items: list[Expr] when by_value_args=False; list[values] when True
        frame: dict[str, Any] = {}

        # Bind fields first (so params/local can override).
        for f in inst._cls.all_fields:
            ff = f # parser ensures upper
            frame[ff] = _ByRef(lambda k=ff: inst._fields.get(k, VBEmpty), lambda v, k=ff: inst._fields.__setitem__(k, v))

        frame['ME'] = inst

        fn_name = proc.name # parser ensures upper
        if proc.kind == 'FUNCTION':
            frame[fn_name] = VBEmpty

        if self.option_explicit:
            decls = []
            self._collect_dim_decls(proc.body, decls)
            self._predeclare_dim_decls(frame, decls)

        for i, p in enumerate(proc.params):
            pnm = p.name # parser ensures upper
            if i < len(arg_items):
                if by_value_args:
                    frame[pnm] = arg_items[i]
                else:
                    if p.byval:
                        frame[pnm] = self.eval_expr(arg_items[i])
                    else:
                        if isinstance(arg_items[i], Ident):
                            try:
                                raw = self._get_var_raw(arg_items[i].name)
                                if isinstance(raw, (_UserProc, _BoundMethod)):
                                    tmp = f"__BYREF_TMP_{pnm}_{i}"
                                    frame[tmp] = self.eval_expr(arg_items[i])
                                    frame[pnm] = _ByRef(lambda t=tmp: frame[t], lambda v, t=tmp: frame.__setitem__(t, v))
                                    continue
                            except Exception:
                                pass
                        try:
                            frame[pnm] = self._make_byref(arg_items[i])
                        except Exception:
                            tmp = f"__BYREF_TMP_{pnm}_{i}"
                            frame[tmp] = self.eval_expr(arg_items[i])
                            frame[pnm] = _ByRef(lambda t=tmp: frame[t], lambda v, t=tmp: frame.__setitem__(t, v))
            else:
                frame[pnm] = VBEmpty

        prev_onerr = self.on_error_resume_next
        self.on_error_resume_next = False
        self._locals_stack.append(frame)
        self._this_stack.append(inst)
        self._proc_name_stack.append(proc.name) # parser ensures upper
        rv_value = VBEmpty
        try:
            for s in proc.body:
                self.exec_stmt(s)
        except _ExitFunction:
            pass
        except _ExitSub:
            pass
        except _ExitProperty:
            pass
        finally:
            # Capture return value before terminating locals; otherwise a
            # returned object could be prematurely Class_Terminate'd.
            if proc.kind == 'FUNCTION':
                rv = frame.get(fn_name, VBEmpty)
                rv_value = rv.get() if isinstance(rv, _ByRef) else rv

            self._terminate_frame_objects(frame, keep=rv_value)
            self._this_stack.pop()
            self._locals_stack.pop()
            self._proc_name_stack.pop()
            self.on_error_resume_next = prev_onerr

        if proc.kind == 'FUNCTION':
            return rv_value
        return VBEmpty



    def _make_byref(self, arg_expr):
        if isinstance(arg_expr, Ident):
            nm = arg_expr.name # parser ensures upper
            # If the identifier is already a ByRef alias (e.g. a ByRef parameter),
            # pass the alias through unchanged to preserve ByRef chaining.
            if self._locals_stack and nm in self._locals_stack[-1]:
                frame = self._locals_stack[-1]
                cur = frame[nm]
                if isinstance(cur, _ByRef):
                    return cur
                return _ByRef(lambda f=frame, k=nm: f[k], lambda v, f=frame, k=nm: f.__setitem__(k, v))
            if nm in self.env:
                cur = self.env[nm]
                if isinstance(cur, _ByRef):
                    return cur
                return _ByRef(lambda k=nm: self.env[k], lambda v, k=nm: self.env.__setitem__(k, v))

            # Not found: ByRef requires a variable.
            raise VBScriptRuntimeError('ByRef argument must be a variable')

        if isinstance(arg_expr, Member):
            # Only allow simple obj.member ByRef; complex member expressions
            # should be treated as ByVal (VBScript uses a temp).
            if not isinstance(arg_expr.obj, Ident):
                raise VBScriptRuntimeError('ByRef argument must be a variable')
            obj_expr = arg_expr.obj
            mem_name = arg_expr.name
            # If member resolves to a function/method, it is not a variable;
            # force ByVal by raising here.
            o = None
            try:
                o = self.eval_expr(obj_expr)
                if isinstance(o, _ByRef):
                    o = o.get()
                if isinstance(o, VBClassInstance):
                    raw = o._vbs_get_member_raw(self, mem_name)
                    if isinstance(raw, _BoundMethod):
                        raise VBScriptRuntimeError('ByRef argument must be a variable')
                else:
                    # Host object: check attribute and treat callables as non-variables
                    attr = None
                    if hasattr(o, mem_name):
                        attr = getattr(o, mem_name)
                    else:
                        attr = _icase_getattr(o, mem_name.upper())
                    if callable(attr):
                        raise VBScriptRuntimeError('ByRef argument must be a variable')
            except VBScriptRuntimeError:
                raise
            except Exception:
                pass
            if o is None:
                raise VBScriptRuntimeError('ByRef argument must be a variable')
            # Capture object reference at bind time to preserve caller context.
            target_obj = o
            def _get_member():
                o2 = target_obj
                if isinstance(o2, VBClassInstance):
                    return o2.vbs_get_member(self, mem_name)
                o2_any = cast(Any, o2)
                get_prop = getattr(o2_any, 'vbs_get_prop', None)
                if get_prop is not None:
                    return get_prop(mem_name)
                _iv = _icase_getattr(o2_any, mem_name.upper())
                if _iv is not _ICASE_MISSING:
                    return _iv
                return getattr(o2_any, mem_name)
            def _set_member(v):
                o2 = target_obj
                if isinstance(o2, VBClassInstance):
                    return o2.vbs_set_member(self, mem_name, v, is_set=False)
                o2_any = cast(Any, o2)
                set_prop = getattr(o2_any, 'vbs_set_prop', None)
                if set_prop is not None:
                    return set_prop(mem_name, v)
                _rn2 = _icase_real_name(o2_any, mem_name.upper())
                if _rn2 is not None:
                    setattr(o2_any, _rn2, v)
                    return
                setattr(o2_any, mem_name, v)
            return _ByRef(_get_member, _set_member)

        if isinstance(arg_expr, Index):
            # Only allow simple arrayvar(idx) ByRef; complex index expressions
            # should be treated as ByVal.
            if not isinstance(arg_expr.obj, Ident):
                raise VBScriptRuntimeError('ByRef argument must be a variable')
            obj_expr = arg_expr.obj
            idx_args = arg_expr.args
            o = self.eval_expr(obj_expr)
            if isinstance(o, _ByRef):
                o = o.get()
            idx_vals = [self.eval_expr(a) for a in idx_args]
            def _get_index():
                if hasattr(o, '__vbs_index_get__'):
                    if len(idx_vals) == 1:
                        return o.__vbs_index_get__(idx_vals[0])
                    return o.__vbs_index_get__(idx_vals)
                return VBEmpty
            def _set_index(v):
                if hasattr(o, '__vbs_index_set__'):
                    if len(idx_vals) == 1:
                        return o.__vbs_index_set__(idx_vals[0], v)
                    return o.__vbs_index_set__(idx_vals, v)
                raise VBScriptRuntimeError('Target is not index-assignable')
            return _ByRef(_get_index, _set_index)

        raise VBScriptRuntimeError('ByRef argument must be a variable')


    def _invoke_user_proc(self, proc: _UserProc, arg_exprs):
        # Bind parameters (VBScript default is ByRef).
        frame: dict[str, Any] = {}
        fn_name = proc.name # parser ensures upper
        if proc.kind == 'FUNCTION':
            frame[fn_name] = VBEmpty

        if self.option_explicit:
            decls = []
            self._collect_dim_decls(proc.body, decls)
            self._predeclare_dim_decls(frame, decls)

        # evaluate/bind args
        for i, p in enumerate(proc.params):
            pnm = p.name # parser ensures upper
            if i < len(arg_exprs):
                if p.byval:
                    frame[pnm] = self.eval_expr(arg_exprs[i])
                else:
                    # If argument is an identifier that resolves to a procedure,
                    # treat it as an expression (VBScript passes the result).
                    if isinstance(arg_exprs[i], Ident):
                        try:
                            raw = self._get_var_raw(arg_exprs[i].name)
                            if isinstance(raw, (_UserProc, _BoundMethod)):
                                tmp = f"__BYREF_TMP_{pnm}_{i}"
                                frame[tmp] = self.eval_expr(arg_exprs[i])
                                frame[pnm] = _ByRef(lambda t=tmp: frame[t], lambda v, t=tmp: frame.__setitem__(t, v))
                                continue
                        except Exception:
                            pass
                    try:
                        frame[pnm] = self._make_byref(arg_exprs[i])
                    except Exception:
                        # VBScript allows passing expressions to ByRef parameters;
                        # bind them to a temporary local.
                        tmp = f"__BYREF_TMP_{pnm}_{i}"
                        frame[tmp] = self.eval_expr(arg_exprs[i])
                        frame[pnm] = _ByRef(lambda t=tmp: frame[t], lambda v, t=tmp: frame.__setitem__(t, v))
            else:
                frame[pnm] = VBEmpty

        prev_onerr = self.on_error_resume_next
        prev_this_stack = self._this_stack
        # Save ASP location context so errors inside procedures point to the
        # correct file/line (the procedure's definition, not the caller's).
        prev_asp_path = getattr(self, '_current_asp_path', None)
        prev_asp_line = getattr(self, '_current_asp_line', None)
        prev_asp_col = getattr(self, '_current_asp_col', None)
        prev_asp_src = getattr(self, '_current_vbs_src', None)
        if proc.asp_file is not None:
            self._current_asp_path = proc.asp_file
        if proc.asp_line is not None:
            self._current_asp_line = proc.asp_line
        if proc.asp_src is not None:
            self._current_vbs_src = proc.asp_src

        # Global procedures should not resolve unqualified names against class members.
        self._this_stack = []
        self.on_error_resume_next = False
        self._locals_stack.append(frame)
        self._proc_name_stack.append(proc.name) # parser ensures upper
        rv_value = VBEmpty
        _proc_error = False
        try:
            for s in proc.body:
                self.exec_stmt(s)
        except _ExitFunction:
            pass
        except _ExitSub:
            pass
        except _ExitProperty:
            pass
        except Exception:
            _proc_error = True
            raise
        finally:
            if proc.kind == 'FUNCTION':
                rv = frame.get(fn_name, VBEmpty)
                rv_value = rv.get() if isinstance(rv, _ByRef) else rv

            self._terminate_frame_objects(frame, keep=rv_value)
            self._locals_stack.pop()
            self.on_error_resume_next = prev_onerr
            self._this_stack = prev_this_stack
            self._proc_name_stack.pop()
            # Only restore ASP location context on success.
            # When an error is propagating, keep the procedure's context
            # so _attach_location can read the correct file/line.
            if not _proc_error:
                self._current_asp_path = prev_asp_path
                self._current_asp_line = prev_asp_line
                self._current_asp_col = prev_asp_col
                self._current_vbs_src = prev_asp_src

        if proc.kind == 'FUNCTION':
            return rv_value
        return VBEmpty


# Exact-type dispatch table for eval_expr. Keyed on the concrete AST node class
# (all dispatched nodes are leaf subclasses of Expr), this replaces the linear
# isinstance() cascade in _eval_expr_slow with a single O(1) dict lookup.
VBInterpreter._EXPR_DISPATCH = {
    StringLit: VBInterpreter._eval_stringlit,
    NumberLit: VBInterpreter._eval_numberlit,
    DateLit: VBInterpreter._eval_datelit,
    BoolLit: VBInterpreter._eval_boollit,
    Ident: VBInterpreter._eval_ident,
    NewExpr: VBInterpreter._eval_newexpr,
    Member: VBInterpreter._eval_member,
    Index: VBInterpreter._eval_index,
    CallExpr: VBInterpreter._eval_callexpr,
    Call: VBInterpreter._eval_call,
    Concat: VBInterpreter._eval_concat,
    UnaryOp: VBInterpreter._eval_unaryop,
    BinaryOp: VBInterpreter._eval_binaryop,
}


def _try_number(v):
    # Fast path: real numbers are by far the most common operand type in
    # arithmetic-heavy loops. `bool` is a subclass of int, so it is screened
    # out first (True/False must map to -1/0, not 1/0).
    t = v.__class__
    if t is int or t is float:
        return v
    if v is VBEmpty or v is VBNothing:
        return 0
    if v is VBNull:
        return None
    if isinstance(v, bool):
        return -1 if v else 0
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, _Decimal):
        # Currency (from CCur): treat numerically as Double so arithmetic and
        # comparisons work (Python's exact Decimal==float would wrongly report
        # CCur(123.45) <> 123.45, and `+` would fall back to concatenation).
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if s == "":
            return 0
        try:
            if '.' in s:
                return float(s)
            return int(s)
        except Exception:
            return None
    return None


def _try_truthy(v):
    # VBScript-like truthiness (minimal): empty string/0/False => False
    if v is VBEmpty or v is VBNull or v is VBNothing or v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v != ""
    return bool(v)


def _compare(op: str, a, b):
    # Minimal coercion: numeric if both look numeric, else string compare.
    # Important: do NOT treat empty strings as numeric 0 for comparisons.
    # VBScript code frequently uses: If Trim(x) = "" Then ...
    # and expects "0" to NOT equal "".
    if a is VBNull or b is VBNull:
        return VBNull
    # Short-circuit: both strings => compare directly without numeric conversion attempt
    if isinstance(a, str) and isinstance(b, str):
        sa = vbs_cstr(a)
        sb = vbs_cstr(b)
        if op == '=':
            return sa == sb
        if op == '<>':
            return sa != sb
        if op == '<':
            return sa < sb
        if op == '<=':
            return sa <= sb
        if op == '>':
            return sa > sb
        if op == '>=':
            return sa >= sb
    a_is_empty_str = isinstance(a, str) and a.strip() == ""
    b_is_empty_str = isinstance(b, str) and b.strip() == ""
    an = None if a_is_empty_str else _try_number(a)
    bn = None if b_is_empty_str else _try_number(b)
    if an is not None and bn is not None:
        if op == '=':
            return an == bn
        if op == '<>':
            return an != bn
        if op == '<':
            return an < bn
        if op == '<=':
            return an <= bn
        if op == '>':
            return an > bn
        if op == '>=':
            return an >= bn
    sa = vbs_cstr(a)
    sb = vbs_cstr(b)
    if op == '=':
        return sa == sb
    if op == '<>':
        return sa != sb
    if op == '<':
        return sa < sb
    if op == '<=':
        return sa <= sb
    if op == '>':
        return sa > sb
    if op == '>=':
        return sa >= sb
    raise VBScriptRuntimeError("Unknown compare op")
_debug_tls = threading.local()
