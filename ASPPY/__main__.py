"""ASPPY.__main__ - start the ASPPY HTTP server.

Reachable three ways, all equivalent:

    asppy 0.0.0.0 8080 www          # console script (pip install asppy)
    python -m ASPPY 0.0.0.0 8080 www
    python -m ASPPY.server 0.0.0.0 8080 www

The positional argument order (host, port, docroot) and the defaults are the
same as ASPPY/server.py's own ``__main__`` block, so existing .bat files and
service units keep working unchanged. Pass an IPv6 host such as ``::`` to bind
an IPv6 socket.
"""
import argparse
import sys

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080
DEFAULT_DOCROOT = "web"


def main(argv=None):
    from ASPPY import __version__

    ap = argparse.ArgumentParser(
        prog="asppy",
        description="Serve a folder of Classic ASP (VBScript) pages over HTTP "
                    "using the ASPPY runtime - no IIS required.",
        epilog="example: asppy 0.0.0.0 8080 www")
    ap.add_argument("host", nargs="?", default=DEFAULT_HOST,
                    help=f"interface to bind (default: {DEFAULT_HOST}); use "
                         "'::' for IPv6, '127.0.0.1' to stay local")
    ap.add_argument("port", nargs="?", type=int, default=DEFAULT_PORT,
                    help=f"TCP port to listen on (default: {DEFAULT_PORT})")
    ap.add_argument("docroot", nargs="?", default=DEFAULT_DOCROOT,
                    help=f"document root holding your .asp files "
                         f"(default: {DEFAULT_DOCROOT})")
    ap.add_argument("-V", "--version", action="version",
                    version=f"ASPPY {__version__}")
    args = ap.parse_args(argv)

    from ASPPY.server import run
    run(args.host, args.port, args.docroot)
    return 0


if __name__ == "__main__":
    sys.exit(main())
