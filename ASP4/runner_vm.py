"""ASP runner that uses the VM interpreter (no Python exec)."""

from __future__ import annotations

from .http_response import RenderResult, Response, ResponseEndException
from .vb_runtime import (
    vbs_cstr,
    vbs_cbool,
    vbs_not,
    vbs_and,
    vbs_or,
    vbs_xor,
    vbs_eqv,
    vbs_imp,
    vbs_eq,
    vbs_neq,
    vbs_lt,
    vbs_lte,
    vbs_gt,
    vbs_gte,
    vbs_set_lcid,
)
from . import vb_datetime, vb_constants
from . import vb_array_funcs
from . import vb_builtins
from . import vb_json
from . import adodb as _adodb
from .adodb import close_all_connections
from .asp_page import parse_asp_page, exec_asp_nodes, parse_asp_file_to_nodes, compile_asp_nodes, ScriptNode, IncludeNode, ExprNode, HtmlNode, _attach_location
from .asp_cache import get_cached_asp_nodes
from .ast_nodes import ClassDef, SubDef, FuncDef, OptionExplicitStmt
from .vm.context import ExecutionContext
from .server_object import ServerTransferException, make_asp_error
from .asp_include import IncludeError
import os
from .vm.interpreter import VBInterpreter
from .vm.values import VBNothing, VBEmpty, VBNull


# Pre-build static environment template to avoid repeated overhead per request.
_STATIC_ENV_TEMPLATE = {
    'TRUE': -1,
    'FALSE': 0,
    'NULL': VBNull,
    'EMPTY': VBEmpty,
    'NOTHING': VBNothing,
    'VBS_CSTR': vbs_cstr,
    'VBS_CBOOL': vbs_cbool,
    'VBS_NOT': vbs_not,
    'VBS_AND': vbs_and,
    'VBS_OR': vbs_or,
    'VBS_XOR': vbs_xor,
    'VBS_EQV': vbs_eqv,
    'VBS_IMP': vbs_imp,
    'VBS_EQ': vbs_eq,
    'VBS_NEQ': vbs_neq,
    'VBS_LT': vbs_lt,
    'VBS_LTE': vbs_lte,
    'VBS_GT': vbs_gt,
    'VBS_GTE': vbs_gte,
    'ASP4': vb_json.ASP4Shim(),
}

# (Re-inject all constants - copied from backup for completeness)
for name in dir(vb_datetime):
    if name.startswith('_'): continue
    _STATIC_ENV_TEMPLATE[name] = getattr(vb_datetime, name)
    _STATIC_ENV_TEMPLATE[name.upper()] = getattr(vb_datetime, name)
for name in dir(vb_constants):
    if name.startswith('_'): continue
    _STATIC_ENV_TEMPLATE[name] = getattr(vb_constants, name)
    _STATIC_ENV_TEMPLATE[name.upper()] = getattr(vb_constants, name)
for name in dir(vb_array_funcs):
    if name.startswith('_'): continue
    _STATIC_ENV_TEMPLATE[name.upper()] = getattr(vb_array_funcs, name)
for name in dir(vb_builtins):
    if name.startswith('_'): continue
    v = getattr(vb_builtins, name)
    if callable(v): _STATIC_ENV_TEMPLATE[name.upper()] = v
    else: _STATIC_ENV_TEMPLATE[name.upper()] = v
for _name in dir(_adodb):
    if _name.startswith('ad') and not _name.startswith('_'):
        val = getattr(_adodb, _name)
        if isinstance(val, int):
            _STATIC_ENV_TEMPLATE[_name.upper()] = val
            _STATIC_ENV_TEMPLATE[_name] = val

def _build_globals_env(ctx: ExecutionContext):
    # Start with static template copy
    env = _STATIC_ENV_TEMPLATE.copy()
    
    # Inject dynamic context
    env['RESPONSE'] = ctx.Response
    env['REQUEST'] = ctx.Request
    env['SERVER'] = ctx.Server
    env['SESSION'] = ctx.Session
    env['APPLICATION'] = ctx.Application
    env['ERR'] = ctx.Err
    
    # Context-bound helpers
    env['GETREF'] = lambda name: ctx._getref(name)
    def _create_object(progid):
        # We need to access ctx.Server safely; _build_globals_env's ctx is closed-over.
        return ctx.Server.CreateObject(vbs_cstr(progid))
    env['CREATEOBJECT'] = _create_object
    env['CreateObject'] = _create_object # legacy key if needed
    
    # Explicitly ensure VBCRLF is available if missing from template
    if 'VBCRLF' not in env:
        env['VBCRLF'] = "\r\n"
    if 'VBLF' not in env:
        env['VBLF'] = "\n"
    if 'VBCR' not in env:
        env['VBCR'] = "\r"
    if 'VBNEWLINE' not in env:
        env['VBNEWLINE'] = "\r\n"
    if 'VBTAB' not in env:
        env['VBTAB'] = "\t"
    if 'VBVERTICALTAB' not in env:
        env['VBVERTICALTAB'] = "\v"
    if 'VBFORMFEED' not in env:
        env['VBFORMFEED'] = "\f"
    if 'VBNULLCHAR' not in env:
        env['VBNULLCHAR'] = "\0"
    if 'VBNULLSTRING' not in env:
        env['VBNULLSTRING'] = ""
    if 'VBUSEDEFAULT' not in env:
        env['VBUSEDEFAULT'] = -2
    if 'VBTRUE' not in env:
        env['VBTRUE'] = -1
    if 'VBFALSE' not in env:
        env['VBFALSE'] = 0
    
    # Standard string functions that some scripts expect to be uppercased in env
    # (Though builtins logic should handle them via global lookup, explicit presence is safer)
    for name in ('LEFT', 'RIGHT', 'MID', 'LEN', 'UCASE', 'LCASE', 'TRIM', 'LTRIM', 'RTRIM', 
                 'INSTR', 'INSTRREV', 'REPLACE', 'SPLIT', 'JOIN', 'SPACE', 'STRING', 'STRREVERSE',
                 'ASC', 'ASCB', 'ASCW', 'CHR', 'CHRB', 'CHRW', 'CBYTE', 'CINT', 'CLNG', 'CSNG',
                 'CDBL', 'CBOOL', 'CDATE', 'CCUR', 'CSTR', 'HEX', 'OCT', 'FIX', 'INT', 'ABS',
                 'SGN', 'SQR', 'SIN', 'COS', 'TAN', 'ATN', 'LOG', 'EXP', 'RND', 'RANDOMIZE',
                 'TIMER', 'NOW', 'DATE', 'TIME', 'DAY', 'MONTH', 'YEAR', 'HOUR', 'MINUTE', 'SECOND',
                 'DATEADD', 'DATEDIFF', 'DATEPART', 'DATESERIAL', 'DATEVALUE', 'TIMESERIAL', 'TIMEVALUE',
                 'WEEKDAY', 'WEEKDAYNAME', 'MONTHNAME', 'ISARRAY', 'ISDATE', 'ISEMPTY', 'ISNULL',
                 'ISNUMERIC', 'ISOBJECT', 'TYPENAME', 'VARTYPE', 'UBOUND', 'LBOUND', 'ARRAY',
                 'FILTER',                  'FORMATCURRENCY', 'FORMATDATETIME', 'FORMATNUMBER', 'FORMATPERCENT',
                 'ROUND', 'RGB', 'SCRIPTENGINE', 'SCRIPTENGINEBUILDVERSION', 'SCRIPTENGINEMAJORVERSION',
                 'SCRIPTENGINEMINORVERSION', 'CREATEOBJECT', 'GETOBJECT', 'EVAL', 'EXECUTE', 'EXECUTEGLOBAL',
                 'STRCOMP', 'INSTRB'):
        if name not in env:
            # Look in vb_builtins or other modules
            try:
                # Most are in vb_builtins
                if hasattr(vb_builtins, name.title()) and callable(getattr(vb_builtins, name.title())):
                     env[name] = getattr(vb_builtins, name.title())
                elif hasattr(vb_builtins, name) and callable(getattr(vb_builtins, name)):
                     env[name] = getattr(vb_builtins, name)
                # Check vb_builtins_stub for rest
                from . import vb_builtins_stub
                if hasattr(vb_builtins_stub, name.title()) and callable(getattr(vb_builtins_stub, name.title())):
                     env[name] = getattr(vb_builtins_stub, name.title())
            except Exception:
                pass
    
    # Pre-inject CBOOL explicitly to ensure it's available despite any import issues
    if 'CBOOL' not in env:
        try:
            from .vb_runtime import vbs_cbool
            env['CBOOL'] = vbs_cbool
        except Exception:
            pass
    if 'STRREVERSE' not in env:
        try:
            from .vb_builtins import StrReverse
            env['STRREVERSE'] = StrReverse
        except Exception:
            pass
    if 'STRCOMP' not in env:
        try:
            from .vb_builtins import StrComp
            env['STRCOMP'] = StrComp
        except Exception:
            pass
    if 'INSTRB' not in env:
        try:
            from .vb_builtins import InStrB
            env['INSTRB'] = InStrB
        except Exception:
            pass
    if 'FORMATCURRENCY' not in env:
        try:
            from .vb_builtins_stub import FormatCurrency
            env['FORMATCURRENCY'] = FormatCurrency
        except Exception:
            pass
    if 'FORMATPERCENT' not in env:
        try:
            from .vb_builtins_stub import FormatPercent
            env['FORMATPERCENT'] = FormatPercent
        except Exception:
            pass
    if 'FORMATDATETIME' not in env:
        try:
            from .vb_builtins_stub import FormatDateTime
            env['FORMATDATETIME'] = FormatDateTime
        except Exception:
            pass
    if 'SCRIPTENGINE' not in env:
        try:
            from .vb_builtins_stub import ScriptEngine
            env['SCRIPTENGINE'] = ScriptEngine
        except Exception:
            pass
    if 'SCRIPTENGINEBUILDVERSION' not in env:
        try:
            from .vb_builtins_stub import ScriptEngineBuildVersion
            env['SCRIPTENGINEBUILDVERSION'] = ScriptEngineBuildVersion
        except Exception:
            pass
    if 'SCRIPTENGINEMAJORVERSION' not in env:
        try:
            from .vb_builtins_stub import ScriptEngineMajorVersion
            env['SCRIPTENGINEMAJORVERSION'] = ScriptEngineMajorVersion
        except Exception:
            pass
    if 'SCRIPTENGINEMINORVERSION' not in env:
        try:
            from .vb_builtins_stub import ScriptEngineMinorVersion
            env['SCRIPTENGINEMINORVERSION'] = ScriptEngineMinorVersion
        except Exception:
            pass
    if 'INSTRREV' not in env:
        try:
            from .vb_builtins_instrrev import InStrRev
            env['INSTRREV'] = InStrRev
        except Exception:
            pass
    if 'EVAL' not in env:
        try:
            # Eval is special, handled by interpreter, but if script expects it in env for GetRef or similar
            # In VBScript, Eval is an intrinsic.
            pass
        except Exception:
            pass
    if 'VARTYPE' not in env:
        try:
            from .vb_builtins import VarType
            env['VARTYPE'] = VarType
        except Exception:
            pass
    if 'TYPENAME' not in env:
        try:
            from .vb_builtins import TypeName
            env['TYPENAME'] = TypeName
        except Exception:
            pass
    if 'ARRAY' not in env:
        try:
            from .vb_builtins import Array
            env['ARRAY'] = Array
        except Exception:
            pass
    if 'FILTER' not in env:
        try:
            from .vb_builtins import Filter
            env['FILTER'] = Filter
        except Exception:
            pass
    
    if 'VBTAB' not in env:



        env['VBTAB'] = "\t"
    if 'VBVERTICALTAB' not in env:
        env['VBVERTICALTAB'] = "\v"
    if 'VBFORMFEED' not in env:
        env['VBFORMFEED'] = "\f"
    if 'VBNULLCHAR' not in env:
        env['VBNULLCHAR'] = "\0"
    if 'VBNULLSTRING' not in env:
        env['VBNULLSTRING'] = ""
    if 'VBUSEDEFAULT' not in env:
        env['VBUSEDEFAULT'] = -2
    if 'VBTRUE' not in env:
        env['VBTRUE'] = -1
    if 'VBFALSE' not in env:
        env['VBFALSE'] = 0

    try:
        app = ctx.Application
        if app is not None and hasattr(app, '_static_objects'):
            for k, v in getattr(app, '_static_objects').items():
                env[str(k).upper()] = v
    except Exception: pass
    try:
        sess = ctx.Session
        if sess is not None and hasattr(sess, '_static_objects'):
            for k, v in getattr(sess, '_static_objects').items():
                env[str(k).upper()] = v
    except Exception: pass
    return env


def render_asp_vm(vb_text: str, request=None, session=None, application=None, server=None, session_is_new: bool = False, on_context_created=None) -> RenderResult:
    """Entry point for executing an ASP request.
    
    vb_text: The RAW CONTENT of the requested file (not expanded).
             Wait, currently `server.py` passes raw content?
             If `server.py` passed expanded content, `vb_text` is huge.
             
             If we use Granular Compilation, `render_asp_vm` should ideally take the PATH, 
             not the text, to leverage the cache.
             But `server.py` reads the file.
             
             To support `server.py` without major refactoring, we can allow `vb_text` to be the
             path or we can ignore `vb_text` if we can derive the path from `request.Path`.
             
             Actually, `server.py` passes the file content.
             If we want to use the cache, we need the path.
             `server` object has `_current_path`.
    """
    res = RenderResult()
    body_out = bytearray()
    resp = Response(res, body_out)

    ctx = ExecutionContext(response=resp, request=request, session=session, application=application, server=server)
    if on_context_created:
        on_context_created(ctx)

    if session is not None and session_is_new:
        try:
            resp.SetCookie("ASP_PY_SESSIONID", getattr(session, 'CookieID', getattr(session, 'SessionID', '')))
        except Exception:
            pass
            
    # Reset thread-local state (LCID, ADO connections) to ensure clean execution
    # even if the server reuses threads (Keep-Alive).
    vbs_set_lcid(0)
    
    env = _build_globals_env(ctx)
    interp = VBInterpreter(ctx, env)
    ctx.Interpreter = interp

    # Determine root path
    # If server is provided, we can map the request path.
    # Otherwise, fallback to parsing `vb_text` (monolithic fallback for testing).
    
    root_path = None
    if server:
        # Prefer server's current path if available, as it might be the resolved file
        # while request.Path might be the original URL.
        # Check server._current_path (which is passed as 'script_name' to Server init)
        if hasattr(server, '_current_path') and server._current_path:
             root_path = server.MapPath(server._current_path)
             # Set current path on Response for relative Redirects
             if hasattr(resp, '_current_path'):
                 resp._current_path = server._current_path
        elif request:
             root_path = server.MapPath(request.Path)
             if hasattr(resp, '_current_path'):
                 resp._current_path = request.Path
    
    # Predeclare common globals that scripts expect to be uppercased
    # This fixes issues where scripts rely on implicit globals like 'GREET'
    # without declaring them, and our new strict parser/runtime case handling
    # might miss them if not initialized.
    # Actually, the issue 'Variable is undefined: GREET' implies Option Explicit is on
    # or the variable was never assigned.
    # If it's a global variable defined in global.asa or similar, it needs to be injected.
    
    try:
        if root_path:
            # Granular Execution Path
            exec_file_granular(root_path, server._docroot, request.Path if request else '/', interp)
        else:
            # Fallback: Parse raw text (monolithic or simple string)
            # This handles cases where vb_text is passed directly (tests).
            nodes = parse_asp_page(vb_text)
            
            # Register explicit/on error statements in interpreter
            # since monolithic exec_asp_nodes does not pre-scan recursively.
            # Actually, `exec_asp_nodes` does handle it.
            
            exec_asp_nodes(nodes, interp)
            
    except ResponseEndException:
        pass
    except ServerTransferException:
        # Server.Transfer stops execution of the current page.
        # It is not an error.
        pass
    except Exception as e:
        # Generate IIS-style error page
        asp_err = make_asp_error(request.Path if request else '/unknown.asp', e)
        
        # IIS 5.0 Style Error (approximate)
        # Format the error code as hex: e.g. 800a0409
        hex_code = f"{asp_err.Number:x}"
        
        # Clear any existing buffer content
        body_out.clear()
        
        # Set status 500
        res.status_code = 500
        res.status_message = "Internal Server Error"
        
        # Construct the caret line for the error source
        caret_line = ""
        if asp_err.Column > 0:
            caret_line = "-" * (asp_err.Column - 1) + "^"

        # Provide minimal HTML
        
        html_err = f"""<font face="Arial" size=2>
<p>{asp_err.Category} '{hex_code}'</p>
<p>{asp_err.Description}</p>
<p>{asp_err.File}, line {asp_err.Line}</p>
<p>{asp_err.Source}<br>
{caret_line}</p>
</font>"""
        resp.Write(html_err)
    finally:
        try:
            # Ensure any open ADO connections on this thread are closed
            # to prevent leaks or locks across requests.
            close_all_connections()
        except Exception:
            pass
        try:
            interp.end_request_cleanup()
        except Exception: pass
        try:
            resp.Flush()
        except Exception: pass
        try:
            resp.finalize_headers()
        except Exception: pass

    res.body = bytes(body_out)
    return res


def exec_file_granular(phys_path: str, docroot: str, virt_path: str, interp: VBInterpreter):
    """Execute an ASP file using granular compilation (caching ASTs)."""
    
    # 1. Load nodes (cached)
    def parse_fn(p):
        # We need to determine the virtual path of `p` relative to docroot
        rel = os.path.relpath(p, docroot).replace('\\', '/')
        vp = '/' + rel.lstrip('/')
        return parse_asp_file_to_nodes(p, docroot, vp)

    nodes = get_cached_asp_nodes(phys_path, parse_fn)
    if nodes is None:
        raise IncludeError(f"File not found: {phys_path}")
    
    # 2. Collect Definitions (Hoisting)
    # We must walk the include tree and register all Subs/Functions/Classes/Dim.
    # We must handle `IncludeNode` recursively.
    # To avoid cycles during collection, we track visited paths.
    
    visited = set()
    
    def collect(n_list):
        for n in n_list:
            if isinstance(n, IncludeNode):
                if n.path in visited:
                    continue
                visited.add(n.path)
                # Recurse
                inc_nodes = get_cached_asp_nodes(n.path, parse_fn)
                if inc_nodes is None:
                    e = IncludeError(f"Include file not found: {n.virtual}")
                    # Attach location of include directive in parent file
                    _attach_location(e, interp, n.start_line, n.start_col, "")
                    raise e
                collect(inc_nodes)
            elif isinstance(n, ScriptNode):
                # Ensure program is parsed
                if n.program is None:
                    # Granular parsing logic for isolated script blocks
                    # We treat each script block as a standalone snippet or part of a sequence.
                    # compile_asp_nodes handles parsing logic correctly.
                    # Since we are in granular mode, we don't have the context of previous blocks 
                    # combined into one string. But VBScript parser handles fragments fine
                    # as long as blocks don't split statements.
                    try:
                        n.program, _ = compile_asp_nodes([n])
                    except Exception:
                        # If parsing fails here, it might be due to split blocks.
                        # However, parse_asp_file_to_nodes attempts to merge split blocks.
                        # So if we are here, it should be parseable.
                        # If not, we can't do much but re-raise.
                        raise

                if n.program:
                    # Register defs
                    # We reuse logic from `exec_vbscript_program` but split it.
                    # We assume `ScriptNode` program is a valid AST list.
                    
                    # Handle Option Explicit (globally flag)
                    for s in n.program:
                        if isinstance(s, OptionExplicitStmt):
                            interp.option_explicit = True
                            break
                    
                    # Dims
                    if interp.option_explicit:
                        decls = []
                        interp._collect_dim_decls(n.program, decls)
                        interp._predeclare_dim_decls(interp.env, decls)
                        
                    # Procs
                    defs = []
                    interp._collect_proc_defs(n.program, defs)
                    for s in defs:
                        # print(f"DEBUG: Registering {s.name}")
                        interp.exec_stmt(s)

    collect(nodes)
    
    # 3. Execute Global Code
    # We walk the tree again and execute statements.
    
    visited_exec = set()
    
    def run(n_list):
        for n in n_list:
            if isinstance(n, IncludeNode):
                if n.path in visited_exec:
                    continue
                visited_exec.add(n.path)
                inc_nodes = get_cached_asp_nodes(n.path, parse_fn)
                if inc_nodes is None:
                    e = IncludeError(f"Include file not found: {n.virtual}")
                    _attach_location(e, interp, n.start_line, n.start_col, "")
                    raise e
                run(inc_nodes)
            elif isinstance(n, ScriptNode):
                # Ensure program is parsed (if missed in collect for some reason, though collect should have done it)
                if n.program is None:
                    try:
                        n.program, _ = compile_asp_nodes([n])
                    except Exception:
                        raise

                if n.program:
                    for s in n.program:
                        if isinstance(s, OptionExplicitStmt):
                            continue
                        if isinstance(s, (ClassDef, SubDef, FuncDef)):
                            continue
                        try:
                            interp.exec_stmt(s)
                        except Exception as e:
                            # Attach location info if missing
                            if getattr(e, 'vbs_pos', None) is None:
                                setattr(e, 'vbs_pos', getattr(s, '_pos', None))
                            raise
            elif isinstance(n, ExprNode):
                # We need to compile expression on the fly?
                # ExprNode just has string.
                # `compile_asp_nodes` turned this into Response.Write.
                # But here we are running granularly.
                # We should pre-compile ExprNode too?
                # Or just parse and eval it now.
                try:
                    # Small optim: cache compiled expr?
                    # For now, just parse.
                    # `Response.Write (expr)`
                    # We can use `interp.eval_expr` directly if we parse it as an expression!
                    # `parser.parse_expression` returns an expr AST.
                    from .parser import Parser
                    expr_ast = Parser(n.expr).parse_expression()
                    val = interp.eval_expr(expr_ast)
                    interp.ctx.Response.Write(val)
                except Exception as e:
                    # Fallback or error
                    interp.ctx.Response.Write(f"Error in expression: {e}")
            elif hasattr(n, 'text'): # HtmlNode
                # Assuming HtmlNode
                interp.ctx.Response.Write(n.text)

    run(nodes)
