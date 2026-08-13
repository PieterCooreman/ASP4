"""asppycli.py - render a single .asp file from the command line (no HTTP server).

Runs an ASP page through the exact same render_asp_vm pipeline that
ASPPY/server.py uses for HTTP requests, but writes the rendered output to
stdout (or a file). Useful for fast iteration on test pages, diffing output
between runs, and CI automation.

Contributed by Jeffrey (https://github.com/jeffreyheping) - see issue #10:
https://github.com/PieterCooreman/ASPPY/issues/10

Examples:
    python asppycli.py www_test/index.asp
    python asppycli.py www_test/01-basics.asp -o out.html
    python asppycli.py www_test/07-request-form.asp --method POST --body "name=Jeff&lang=vbscript"
    python asppycli.py www_test/index.asp --query "id=42" --show-headers
    python asppycli.py www_starter/default.asp --path /contacts/1/edit

Exit codes:
    0  page rendered with HTTP status < 400
    1  page rendered with HTTP status >= 400 (e.g. 500 ASP runtime error)
    2  usage / file-not-found error
"""
import argparse
import os
import sys
import uuid

# Allow running from the repo root (or anywhere) without installing the package.
_project_root = os.path.abspath(os.path.dirname(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from ASPPY.http_request import Request
from ASPPY.http_response import ResponseEndException
from ASPPY.server_object import Server
from ASPPY.runner_vm import render_asp_vm, exec_file_granular
from ASPPY.server import (
    _find_app_root,
    _get_app_store,
    _get_session_store,
    _init_application_from_global_asa,
    _init_session_from_global_asa,
)


def render_file(asp_file, docroot=None, method="GET", query="", headers=None,
                body=b"", virtual_path=None):
    """Render one .asp file and return a RenderResult (status, headers, body).

    Reuses server.py's global.asa loading, application/session stores and
    Request/Server construction - same code paths as the HTTP server, just
    without the socket.
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
        prog="asppycli.py",
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
    args = ap.parse_args(argv)

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
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"asppycli: error: {e}", file=sys.stderr)
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


if __name__ == "__main__":
    sys.exit(main())
