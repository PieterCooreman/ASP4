"""Classic ASP Server object emulation (cross-platform)."""

from __future__ import annotations

import html
import glob
import os
import shutil
import uuid
import urllib.parse
from typing import Any, cast
import mimetypes
import datetime

from .vb_runtime import vbs_cstr, VBScriptRuntimeError
from .vb_errors import VBScriptError


def make_asp_error(request_path: str, exc: Exception) -> ASPError:
    from .parser import ParseError
    from .lexer import LexerError

    start_line = getattr(exc, 'asp_start_line', 0)
    start_col = getattr(exc, 'asp_start_col', 0)
    src_block = getattr(exc, 'asp_source_block', '')
    src_line = ''
    if src_block:
        # take first line of block for now
        lines = src_block.splitlines()
        src_line = lines[0] if lines else src_block

    number = 0x80004005
    category = "Microsoft VBScript runtime error" # Default to runtime error
    description = str(exc)

    if isinstance(exc, VBScriptError):
        if exc.error_def and exc.error_def.hex_code:
            try:
                number = int(exc.error_def.hex_code, 16)
            except ValueError:
                pass
        description = exc.description
        # Distinguish compilation vs runtime if possible
        # VBScriptCompilationError is a subclass of VBScriptError
        if "Compilation" in exc.__class__.__name__:
             category = "Microsoft VBScript compilation error"
        else:
             category = "Microsoft VBScript runtime error"

    elif isinstance(exc, (ParseError, LexerError)):
        # IIS: 800a03ea = VBScript compilation error (syntax)
        number = 0x800A03EA
        category = "Microsoft VBScript compilation error"

    else:
        # Default fallback for unknown python exceptions, but let's try to mimic
        # runtime error if it looks like one or just wrap it.
        # But the user asked to ALWAYS use Microsoft VBScript for consistency.
        # If it's a generic python error, we might label it "Microsoft VBScript runtime error"
        # and use a generic error code if we don't have one, or just keep asp.py
        # BUT the user specifically complained about "asp.py".
        # So let's force the category for standard exceptions too.
        category = "Microsoft VBScript runtime error"
        # 80004005 is "Unspecified error", which is standard for unmapped errors.

    return ASPError(
        number=number,
        description=description,
        category=category,
        asp_code="",
        asp_description="",
        file=request_path,
        line=start_line,
        column=start_col,
        source=src_line,
    )


class ServerTransferException(Exception):
    def __init__(self, target: str):
        super().__init__(target)
        self.target = target


class WScriptShell:
    def _unsupported(self, *_args, **_kwargs):
        raise VBScriptRuntimeError("WScript.Shell is not supported in ASP4")

    def __getattr__(self, _name):
        return self._unsupported

    def vbs_get_prop(self, _name: str):
        self._unsupported()

    def vbs_set_prop(self, _name: str, _value):
        self._unsupported()


class ASPError:
    """ASPError object returned by Server.GetLastError().

    Properties are intended to be read-only from VBScript.
    """

    def __init__(
        self,
        *,
        number: int = 0x80004005,
        description: str = "",
        category: str = "asp.py",
        asp_code: str = "",
        asp_description: str = "",
        file: str = "",
        line: int = 0,
        column: int = 0,
        source: str = "",
    ):
        self.ASPCode = asp_code
        self.ASPDescription = asp_description
        self.Category = category
        self.Column = int(column)
        self.Description = description
        self.File = file
        self.Line = int(line)
        self.Number = int(number)
        self.Source = source


class ScriptingDictionary:
    """Minimal Scripting.Dictionary adapter."""

    def __init__(self):
        # normalized_key -> (original_key, value)
        self._d: dict[str, tuple[str, Any]] = {}
        # 0=BinaryCompare (case-sensitive), 1=TextCompare (case-insensitive), 2=DatabaseCompare
        self._compare_mode = 0

    def _norm(self, key: str) -> str:
        k = vbs_cstr(key)
        if self._compare_mode == 0:
            return k
        return k.lower()

    @property
    def Count(self):
        return len(self._d)

    @property
    def CompareMode(self):
        return self._compare_mode

    @CompareMode.setter
    def CompareMode(self, value):
        v = int(value)
        if v not in (0, 1, 2):
            raise Exception("Invalid CompareMode")
        # Reindex existing keys if switching modes (preserve original casing)
        if v != self._compare_mode:
            items = list(self._d.values())
            self._d = {}
            self._compare_mode = v
            for orig, it in items:
                nk = self._norm(orig)
                self._d[nk] = (orig, it)
        else:
            self._compare_mode = v

    def Add(self, key, item):
        orig = vbs_cstr(key)
        k = self._norm(orig)
        if k in self._d:
            raise Exception("Key already exists")
        self._d[k] = (orig, item)

    def Exists(self, key):
        return self._norm(key) in self._d

    def Remove(self, key):
        k = self._norm(key)
        if k in self._d:
            del self._d[k]

    def RemoveAll(self):
        self._d.clear()

    def __vbs_index_get__(self, key):
        ent = self._d.get(self._norm(key))
        return ent[1] if ent is not None else ""

    def __vbs_index_set__(self, key, value):
        orig = vbs_cstr(key)
        nk = self._norm(orig)
        if nk in self._d:
            old_orig, _old_val = self._d[nk]
            self._d[nk] = (old_orig, value)
        else:
            self._d[nk] = (orig, value)

    @property
    def Item(self):
        # VBScript: Item is the default member (indexable).
        # This allows both reads:  d.Item("k")
        # and writes:             d.Item("k") = "v"
        return self

    @property
    def Keys(self):
        # Return a VBArray of keys
        try:
            from .vm.values import VBArray
        except Exception:
            return [k for (k, _v) in self._d.values()]
        keys = [k for (k, _v) in self._d.values()]
        a = VBArray(len(keys) - 1, allocated=True, dynamic=True)
        for i, k in enumerate(keys):
            a.__vbs_index_set__(i, k)
        return a

    @property
    def Items(self):
        try:
            from .vm.values import VBArray
        except Exception:
            return [v for (_k, v) in self._d.values()]
        items = [v for (_k, v) in self._d.values()]
        a = VBArray(len(items) - 1, allocated=True, dynamic=True)
        for i, v in enumerate(items):
            a.__vbs_index_set__(i, v)
        return a

    def __iter__(self):
        return iter([k for (k, _v) in self._d.values()])


class Server:
    def __init__(
        self,
        docroot: str,
        current_path: str,
        render_include_fn,
        last_error_getter=None,
        ctx_getter=None,
    ):
        self._docroot = os.path.abspath(docroot)
        self._current_path = current_path or "/"
        self._render_include_fn = render_include_fn
        self._last_error_getter = last_error_getter or (lambda: None)
        self._ctx_getter = ctx_getter
        self._script_timeout = 90

    @property
    def ScriptTimeout(self):
        return self._script_timeout

    @ScriptTimeout.setter
    def ScriptTimeout(self, value):
        self._script_timeout = int(value)

    def CreateObject(self, progid):
        pid = str(progid).strip().lower()
        if pid == "wscript.shell":
            return WScriptShell()
        if pid == "scripting.dictionary":
            return ScriptingDictionary()
        if pid == "scripting.filesystemobject":
            return FileSystemObject(self._docroot)
        if pid == "adodb.stream":
            return ADODBStream(self._docroot)
        if pid in ("vbscript.regexp", "regexp"):
            return VBScriptRegExp()
        if pid in ("msxml2.serverxmlhttp", "msxml2.serverxmlhttp.6.0", "msxml2.serverxmlhttp.3.0"):
            from .msxml import ServerXMLHTTP

            return ServerXMLHTTP()
        if pid in ("msxml2.xmlhttp", "msxml2.xmlhttp.6.0", "msxml2.xmlhttp.3.0"):
            from .msxml import XMLHTTP

            return XMLHTTP()
        if pid in ("msxml2.domdocument", "msxml2.domdocument.6.0", "msxml2.domdocument.3.0"):
            from .msxml import DOMDocument

            return DOMDocument(docroot=self._docroot)
        if pid in ("microsoft.xmldom", "msxml.domdocument"):
            from .msxml import DOMDocument

            return DOMDocument(docroot=self._docroot)
        if pid in ("cdo.message", "cdosys.message"):
            from .cdo import CDOMessage

            return CDOMessage(docroot=self._docroot)
        if pid in ("adodb.connection",):
            from .adodb import ADOConnection
            obj = ADOConnection(docroot=self._docroot)
            return obj
        if pid in ("adodb.recordset",):
            from .adodb import ADORecordset
            return ADORecordset()
        if pid in ("adodb.command",):
            from .adodb import ADOCommand
            return ADOCommand()
        raise Exception(f"Server.CreateObject not supported: {progid}")

    def HTMLEncode(self, s):
        # VBScript coerces Empty/Nothing/Null to an empty string in most
        # string contexts; avoid leaking sentinel reprs like "VBEmpty".
        return html.escape(vbs_cstr(s), quote=True)

    def URLEncode(self, s):
        # Use '+' for spaces like typical URL encoding
        return urllib.parse.quote_plus(vbs_cstr(s))

    def MapPath(self, path):
        p = str(path)
        # Remove querystring
        p = p.split('?', 1)[0]
        if p.startswith('~'):
            p = p[1:]

        if p.startswith('/') or p.startswith('\\'):
            rel = p.lstrip('/\\')
            target = os.path.abspath(os.path.join(self._docroot, rel))
        else:
            # Relative to current file
            cur_dir = os.path.dirname(self._current_path.lstrip('/\\'))
            target = os.path.abspath(os.path.join(self._docroot, cur_dir, p))

        # Prevent path traversal outside docroot
        if os.path.commonpath([self._docroot, target]) != self._docroot:
            raise Exception("Server.MapPath: path outside application")
        return target

    def Execute(self, path):
        # Include another ASP file and continue.
        self._render_include_fn(str(path), transfer=False)

    def Transfer(self, path):
        # Transfer control to another ASP file.
        # IIS keeps already-generated output (typically buffered) and stops executing
        # the current page.
        self._render_include_fn(str(path), transfer=True)
        raise ServerTransferException(str(path))

    def GetLastError(self):
        e = self._last_error_getter()
        if e is None:
            # IIS behavior: when no error occurred, properties are mostly blank/zero.
            return ASPError(
                number=0,
                description="",
                category="",
                asp_code="",
                asp_description="",
                file="",
                line=0,
                column=-1,
                source="",
            )
        if isinstance(e, ASPError):
            return e
        return ASPError(description=str(e))

    def ASP4ListAspPages(self):
        """asp.py extension: list .asp pages under docroot.

        Returns a VBArray of virtual paths like "/hello.asp".
        """
        try:
            from .vm.values import VBArray
        except Exception:
            VBArray = None

        paths = []
        for root, _dirs, files in os.walk(self._docroot):
            for fn in files:
                if not fn.lower().endswith('.asp'):
                    continue
                phys = os.path.join(root, fn)
                rel = os.path.relpath(phys, self._docroot)
                v = '/' + rel.replace('\\', '/').replace(os.sep, '/').lstrip('/')
                paths.append(v.lower())
        paths = sorted(set(paths))
        if VBArray is None:
            return paths
        a = VBArray(len(paths) - 1, allocated=True, dynamic=True)
        for i, p in enumerate(paths):
            a.__vbs_index_set__(i, p)
        return a

    def ASP4Run(self, virtual_path: str):
        """asp.py extension: render another ASP page and capture status.

        Runs in an isolated view of the current Session/Application (state is restored).
        """
        from .http_response import RenderResult, Response, ResponseEndException
        from .asp_page import parse_asp_page, exec_asp_nodes
        from .vm.context import ExecutionContext
        from .vm.interpreter import VBInterpreter
        from .runner_vm import _build_globals_env
        from .http_request import Request
        from .asp_include import expand_includes, IncludeError
        from .vb_err import VBErr

        target_v = str(virtual_path).strip() or "/"
        if not target_v.startswith('/'):
            target_v = '/' + target_v

        class ASP4RunResult:
            def __init__(self, path: str, status_code: int, status_message: str, error: str):
                self.Path = path
                self.StatusCode = int(status_code)
                self.StatusMessage = str(status_message or "")
                self.Error = str(error or "")

        parent_ctx = None
        if callable(self._ctx_getter):
            try:
                parent_ctx = self._ctx_getter()
            except Exception:
                parent_ctx = None

        sess = getattr(parent_ctx, 'Session', None) if parent_ctx is not None else None
        app = getattr(parent_ctx, 'Application', None) if parent_ctx is not None else None
        parent_req = getattr(parent_ctx, 'Request', None) if parent_ctx is not None else None

        sess_backing = None
        sess_static = None
        sess_abandoned = None
        app_backing = None
        app_static = None
        try:
            if sess is not None and hasattr(sess, '_backing'):
                sess_backing = dict(getattr(sess, '_backing'))
                sess_abandoned = bool(getattr(sess, '_abandoned', False))
                if hasattr(sess, '_static_objects'):
                    sess_static = dict(getattr(sess, '_static_objects'))
            if app is not None and hasattr(app, '_backing'):
                app_backing = dict(getattr(app, '_backing'))
                if hasattr(app, '_static_objects'):
                    app_static = dict(getattr(app, '_static_objects'))

            phys = self.MapPath(target_v)
            if not os.path.isfile(phys):
                return ASP4RunResult(target_v, 404, "Not Found", "")
            with open(phys, 'r', encoding='utf-8') as f:
                raw = f.read()

            try:
                raw = expand_includes(raw, current_phys=phys, docroot=self._docroot, current_virtual=target_v)
            except IncludeError as e:
                return ASP4RunResult(target_v, 500, "Internal Server Error", str(e))

            # Build a response for the child run.
            res = RenderResult()
            body_out = bytearray()
            resp = Response(res, body_out)

            holder = cast(dict[str, Any], {'interp': None, 'ctx': None})

            def render_include(target_path: str, transfer: bool = False):
                interp = holder['interp']
                # Map relative to current page.
                tmp_server = Server(self._docroot, target_v, render_include_fn=lambda *_a, **_k: None)
                inc_phys = tmp_server.MapPath(target_path)
                if not os.path.isfile(inc_phys):
                    raise Exception("Server.Execute/Transfer: file not found")
                with open(inc_phys, 'r', encoding='utf-8') as f2:
                    inc_text = f2.read()
                try:
                    inc_text = expand_includes(inc_text, current_phys=inc_phys, docroot=self._docroot, current_virtual=target_path)
                except IncludeError as e:
                    raise Exception(f"Include error: {e}")
                exec_asp_nodes(parse_asp_page(inc_text), interp)

            child_box = cast(dict[str, Any], {'ctx': None})
            child_srv = Server(self._docroot, target_v, render_include_fn=render_include, ctx_getter=lambda: child_box['ctx'])

            headers = {}
            remote = ""
            if parent_req is not None and hasattr(parent_req, '_headers'):
                try:
                    headers = dict(getattr(parent_req, '_headers'))
                except Exception:
                    headers = {}
            if parent_req is not None and hasattr(parent_req, '_remote_addr'):
                try:
                    remote = str(getattr(parent_req, '_remote_addr'))
                except Exception:
                    remote = ""
            req = Request('GET', target_v, '', headers, b'', remote_addr=remote)

            ctx = ExecutionContext(response=resp, request=req, session=sess, application=app, server=child_srv, err=VBErr())
            child_box['ctx'] = ctx
            env = _build_globals_env(ctx)
            interp = VBInterpreter(ctx, env)
            holder['interp'] = interp
            holder['ctx'] = ctx

            try:
                exec_asp_nodes(parse_asp_page(raw), interp)
            except (ServerTransferException, ResponseEndException):
                pass
            except Exception as e:
                res.status_code = 500
                res.status_message = 'Internal Server Error'
                resp.Write('Error during ASP execution: ' + str(e) + '\n')
                resp.Flush()
                resp.finalize_headers()
                res.body = bytes(body_out)
                return ASP4RunResult(target_v, res.status_code, res.status_message, str(e))
            finally:
                try:
                    resp.Flush()
                except Exception:
                    pass
                try:
                    resp.finalize_headers()
                except Exception:
                    pass
                res.body = bytes(body_out)

            return ASP4RunResult(target_v, res.status_code, res.status_message, "")
        finally:
            # Restore parent session/application state.
            try:
                if sess is not None and sess_backing is not None and hasattr(sess, '_backing'):
                    b = getattr(sess, '_backing')
                    b.clear()
                    b.update(sess_backing)
                    if sess_abandoned is not None:
                        setattr(sess, '_abandoned', bool(sess_abandoned))
                    if sess_static is not None and hasattr(sess, '_static_objects'):
                        so = getattr(sess, '_static_objects')
                        so.clear()
                        so.update(sess_static)
            except Exception:
                pass
            try:
                if app is not None and app_backing is not None and hasattr(app, '_backing'):
                    b = getattr(app, '_backing')
                    b.clear()
                    b.update(app_backing)
                    if app_static is not None and hasattr(app, '_static_objects'):
                        so = getattr(app, '_static_objects')
                        so.clear()
                        so.update(app_static)
            except Exception:
                pass


def _has_ads(path: str) -> bool:
    # Disallow NTFS alternate data streams ("file.txt:stream").
    # Allow a single drive letter colon prefix ("C:\...").
    p = str(path)
    if ':' not in p:
        return False
    if len(p) >= 2 and p[1] == ':':
        return p.count(':') != 1
    return True


class VBScriptRegExpSubMatches:
    def __init__(self, groups: list[str]):
        self._groups = list(groups)

    @property
    def Count(self):
        return len(self._groups)

    def Item(self, idx):
        i = int(idx)
        return self._groups[i]

    def __vbs_index_get__(self, idx):
        return self.Item(idx)

    def __iter__(self):
        return iter(self._groups)


class VBScriptRegExpMatch:
    def __init__(self, value: str, first_index: int, length: int, groups: list[str]):
        self.Value = value
        self.FirstIndex = int(first_index)
        self.Length = int(length)
        self.SubMatches = VBScriptRegExpSubMatches(groups)


class VBScriptRegExpMatches:
    def __init__(self, matches: list[VBScriptRegExpMatch]):
        self._matches = list(matches)

    @property
    def Count(self):
        return len(self._matches)

    def Item(self, idx):
        i = int(idx)
        return self._matches[i]

    def __vbs_index_get__(self, idx):
        return self.Item(idx)

    def __iter__(self):
        return iter(self._matches)


class VBScriptRegExp:
    """Minimal VBScript.RegExp shim (enough for common legacy apps)."""

    def __init__(self):
        self.Pattern = ""
        self.IgnoreCase = False
        self.Global = False
        self.MultiLine = False

    def _compile(self):
        import re

        flags = 0
        if bool(self.IgnoreCase):
            flags |= re.IGNORECASE
        if bool(self.MultiLine):
            flags |= re.MULTILINE
        try:
            return re.compile(vbs_cstr(self.Pattern), flags)
        except Exception as e:
            raise Exception(f"RegExp pattern error: {e}")

    def Test(self, s):
        r = self._compile()
        return r.search(vbs_cstr(s)) is not None

    def Replace(self, s, replace_with):
        r = self._compile()
        text = vbs_cstr(s)
        repl = vbs_cstr(replace_with)
        if bool(self.Global):
            return r.sub(repl, text)
        return r.sub(repl, text, count=1)

    def Execute(self, s):
        r = self._compile()
        text = vbs_cstr(s)
        out: list[VBScriptRegExpMatch] = []
        for m in r.finditer(text):
            groups = [g if g is not None else "" for g in m.groups()]
            out.append(VBScriptRegExpMatch(m.group(0), m.start(), m.end() - m.start(), groups))
            if not bool(self.Global):
                break
        return VBScriptRegExpMatches(out)


class ADODBStream:
    """Sandboxed ADODB.Stream shim.

    Implements the small subset used by legacy apps (read/write text and binary,
    load/save files).
    """

    # Common ADODB.Stream constants
    adTypeBinary = 1
    adTypeText = 2

    adSaveCreateNotExist = 1
    adSaveCreateOverWrite = 2

    def __init__(self, default_root: str):
        root = os.environ.get('ASP_PY_ADO_ROOT', '')
        self._root = os.path.abspath(root) if root else os.path.abspath(default_root)

        self._opened = False
        self._type = self.adTypeText
        # ADODB.Stream default Charset under Windows/ADO is typically "Unicode".
        self.Charset = "Unicode"
        # Default line separator for text streams (adCRLF).
        self.LineSeparator = "\r\n"
        self.Mode = 1
        self._pos = 0
        self._buf_text = ""
        self._buf_bin = bytearray()

    def _ensure_in_root(self, phys: str) -> str:
        phys = os.path.abspath(phys)
        if os.path.commonpath([self._root, phys]) != self._root:
            raise Exception("ADODB.Stream: path outside sandbox")
        return phys

    def _resolve(self, path: str) -> str:
        if _has_ads(path):
            raise Exception("ADODB.Stream: ADS not allowed")
        p = vbs_cstr(path).strip()
        if p.startswith('\\'):
            raise Exception("ADODB.Stream: UNC paths not supported")

        p_os = p.replace('\\', os.sep)

        # Absolute physical paths (including Server.MapPath output)
        if os.path.isabs(p_os):
            return self._ensure_in_root(p_os)

        # Windows drive-letter paths on non-Windows hosts: treat as sandbox-rooted.
        p_norm = p.replace('\\', '/')
        if len(p_norm) >= 3 and p_norm[1] == ':' and p_norm[2] == '/':
            rest = p_norm[3:]
            phys = os.path.join(self._root, rest)
            return self._ensure_in_root(phys)

        phys = os.path.join(self._root, p_os)
        return self._ensure_in_root(phys)

    @property
    def Type(self):
        return int(self._type)

    @Type.setter
    def Type(self, v):
        new_t = int(v)
        old_t = int(getattr(self, '_type', self.adTypeText))
        self._type = new_t
        self._pos = 0
        # Best-effort conversion between buffers to match common ADO.Stream usage:
        # - binary -> text: defer decoding until ReadText (Charset may be set after Type)
        # - text -> binary: encode text using Charset
        try:
            if old_t == self.adTypeBinary and new_t == self.adTypeText:
                # Keep binary buffer; decode lazily so setting Charset after
                # Type change behaves like ADO.Stream.
                self._buf_text = ""
            elif old_t == self.adTypeText and new_t == self.adTypeBinary:
                cs = vbs_cstr(getattr(self, 'Charset', '') or 'utf-8')
                try:
                    self._buf_bin = bytearray(vbs_cstr(self._buf_text).encode(cs, errors='replace'))
                except Exception:
                    self._buf_bin = bytearray(vbs_cstr(self._buf_text).encode('utf-8', errors='replace'))
        except Exception:
            pass

    @property
    def CharSet(self):
        return getattr(self, 'Charset', '')

    @CharSet.setter
    def CharSet(self, v):
        self.Charset = v

    @property
    def Position(self):
        return int(self._pos)

    @Position.setter
    def Position(self, v):
        n = int(v)
        if n < 0:
            n = 0
        self._pos = n

    @property
    def Size(self):
        # Some legacy scripts write raw bytes via WriteText into a text stream.
        # If binary buffer is populated, prefer it.
        if len(self._buf_bin) > 0 and (not self._buf_text):
            # ADO.Stream in text mode can report a size slightly larger than the
            # raw payload (implementation detail). This matches common IIS
            # behavior and keeps legacy upload scripts working.
            if self._type == self.adTypeText:
                return len(self._buf_bin) + 2
            return len(self._buf_bin)
        if self._type == self.adTypeBinary:
            return len(self._buf_bin)
        # Text stream: IIS/ADO often reports Size as character count + 2.
        try:
            cs = vbs_cstr(getattr(self, 'Charset', '') or '').strip().lower()
        except Exception:
            cs = ''
        if cs in ('unicode', 'utf-16', 'utf16', 'utf-16le', 'utf-16-le'):
            return len(vbs_cstr(self._buf_text)) + 2
        try:
            return len(vbs_cstr(self._buf_text).encode(vbs_cstr(self.Charset) or 'utf-8', errors='replace'))
        except Exception:
            return len(vbs_cstr(self._buf_text).encode('utf-8', errors='replace'))

    @property
    def EOS(self):
        return int(self._pos) >= int(self._effective_length())

    @property
    def State(self):
        # adStateClosed=0, adStateOpen=1
        return 1 if self._opened else 0

    def _effective_length(self) -> int:
        if len(self._buf_bin) > 0 and (not self._buf_text):
            return len(self._buf_bin)
        if self._type == self.adTypeBinary:
            return len(self._buf_bin)
        return len(vbs_cstr(self._buf_text))

    def _get_line_separator(self):
        ls = getattr(self, 'LineSeparator', "\r\n")
        if isinstance(ls, int):
            if ls == -1:
                return "\r\n"
            if ls == 10:
                return "\n"
            if ls == 13:
                return "\r"
            return "\r\n"
        s = vbs_cstr(ls)
        return s or "\r\n"

    def _text_bytes_for_io(self) -> bytes:
        """Encode text buffer to bytes for IO-like operations (CopyTo, SaveToFile).

        ADO.Stream text-to-bytes conversion can include a BOM for Unicode.
        """
        txt = vbs_cstr(self._buf_text)
        cs = vbs_cstr(getattr(self, 'Charset', '') or 'Unicode').strip()
        cs_l = cs.lower()
        if cs_l in ('unicode', 'utf-16', 'utf16', 'utf-16le', 'utf-16-le'):
            enc = 'utf-16-le'
            bom = b"\xff\xfe"
        elif cs_l in ('utf-8', 'utf8'):
            enc = 'utf-8'
            bom = b""
        elif cs_l in ('iso-8859-1', 'latin1', 'latin-1'):
            enc = 'latin-1'
            bom = b""
        elif cs_l in ('windows-1252', 'cp1252'):
            enc = 'cp1252'
            bom = b""
        else:
            enc = cs or 'utf-8'
            bom = b""
        try:
            return bom + txt.encode(enc, errors='replace')
        except Exception:
            return bom + txt.encode('utf-8', errors='replace')

    def Open(self):
        self._opened = True

    def Close(self):
        self._opened = False

    def Cancel(self):
        return

    def SetEOS(self):
        self._ensure_open()
        self._pos = int(self._effective_length())

    def SkipLine(self):
        self._ensure_open()
        sep = self._get_line_separator()
        if not sep:
            return

        if len(self._buf_bin) > 0 and (not self._buf_text):
            src = bytes(self._buf_bin)
            sep_b = sep.encode('latin-1', errors='replace')
            start = min(max(0, int(self._pos)), len(src))
            idx = src.find(sep_b, start)
            if idx == -1:
                self._pos = len(src)
            else:
                self._pos = idx + len(sep_b)
            return

        text = vbs_cstr(self._buf_text)
        start = min(max(0, int(self._pos)), len(text))
        idx = text.find(sep, start)
        if idx == -1:
            self._pos = len(text)
        else:
            self._pos = idx + len(sep)
        return

    def _ensure_open(self):
        if not self._opened:
            self.Open()

    def LoadFromFile(self, filename):
        self._ensure_open()
        phys = self._resolve(filename)
        if not os.path.isfile(phys):
            # Graceful fallback: if path ends with duplicate extension
            # (e.g. .inc.inc), try single extension.
            base, ext1 = os.path.splitext(phys)
            base2, ext2 = os.path.splitext(base)
            if ext1 and ext2 and ext1.lower() == ext2.lower():
                alt = base
                if os.path.isfile(alt):
                    phys = alt
        if self._type == self.adTypeBinary:
            with open(phys, 'rb') as f:
                self._buf_bin = bytearray(f.read())
            self._pos = 0
            return

        with open(phys, 'rb') as f:
            raw = f.read()
        cs = vbs_cstr(getattr(self, 'Charset', '') or 'utf-8')
        try:
            self._buf_text = raw.decode(cs, errors='replace')
        except Exception:
            self._buf_text = raw.decode('utf-8', errors='replace')
        self._pos = 0

    def SaveToFile(self, filename, option=adSaveCreateOverWrite):
        self._ensure_open()
        phys = self._resolve(filename)
        opt = int(option)
        if opt == self.adSaveCreateNotExist and os.path.exists(phys):
            raise Exception("ADODB.Stream: file already exists")

        os.makedirs(os.path.dirname(phys) or '.', exist_ok=True)

        if self._type == self.adTypeBinary or (len(self._buf_bin) > 0 and (not self._buf_text)):
            data = bytes(self._buf_bin)
            with open(phys, 'wb') as f:
                f.write(data)
            return

        cs = vbs_cstr(getattr(self, 'Charset', '') or 'utf-8')
        try:
            data = vbs_cstr(self._buf_text).encode(cs, errors='replace')
        except Exception:
            data = vbs_cstr(self._buf_text).encode('utf-8', errors='replace')
        with open(phys, 'wb') as f:
            f.write(data)

    def Read(self, count=None):
        self._ensure_open()
        if self._type == self.adTypeText:
            from .vb_runtime import VBScriptCOMError

            # Match ADODB.Stream behavior: Read() is not valid for text streams.
            raise VBScriptCOMError(-2147024809, "The parameter is incorrect.")
        if len(self._buf_bin) > 0 and (not self._buf_text):
            start = int(self._pos)
            # Compatibility: legacy upload scripts using ADODB.Stream in text mode
            # treat Position as 1-based when reading raw request bytes.
            if self._type == self.adTypeText and start > 0:
                start -= 1
            start = min(max(0, start), len(self._buf_bin))
            if count is None:
                out = bytes(self._buf_bin[start:])
                self._pos = len(self._buf_bin)
                return out
            n = int(count)
            if n < 0:
                n = 0
            out = bytes(self._buf_bin[start:start + n])
            self._pos = start + len(out)
            return out
        if self._type != self.adTypeBinary:
            # Best-effort: return encoded text.
            cs = vbs_cstr(getattr(self, 'Charset', '') or 'utf-8')
            try:
                b = vbs_cstr(self._buf_text).encode(cs, errors='replace')
            except Exception:
                b = vbs_cstr(self._buf_text).encode('utf-8', errors='replace')
            start = min(self._pos, len(b))
            if count is None:
                out = b[start:]
                self._pos = len(b)
                return out
            n = int(count)
            if n < 0:
                n = 0
            out = b[start:start + n]
            self._pos = start + len(out)
            return out

        start = min(self._pos, len(self._buf_bin))
        if count is None:
            out = bytes(self._buf_bin[start:])
            self._pos = len(self._buf_bin)
            return out
        n = int(count)
        if n < 0:
            n = 0
        out = bytes(self._buf_bin[start:start + n])
        self._pos = start + len(out)
        return out

    def ReadText(self, count=-1):
        self._ensure_open()
        if len(self._buf_bin) > 0 and (not self._buf_text):
            cs = vbs_cstr(getattr(self, 'Charset', '') or 'utf-8')
            start = int(self._pos)
            if self._type == self.adTypeText and start > 0:
                start -= 1
            start = min(max(0, start), len(self._buf_bin))
            n = int(count) if count is not None else -1
            if n < 0:
                chunk = bytes(self._buf_bin[start:])
                self._pos = len(self._buf_bin)
            else:
                chunk = bytes(self._buf_bin[start:start + n])
                self._pos = start + len(chunk)
            try:
                return chunk.decode(cs, errors='strict')
            except Exception:
                # Avoid raising here; callers often use On Error Resume Next.
                # Returning empty matches common ADO.Stream behavior when the
                # byte sequence isn't valid for the selected Charset.
                return ""
        # If we are in text mode but only binary data exists, decode lazily.
        if self._type == self.adTypeText and (not self._buf_text) and len(self._buf_bin) > 0:
            try:
                self.Type = self.adTypeText
            except Exception:
                pass
        text = vbs_cstr(self._buf_text)
        start = min(self._pos, len(text))
        n = int(count) if count is not None else -1
        if n < 0:
            out = text[start:]
            self._pos = len(text)
            return out
        out = text[start:start + n]
        self._pos = start + len(out)
        return out

    def Write(self, data):
        self._ensure_open()
        if self._type != self.adTypeBinary:
            # Best-effort: treat as bytes and append to text via latin-1.
            b = self._coerce_bytes(data)
            try:
                s = b.decode('latin-1')
            except Exception:
                s = ''
            return self.WriteText(s)

        b = self._coerce_bytes(data)
        pos = min(self._pos, len(self._buf_bin))
        end = pos + len(b)
        if end <= len(self._buf_bin):
            self._buf_bin[pos:end] = b
        else:
            if pos < len(self._buf_bin):
                self._buf_bin[pos:] = b
            else:
                self._buf_bin.extend(b)
        self._pos = end

    def WriteText(self, s):
        self._ensure_open()
        if isinstance(s, (bytes, bytearray)) and self._type == self.adTypeText:
            # Preserve bytes 1:1 in the binary buffer (upload scripts depend on this).
            b = bytes(s)
            pos = int(self._pos)
            if pos < 0:
                pos = 0
            if pos > len(self._buf_bin):
                self._buf_bin.extend(b"\x00" * (pos - len(self._buf_bin)))
            end = pos + len(b)
            if end <= len(self._buf_bin):
                self._buf_bin[pos:end] = b
            else:
                if pos < len(self._buf_bin):
                    self._buf_bin[pos:] = b
                else:
                    self._buf_bin.extend(b)
            self._pos = end
            # Mark text buffer as not authoritative.
            self._buf_text = ""
            return
        if self._type == self.adTypeBinary:
            return self.Write(self._coerce_bytes(s))

        ins = vbs_cstr(s)
        text = vbs_cstr(self._buf_text)
        pos = min(self._pos, len(text))
        if pos == 0:
            self._buf_text = ins
            self._pos = len(ins)
            return
        if pos >= len(text):
            self._buf_text = text + ins
            self._pos = len(self._buf_text)
            return
        self._buf_text = text[:pos] + ins + text[pos + len(ins):]
        self._pos = pos + len(ins)

    def CopyTo(self, dest_stream, count=None):
        """Copy bytes from this stream to dest_stream.

        Used heavily by legacy upload scripts.
        """
        self._ensure_open()
        if dest_stream is None:
            raise Exception("ADODB.Stream.CopyTo: dest is Nothing")

        # Get a byte view of the source.
        if len(self._buf_bin) > 0 and (not self._buf_text):
            src = bytes(self._buf_bin)
        elif self._type == self.adTypeBinary:
            src = bytes(self._buf_bin)
        else:
            src = self._text_bytes_for_io()

        start = int(self._pos)
        one_based = False
        if (len(self._buf_bin) > 0 and (not self._buf_text)) and self._type == self.adTypeText and start > 0:
            start -= 1
            one_based = True
        start = min(max(0, start), len(src))
        n = None
        if count is not None and str(count) != "":
            try:
                n = int(count)
            except Exception:
                n = None
        chunk = src[start:] if n is None else src[start:start + max(0, n)]
        self._pos = start + len(chunk) + (1 if one_based else 0)

        try:
            dest_stream.Write(chunk)
        except Exception:
            dest_stream.WriteText(chunk)

    def Flush(self):
        return

    def _coerce_bytes(self, data) -> bytes:
        if isinstance(data, (bytes, bytearray)):
            return bytes(data)
        if isinstance(data, (list, tuple)):
            return bytes(int(x) & 0xFF for x in data)
        # VBArray (from vm.values) best-effort
        try:
            if hasattr(data, '__vbs_index_get__') and hasattr(data, 'UBound'):
                ub = int(data.UBound(1))
                out = bytearray()
                for i in range(0, ub + 1):
                    out.append(int(data.__vbs_index_get__(i)) & 0xFF)
                return bytes(out)
        except Exception:
            pass
        try:
            return vbs_cstr(data).encode('latin-1')
        except Exception:
            return vbs_cstr(data).encode('utf-8', errors='replace')


class TextStream:
    def __init__(self, f):
        self._f = f

    def Close(self):
        if self._f is None:
            return
        try:
            self._f.close()
        finally:
            self._f = None

    @property
    def AtEndOfStream(self):
        if self._f is None:
            return True
        pos = self._f.tell()
        ch = self._f.read(1)
        self._f.seek(pos)
        return ch == ""

    def ReadAll(self):
        if self._f is None:
            return ""
        return self._f.read()

    def ReadLine(self):
        if self._f is None:
            return ""
        s = self._f.readline()
        if s.endswith("\r\n"):
            return s[:-2]
        if s.endswith("\n"):
            return s[:-1]
        return s

    def Write(self, s):
        if self._f is None:
            return
        self._f.write(vbs_cstr(s))

    def WriteLine(self, s=""):
        if self._f is None:
            return
        self._f.write(vbs_cstr(s) + "\r\n")


class Drive:
    def __init__(self, path: str):
        self.Path = path


class DrivesCollection:
    def __init__(self, drives: list[Drive]):
        self._drives = drives

    def __iter__(self):
        return iter(self._drives)

    @property
    def Count(self):
        return len(self._drives)


class File:
    def __init__(self, path: str):
        self.Path = path

    @property
    def Name(self):
        return os.path.basename(self.Path)

    @Name.setter
    def Name(self, new_name):
        nm = vbs_cstr(new_name).strip()
        if not nm:
            return
        nm = os.path.basename(nm)
        base = os.path.dirname(self.Path)
        dest = os.path.abspath(os.path.join(base, nm))
        src = os.path.abspath(self.Path)
        if dest == src:
            return
        try:
            os.replace(src, dest)
        except Exception:
            shutil.move(src, dest)
        self.Path = dest

    @property
    def Attributes(self):
        """Best-effort Scripting.File.Attributes bitmask.

        Windows: returns GetFileAttributesW value (shares common bit values with FSO).
        Non-Windows: approximates ReadOnly/Hidden/Directory/Archive.
        """
        p = self.Path
        try:
            if os.name == 'nt':
                import ctypes

                GetFileAttributesW = ctypes.windll.kernel32.GetFileAttributesW
                GetFileAttributesW.argtypes = [ctypes.c_wchar_p]
                GetFileAttributesW.restype = ctypes.c_uint32
                attrs = int(GetFileAttributesW(p))
                if attrs == 0xFFFFFFFF:
                    return 0
                return attrs
        except Exception:
            pass

        # Fallback approximation
        attrs = 0
        try:
            # Read-only
            if not os.access(p, os.W_OK):
                attrs |= 1
            # Hidden (unix-style)
            if os.path.basename(p).startswith('.'):
                attrs |= 2
            # Directory
            if os.path.isdir(p):
                attrs |= 16
            # Archive (treat as regular file)
            if os.path.isfile(p):
                attrs |= 32
        except Exception:
            return 0
        return attrs

    @property
    def Size(self):
        try:
            return os.path.getsize(self.Path)
        except Exception:
            return 0

    @property
    def DateCreated(self):
        try:
            ts = os.path.getctime(self.Path)
            return datetime.datetime.fromtimestamp(ts)
        except Exception:
            return None

    @property
    def DateLastAccessed(self):
        try:
            ts = os.path.getatime(self.Path)
            return datetime.datetime.fromtimestamp(ts)
        except Exception:
            return None

    @property
    def DateLastModified(self):
        try:
            ts = os.path.getmtime(self.Path)
            return datetime.datetime.fromtimestamp(ts)
        except Exception:
            return None

    @property
    def Drive(self):
        drive, _ = os.path.splitdrive(self.Path)
        if drive:
            root = drive
            if not root.endswith('\\') and not root.endswith('/'):
                root = root + '\\'
            return Drive(root)
        return Drive(self.Path)

    @property
    def ParentFolder(self):
        parent = os.path.dirname(self.Path)
        return Folder(parent) if parent else Folder(self.Path)

    @property
    def ShortName(self):
        p = self.Path
        try:
            if os.name == 'nt':
                import ctypes
                from ctypes import create_unicode_buffer

                GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
                GetShortPathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
                GetShortPathNameW.restype = ctypes.c_uint
                buf = create_unicode_buffer(260)
                if GetShortPathNameW(p, buf, 260):
                    s = buf.value
                    if s:
                        return s
        except Exception:
            pass
        return os.path.basename(self.Path)

    @property
    def ShortPath(self):
        p = self.Path
        try:
            if os.name == 'nt':
                import ctypes
                from ctypes import create_unicode_buffer

                GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
                GetShortPathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
                GetShortPathNameW.restype = ctypes.c_uint
                buf = create_unicode_buffer(260)
                if GetShortPathNameW(p, buf, 260):
                    s = buf.value
                    if s:
                        return s
        except Exception:
            pass
        return self.Path

    @property
    def Type(self):
        mime, _ = mimetypes.guess_type(self.Path)
        if mime:
            return mime
        ext = os.path.splitext(self.Path)[1]
        if ext:
            return f"{ext[1:].upper()} File"
        return "File"

    def Copy(self, destination, overwrite=True):
        dest = destination
        if os.path.isdir(destination) or destination.endswith(('/', '\\')):
            dest = os.path.join(destination, os.path.basename(self.Path))
        dest = os.path.abspath(dest)
        if os.path.exists(dest) and not bool(overwrite):
            raise Exception("Copy: destination exists")
        shutil.copy2(self.Path, dest)

    def Move(self, destination):
        dest = destination
        if os.path.isdir(destination) or destination.endswith(('/', '\\')):
            dest = os.path.join(destination, os.path.basename(self.Path))
        dest = os.path.abspath(dest)
        shutil.move(self.Path, dest)
        self.Path = dest
        self.Name = os.path.basename(dest)

    def OpenAsTextStream(self, iomode=1, create=False, format=-2):
        mode = int(iomode)
        if mode == 1:
            fmode = 'r'
        elif mode == 2:
            fmode = 'w'
        elif mode == 8:
            fmode = 'a'
        else:
            raise Exception("OpenAsTextStream: invalid iomode")

        phys = self.Path
        if (not os.path.exists(phys)) and (not bool(create)) and fmode == 'r':
            raise Exception("OpenAsTextStream: file not found")

        parent = os.path.dirname(phys)
        if parent and not os.path.isdir(parent):
            raise Exception("Path not found")

        f = open(phys, fmode, encoding='utf-8', newline='')
        return TextStream(f)

    def Delete(self, force=False):
        try:
            os.remove(self.Path)
        except Exception:
            if bool(force):
                try:
                    os.chmod(self.Path, 0o666)
                    os.remove(self.Path)
                except Exception:
                    pass
            else:
                raise

    def __str__(self):
        return str(self.Path)


class Folder:
    def __init__(self, path: str):
        self.Path = path
        self.Name = os.path.basename(os.path.normpath(path))

    def __str__(self):
        return str(self.Path)

    @property
    def Files(self):
        return FilesCollection(self.Path)

    @property
    def SubFolders(self):
        return FoldersCollection(self.Path)

    @property
    def Attributes(self):
        p = self.Path
        try:
            if os.name == 'nt':
                import ctypes

                GetFileAttributesW = ctypes.windll.kernel32.GetFileAttributesW
                GetFileAttributesW.argtypes = [ctypes.c_wchar_p]
                GetFileAttributesW.restype = ctypes.c_uint32
                attrs = int(GetFileAttributesW(p))
                if attrs == 0xFFFFFFFF:
                    return 0
                return attrs
        except Exception:
            pass

        attrs = 0
        try:
            if not os.access(p, os.W_OK):
                attrs |= 1
            if os.path.basename(p).startswith('.'):
                attrs |= 2
            if os.path.isdir(p):
                attrs |= 16
            if os.path.isdir(p):
                attrs |= 32
        except Exception:
            return 0
        return attrs

    @property
    def DateCreated(self):
        try:
            ts = os.path.getctime(self.Path)
            return datetime.datetime.fromtimestamp(ts)
        except Exception:
            return None

    @property
    def DateLastAccessed(self):
        try:
            ts = os.path.getatime(self.Path)
            return datetime.datetime.fromtimestamp(ts)
        except Exception:
            return None

    @property
    def DateLastModified(self):
        try:
            ts = os.path.getmtime(self.Path)
            return datetime.datetime.fromtimestamp(ts)
        except Exception:
            return None

    @property
    def Drive(self):
        drive, _ = os.path.splitdrive(self.Path)
        if drive:
            root = drive
            if not root.endswith('\\') and not root.endswith('/'):
                root = root + '\\'
            return Drive(root)
        return Drive(self.Path)

    @property
    def IsRootFolder(self):
        try:
            p = os.path.abspath(self.Path)
            parent = os.path.dirname(p)
            return parent == p
        except Exception:
            return False

    @property
    def ShortName(self):
        p = self.Path
        try:
            if os.name == 'nt':
                import ctypes
                from ctypes import create_unicode_buffer

                GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
                GetShortPathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
                GetShortPathNameW.restype = ctypes.c_uint
                buf = create_unicode_buffer(260)
                if GetShortPathNameW(p, buf, 260):
                    s = buf.value
                    if s:
                        return s
        except Exception:
            pass
        return os.path.basename(self.Path)

    @property
    def ShortPath(self):
        p = self.Path
        try:
            if os.name == 'nt':
                import ctypes
                from ctypes import create_unicode_buffer

                GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
                GetShortPathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
                GetShortPathNameW.restype = ctypes.c_uint
                buf = create_unicode_buffer(260)
                if GetShortPathNameW(p, buf, 260):
                    s = buf.value
                    if s:
                        return s
        except Exception:
            pass
        return self.Path

    @property
    def Size(self):
        total = 0
        try:
            for root, _dirs, files in os.walk(self.Path):
                for name in files:
                    p = os.path.join(root, name)
                    try:
                        total += os.path.getsize(p)
                    except Exception:
                        pass
        except Exception:
            return 0
        return total

    @property
    def Type(self):
        return "File Folder"

    @property
    def ParentFolder(self):
        parent = os.path.dirname(self.Path)
        return Folder(parent) if parent else Folder(self.Path)

    def Copy(self, destination, overwrite=True):
        dest = destination
        if os.path.isdir(destination) or destination.endswith(('/', '\\')):
            dest = os.path.join(destination, os.path.basename(os.path.normpath(self.Path)))
        dest = os.path.abspath(dest)
        if os.path.exists(dest):
            if not bool(overwrite):
                raise Exception("Copy: destination exists")
            shutil.rmtree(dest, ignore_errors=True)
        parent = os.path.dirname(dest)
        if parent and not os.path.isdir(parent):
            raise Exception("Copy: destination parent not found")
        shutil.copytree(self.Path, dest)

    def CreateTextFile(self, filename, overwrite=True, unicode=False):
        phys = os.path.join(self.Path, vbs_cstr(filename).strip())
        if os.path.exists(phys) and not bool(overwrite):
            raise Exception("CreateTextFile: file already exists")
        parent = os.path.dirname(phys)
        if parent and not os.path.isdir(parent):
            raise Exception("Path not found")
        f = open(phys, 'w', encoding='utf-8', newline='')
        return TextStream(f)

    def Delete(self, force=False):
        try:
            if bool(force):
                def _onerror(func, path, _exc):
                    try:
                        os.chmod(path, 0o666)
                        func(path)
                    except Exception:
                        pass

                shutil.rmtree(self.Path, onerror=_onerror)
            else:
                shutil.rmtree(self.Path)
        except Exception:
            if bool(force):
                return
            raise

    def Move(self, destination):
        dest = destination
        if os.path.isdir(destination) or destination.endswith(('/', '\\')):
            dest = os.path.join(destination, os.path.basename(os.path.normpath(self.Path)))
        dest = os.path.abspath(dest)
        parent = os.path.dirname(dest)
        if parent and not os.path.isdir(parent):
            raise Exception("Move: destination parent not found")
        shutil.move(self.Path, dest)
        self.Path = dest
        self.Name = os.path.basename(os.path.normpath(dest))

    def GetFile(self, filename):
        phys = os.path.join(self.Path, vbs_cstr(filename).strip())
        phys = os.path.abspath(phys)
        if not os.path.isfile(phys):
            raise Exception("GetFile: not found")
        return File(phys)

    def GetFolder(self, foldername):
        phys = os.path.join(self.Path, vbs_cstr(foldername).strip())
        phys = os.path.abspath(phys)
        if not os.path.isdir(phys):
            raise Exception("GetFolder: not found")
        return Folder(phys)

    def CreateFolder(self, name):
        phys = os.path.join(self.Path, vbs_cstr(name).strip())
        if os.path.exists(phys):
            raise Exception("Folder already exists")
        os.makedirs(phys, exist_ok=False)
        return Folder(phys)

    def DeleteFolder(self, folder, force=False):
        pat = os.path.join(self.Path, vbs_cstr(folder).strip())
        if not os.path.isdir(pat) and not os.path.exists(pat):
            return
        if bool(force):
            def _onerror(func, path, _exc):
                try:
                    os.chmod(path, 0o666)
                    func(path)
                except Exception:
                    pass

            shutil.rmtree(pat, onerror=_onerror)
        else:
            shutil.rmtree(pat)


class FoldersCollection:
    def __init__(self, folder_path: str):
        self._path = folder_path

    def __iter__(self):
        try:
            names = os.listdir(self._path)
        except Exception:
            names = []
        for n in names:
            p = os.path.join(self._path, n)
            if os.path.isdir(p):
                yield Folder(p)

    @property
    def Count(self):
        try:
            return sum(1 for e in os.scandir(self._path) if e.is_dir())
        except Exception:
            return 0


class FilesCollection:
    def __init__(self, folder_path: str):
        self._path = folder_path

    def __iter__(self):
        try:
            names = os.listdir(self._path)
        except Exception:
            names = []
        for n in names:
            p = os.path.join(self._path, n)
            if os.path.isfile(p):
                yield File(p)

    @property
    def Count(self):
        try:
            return sum(1 for e in os.scandir(self._path) if e.is_file())
        except Exception:
            return 0


class FileSystemObject:
    """Sandboxed Scripting.FileSystemObject adapter.

    By default, all paths are restricted to the ASP server docroot.
    Override with ASP_PY_FSO_ROOT to widen/narrow the sandbox.
    """

    def __init__(self, default_root: str):
        root = os.environ.get('ASP_PY_FSO_ROOT', '')
        self._root = os.path.abspath(root) if root else os.path.abspath(default_root)

    def _ensure_in_root(self, phys: str) -> str:
        phys = os.path.abspath(phys)
        if os.path.commonpath([self._root, phys]) != self._root:
            raise Exception("FileSystemObject: path outside sandbox")
        return phys

    def _resolve(self, path: str) -> str:
        if _has_ads(path):
            raise Exception("FileSystemObject: ADS not allowed")
        p = vbs_cstr(path).strip()
        if p.startswith('\\\\'):
            raise Exception("FileSystemObject: UNC paths not supported")

        p_os = p.replace('\\', os.sep)

        # Absolute physical paths (including Server.MapPath output).
        if os.path.isabs(p_os):
            return self._ensure_in_root(p_os)

        # Windows drive-letter paths on non-Windows hosts: treat as sandbox-rooted.
        p_norm = p.replace('\\', '/')
        if len(p_norm) >= 3 and p_norm[1] == ':' and p_norm[2] == '/':
            rest = p_norm[3:]
            phys = os.path.join(self._root, rest)
            return self._ensure_in_root(phys)

        # Relative paths are sandbox-root-relative.
        phys = os.path.join(self._root, p_os)
        return self._ensure_in_root(phys)

    def _resolve_pattern(self, pattern: str) -> tuple[str, list[str]]:
        if _has_ads(pattern):
            raise Exception("FileSystemObject: ADS not allowed")
        raw = vbs_cstr(pattern).strip()
        raw_os = raw.replace('\\', os.sep)
        if os.path.isabs(raw_os):
            phys_pat = raw_os
        else:
            raw_norm = raw.replace('\\', '/')
            if len(raw_norm) >= 3 and raw_norm[1] == ':' and raw_norm[2] == '/':
                rest = raw_norm[3:]
                phys_pat = os.path.join(self._root, rest)
            else:
                phys_pat = os.path.join(self._root, raw_os)

        phys_pat = os.path.abspath(phys_pat)
        if os.path.commonpath([self._root, phys_pat]) != self._root:
            raise Exception("FileSystemObject: path outside sandbox")

        matches = glob.glob(phys_pat)
        out = []
        for m in matches:
            m2 = os.path.abspath(m)
            if os.path.commonpath([self._root, m2]) != self._root:
                continue
            out.append(m2)
        return phys_pat, out

    def BuildPath(self, path, name):
        base = vbs_cstr(path).strip().replace('\\', os.sep)
        nm = vbs_cstr(name).strip().lstrip('\\/').replace('\\', os.sep)
        return os.path.join(base, nm)

    def FileExists(self, path):
        return os.path.isfile(self._resolve(path))

    def FolderExists(self, path):
        return os.path.isdir(self._resolve(path))

    def CreateFolder(self, path):
        phys = self._resolve(path)
        if os.path.exists(phys):
            raise Exception("Folder already exists")
        parent = os.path.dirname(phys)
        if parent and not os.path.isdir(parent):
            raise Exception("Path not found")
        os.mkdir(phys)
        return Folder(phys)

    def DeleteFolder(self, folder, force=False):
        _pat, matches = self._resolve_pattern(folder)
        if not matches:
            return
        for m in matches:
            if not os.path.isdir(m):
                continue
            if bool(force):
                def _onerror(func, path, _exc):
                    try:
                        os.chmod(path, 0o666)
                        func(path)
                    except Exception:
                        pass

                shutil.rmtree(m, onerror=_onerror)
            else:
                shutil.rmtree(m)

    def DeleteFile(self, filespec, force=False):
        _pat, matches = self._resolve_pattern(filespec)
        if not matches:
            return
        for m in matches:
            if not os.path.isfile(m):
                continue
            try:
                os.remove(m)
            except Exception:
                if bool(force):
                    try:
                        os.chmod(m, 0o666)
                        os.remove(m)
                    except Exception:
                        pass
                else:
                    raise

    def CopyFile(self, source, destination, overwrite=True):
        _pat, sources = self._resolve_pattern(source)
        if not sources:
            raise Exception("CopyFile: source not found")

        dest_phys = self._resolve(destination)
        dest_is_dir = os.path.isdir(dest_phys) or vbs_cstr(destination).strip().endswith(('\\', '/'))
        if len(sources) > 1 and not dest_is_dir:
            raise Exception("CopyFile: destination must be a folder")

        if dest_is_dir and not os.path.isdir(dest_phys):
            raise Exception("CopyFile: destination folder not found")

        for src in sources:
            if dest_is_dir:
                dst = os.path.join(dest_phys, os.path.basename(src))
            else:
                dst = dest_phys
            dst = self._ensure_in_root(dst)
            if os.path.exists(dst) and not bool(overwrite):
                raise Exception("CopyFile: destination exists")
            shutil.copy2(src, dst)

    def MoveFile(self, source, destination):
        _pat, sources = self._resolve_pattern(source)
        if not sources:
            raise Exception("MoveFile: source not found")

        dest_phys = self._resolve(destination)
        dest_is_dir = os.path.isdir(dest_phys) or vbs_cstr(destination).strip().endswith(('\\', '/'))
        if len(sources) > 1 and not dest_is_dir:
            raise Exception("MoveFile: destination must be a folder")
        if dest_is_dir and not os.path.isdir(dest_phys):
            raise Exception("MoveFile: destination folder not found")

        for src in sources:
            if dest_is_dir:
                dst = os.path.join(dest_phys, os.path.basename(src))
            else:
                dst = dest_phys
            dst = self._ensure_in_root(dst)
            shutil.move(src, dst)

    def CopyFolder(self, source, destination, overwrite=True):
        src = self._resolve(source)
        dst = self._resolve(destination)
        if not os.path.isdir(src):
            raise Exception("CopyFolder: source not found")
        if os.path.exists(dst):
            if not bool(overwrite):
                raise Exception("CopyFolder: destination exists")
            shutil.rmtree(dst, ignore_errors=True)
        parent = os.path.dirname(dst)
        if parent and not os.path.isdir(parent):
            raise Exception("CopyFolder: destination parent not found")
        shutil.copytree(src, dst)

    def MoveFolder(self, source, destination):
        src = self._resolve(source)
        dst = self._resolve(destination)
        if not os.path.isdir(src):
            raise Exception("MoveFolder: source not found")
        parent = os.path.dirname(dst)
        if parent and not os.path.isdir(parent):
            raise Exception("MoveFolder: destination parent not found")
        shutil.move(src, dst)

    def GetAbsolutePathName(self, path):
        return self._resolve(path)

    def GetBaseName(self, path):
        b = os.path.basename(vbs_cstr(path).replace('\\', os.sep))
        return os.path.splitext(b)[0]

    def GetDriveName(self, path):
        p = vbs_cstr(path).strip()
        if len(p) >= 2 and p[1] == ':':
            return p[:2]
        return ""

    def DriveExists(self, drive):
        d = vbs_cstr(drive).strip()
        if len(d) == 1:
            d = d + ':'
        if len(d) == 2 and d[1] == ':':
            if os.name == 'nt':
                return os.path.exists(d + '\\')
            return False
        return False

    def GetDrive(self, drive_spec):
        d = vbs_cstr(drive_spec).strip()
        if len(d) == 1:
            d = d + ':'
        if os.name == 'nt' and len(d) == 2 and d[1] == ':':
            return Drive(d + '\\')
        # POSIX: single root drive
        return Drive(self._root)

    @property
    def Drives(self):
        if os.name == 'nt':
            ds: list[Drive] = []
            for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                p = c + ':\\'
                if os.path.exists(p):
                    ds.append(Drive(p))
            return DrivesCollection(ds)
        return DrivesCollection([Drive(self._root)])

    def GetExtensionName(self, path):
        p = vbs_cstr(path).replace('\x00', '')
        b = os.path.basename(p.replace('\\', os.sep))
        ext = os.path.splitext(b)[1]
        if ext.startswith('.'):
            ext = ext[1:]
        ext = ext.strip()
        if ext:
            ext = "".join(ch for ch in ext if ch.isalnum())
        ext = ext.strip(".")
        return ext

    def GetFileName(self, path):
        return os.path.basename(vbs_cstr(path).replace('\\', os.sep))

    def GetParentFolderName(self, path):
        p = vbs_cstr(path).replace('\\', os.sep)
        return os.path.dirname(p)

    def GetTempName(self):
        return "rad" + uuid.uuid4().hex[:6] + ".tmp"

    def GetSpecialFolder(self, folder_spec):
        # 0=WindowsFolder, 1=SystemFolder, 2=TemporaryFolder
        n = int(folder_spec)
        if n == 2:
            p = os.path.join(self._root, '_tmp')
            p = self._ensure_in_root(p)
            os.makedirs(p, exist_ok=True)
            return p
        return self._root

    def GetFile(self, path):
        phys = self._resolve(path)
        if not os.path.isfile(phys):
            raise Exception("GetFile: not found")
        return File(phys)

    def GetFolder(self, path):
        phys = self._resolve(path)
        if not os.path.isdir(phys):
            raise Exception("GetFolder: not found")
        return Folder(phys)

    def OpenTextFile(self, filename, iomode=1, create=False, format=-2):
        mode = int(iomode)
        phys = self._resolve(filename)
        # Do not expose ForReading/ForWriting/ForAppending as properties.
        # In Classic ASP these are typically user-defined Const values.
        if mode == 1:
            fmode = 'r'
        elif mode == 2:
            fmode = 'w'
        elif mode == 8:
            fmode = 'a'
        else:
            raise Exception("OpenTextFile: invalid iomode")

        if (not os.path.exists(phys)) and (not bool(create)) and fmode == 'r':
            raise Exception("OpenTextFile: file not found")

        parent = os.path.dirname(phys)
        if parent and not os.path.isdir(parent):
            raise Exception("Path not found")

        # Deterministic, cross-platform: use UTF-8 and explicit CRLF in WriteLine.
        f = open(phys, fmode, encoding='utf-8', newline='')
        return TextStream(f)

    def CreateTextFile(self, filename, overwrite=True, unicode=False):
        phys = self._resolve(filename)
        if os.path.exists(phys) and not bool(overwrite):
            raise Exception("CreateTextFile: file already exists")
        parent = os.path.dirname(phys)
        if parent and not os.path.isdir(parent):
            raise Exception("Path not found")
        f = open(phys, 'w', encoding='utf-8', newline='')
        return TextStream(f)
