"""ASPPY.check - batch-check every .asp file in a folder (recursively).

Renders each page through the same VM pipeline as ASPPY/server.py (via
ASPPY.cli.render_file) and reports any page that fails, including the file,
line number and error description from the ASP error page. Designed for AI
agents and CI pipelines that need a one-command health check of a whole app.

Examples:
    asppy-check www_test
    asppy-check www                 # check your own app
    asppy-check www_test --verbose  # also list passing pages
    asppy-check www --exclude drafts --exclude old

Directories holding include fragments that cannot render standalone -
'includes', 'views', 'partials', 'layouts' - and directories starting with
'_' (data folders such as _appdata) are skipped by default. Use
--no-default-excludes to scan them anyway.

The same entry point is reachable as ``python -m ASPPY.check ...`` or, from a
source checkout, as ``python asppycheck.py ...``.

Exit codes:
    0  every page rendered with HTTP status < 500
    1  at least one page failed (HTTP status >= 500 or engine exception)
    2  usage error / folder not found
"""
import argparse
import os
import re
import sys

from ASPPY.cli import render_file

# Directories whose .asp files are fragments, not pages: they are pulled in by
# a controller or a front controller via #include, and reference variables and
# helper functions that only exist in that context. Rendering them standalone
# always fails, so scanning them produces noise rather than signal - the MVC
# starter reported three phantom failures before these were excluded.
# Pass --no-default-excludes to scan them anyway.
DEFAULT_EXCLUDED_DIRS = ("includes", "views", "partials", "layouts")

# The IIS-style error page emitted by the VM looks like:
#   <p>ASPPY runtime error '8000ffff'</p>
#   <p>Variable is undefined: 'X'</p>
#   <p>/page.asp, line 12</p>
_ERROR_P_RE = re.compile(rb"<p>(.*?)</p>", re.DOTALL)


def _extract_error(body: bytes) -> str:
    """Pull a one-line error summary out of the ASP error page body."""
    paras = [p.strip().replace(b"\r", b" ").replace(b"\n", b" ")
             for p in _ERROR_P_RE.findall(body)]
    if len(paras) >= 3:
        desc = paras[1].decode("utf-8", errors="replace")
        loc = paras[2].decode("utf-8", errors="replace")
        return f"{desc} ({loc})"
    return body[:200].decode("utf-8", errors="replace").strip()


def find_asp_files(root: str, extra_excludes, no_default_excludes: bool):
    excluded = {d.lower() for d in extra_excludes}
    if not no_default_excludes:
        excluded.update(DEFAULT_EXCLUDED_DIRS)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames
            if d.lower() not in excluded
            and not (not no_default_excludes and d.startswith("_"))
        )
        for fn in sorted(filenames):
            if fn.lower().endswith(".asp") and fn.lower() != "global.asa":
                yield os.path.join(dirpath, fn)


def main(argv=None):
    from ASPPY import __version__

    ap = argparse.ArgumentParser(
        prog="asppy-check",
        description="Recursively render every .asp file in a folder through "
                    "the ASPPY VM and report pages that fail.")
    ap.add_argument("folder", nargs="?", default="www_test",
                    help="folder to scan (default: www_test); also used as "
                         "the docroot")
    ap.add_argument("--exclude", action="append", default=[], metavar="DIR",
                    help="directory name to skip (repeatable)")
    ap.add_argument("--no-default-excludes", action="store_true",
                    help="also scan the include-fragment directories "
                         "(includes, views, partials, layouts) and '_*' "
                         "data directories")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="list passing pages too, not just failures")
    ap.add_argument("--fail-fast", action="store_true",
                    help="stop at the first failing page")
    ap.add_argument("-V", "--version", action="version",
                    version=f"ASPPY {__version__}")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.folder)
    if not os.path.isdir(root):
        print(f"asppy-check: error: folder not found: {root}", file=sys.stderr)
        return 2

    files = list(find_asp_files(root, args.exclude, args.no_default_excludes))
    if not files:
        print(f"asppy-check: no .asp files found under {root}", file=sys.stderr)
        return 2

    n_pass = n_warn = n_fail = 0
    failures = []

    for f in files:
        rel = os.path.relpath(f, root).replace(os.sep, "/")
        try:
            res = render_file(f, docroot=root)
            status = res.status_code
        except Exception as e:  # engine-level crash, not an ASP error page
            n_fail += 1
            failures.append((rel, f"engine exception: {e}"))
            print(f"FAIL  {rel}  engine exception: {e}")
            if args.fail_fast:
                break
            continue

        if status >= 500:
            n_fail += 1
            detail = _extract_error(res.body)
            failures.append((rel, detail))
            print(f"FAIL  {rel}  [{status}] {detail}")
            if args.fail_fast:
                break
        elif status >= 400:
            # 4xx is often intentional (routers returning 404) - warn only.
            n_warn += 1
            print(f"WARN  {rel}  [{status} {res.status_message}]")
        else:
            n_pass += 1
            print(f"ok    {rel}  [{status}]")

    total = n_pass + n_warn + n_fail
    print(f"\nchecked {total} page(s): "
          f"{n_pass} ok, {n_warn} warning(s), {n_fail} failure(s)")
    if failures:
        print("\nfailures:")
        for rel, detail in failures:
            print(f"  {rel}: {detail}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
