"""ASPPY.guide - reach the bundled documentation from the command line.

ASPPY is newer than every LLM's training cut-off, so no model knows anything
about it out of the box. Installing the package cannot change that: knowledge
only reaches a model as text in its context window. This command exists to make
that one step trivial.

    asppy-guide                      print developers.md to stdout
    asppy-guide | clip               copy it, ready to paste into a chat
    asppy-guide --list               show everything that ships with the package
    asppy-guide --open prompt-builder    open a prompt builder in your browser
    asppy-guide --path               print the folder holding the docs

Point an AI agent at the output of a bare ``asppy-guide`` before asking it to
write any ASP, and it will have the full picture: object model, conventions,
gotchas and idioms. That reliably cuts development time and improves code
quality, even with free models.

For chat assistants that cannot read your disk (Gemini, ChatGPT in a browser),
pipe the output into your clipboard and paste it, or use the prompt builders,
which generate a complete ready-to-send prompt for you.
"""
from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

GUIDES_DIR = Path(__file__).resolve().parent / "guides"
HTML_DIR = GUIDES_DIR / "html"

# The document an AI agent should read first, and what a bare invocation prints.
DEFAULT_DOC = "developers.md"

# Friendlier labels for the pages worth calling out in --list.
DESCRIPTIONS = {
    "developers.md": "START HERE for AI agents - conventions, object model, gotchas",
    "README.md": "project overview, installation, feature matrix",
    "ASPPY_The_Vibe_Coders_Guide.html": "the full ebook, for agents and developers",
    "prompt-builder.html": "build a prompt for classic MVC-style ASPPY apps",
    "prompt-builder-SPA.html": "build a prompt for React front-end + ASPPY back-end",
    "specifications.html": "supported VBScript surface, 60 locales, exact semantics",
    "cli.html": "asppy / asppy-render / asppy-check reference",
    "database.html": "ADODB, SQLite, Access, Excel, ODBC, PostgreSQL",
    "legacy_asp.html": "migrating an existing Classic ASP app off IIS",
    "iis_setup.html": "differences from IIS, deployment notes",
    "python.html": "calling Python from VBScript",
    "json.html": "JSON encode/decode helpers",
    "crypto.html": "bcrypt password hashing",
    "pdf.html": "PDF generation",
    "image.html": "image processing",
    "zip.html": "ZIP archives",
    "pop3_imap.html": "reading mail over POP3 / IMAP",
    "sample_apps.html": "worked example applications",
    "why_asppy.html": "design rationale and trade-offs",
    "index.html": "documentation home page",
}


def available() -> dict[str, Path]:
    """Map lookup name -> file, for every document that shipped.

    Names are matched without their extension too, so 'prompt-builder',
    'prompt-builder.html' and 'PROMPT-BUILDER' all resolve to the same page.
    """
    found: dict[str, Path] = {}
    for d in (GUIDES_DIR, HTML_DIR):
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.is_file():
                found[p.name] = p
    return found


def resolve(name: str) -> Path | None:
    """Find a document by full name or by stem, case-insensitively."""
    docs = available()
    for key, path in docs.items():
        if name.lower() == key.lower():
            return path
    for key, path in docs.items():
        if name.lower() == Path(key).stem.lower():
            return path
    # Last resort: unique substring match, so 'vibe' finds the ebook.
    hits = [p for k, p in docs.items() if name.lower() in k.lower()]
    return hits[0] if len(hits) == 1 else None


def do_list() -> int:
    docs = available()
    if not docs:
        print("asppy-guide: no bundled documentation found. This install looks "
              "incomplete - try 'pip install --force-reinstall asppy'.",
              file=sys.stderr)
        return 1

    print(f"Documentation bundled with ASPPY  ({GUIDES_DIR})\n")
    md = {k: v for k, v in docs.items() if k.lower().endswith(".md")}
    html = {k: v for k, v in docs.items() if not k.lower().endswith(".md")}

    def show(group: dict[str, Path]) -> None:
        for name, path in group.items():
            desc = DESCRIPTIONS.get(name, "")
            kb = path.stat().st_size / 1024
            print(f"  {Path(name).stem:<34} {kb:>6.1f} KB  {desc}")

    print("Markdown - print with 'asppy-guide NAME':")
    show(md)
    print("\nHTML - view with 'asppy-guide --open NAME':")
    show(html)
    print("\nTip: 'asppy-guide' with no arguments prints developers.md, which is "
          "\n     what an AI agent should read before writing any ASP.")
    return 0


def main(argv=None) -> int:
    from ASPPY import __version__

    ap = argparse.ArgumentParser(
        prog="asppy-guide",
        description="Print or open the documentation bundled with ASPPY. "
                    "With no arguments, prints developers.md - the document to "
                    "give an AI agent before it writes any ASP code.",
        epilog="examples:  asppy-guide | clip     "
               "asppy-guide --open prompt-builder     asppy-guide --list")
    ap.add_argument("name", nargs="?",
                    help="document to print (default: developers.md). Accepts "
                         "a short name, e.g. 'specifications' or 'cli'.")
    ap.add_argument("-l", "--list", action="store_true",
                    help="list every bundled document and exit")
    ap.add_argument("-o", "--open", metavar="NAME", dest="open_name",
                    help="open NAME in your default web browser")
    ap.add_argument("-p", "--path", action="store_true",
                    help="print the path of the document (or of the guides "
                         "folder, if no name is given) instead of its contents")
    ap.add_argument("-V", "--version", action="version",
                    version=f"ASPPY {__version__}")
    args = ap.parse_args(argv)

    if args.list:
        return do_list()

    if args.open_name:
        target = resolve(args.open_name)
        if target is None:
            print(f"asppy-guide: no document matching {args.open_name!r}. "
                  f"Try 'asppy-guide --list'.", file=sys.stderr)
            return 2
        webbrowser.open(target.as_uri())
        print(f"opened {target.name} in your browser")
        return 0

    if args.path and not args.name:
        print(GUIDES_DIR)
        return 0

    target = resolve(args.name or DEFAULT_DOC)
    if target is None:
        print(f"asppy-guide: no document matching {args.name!r}. "
              f"Try 'asppy-guide --list'.", file=sys.stderr)
        return 2

    if args.path:
        print(target)
        return 0

    if target.suffix.lower() == ".html":
        print(f"asppy-guide: {target.name} is an HTML page - open it with "
              f"'asppy-guide --open {target.stem}', or find it at:\n{target}",
              file=sys.stderr)
        return 2

    # Write bytes so the output pipes cleanly into a file or the clipboard
    # without Windows console encoding mangling non-ASCII characters.
    sys.stdout.buffer.write(target.read_bytes())
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
