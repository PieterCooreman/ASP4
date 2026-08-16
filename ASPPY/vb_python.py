"""ASPPY.ExecutePython - run real CPython code from VBScript.

Bridges Classic ASP / VBScript pages to the full Python ecosystem. Each call
spawns an isolated subprocess running the same interpreter that hosts ASPPY
(``sys.executable``); the snippet hands a string back to VBScript by calling
the injected builtin ``ASPPY_RETURN(value)``.

Both methods take the same two optional arguments::

    ASPPY.ExecutePython(code [, args] [, timeout])
    ASPPY.ExecutePythonFile(path [, args] [, timeout])

``args``     Any JSON-encodable VBScript value (string, number, boolean,
             Array, Scripting.Dictionary, or a nesting of those). It arrives
             in the snippet as the injected builtin ``ASPPY_ARGS``, already
             decoded into plain Python objects. Omit it (or pass Empty/Null)
             and ``ASPPY_ARGS`` is ``None``. This is what makes
             ExecutePythonFile usable for real work: the .py file lives on
             disk as a normal, lintable module instead of being rebuilt as a
             VBScript string on every request.
``timeout``  Per-call timeout in seconds, overriding ASP_PY_PYTHON_TIMEOUT.
             Needed when one page mixes fast polling calls with a slow one
             (e.g. a package install) that must not be capped at the global
             default.

Security: disabled by default. ``ASP_PY_ALLOW_PYTHON=1`` must be set in the
server environment, otherwise every call raises a VBScript runtime error.

Environment variables:
    ASP_PY_ALLOW_PYTHON    Set to 1 to enable the feature (default: disabled).
    ASP_PY_PYTHON_TIMEOUT  Default max seconds a snippet may run (default: 30).
    ASP_PY_PYTHON_ROOT     Sandbox root for ExecutePythonFile (default: docroot).

Note: ``subprocess``, ``tempfile`` and ``json`` are imported lazily (inside
_run() / _write_args_file()) so that merely importing this module - which
happens for every request through the ASPPY shim - stays cheap for the vast
majority of pages that never call it.
"""

from __future__ import annotations

import os
import sys
import threading

from .vb_runtime import VBScriptRuntimeError, vbs_cstr
from .vm.values import VBEmpty, VBNull, VBNothing

_DEFAULT_TIMEOUT = 30

# Sentinels wrapping the payload on the child's stdout. The snippet is free to
# print whatever it likes; only what sits between these markers is returned to
# VBScript, so stray print()/logging output can never corrupt the result.
_BEGIN = "\x02ASPPY_RETURN\x02"
_END = "\x03ASPPY_RETURN\x03"

# Display name used when compiling an inline snippet, so SyntaxError/traceback
# messages read "<asppy>, line 3" instead of leaking a temp file path. Line
# numbers match the VBScript-supplied source exactly (the ASPPY_RETURN prelude
# lives in a separate bootstrap, never prepended to the user's code).
_INLINE_NAME = "<asppy>"

# Bootstrap executed via `python -c`. It installs ASPPY_RETURN and ASPPY_ARGS
# as builtins, then compiles and runs the target file as __main__.
#   argv[1] = physical path of the file to execute
#   argv[2] = display name used for compile()/tracebacks
#   argv[3] = directory to place on sys.path[0] ("" for none)
#   argv[4] = path of a JSON file holding ASPPY_ARGS ("" for none)
_BOOTSTRAP = r'''
import builtins, os, sys

_B = os.environ.pop("ASPPY_RETURN_BEGIN")
_E = os.environ.pop("ASPPY_RETURN_END")


def ASPPY_RETURN(value=""):
    """Return a string to VBScript and stop the snippet. First call wins."""
    try:
        if value is None:
            text = ""
        elif isinstance(value, str):
            text = value
        elif isinstance(value, (bytes, bytearray)):
            text = bytes(value).decode("utf-8", "replace")
        else:
            text = str(value)
    except Exception:
        text = ""
    try:
        sys.stdout.write(_B + text + _E)
        sys.stdout.flush()
    except Exception:
        pass
    try:
        sys.stderr.flush()
    except Exception:
        pass
    # Hard exit: guarantees "first call wins" even when ASPPY_RETURN is called
    # from inside a try/except or a generator/finally block that would
    # otherwise swallow a normal exception.
    os._exit(0)


builtins.ASPPY_RETURN = ASPPY_RETURN

_target, _display, _syspath = sys.argv[1], sys.argv[2], sys.argv[3]
_argsfile = sys.argv[4] if len(sys.argv) > 4 else ""

# `python -c` puts '' (the cwd) on sys.path, which would let a stray json.py or
# platform.py sitting in the web root shadow the stdlib. Drop it and use only
# the explicit directory we were given.
while sys.path and sys.path[0] in ("", ".", os.getcwd()):
    del sys.path[0]

# Load the stdlib json now, while sys.path is still clean, and decode
# ASPPY_ARGS with it. Two consequences, both deliberate:
#   * a json.py sitting next to the target script cannot hijack the decode;
#   * because the stdlib module is now in sys.modules, the target script's own
#     `import json` also gets the stdlib one. That differs from plain
#     `python script.py`, but the docroot can contain web-uploaded files, so
#     the defensive reading wins - and it is done unconditionally so the
#     behaviour never depends on whether args happened to be supplied.
import json as _json

ASPPY_ARGS = None
if _argsfile:
    with open(_argsfile, "r", encoding="utf-8") as _af:
        ASPPY_ARGS = _json.load(_af)
builtins.ASPPY_ARGS = ASPPY_ARGS

if _syspath:
    sys.path.insert(0, _syspath)

with open(_target, "r", encoding="utf-8") as _f:
    _src = _f.read()

sys.argv = [_display]
_globals = {
    "__name__": "__main__",
    "__file__": _display,
    "__builtins__": builtins,
    "ASPPY_RETURN": ASPPY_RETURN,
    "ASPPY_ARGS": ASPPY_ARGS,
}
exec(compile(_src, _display, "exec"), _globals)
'''


# Per-request docroot, published by ASPPY.runner_vm._build_globals_env(). Used
# to resolve relative ExecutePythonFile paths and as the default sandbox root.
# Thread-local because the HTTP server handles requests on multiple threads and
# each may serve a different docroot.
_tls = threading.local()


def set_current_docroot(path) -> None:
    """Record the docroot of the request running on this thread."""
    try:
        _tls.docroot = os.path.abspath(path) if path else ""
    except Exception:
        _tls.docroot = ""


def _current_docroot() -> str:
    return getattr(_tls, "docroot", "") or ""


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _timeout_seconds() -> float:
    raw = os.environ.get("ASP_PY_PYTHON_TIMEOUT", "")
    if not str(raw).strip():
        return float(_DEFAULT_TIMEOUT)
    try:
        val = float(str(raw).strip())
    except Exception:
        return float(_DEFAULT_TIMEOUT)
    return val if val > 0 else float(_DEFAULT_TIMEOUT)


def _sandbox_root() -> str:
    """Root that ExecutePythonFile targets must live under."""
    root = os.environ.get("ASP_PY_PYTHON_ROOT", "")
    if str(root).strip():
        return os.path.abspath(str(root).strip())
    return _current_docroot()


def _ensure_enabled(method: str) -> None:
    if not _env_bool("ASP_PY_ALLOW_PYTHON", False):
        raise VBScriptRuntimeError(
            f"ASPPY.{method}: Python execution is disabled. "
            "Set the ASP_PY_ALLOW_PYTHON=1 environment variable to enable it."
        )


def _is_omitted(value) -> bool:
    """True when VBScript did not really supply this optional argument.

    ``None`` is what the VM passes for an elided slot (``Foo(a, , c)``);
    Empty/Null/Nothing are what an uninitialised or cleared variable holds.
    """
    return value is None or value is VBEmpty or value is VBNull or value is VBNothing


def _resolve_timeout(override, method: str) -> float:
    """Per-call timeout in seconds, falling back to ASP_PY_PYTHON_TIMEOUT."""
    if _is_omitted(override):
        return _timeout_seconds()
    try:
        secs = float(override)
    except (TypeError, ValueError):
        try:
            secs = float(vbs_cstr(override).strip())
        except Exception:
            raise VBScriptRuntimeError(
                f"ASPPY.{method}: timeout must be a number of seconds"
            )
    # `not (secs > 0)` also rejects NaN, which would make subprocess.run hang.
    if not (secs > 0):
        raise VBScriptRuntimeError(f"ASPPY.{method}: timeout must be greater than 0")
    if secs == float("inf"):
        raise VBScriptRuntimeError(
            f"ASPPY.{method}: timeout must be a finite number of seconds"
        )
    return secs


def _write_args_file(value, method: str) -> str:
    """Serialise the optional `args` value to a temp JSON file for the child.

    Returns the file's path, or "" when no args were supplied (caller must
    unlink whatever it gets back). A file rather than argv or the environment:
    argv is capped at 32767 chars on Windows and the environment block has its
    own limit, whereas a params payload is caller-controlled and unbounded.
    """
    if _is_omitted(value):
        return ""

    # Imported here (not at module scope) both to keep the common no-args path
    # cheap and because vb_json pulls in server_object, which would otherwise
    # create an import cycle through the ASPPY shim.
    import json
    import tempfile

    from . import vb_json

    try:
        payload = vb_json._to_json_value(value)
    except Exception as e:
        raise VBScriptRuntimeError(f"ASPPY.{method}: args are not JSON-encodable: {e}")

    fd, tmp = tempfile.mkstemp(prefix="asppy_args_", suffix=".json", text=False)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return tmp


def _unlink_quietly(path: str) -> None:
    if not path:
        return
    try:
        os.unlink(path)
    except OSError:
        pass


def _require_string(value, method: str, what: str) -> str:
    if value is None or value is VBEmpty or value is VBNull or value is VBNothing:
        raise VBScriptRuntimeError(f"ASPPY.{method}: {what} is required")
    text = vbs_cstr(value)
    if text.strip() == "":
        raise VBScriptRuntimeError(f"ASPPY.{method}: {what} is required")
    return text


def _extract_payload(stdout: str):
    """Pull the ASPPY_RETURN payload out of the child's stdout."""
    start = stdout.find(_BEGIN)
    if start < 0:
        return None
    start += len(_BEGIN)
    end = stdout.find(_END, start)
    if end < 0:
        return None
    return stdout[start:end]


def _error_summary(stderr: str, display_name: str = "") -> str:
    """Condense a child traceback into a single readable VBScript message.

    The exception type/message is the last line of a traceback; we append the
    most relevant "File ..., line N" frame so the ASP page can point at the
    offending line. Frames inside the author's own snippet/file win over frames
    deep inside a third-party library.
    """
    lines = [ln.rstrip() for ln in str(stderr).splitlines() if ln.strip()]
    if not lines:
        return "Python exited with an error but produced no diagnostics"

    summary = lines[-1]
    frames = [ln.strip() for ln in lines[:-1] if ln.strip().startswith('File "')]
    if not frames:
        return summary

    frame = None
    if display_name:
        needle = 'File "%s"' % display_name
        for candidate in reversed(frames):
            if candidate.startswith(needle):
                frame = candidate
                break
    if frame is None:
        frame = frames[-1]

    # ", in <module>" is noise for top-level snippets.
    if frame.endswith(", in <module>"):
        frame = frame[: -len(", in <module>")]
    return f"{summary} ({frame})"


def _run(
    method: str,
    target_path: str,
    display_name: str,
    sys_path_dir: str,
    cwd: str,
    args_path: str = "",
    timeout: float = 0.0,
) -> str:
    import subprocess

    env = dict(os.environ)
    env["ASPPY_RETURN_BEGIN"] = _BEGIN
    env["ASPPY_RETURN_END"] = _END
    # Keep the child's text I/O on UTF-8 so non-ASCII payloads survive the trip
    # regardless of the host's console code page.
    env["PYTHONIOENCODING"] = "utf-8"

    argv = [
        sys.executable,
        "-u",  # unbuffered: nothing is lost when ASPPY_RETURN hard-exits
        "-c",
        _BOOTSTRAP,
        target_path,
        display_name,
        sys_path_dir or "",
        args_path or "",
    ]

    if not timeout:
        timeout = _timeout_seconds()
    try:
        proc = subprocess.run(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            cwd=cwd if cwd and os.path.isdir(cwd) else None,
            env=env,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        raise VBScriptRuntimeError(
            f"ASPPY.{method}: Python code timed out after {timeout:g} second(s) "
            "(pass a timeout argument, or raise ASP_PY_PYTHON_TIMEOUT, to allow more)"
        )
    except FileNotFoundError:
        raise VBScriptRuntimeError(
            f"ASPPY.{method}: Python interpreter not found ({sys.executable})"
        )
    except OSError as e:
        raise VBScriptRuntimeError(f"ASPPY.{method}: cannot start Python subprocess: {e}")

    payload = _extract_payload(proc.stdout or "")

    if proc.returncode != 0:
        # A snippet may legitimately ASPPY_RETURN and then have a shutdown hook
        # fail; if we already captured a payload, honour it. Otherwise surface
        # the Python error to VBScript so On Error Resume Next can report it.
        if payload is None:
            raise VBScriptRuntimeError(
                f"ASPPY.{method}: {_error_summary(proc.stderr or '', display_name)}"
            )

    # ASPPY_RETURN never called -> empty string, per the documented convention.
    return payload if payload is not None else ""


def ExecutePython(code, args=None, timeout=None) -> str:
    """Execute inline Python source and return the ASPPY_RETURN value.

    `args` is exposed to the snippet as the builtin ASPPY_ARGS; `timeout`
    overrides ASP_PY_PYTHON_TIMEOUT for this call only. Both are optional.
    """
    _ensure_enabled("ExecutePython")
    src = _require_string(code, "ExecutePython", "Python code")
    secs = _resolve_timeout(timeout, "ExecutePython")
    args_path = _write_args_file(args, "ExecutePython")

    import tempfile

    cwd = _current_docroot()
    fd, tmp = tempfile.mkstemp(prefix="asppy_", suffix=".py", text=False)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            # VBScript builds snippets with vbCrLf; CRLF is fine for compile(),
            # but normalising keeps reported line numbers and error offsets
            # identical to what the author wrote.
            f.write(src.replace("\r\n", "\n").replace("\r", "\n"))
        # No sys.path entry: an inline snippet has no "own directory", and
        # exposing the docroot would let web-uploaded .py files be imported.
        return _run("ExecutePython", tmp, _INLINE_NAME, "", cwd, args_path, secs)
    finally:
        _unlink_quietly(tmp)
        _unlink_quietly(args_path)


def ExecutePythonFile(path, args=None, timeout=None) -> str:
    """Execute a .py file (relative paths resolve against the docroot).

    `args` is exposed to the script as the builtin ASPPY_ARGS; `timeout`
    overrides ASP_PY_PYTHON_TIMEOUT for this call only. Both are optional.
    """
    _ensure_enabled("ExecutePythonFile")
    raw = _require_string(path, "ExecutePythonFile", "path")
    secs = _resolve_timeout(timeout, "ExecutePythonFile")

    # Two distinct roots, per the documented contract: relative paths resolve
    # against the web root, while the sandbox that the resolved file must sit
    # inside is ASP_PY_PYTHON_ROOT (which defaults to the web root). Setting
    # ASP_PY_PYTHON_ROOT therefore narrows/widens what may run without changing
    # how "scripts/status.py" is interpreted.
    root = _sandbox_root()
    base = _current_docroot() or root
    p = raw.strip().replace("\\", os.sep).replace("/", os.sep)

    if os.path.isabs(p):
        phys = os.path.abspath(p)
    else:
        if not base:
            raise VBScriptRuntimeError(
                "ASPPY.ExecutePythonFile: cannot resolve a relative path "
                "(no web root is known; pass a physical path from Server.MapPath "
                "or set ASP_PY_PYTHON_ROOT)"
            )
        phys = os.path.abspath(os.path.join(base, p))

    if root:
        try:
            inside = os.path.commonpath([root, phys]) == root
        except ValueError:
            # Different drives on Windows.
            inside = False
        if not inside:
            raise VBScriptRuntimeError(
                "ASPPY.ExecutePythonFile: path is outside the Python sandbox "
                "(see ASP_PY_PYTHON_ROOT)"
            )

    if not os.path.exists(phys):
        raise VBScriptRuntimeError(f"ASPPY.ExecutePythonFile: file not found: {raw}")
    if not os.path.isfile(phys):
        raise VBScriptRuntimeError(f"ASPPY.ExecutePythonFile: not a file: {raw}")

    script_dir = os.path.dirname(phys)
    args_path = _write_args_file(args, "ExecutePythonFile")
    try:
        # The script's own folder goes on sys.path (like `python script.py`) so
        # it can import sibling helper modules.
        return _run(
            "ExecutePythonFile", phys, phys, script_dir, script_dir, args_path, secs
        )
    finally:
        _unlink_quietly(args_path)
