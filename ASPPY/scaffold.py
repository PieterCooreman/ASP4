"""ASPPY.scaffold - create a new ASPPY app from the bundled starter.

    asppy-new myapp              create ./myapp from the starter template
    asppy-new myapp --run        create it, then start the server on it
    asppy-new --list             show what the starter contains

developers.md tells every developer and AI agent to "start every new app from
www_starter" rather than from a blank folder, because the starter carries the
MVC layout, the routing front controller, the SQLite helper and the layout
template that the rest of the guidance assumes. Anyone who installed ASPPY with
pip has no checkout and therefore no www_starter, so a copy ships inside the
package and this command unpacks it.

The result is a complete, runnable app - not an empty directory:

    myapp/
      default.asp          front controller, routes every request
      index.asp
      web.config           for IIS parity, harmless under ASPPY
      asp/
        db.asp             SQLite connection helper
        helpers.asp        HTML escaping, formatting
        layout.asp         page shell
        controllers/       home.asp, shared.asp
        models/            app.asp
        views/             home/, errors/
      assets/app.css
      data/app.db          empty SQLite database
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

STARTER_DIR = Path(__file__).resolve().parent / "starter"


def starter_files() -> list[Path]:
    if not STARTER_DIR.is_dir():
        return []
    return sorted(p for p in STARTER_DIR.rglob("*") if p.is_file())


def do_list() -> int:
    files = starter_files()
    if not files:
        print("asppy-new: the bundled starter is missing. This install looks "
              "incomplete - try 'pip install --force-reinstall asppy'.",
              file=sys.stderr)
        return 1
    total = sum(p.stat().st_size for p in files)
    print(f"Starter template ({len(files)} files, {total / 1024:,.1f} KB)")
    print(f"source: {STARTER_DIR}\n")
    for p in files:
        rel = p.relative_to(STARTER_DIR).as_posix()
        print(f"  {rel:<44} {p.stat().st_size / 1024:>6.1f} KB")
    print("\nCreate a copy with:  asppy-new myapp")
    return 0


def main(argv=None) -> int:
    from ASPPY import __version__

    ap = argparse.ArgumentParser(
        prog="asppy-new",
        description="Create a new ASPPY application from the bundled starter "
                    "template - an MVC scaffold with routing, SQLite and views "
                    "already wired up.",
        epilog="example:  asppy-new myapp --run")
    ap.add_argument("target", nargs="?",
                    help="folder to create, e.g. myapp (must not already exist "
                         "unless --force is given)")
    ap.add_argument("-l", "--list", action="store_true",
                    help="list the starter's contents and exit")
    ap.add_argument("-f", "--force", action="store_true",
                    help="write into TARGET even if it already exists "
                         "(existing files with the same name are overwritten)")
    ap.add_argument("--run", action="store_true",
                    help="start the ASPPY server on the new folder afterwards")
    ap.add_argument("--port", type=int, default=8080,
                    help="port to use with --run (default: 8080)")
    ap.add_argument("-V", "--version", action="version",
                    version=f"ASPPY {__version__}")
    args = ap.parse_args(argv)

    if args.list:
        return do_list()

    if not args.target:
        ap.error("give a folder name, e.g. 'asppy-new myapp' "
                 "(or use --list to see what the starter contains)")

    files = starter_files()
    if not files:
        print("asppy-new: the bundled starter is missing. This install looks "
              "incomplete - try 'pip install --force-reinstall asppy'.",
              file=sys.stderr)
        return 1

    dest = Path(args.target).resolve()
    if dest.exists() and not args.force:
        if any(dest.iterdir()):
            print(f"asppy-new: {dest} already exists and is not empty. "
                  f"Choose another name, or pass --force to write into it "
                  f"anyway.", file=sys.stderr)
            return 2

    try:
        for src in files:
            rel = src.relative_to(STARTER_DIR)
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, out)
    except OSError as e:
        print(f"asppy-new: could not create {dest}: {e}", file=sys.stderr)
        return 1

    print(f"Created {dest} ({len(files)} files)")
    print()
    print("Next steps:")
    print(f"  asppy 127.0.0.1 {args.port} {args.target}")
    print(f"  then open http://localhost:{args.port}")
    print()
    print("Working with an AI agent? Give it the output of 'asppy-guide' first -")
    print("it explains the conventions this scaffold follows.")

    if args.run:
        print()
        from ASPPY.server import run
        run("127.0.0.1", args.port, str(dest))

    return 0


if __name__ == "__main__":
    sys.exit(main())
