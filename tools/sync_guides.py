#!/usr/bin/env python3
"""Copy the documentation set into ASPPY/guides/ so it ships with the package.

Why this exists
---------------
GitHub Pages serves the website from ``docs/`` at the repository root, so that
folder cannot move. But ``pip install asppy`` must also deliver the docs: anyone
working with ASPPY - human or AI agent - needs ``developers.md`` and the
prompt builders before they can write a single line, and a runtime nobody can
learn is not a usable runtime.

So ``docs/`` stays where GitHub Pages needs it and this script mirrors it into
``ASPPY/guides/``, which is declared as package data in pyproject.toml. The
copies are committed to git, so users never run a build step - consistent with
ASPPY's "no build step, ever" promise.

Run this whenever the docs or README change, and always before cutting a
release::

    python tools/sync_guides.py            # sync, report what changed
    python tools/sync_guides.py --check    # verify only, exit 1 if stale

``--check`` is the CI-friendly form: it fails if the packaged copies have
drifted from the originals, so a release can never ship stale documentation.

Screenshots under docs/screenshots/ are deliberately NOT copied. Only the
GitHub README references them, and it does so through absolute
raw.githubusercontent.com URLs, so bundling ~540 KB of PNGs would bloat the
wheel for no benefit.
"""
from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GUIDES_DIR = REPO_ROOT / "ASPPY" / "guides"

# www_starter is mirrored too, so `asppy-new myapp` can scaffold a real MVC app
# for someone who pip-installed and has no checkout. developers.md tells every
# agent to "start every new app from www_starter", so that folder has to travel
# with the package or the instruction is a dead end.
STARTER_SRC_DIR = REPO_ROOT / "www_starter"
STARTER_DST_DIR = REPO_ROOT / "ASPPY" / "starter"

# Markdown files copied from the repo root into ASPPY/guides/.
ROOT_DOCS = ("developers.md", "README.md")

# Every .html page in docs/ is copied into ASPPY/guides/html/.
HTML_SRC_DIR = REPO_ROOT / "docs"
HTML_DST_DIR = GUIDES_DIR / "html"

# Pages that exist only to serve the website and make no sense offline.
# prompt_builder.html is a meta-refresh stub kept so an old URL keeps working.
HTML_EXCLUDE = frozenset({"prompt_builder.html"})


def planned_copies() -> list[tuple[Path, Path]]:
    """Return the (source, destination) pairs this script is responsible for."""
    pairs: list[tuple[Path, Path]] = []

    for name in ROOT_DOCS:
        src = REPO_ROOT / name
        if not src.is_file():
            raise SystemExit(f"sync_guides: expected file is missing: {src}")
        pairs.append((src, GUIDES_DIR / name))

    if not HTML_SRC_DIR.is_dir():
        raise SystemExit(f"sync_guides: docs folder is missing: {HTML_SRC_DIR}")
    for src in sorted(HTML_SRC_DIR.glob("*.html")):
        if src.name in HTML_EXCLUDE:
            continue
        pairs.append((src, HTML_DST_DIR / src.name))

    if not STARTER_SRC_DIR.is_dir():
        raise SystemExit(f"sync_guides: starter folder is missing: {STARTER_SRC_DIR}")
    for src in sorted(STARTER_SRC_DIR.rglob("*")):
        if src.is_file():
            rel = src.relative_to(STARTER_SRC_DIR)
            pairs.append((src, STARTER_DST_DIR / rel))

    return pairs


def is_stale(src: Path, dst: Path) -> bool:
    """True if dst is missing or differs from src (content, not timestamps)."""
    if not dst.is_file():
        return True
    return not filecmp.cmp(src, dst, shallow=False)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="sync_guides.py",
        description="Mirror docs/ and the root markdown files into "
                    "ASPPY/guides/ so they ship inside the installed package.")
    ap.add_argument("--check", action="store_true",
                    help="do not write anything; exit 1 if any packaged copy "
                         "is missing or out of date (use this in CI)")
    args = ap.parse_args(argv)

    pairs = planned_copies()
    stale = [(s, d) for s, d in pairs if is_stale(s, d)]

    # Anything in the destination that no longer has a source is orphaned -
    # e.g. a docs page that was renamed or deleted upstream.
    expected = {d.resolve() for _, d in pairs}
    orphans = []
    for root in (GUIDES_DIR, STARTER_DST_DIR):
        if not root.exists():
            continue
        for existing in root.rglob("*"):
            if existing.is_file() and existing.resolve() not in expected:
                orphans.append(existing)

    if args.check:
        if not stale and not orphans:
            print(f"sync_guides: up to date ({len(pairs)} files)")
            return 0
        for s, d in stale:
            print(f"  STALE   {d.relative_to(REPO_ROOT)}")
        for o in orphans:
            print(f"  ORPHAN  {o.relative_to(REPO_ROOT)}")
        print(f"\nsync_guides: {len(stale)} stale, {len(orphans)} orphaned. "
              f"Run 'python tools/sync_guides.py' to fix.")
        return 1

    for src, dst in pairs:
        if is_stale(src, dst):
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"  updated  {dst.relative_to(REPO_ROOT)}")

    for o in orphans:
        o.unlink()
        print(f"  removed  {o.relative_to(REPO_ROOT)}")

    total_kb = sum(d.stat().st_size for _, d in pairs) / 1024
    print(f"\nsync_guides: {len(pairs)} files bundled "
          f"({total_kb:,.1f} KB), {len(stale)} updated, {len(orphans)} removed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
