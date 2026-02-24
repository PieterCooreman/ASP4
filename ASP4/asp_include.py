"""ASP #include directive support.

Implements Classic ASP style includes:
  <!--#include file="relative\\path.inc" -->
  <!--#include virtual="/absolute/from/app/root.inc" -->

Includes are expanded as plain text *before* ASP/VBScript parsing/execution.
"""

from __future__ import annotations

import os
import re


def _read_text_best_effort(path: str) -> str:
    # Classic ASP content is commonly ANSI (cp1252) or UTF-8.
    with open(path, 'rb') as f:
        data = f.read()
    try:
        return data.decode('utf-8-sig')
    except Exception:
        return data.decode('cp1252', errors='replace')


class IncludeError(Exception):
    pass


_INCLUDE_RE = re.compile(
    r"(?is)<!--\s*#include\s+(file|virtual)\s*=\s*(?:\"([^\"]+)\"|'([^']+)'|([^\s>]+))\s*-->",
)


def resolve_include_path(kind: str, val: str, current_phys: str, docroot: str, current_virtual: str) -> tuple[str, str]:
    docroot_abs = os.path.abspath(docroot)
    phys_path_abs = os.path.abspath(current_phys)
    virt_path_norm = current_virtual

    kind_l = kind.lower()
    val_s = val.strip()
    if kind_l == 'file':
        base = os.path.dirname(phys_path_abs)
        phys = os.path.abspath(os.path.join(base, val_s))
        virt = _join_virtual(_dir_virtual(virt_path_norm), val_s)
    else:
        rel = val_s.lstrip('/\\')
        phys = os.path.abspath(os.path.join(docroot_abs, rel))
        virt = '/' + rel.replace('\\', '/')
    # Prevent traversal outside docroot
    if os.path.commonpath([docroot_abs, phys]) != docroot_abs:
        raise IncludeError('Include path outside application')
    return phys, virt


def expand_includes_with_deps(text: str, *, current_phys: str, docroot: str, current_virtual: str, max_depth: int = 20):
    """Expand includes and return (expanded_text, deps).

    deps is a set of absolute physical paths of all files that contributed to the
    final expanded text (including current_phys).
    """
    deps: set[str] = set()

    def rec(t: str, phys_path: str, virt_path: str, depth: int, stack: list[str], stack_set: set[str]) -> str:
        if depth > max_depth:
            raise IncludeError('Include max depth exceeded')

        phys_path_abs = os.path.abspath(phys_path)
        deps.add(phys_path_abs)

        def repl(m):
            kind = m.group(1)
            val = m.group(2) or m.group(3) or m.group(4) or ""
            inc_phys, inc_virt = resolve_include_path(kind, val, phys_path_abs, docroot, virt_path)

            if inc_phys in stack_set:
                raise IncludeError('Include cycle detected')
            if not os.path.isfile(inc_phys):
                raise IncludeError(f'Include not found: {val}')
            inc_text = _read_text_best_effort(inc_phys)
            stack.append(inc_phys)
            stack_set.add(inc_phys)
            try:
                return rec(inc_text, inc_phys, inc_virt, depth + 1, stack, stack_set)
            finally:
                stack.pop()
                stack_set.discard(inc_phys)

        return _INCLUDE_RE.sub(repl, t)

    cur_phys_abs0 = os.path.abspath(current_phys)
    stack = [cur_phys_abs0]
    stack_set = {cur_phys_abs0}
    out = rec(text, cur_phys_abs0, current_virtual, 0, stack, stack_set)
    return out, deps


def expand_includes(text: str, *, current_phys: str, docroot: str, current_virtual: str, max_depth: int = 20) -> str:
    """Expand #include directives recursively."""
    result, _ = expand_includes_with_deps(
        text,
        current_phys=current_phys,
        docroot=docroot,
        current_virtual=current_virtual,
        max_depth=max_depth,
    )
    return result


def _dir_virtual(vpath: str) -> str:
    v = (vpath or '/').split('?', 1)[0]
    if not v.startswith('/'):
        v = '/' + v
    if v.endswith('/'):
        v = v[:-1]
    if '/' not in v[1:]:
        return '/'
    return v.rsplit('/', 1)[0] + '/'


def _join_virtual(base_dir: str, rel: str) -> str:
    base = base_dir or '/'
    if not base.endswith('/'):
        base += '/'
    rel = rel.replace('\\', '/')
    # naive normalization
    return (base + rel).replace('//', '/')