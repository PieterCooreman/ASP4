"""ASPPY.cli - render a single .asp file from the command line (no HTTP server).

Runs an ASP page through the exact same render_asp_vm pipeline that
ASPPY/server.py uses for HTTP requests, but writes the rendered output to
stdout (or a file). Useful for fast iteration on test pages, diffing output
between runs, and CI automation.

Contributed by Jeffrey (https://github.com/jeffreyheping) - see issue #10:
https://github.com/PieterCooreman/ASPPY/issues/10

Examples:
    asppy-render www_test/index.asp
    asppy-render www_test/01-basics.asp -o out.html
    asppy-render www_test/07-request-form.asp --method POST --body "name=Jeff&lang=vbscript"
    asppy-render www_test/index.asp --query "id=42" --show-headers
    asppy-render www_starter/default.asp --path /contacts/1/edit
    asppy-render www/servicedeck/api.asp --docroot www --query "action=services" --session authed=True

The same entry point is reachable as ``python -m ASPPY.cli ...`` or, from a
source checkout, as ``python asppycli.py ...``.

Exit codes:
    0  page rendered with HTTP status < 400
    1  page rendered with HTTP status >= 400 (e.g. 500 ASP runtime error)
    2  usage / file-not-found error
"""
import argparse
import os
import sys
import uuid

from ASPPY.http_request import Request
from ASPPY.http_response import ResponseEndException
from ASPPY.server_object import Server
from ASPPY.vm.values import VBEmpty, VBNull
from ASPPY.runner_vm import render_asp_vm, exec_file_granular
from ASPPY.server import (
    _find_app_root,
    _get_app_store,
    _get_session_store,
    _init_application_from_global_asa,
    _init_session_from_global_asa,
)


def parse_session_var(text):
    """Parse a --session "name=value" pair into (name, typed_value).

    Session values are Variants, so the literal is typed the way VBScript would
    type it: True/False -> Boolean, a bare number -> Number, Empty/Null -> the
    matching sentinel, anything else -> String. `name:s=value` forces String,
    which is how you store "True" as text.
    """
    name, sep, raw = text.partition("=")
    if not sep:
        raise ValueError(f'expected "name=value", got {text!r}')
    name = name.strip()
    force_str = False
    if name.lower().endswith(":s"):
        name, force_str = name[:-2].strip(), True
    if not name:
        raise ValueError(f'missing session variable name in {text!r}')

    if force_str:
        return name, raw
    low = raw.strip().lower()
    if low == "true":
        return name, True
    if low == "false":
        return name, False
    if low == "empty":
        return name, VBEmpty
    if low == "null":
        return name, VBNull
    try:
        return name, int(raw.strip())
    except ValueError:
        pass
    try:
        return name, float(raw.strip())
    except ValueError:
        pass
    return name, raw


def render_file(asp_file, docroot=None, method="GET", query="", headers=None,
                body=b"", virtual_path=None, session_vars=None):
    """Render one .asp file and return a RenderResult (status, headers, body).

    Reuses server.py's global.asa loading, application/session stores and
    Request/Server construction - same code paths as the HTTP server, just
    without the socket.

    `session_vars` is a mapping pre-loaded into Session before the page runs,
    so an authenticated route can be rendered offline without replaying a login.
    """
    asp_file = os.path.abspath(asp_file)
    if not os.path.isfile(asp_file):
        raise FileNotFoundError(asp_file)

    if docroot is None:
        docroot = os.path.dirname(asp_file)
    docroot = os.path.abspath(docroot)

    rel = os.path.relpath(asp_file, docroot).replace(os.sep, "/")
    if rel.startswith(".."):
        raise ValueError(
            "The .asp file must live inside the docroot "
            f"(file={asp_file!r}, docroot={docroot!r})"
        )
    script_path = "/" + rel.lstrip("/")
    request_path = virtual_path or script_path

    # Per-request include renderer for Server.Execute/Transfer
    # (mirrors ASPRequestHandler._handle in ASPPY/server.py).
    ctx_box = {"ctx": None}

    def render_include(target_path, transfer=False):
        tmp_server = Server(docroot, script_path,
                            render_include_fn=lambda *_a, **_k: None)
        phys = tmp_server.MapPath(target_path)
        if not os.path.isfile(phys):
            raise Exception("Server.Execute/Transfer: file not found")
        ctx = ctx_box["ctx"]
        if not ctx:
            raise Exception("No active context")
        exec_file_granular(phys, docroot, target_path, ctx.Interpreter)

    hdrs = dict(headers or {})
    # Default Host header so Request.ServerVariables("SERVER_NAME") resolves
    # the same way it does under the HTTP server / IIS (which always has Host).
    if not any(k.lower() == "host" for k in hdrs):
        hdrs["Host"] = "localhost"
    if body and method.upper() == "POST" and not any(
            k.lower() == "content-type" for k in hdrs):
        hdrs["Content-Type"] = "application/x-www-form-urlencoded"

    req = Request(
        method,
        request_path,
        query,
        hdrs,
        body,
        remote_addr="127.0.0.1",
        script_path=script_path,
        docroot=docroot,
    )

    # Application_OnStart / Session_OnStart via global.asa (if present).
    app_root = _find_app_root(docroot, asp_file)
    app_store = _get_app_store(app_root)
    sess_store = _get_session_store(app_root)
    app_store.ensure_started(
        app_root, lambda dr: _init_application_from_global_asa(dr, app_store))
    sess, is_new = sess_store.get_or_create("", lambda: uuid.uuid4().hex)
    if is_new:
        _init_session_from_global_asa(app_root, app_store, sess)

    # Seed Session AFTER Session_OnStart, so an injected value wins over a
    # default the global.asa may have set.
    for k, v in (session_vars or {}).items():
        sess.Contents.__vbs_index_set__(k, v)

    last_error = {"exc": None, "asp": None}
    srv = Server(
        docroot,
        script_path,
        render_include_fn=render_include,
        last_error_getter=lambda: last_error["asp"],
        ctx_getter=lambda: ctx_box["ctx"],
    )

    try:
        res = render_asp_vm(
            "",
            request=req,
            session=sess,
            application=app_store.app,
            server=srv,
            session_is_new=is_new,
            on_context_created=lambda ctx: ctx_box.update({"ctx": ctx}),
        )
    except ResponseEndException as e:
        res = e.result  # partial response built up to the point of Response.End
    finally:
        try:
            req.Close()
        except Exception:
            pass
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="asppy-render",
        description="Render a single .asp file offline through the ASPPY VM "
                    "(same pipeline as ASPPY/server.py, no HTTP server needed).")
    ap.add_argument("file", help="path to the .asp file to render")
    ap.add_argument("-o", "--output", metavar="FILE",
                    help="write rendered body to FILE instead of stdout")
    ap.add_argument("--docroot", metavar="DIR",
                    help="document root (default: directory of the .asp file)")
    ap.add_argument("--method", default="GET",
                    help="HTTP method to simulate (default: GET)")
    ap.add_argument("--query", default="",
                    metavar="QS", help='query string, e.g. "id=42&mode=edit"')
    ap.add_argument("--body", default="",
                    help="request body (implies Content-Type "
                         "application/x-www-form-urlencoded for POST)")
    ap.add_argument("--header", action="append", default=[], metavar="H",
                    help='extra request header, e.g. --header "Accept: text/html" '
                         "(repeatable)")
    ap.add_argument("--path", metavar="URL",
                    help="virtual request path seen by Request.Path (for "
                         "front-controller routing, e.g. --path /contacts/1)")
    ap.add_argument("--show-headers", action="store_true",
                    help="print HTTP status line and response headers to stderr")
    ap.add_argument("--session", action="append", default=[], metavar="NAME=VALUE",
                    help='preload a Session variable so protected pages can be '
                         'rendered without logging in, e.g. --session authed=True '
                         '(repeatable). True/False, numbers, Empty and Null are '
                         'typed as VBScript would type them; use NAME:s=VALUE to '
                         'force a string.')
    ap.add_argument("-V", "--version", action="version",
                    version=f"ASPPY {_version()}")
    args = ap.parse_args(argv)

    session_vars = {}
    for sv in args.session:
        try:
            name, value = parse_session_var(sv)
        except ValueError as e:
            ap.error(f"invalid --session {sv!r}: {e}")
        session_vars[name] = value

    headers = {}
    for h in args.header:
        name, _, value = h.partition(":")
        if not _:
            ap.error(f'invalid --header {h!r}, expected "Name: Value"')
        headers[name.strip()] = value.strip()

    method = args.method.upper()
    body = args.body.encode("utf-8") if args.body else b""
    if body and method == "GET":
        method = "POST"

    try:
        res = render_file(
            args.file,
            docroot=args.docroot,
            method=method,
            query=args.query,
            headers=headers,
            body=body,
            virtual_path=args.path,
            session_vars=session_vars,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"asppy-render: error: {e}", file=sys.stderr)
        return 2

    if args.show_headers:
        print(f"HTTP/1.1 {res.status_code} {res.status_message}", file=sys.stderr)
        for (hn, hv) in res.headers:
            print(f"{hn}: {hv}", file=sys.stderr)
        print("", file=sys.stderr)

    if args.output:
        with open(args.output, "wb") as f:
            f.write(res.body)
    else:
        # Write raw bytes to preserve binary output and encoding exactly.
        sys.stdout.buffer.write(res.body)
        sys.stdout.buffer.flush()

    return 0 if res.status_code < 400 else 1


def _version():
    from ASPPY import __version__
    return __version__


if __name__ == "__main__":
    sys.exit(main())
