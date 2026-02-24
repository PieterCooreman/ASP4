"""Tiny HTTP server to serve .asp pages using the Python-based ASP runner."""
import os
import socket
import sys
import threading
import collections
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import cast
import urllib.parse
import email.utils
import shutil
import uuid
from typing import Any

# Allow running via: python ASP4/server.py ...
# Add the project root (parent of this file's directory) to sys.path so the
# ASP4 package can be imported.
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from ASP4.http_request import Request
from ASP4.session import SessionStore
from ASP4.application import ApplicationStore
from ASP4.global_asa import compile_global_asa, GlobalAsaCompiled
from ASP4.http_response import RenderResult, Response, ResponseEndException
from ASP4.server_object import Server, ServerTransferException
from ASP4.asp_include import IncludeError
from ASP4.vb_err import VBErr
from ASP4.runner_vm import render_asp_vm, exec_file_granular

_store_lock = threading.RLock()
_session_stores: dict[str, SessionStore] = {}
_app_stores: dict[str, ApplicationStore] = {}

# ---------------------------------------------------------------------------
# Module-level constants — built once at import time, not per-request.
# ---------------------------------------------------------------------------

_STATIC_MIME_TYPES: dict[str, str] = {
    'jpeg': 'image/jpeg',
    'jpg':  'image/jpeg',
    'png':  'image/png',
    'gif':  'image/gif',
    'ico':  'image/x-icon',
    'svg':  'image/svg+xml',
    'htm':  'text/html',
    'html': 'text/html',
    'js':   'application/javascript',
    'css':  'text/css',
    'txt':  'text/plain',
    'zip':  'application/x-zip-compressed',
    'pdf':  'application/pdf',
    'doc':  'application/msword',
    'docx': 'application/msword',
    'rtf':  'text/rtf',
    'xls':  'application/x-msexcel',
    'xlsx': 'application/x-msexcel',
    'mpeg': 'video/mpeg',
    'mp3':  'audio/mpeg',
    'mp4':  'video/mp4',
    'avi':  'video/x-msvideo',
    'wmv':  'video/x-ms-wmv',
    'm4v':  'video/x-m4v',
    'mov':  'video/quicktime',
    '3gp':  'video/3gpp',
    'xml':  'application/xml',
    'wav':  'audio/wav',
}

_DEFAULT_DOCS = (
    "index.asp",
    "default.asp",
    "index.html",
    "index.htm",
    "default.html",
    "default.htm",
)

# ---------------------------------------------------------------------------
# Module-level pure helper functions — no per-request state, defined once.
# ---------------------------------------------------------------------------

def _safe_join(root: str, url_path: str) -> str:
    phys = os.path.abspath(os.path.join(root, url_path.lstrip('/')))
    root_abs = os.path.abspath(root)
    if os.path.commonpath([root_abs, phys]) != root_abs:
        raise PermissionError("Forbidden")
    return phys


def _phys_to_url(root: str, phys: str) -> str:
    rel = os.path.relpath(phys, root)
    rel = rel.replace(os.sep, '/')
    return '/' + rel.lstrip('/')


def _resolve_case_insensitive_path(root: str, url_path: str):
    if os.name == "nt":
        return None
    root_abs = os.path.abspath(root)
    parts = [p for p in url_path.lstrip('/').split('/') if p]
    cur = root_abs
    for part in parts:
        if part in (".", ".."):
            return None
        try:
            entries = os.listdir(cur)
        except Exception:
            return None
        match = None
        part_lower = part.lower()
        for name in entries:
            if name.lower() == part_lower:
                match = name
                break
        if match is None:
            return None
        cur = os.path.join(cur, match)
    if os.path.commonpath([root_abs, cur]) != root_abs:
        return None
    return cur


def _try_default_document(docroot: str, url_path: str):
    if not url_path.startswith('/'):
        url_path = '/' + url_path
    if url_path.endswith('/'):
        dir_url = url_path
        try:
            dir_phys = _safe_join(docroot, dir_url)
        except PermissionError:
            return None
        if not os.path.isdir(dir_phys):
            alt_dir = _resolve_case_insensitive_path(docroot, dir_url)
            if alt_dir and os.path.isdir(alt_dir):
                dir_phys = alt_dir
                dir_url = _phys_to_url(docroot, dir_phys) + '/'
            else:
                return None
    else:
        try:
            phys = _safe_join(docroot, url_path)
        except PermissionError:
            return None
        if os.path.isdir(phys):
            dir_phys = phys
            dir_url = url_path + '/'
        else:
            alt_dir = _resolve_case_insensitive_path(docroot, url_path)
            if alt_dir and os.path.isdir(alt_dir):
                dir_phys = alt_dir
                dir_url = _phys_to_url(docroot, dir_phys) + '/'
            else:
                return None

    for fn in _DEFAULT_DOCS:
        cand_phys = os.path.join(dir_phys, fn)
        if os.path.isfile(cand_phys):
            cand_url = dir_url + fn
            return cand_url, cand_phys
    return None


# ---------------------------------------------------------------------------
# Application / session helpers
# ---------------------------------------------------------------------------

def _find_app_root(docroot: str, phys_path: str) -> str:
    docroot_abs = os.path.abspath(docroot)
    cur = os.path.abspath(os.path.dirname(phys_path))
    while True:
        if os.path.isfile(os.path.join(cur, 'global.asa')):
            return cur
        if cur == docroot_abs:
            break
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return docroot_abs


def _get_app_store(app_root: str) -> ApplicationStore:
    with _store_lock:
        store = _app_stores.get(app_root)
        if store is None:
            store = ApplicationStore()
            _app_stores[app_root] = store
        return store


def _get_session_store(app_root: str) -> SessionStore:
    with _store_lock:
        store = _session_stores.get(app_root)
        if store is None:
            store = SessionStore()
            _session_stores[app_root] = store
        return store


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return bool(default)
    return v.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    if v is None:
        return int(default)
    try:
        return int(str(v).strip())
    except Exception:
        return int(default)


# This server is multi-threaded (ThreadingMixIn). Shared state must be protected.


def _run_global_asa_body(app_root: str, app_store: ApplicationStore, body: str, sess=None):
    if not body:
        return
    from ASP4.parser import Parser
    from ASP4.vm.context import ExecutionContext
    from ASP4.vm.interpreter import VBInterpreter
    from ASP4.runner_vm import _build_globals_env
    from ASP4.http_request import Request as Req
    from ASP4.server_object import Server as Srv

    dummy_res = RenderResult()
    dummy_body = bytearray()
    dummy_resp = Response(dummy_res, dummy_body)
    dummy_req = Req('GET', '/global.asa', '', {}, b'')
    srv = Srv(app_root, '/global.asa', render_include_fn=lambda *_a, **_k: None)
    ctx = ExecutionContext(response=dummy_resp, request=dummy_req, session=sess, application=app_store.app, server=srv, err=VBErr())
    env = _build_globals_env(ctx)
    interp = VBInterpreter(ctx, env)
    prog = Parser(body).parse_program()
    for s in prog:
        interp.exec_stmt(s)


def _ensure_global_asa_compiled(app_root: str, app_store: ApplicationStore):
    cache = getattr(app_store, '_global_asa_cache', None)
    if cache is None:
        app_store._global_asa_cache = compile_global_asa(app_root)
        cache = app_store._global_asa_cache
    if cache is None:
        return GlobalAsaCompiled()
    return cache


def _init_application_from_global_asa(app_root: str, app_store: ApplicationStore):
    comp = _ensure_global_asa_compiled(app_root, app_store)
    # instantiate application-scope objects
    try:
        from ASP4.server_object import Server as Srv
        srv = Srv(app_root, '/', render_include_fn=lambda *_a, **_k: None)
        for od in comp.app_objects:
            obj = srv.CreateObject(od.progid)
            app_store.app._set_static_object(od.obj_id, obj)
    except Exception:
        pass
    _run_global_asa_body(app_root, app_store, comp.app_on_start, sess=None)


def _init_session_from_global_asa(app_root: str, app_store: ApplicationStore, sess):
    comp = _ensure_global_asa_compiled(app_root, app_store)
    try:
        from ASP4.server_object import Server as Srv
        srv = Srv(app_root, '/', render_include_fn=lambda *_a, **_k: None)
        for od in comp.sess_objects:
            obj = srv.CreateObject(od.progid)
            sess._set_static_object(od.obj_id, obj)
    except Exception:
        pass
    _run_global_asa_body(app_root, app_store, comp.sess_on_start, sess=sess)


# ---------------------------------------------------------------------------
# HTTP server classes
# ---------------------------------------------------------------------------

class ASPHTTPServer(ThreadingMixIn, HTTPServer):
    # Ensure worker threads don't keep the process alive on Ctrl-C
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass, docroot: str):
        super().__init__(server_address, RequestHandlerClass)
        self.docroot = docroot


class ASPHTTPServerV6(ASPHTTPServer):
    address_family = socket.AF_INET6

    def __init__(self, server_address, RequestHandlerClass, docroot: str):
        super().__init__(server_address, RequestHandlerClass, docroot)
        # Try to enable dual-stack (accept IPv4-mapped addresses) where supported.
        try:
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        except Exception:
            pass


class ASPRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        if not _env_bool("ASP_PY_LOG", False):
            return
        try:
            super().log_message(format, *args)
        except Exception:
            pass

    def do_GET(self):
        self._handle()

    def do_POST(self):
        self._handle()

    def _handle(self):
        parsed = urllib.parse.urlsplit(self.path)
        raw_path = parsed.path or "/"
        try:
            path = urllib.parse.unquote(raw_path)
        except Exception:
            path = raw_path
        request_path = path
        request_query = parsed.query or ""
        docroot = cast(ASPHTTPServer, self.server).docroot

        # Default documents (/, /dir/, /dir)
        dd = _try_default_document(docroot, path)
        if dd is not None:
            path, _phys = dd

        # Serve static files (html, js, css, images, etc.)
        if not path.lower().endswith('.asp'):
            try:
                phys = _safe_join(docroot, path)
            except PermissionError:
                self.send_error(403, "Forbidden")
                return
            if not os.path.isfile(phys):
                alt_phys = _resolve_case_insensitive_path(docroot, path)
                if alt_phys and os.path.isfile(alt_phys):
                    phys = alt_phys
            if os.path.isfile(phys):
                ext = os.path.splitext(phys)[1].lstrip('.').lower()
                ctype = _STATIC_MIME_TYPES.get(ext)
                if ctype is None:
                    self.send_error(403, "Forbidden")
                    return
                try:
                    st = os.stat(phys)
                except Exception:
                    self.send_error(500, "Failed to read file")
                    return
                last_mod = email.utils.formatdate(st.st_mtime, usegmt=True)
                ims = self.headers.get('If-Modified-Since') or self.headers.get('if-modified-since')
                if ims:
                    try:
                        ims_dt = email.utils.parsedate_to_datetime(ims)
                        if ims_dt is not None:
                            ims_ts = int(ims_dt.timestamp())
                            if int(st.st_mtime) <= ims_ts:
                                self.send_response(304)
                                self.send_header('Last-Modified', last_mod)
                                if ctype.startswith('text/') or ctype in ('application/javascript', 'application/xml'):
                                    self.send_header('Content-Type', ctype + '; charset=utf-8')
                                else:
                                    self.send_header('Content-Type', ctype)
                                self.end_headers()
                                return
                    except Exception:
                        pass
                self.send_response(200)
                if ctype.startswith('text/') or ctype in ('application/javascript', 'application/xml'):
                    self.send_header('Content-Type', ctype + '; charset=utf-8')
                else:
                    self.send_header('Content-Type', ctype)
                self.send_header('Content-Length', str(st.st_size))
                self.send_header('Last-Modified', last_mod)
                if ctype.lower().startswith('text/html'):
                    self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
                    self.send_header('Pragma', 'no-cache')
                    self.send_header('Expires', '0')
                self.end_headers()
                try:
                    with open(phys, 'rb') as f:
                        shutil.copyfileobj(f, self.wfile)
                except Exception:
                    return
                return
            else:
                # If the URL has a file extension, return 404 (static asset missing).
                if os.path.splitext(path)[1]:
                    self.send_error(404, "Not Found")
                    return
                # For extensionless URLs, fall through to ASP execution (no 404 override).
                # If we remapped to an ASP page, fall through to ASP execution.
            # If we did not return a static file, we fall through to ASP execution.

        full_path = os.path.join(docroot, path.lstrip("/"))
        exec_path = path

        if not os.path.isfile(full_path):
            alt_full = _resolve_case_insensitive_path(docroot, path)
            if alt_full and os.path.isfile(alt_full):
                full_path = alt_full
            else:
                self.send_error(404, "ASP page not found")
                return

        # Provide a per-request include renderer for Server.Execute/Transfer
        ctx_box: dict[str, Any] = {'ctx': None}

        def render_include(target_path: str, transfer: bool = False):
            # Use the Server.MapPath logic; construct a temporary server object for mapping
            tmp_server = Server(docroot, exec_path, render_include_fn=lambda *_a, **_k: None)
            phys = tmp_server.MapPath(target_path)
            if not os.path.isfile(phys):
                raise Exception("Server.Execute/Transfer: file not found")

            # Execute included page in current request context
            ctx = ctx_box['ctx']
            if not ctx:
                raise Exception("No active context")

            exec_file_granular(phys, docroot, target_path, ctx.Interpreter)

        # Read body (for POST/PUT). Support both Content-Length and chunked transfer encoding.
        body = b""
        if self.command.upper() in ("POST", "PUT"):
            te = (self.headers.get('Transfer-Encoding', '') or '').lower()
            if 'chunked' in te:
                chunks = []
                total = 0
                maxb = 25 * 1024 * 1024
                while True:
                    line = self.rfile.readline(64 * 1024)
                    if not line:
                        break
                    line = line.strip()
                    if b';' in line:
                        line = line.split(b';', 1)[0]
                    try:
                        sz = int(line.decode('ascii', errors='ignore') or '0', 16)
                    except Exception:
                        sz = 0
                    if sz <= 0:
                        # Consume trailer headers until blank line
                        while True:
                            trailer = self.rfile.readline(64 * 1024)
                            if not trailer or trailer in (b"\r\n", b"\n"):
                                break
                        break
                    # Ensure full chunk is read.
                    remaining = sz
                    parts = []
                    while remaining > 0:
                        part = self.rfile.read(remaining)
                        if not part:
                            break
                        parts.append(part)
                        remaining -= len(part)
                    data = b"".join(parts)
                    # consume CRLF
                    try:
                        self.rfile.read(2)
                    except Exception:
                        pass
                    total += len(data)
                    if total > maxb:
                        break
                    chunks.append(data)
                body = b"".join(chunks)
            else:
                try:
                    n = int(self.headers.get('Content-Length', '0'))
                except Exception:
                    n = 0
                if n > 0:
                    # rfile.read(n) is not guaranteed to return all bytes in one call.
                    remaining = n
                    chunks = []
                    while remaining > 0:
                        part = self.rfile.read(remaining)
                        if not part:
                            break
                        chunks.append(part)
                        remaining -= len(part)
                    body = b"".join(chunks)

        # Build Request
        headers = {k: v for (k, v) in self.headers.items()}
        remote = self.client_address[0] if self.client_address else ""
        req = Request(self.command, request_path, request_query, headers, body, remote_addr=remote)

        # Optional request tracing (disabled by default).
        if _env_bool("ASP_PY_TRACE_REQUEST", False):
            try:
                ctype = headers.get('Content-Type') or headers.get('content-type') or ''
                form_map = {}
                try:
                    form_map = dict(getattr(req.Form, '_m', {}) or {})
                except Exception:
                    form_map = {}
                body_preview = body[:1000]
                try:
                    body_preview_txt = body_preview.decode('utf-8', errors='replace')
                except Exception:
                    body_preview_txt = repr(body_preview)
                print(
                    f"[asp.py trace] {self.command} {path} ctype={ctype!r} content_length={headers.get('Content-Length') or headers.get('content-length')!r} body_len={len(body)} form_keys={list(form_map.keys())}",
                    file=sys.stderr,
                )
                if self.command.upper() in ("POST", "PUT"):
                    print(f"[asp.py trace] body_preview={body_preview_txt!r}", file=sys.stderr)
                    # Common aspLite fields
                    for k in ("aspFormAction", "yesno", "checkbox", "radio"):
                        try:
                            v = req.Form.Item(k)
                        except Exception as e:
                            v = f"<error {e}>"
                        print(f"[asp.py trace] form[{k}]={v!r}", file=sys.stderr)
            except Exception:
                pass

        # Application_OnStart (before first session)
        app_root = _find_app_root(docroot, full_path)
        app_store = _get_app_store(app_root)
        sess_store = _get_session_store(app_root)
        app_store.ensure_started(app_root, lambda dr: _init_application_from_global_asa(dr, app_store))

        # Session
        sid_cookie = req.Cookies.__vbs_index_get__("ASP_PY_SESSIONID")
        sid = str(sid_cookie) if sid_cookie is not None else ""
        sess, is_new = sess_store.get_or_create(sid, lambda: uuid.uuid4().hex)
        if is_new:
            _init_session_from_global_asa(app_root, app_store, sess)

        # Render via VM
        last_error: dict[str, Any] = {'exc': None, 'asp': None}
        srv = Server(
            docroot,
            exec_path,
            render_include_fn=render_include,
            last_error_getter=lambda: last_error['asp'],
            ctx_getter=lambda: ctx_box['ctx'],
        )

        res = render_asp_vm(
            "",
            request=req,
            session=sess,
            application=app_store.app,
            server=srv,
            session_is_new=is_new,
            on_context_created=lambda ctx: ctx_box.update({'ctx': ctx})
        )

        if not any(h[0].lower() == 'content-length' for h in res.headers):
            res.headers.append(("Content-Length", str(len(res.body))))
        if not any(h[0].lower() == 'connection' for h in res.headers):
            res.headers.append(("Connection", "keep-alive"))
        self.send_response(res.status_code, res.status_message)
        for (hn, hv) in res.headers:
            self.send_header(hn, hv)
        self.end_headers()

        # Runtime Patch: Filter out legacy "setRequestHeader('Content-length', ...)" calls
        # from the response body to prevent browser console errors.
        # This is necessary because we cannot modify the source code of the example apps.
        final_body = res.body
        try:
            # Check if it looks like text/html or text/javascript
            is_text = False
            for h in res.headers:
                if h[0].lower() == 'content-type':
                    v = h[1].lower()
                    if 'html' in v or 'javascript' in v or 'text' in v:
                        is_text = True
                        break

            if is_text:
                # Naive replacement of specific known bad patterns in QS app
                # Pattern 1: http_request.setRequestHeader("Content-length", path.length);
                # Pattern 2: http_request.setRequestHeader("Connection", "close");
                p1 = b'http_request.setRequestHeader("Content-length",'
                p2 = b'http_request.setRequestHeader("Connection",'

                if p1 in final_body or p2 in final_body:
                    final_body = final_body.replace(p1, b'// http_request.setRequestHeader("Content-length",')
                    final_body = final_body.replace(p2, b'// http_request.setRequestHeader("Connection",')
        except Exception:
            pass

        self.wfile.write(final_body)

        # AppendToLog support: write to stdout (pragmatic)
        if getattr(res, 'log_tail', None):
            try:
                self.log_message("asp-log: %s", "".join(res.log_tail))
            except Exception:
                pass


def run(host="0.0.0.0", port=8080, docroot="web"):
    host_s = str(host)
    port_i = int(port)
    # If caller passes an IPv6 host (contains ':'), bind an IPv6 socket.
    # Example: python ASP4/server.py :: 8080 examples
    if ':' in host_s:
        httpd = ASPHTTPServerV6((host_s, port_i), ASPRequestHandler, docroot)
    else:
        httpd = ASPHTTPServer((host_s, port_i), ASPRequestHandler, docroot)
    print(f"ASP.py-like server running at http://{host}:{port}/ (docroot={docroot})")
    try:
        httpd.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            # Run Application_OnEnd for all known app roots
            for app_root, app_store in list(_app_stores.items()):
                try:
                    comp = _ensure_global_asa_compiled(app_root, app_store)
                    _run_global_asa_body(app_root, app_store, comp.app_on_end, sess=None)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            httpd.shutdown()
        except Exception:
            pass
        httpd.server_close()
        print("Server stopped")


if __name__ == "__main__":
    host = "0.0.0.0"
    port = 8080
    docroot = "web"
    if len(sys.argv) > 1:
        host = sys.argv[1]
    if len(sys.argv) > 2:
        port = int(sys.argv[2])
    if len(sys.argv) > 3:
        docroot = sys.argv[3]
    run(host, port, docroot)