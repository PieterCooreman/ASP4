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
from . import vb_python as _vb_python
from . import adodb as _adodb
from .adodb import close_all_connections
from . import vb_builtins_stub as _vb_builtins_stub
from .vb_builtins_instrrev import InStrRev as _InStrRev
from .asp_page import parse_asp_page, exec_asp_nodes, parse_asp_file_to_nodes, compile_asp_nodes, ScriptNode, IncludeNode, ExprNode, HtmlNode, DirectiveNode, _attach_location
from .asp_cache import get_cached_asp_nodes
from .ast_nodes import ClassDef, SubDef, FuncDef, OptionExplicitStmt
from .vm.context import ExecutionContext
from .server_object import ServerTransferException, make_asp_error
from .asp_include import IncludeError
import hashlib as _hashlib
import os
from .ast_nodes import StringLit
from .vm.interpreter import VBInterpreter, _UserProc
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
    'ASPPY': vb_json.ASPPYShim(),
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

# Pre-inject builtins from vb_builtins_stub and vb_builtins_instrrev so that
# _build_globals_env does not need to do per-request hasattr/getattr probes.
# setdefault: the stub only FILLS GAPS (ScriptEngine, GetObject, Sgn, ...).
# It must not shadow real implementations - many stub entries are lazy-import
# wrappers around vb_datetime/vb_builtins (per-call import overhead) and some
# (Sgn/Sin/Tan) use looser float() coercion than the real VBScript semantics.
for _name in dir(_vb_builtins_stub):
    if _name.startswith('_'):
        continue
    _v = getattr(_vb_builtins_stub, _name)
    if callable(_v):
        _STATIC_ENV_TEMPLATE.setdefault(_name.upper(), _v)

_STATIC_ENV_TEMPLATE['INSTRREV'] = _InStrRev
# NB: bind vb_builtins.CBool, not the raw vbs_cbool coercion helper. CBool(Null)
# must raise Invalid use of Null (94) like IIS; vbs_cbool would quietly yield
# False.
_STATIC_ENV_TEMPLATE['CBOOL'] = vb_builtins.CBool

# Ensure VB string constants are in the template (belt-and-suspenders;
# they should already be injected via vb_constants, but guarantee it).
_STATIC_ENV_TEMPLATE.setdefault('VBCRLF', "\r\n")
_STATIC_ENV_TEMPLATE.setdefault('VBLF', "\n")
_STATIC_ENV_TEMPLATE.setdefault('VBCR', "\r")
_STATIC_ENV_TEMPLATE.setdefault('VBNEWLINE', "\r\n")
_STATIC_ENV_TEMPLATE.setdefault('VBTAB', "\t")
_STATIC_ENV_TEMPLATE.setdefault('VBVERTICALTAB', "\v")
_STATIC_ENV_TEMPLATE.setdefault('VBFORMFEED', "\f")
_STATIC_ENV_TEMPLATE.setdefault('VBNULLCHAR', "\0")
_STATIC_ENV_TEMPLATE.setdefault('VBNULLSTRING', "")
_STATIC_ENV_TEMPLATE.setdefault('VBUSEDEFAULT', -2)
_STATIC_ENV_TEMPLATE.setdefault('VBTRUE', -1)
_STATIC_ENV_TEMPLATE.setdefault('VBFALSE', 0)

# Re-assert VBScript language constants LAST. The dir()-based module scans
# above also pick up each module's own Python-level imports (e.g. the
# VBNull/VBEmpty/VBNothing sentinels imported by vb_builtins/vb_builtins_stub,
# or the VBArray class from vb_array_funcs). Those leaked names would
# otherwise shadow the real VBScript constants vbNull (=1), vbEmpty (=0) and
# vbArray (=8192). The Null/Empty/Nothing *keywords* are unaffected (they map
# to the NULL/EMPTY/NOTHING env entries above).
for _name in dir(vb_constants):
    if _name.startswith('_'):
        continue
    _cval = getattr(vb_constants, _name)
    _STATIC_ENV_TEMPLATE[_name] = _cval
    _STATIC_ENV_TEMPLATE[_name.upper()] = _cval

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

    # Publish this request's docroot for ASPPY.ExecutePythonFile, which resolves
    # relative paths against the web root and sandboxes them there by default.
    # This is the single choke point every entry point (server.py, asppycli.py,
    # render_asp_vm) funnels through, so the thread-local always matches the
    # request currently executing on this thread.
    try:
        _srv = ctx.Server
        _vb_python.set_current_docroot(getattr(_srv, '_docroot', '') if _srv is not None else '')
    except Exception:
        pass

    
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

    # Make cookies set via Response.Cookies visible through Request.Cookies
    # within the same request (IIS Classic ASP behavior).
    if request is not None:
        try:
            request.Cookies._attach_response(resp)
        except Exception:
            pass

    if session is not None:
        try:
            resp.SetCookie("ASP_PY_SESSIONID", getattr(session, 'CookieID', getattr(session, 'SessionID', '')))
        except Exception:
            pass
            
    # Reset thread-local state (LCID, ADO connections) to ensure clean execution
    # even if the server reuses threads (Keep-Alive), then re-seed the script
    # engine locale from Session.LCID the way IIS does at the start of a request.
    vbs_set_lcid(0)
    if session is not None:
        try:
            if getattr(session, '_lcid', 0):
                vbs_set_lcid(session._lcid)
        except Exception:
            pass
    
    env = _build_globals_env(ctx)
    interp = VBInterpreter(ctx, env)
    ctx.Interpreter = interp

    # Determine root path
    # If server is provided, we can map the request path.
    # Otherwise, fallback to parsing `vb_text` (monolithic fallback for testing).
    
    root_path = None
    script_path = request.Path if request else '/'
    if server:
        # Prefer server's current path if available, as it might be the resolved file
        # while request.Path might be the original URL.
        # Check server._current_path (which is passed as 'script_name' to Server init)
        if hasattr(server, '_current_path') and server._current_path:
             script_path = server._current_path
             root_path = server.MapPath(script_path)
             # Set current path on Response for relative Redirects
             if hasattr(resp, '_current_path'):
                 resp._current_path = script_path
        elif request:
             script_path = getattr(request, 'ScriptPath', request.Path)
             root_path = server.MapPath(script_path)
             if hasattr(resp, '_current_path'):
                 resp._current_path = script_path
    
    # Predeclare common globals that scripts expect to be uppercased
    # This fixes issues where scripts rely on implicit globals like 'GREET'
    # without declaring them, and our new strict parser/runtime case handling
    # might miss them if not initialized.
    # Actually, the issue 'Variable is undefined: GREET' implies Option Explicit is on
    # or the variable was never assigned.
    # If it's a global variable defined in global.asa or similar, it needs to be injected.
    
    try:
        if root_path and server:
            # Granular Execution Path
            exec_file_granular(root_path, server._docroot, script_path, interp)
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
        try:
            if not getattr(e, 'asp_start_line', 0):
                _attach_location(
                    e,
                    interp,
                    int(getattr(interp, '_current_asp_line', 1) or 1),
                    int(getattr(interp, '_current_asp_col', 1) or 1),
                    str(getattr(interp, '_current_vbs_src', '') or ''),
                    str(getattr(interp, '_current_asp_path', script_path or '/unknown.asp') or '/unknown.asp'),
                )
        except Exception:
            pass
        # Generate IIS-style error page
        asp_err = make_asp_error(script_path or '/unknown.asp', e)
        
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
            resp._finalize_headers()
        except Exception: pass

    res.body = bytes(body_out)
    return res


_MAX_INCLUDE_DEPTH = 32


def _native_sha256_digest(s: str) -> str:
    """SHA-256 the way QuickerSite's includes/sha256.asp computes it.

    That script hashes one byte per character, taken via AscB(Mid(s, i, 1)) -
    in this runtime the first byte of the character's UTF-16LE encoding - with
    a bit length of Len(s) * 8, and returns lowercase hex. That is exactly a
    plain SHA-256 over that byte stream.
    """
    s = str(s)  # collapse IStringList (str subclass w/ value-based __iter__) to its text
    data = bytearray()
    for c in s:
        data.append(c.encode('utf-16le')[0])
    return _hashlib.sha256(bytes(data)).hexdigest()


# Verdicts of runtime verification, keyed by a hash of the VBScript source
# block that defined SHA256. True: the interpreted implementation matched the
# native digest on all probes, so the native fast path may be used. False: it
# diverged (someone customized sha256.asp), so every call runs interpreted.
# Editing the file changes the source hash, which triggers re-verification.
_sha256_verified_sources: dict = {}

# Probe inputs covering the empty string, an ordinary password, a >1-block
# message (64-byte boundary) and a non-ASCII character.
_SHA256_PROBES = ("", "admin", "x" * 65, "caf\u00e9")


class _VerifiedNativeSha256(_UserProc):
    """Drop-in replacement for the hoisted VBScript SHA256 _UserProc.

    Being a _UserProc, it uses the interpreter's normal invoke() dispatch and
    can therefore delegate to the original interpreted implementation whenever
    the native fast path is not proven equivalent for this exact source text.
    """

    def __init__(self, original: _UserProc):
        super().__init__(original.name, original.kind, original.params, original.body)
        self._dim_decls = original._dim_decls
        self.asp_file = original.asp_file
        self.asp_line = original.asp_line
        self.asp_src = original.asp_src
        self._original = original
        src = original.asp_src if isinstance(original.asp_src, str) else ''
        self._src_key = _hashlib.sha256(src.encode('utf-8', 'replace')).hexdigest() if src else None

    def _verify(self, interp) -> bool:
        """Run the interpreted SHA256 against known inputs once per source text."""
        if self._src_key is None:
            return False
        verdict = _sha256_verified_sources.get(self._src_key)
        if verdict is not None:
            return verdict
        verdict = True
        try:
            for probe in _SHA256_PROBES:
                got = interp._invoke_user_proc(self._original, [StringLit(probe)])
                if got != _native_sha256_digest(probe):
                    verdict = False
                    break
        except Exception:
            verdict = False
        _sha256_verified_sources[self._src_key] = verdict
        return verdict

    def invoke(self, interp, arg_exprs):
        # Match the interpreted proc's arity behavior exactly.
        if len(arg_exprs) == 1 and self._verify(interp):
            try:
                arg = interp.eval_expr(arg_exprs[0])
            except Exception:
                return interp._invoke_user_proc(self._original, arg_exprs)
            if isinstance(arg, str):
                return _native_sha256_digest(arg)
            # Non-string arguments (Null, objects, numbers...) keep the exact
            # interpreted semantics, including its error behavior.
        return interp._invoke_user_proc(self._original, arg_exprs)


def _install_native_proc_overrides(interp):
    """Wrap hot hoisted VBScript procs in verified native fast paths.

    Runs after hoisting on every request (the interpreter and its _procs table
    are rebuilt per request). Pages that never define SHA256 are untouched.
    """
    p = interp._procs.get('SHA256')
    if isinstance(p, _UserProc) and not isinstance(p, _VerifiedNativeSha256):
        wrapped = _VerifiedNativeSha256(p)
        interp._procs['SHA256'] = wrapped
        interp.env['SHA256'] = wrapped


def _include_cycle_message(stack, node) -> str:
    """Name the file that closes the loop, and show the chain that got there."""
    chain = [os.path.basename(p) for p in stack] + [os.path.basename(node.path)]
    return "Include cycle: %s (%s)" % (node.virtual, " -> ".join(chain))


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
    # Walk the include tree and register all Subs/Functions/Classes/Dim.
    # Results are cached on ScriptNode objects so subsequent requests
    # skip the expensive _collect_proc_defs/_collect_dim_decls walks.
    
    from .vm.interpreter import _UserProc
    
    # Definitions are idempotent, so each file is hoisted at most once. Cycles
    # are caught by the include STACK, not by this set - see run() below for why
    # the distinction matters.
    hoisted: set = set()

    def collect(n_list, cur_virt_path, stack=()):
        for n in n_list:
            if isinstance(n, IncludeNode):
                if n.path in stack:
                    e = IncludeError(_include_cycle_message(stack, n))
                    _attach_location(e, interp, n.start_line, n.start_col, "", cur_virt_path)
                    raise e
                inc_nodes = get_cached_asp_nodes(n.path, parse_fn)
                if inc_nodes is None:
                    e = IncludeError(f"Include file not found: {n.virtual}")
                    _attach_location(e, interp, n.start_line, n.start_col, "", cur_virt_path)
                    raise e
                if n.path in hoisted:
                    continue
                hoisted.add(n.path)
                collect(inc_nodes, n.virtual, stack + (n.path,))
            elif isinstance(n, ScriptNode):
                # Ensure program is parsed (cached on node after first request)
                if n.program is None:
                    try:
                        n.program, _ = compile_asp_nodes([n])
                    except Exception as e:
                        _attach_location(e, interp, n.start_line, n.start_col, n.code, cur_virt_path)
                        raise

                if not n.program:
                    continue

                # Cache the collect results on the node to avoid
                # re-walking the AST on every request.
                if not hasattr(n, '_cached_collect') or n._cached_collect is None:
                    has_option_explicit = False
                    for s in n.program:
                        if isinstance(s, OptionExplicitStmt):
                            has_option_explicit = True
                            break
                    dim_decls = []
                    interp._collect_dim_decls(n.program, dim_decls)
                    proc_defs = []
                    interp._collect_proc_defs(n.program, proc_defs)
                    n._cached_collect = (has_option_explicit, dim_decls, proc_defs)

                has_opt_exp, cached_dims, cached_procs = n._cached_collect

                if has_opt_exp:
                    interp.option_explicit = True

                if interp.option_explicit and cached_dims:
                    interp._predeclare_dim_decls(interp.env, cached_dims)

                # Register procs and tag with ASP source location
                for s in cached_procs:
                    interp.exec_stmt(s)
                    proc_name = s.name.upper() if hasattr(s, 'name') else None
                    if proc_name and proc_name in interp._procs:
                        p = interp._procs[proc_name]
                        if isinstance(p, _UserProc):
                            p.asp_file = cur_virt_path
                            p.asp_line = int(n.start_line)
                            p.asp_src = n.code

    collect(nodes, virt_path)

    # Wrap hot hoisted procs (sha256) in content-verified native fast paths.
    _install_native_proc_overrides(interp)

    # 3. Execute Global Code
    # We walk the tree again and execute statements.
    
    def run(n_list, cur_virt_path, stack=()):
        for n in n_list:
            if isinstance(n, IncludeNode):
                # Cycle detection uses the CURRENT include chain, not a set of
                # everything seen so far. A global "visited" set also suppressed
                # legitimate repeats: including the same snippet twice on one
                # page emitted it once here and twice on IIS.
                if n.path in stack:
                    e = IncludeError(_include_cycle_message(stack, n))
                    _attach_location(e, interp, n.start_line, n.start_col, "", cur_virt_path)
                    raise e
                if len(stack) >= _MAX_INCLUDE_DEPTH:
                    e = IncludeError(
                        "Include nesting deeper than %d levels" % _MAX_INCLUDE_DEPTH)
                    _attach_location(e, interp, n.start_line, n.start_col, "", cur_virt_path)
                    raise e
                inc_nodes = get_cached_asp_nodes(n.path, parse_fn)
                if inc_nodes is None:
                    e = IncludeError(f"Include file not found: {n.virtual}")
                    _attach_location(e, interp, n.start_line, n.start_col, "", cur_virt_path)
                    raise e
                run(inc_nodes, n.virtual, stack + (n.path,))
            elif isinstance(n, DirectiveNode):
                # <%@ LCID=... CODEPAGE=... %> - same effect as assigning
                # Response.LCID / Response.CodePage at the top of the page.
                try:
                    if n.lcid is not None:
                        resp.SetProperty("LCID", n.lcid)
                    if n.codepage is not None:
                        resp.SetProperty("CODEPAGE", n.codepage)
                except Exception:
                    pass
            elif isinstance(n, ScriptNode):
                interp._current_vbs_src = n.code
                interp._current_asp_path = cur_virt_path
                interp._current_asp_line = int(n.start_line)
                interp._current_asp_col = int(n.start_col)
                # Ensure program is parsed (if missed in collect for some reason, though collect should have done it)
                if n.program is None:
                    try:
                        n.program, _ = compile_asp_nodes([n])
                    except Exception as e:
                        _attach_location(e, interp, n.start_line, n.start_col, n.code, cur_virt_path)
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
                            _attach_location(e, interp, n.start_line, n.start_col, n.code, cur_virt_path)
                            raise
            elif isinstance(n, ExprNode):
                interp._current_vbs_src = n.expr
                interp._current_asp_path = cur_virt_path
                interp._current_asp_line = int(n.start_line)
                interp._current_asp_col = int(n.start_col)
                # We need to compile expression on the fly?
                # ExprNode just has string.
                # `compile_asp_nodes` turned this into Response.Write.
                # But here we are running granularly.
                # We should pre-compile ExprNode too?
                # Or just parse and eval it now.
                try:
                    # Cache the parsed expression AST on the node to avoid
                    # re-parsing on every request for the same page.
                    if not hasattr(n, '_cached_expr_ast') or n._cached_expr_ast is None:
                        from .parser import Parser
                        n._cached_expr_ast = Parser(n.expr).parse_expression()
                    expr_ast = n._cached_expr_ast
                    val = interp.eval_expr(expr_ast)
                    interp.ctx.Response.Write(val)
                except Exception as e:
                    _attach_location(e, interp, n.start_line, n.start_col, n.expr, cur_virt_path)
                    raise
            elif hasattr(n, 'text'): # HtmlNode
                # Assuming HtmlNode
                interp.ctx.Response.Write(n.text)

    run(nodes, virt_path)
