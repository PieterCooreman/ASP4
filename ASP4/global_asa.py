"""Global.asa support (minimal, cross-platform).

Supports:
- Application_OnStart / Application_OnEnd
- Session_OnStart / Session_OnEnd
- <!--#include file=... --> and <!--#include virtual=... -->
- <object runat="server" scope="application|session" id="..." progid="..."> declarations
- <!--METADATA TYPE="TypeLib" ... --> declarations (accepted, currently no-op)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import List, Set


@dataclass
class ObjectDecl:
    scope: str
    obj_id: str
    progid: str


@dataclass
class GlobalAsaCompiled:
    app_on_start: str = ""
    app_on_end: str = ""
    sess_on_start: str = ""
    sess_on_end: str = ""
    app_objects: List[ObjectDecl] = field(default_factory=list)
    sess_objects: List[ObjectDecl] = field(default_factory=list)
    typelibs: List[str] = field(default_factory=list)


def load_global_asa(docroot: str) -> str:
    path = os.path.join(docroot, 'global.asa')
    if not os.path.isfile(path):
        return ""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def compile_global_asa(docroot: str) -> GlobalAsaCompiled:
    txt = load_global_asa(docroot)
    if not txt:
        return GlobalAsaCompiled()

    expanded = _expand_includes(txt, os.path.join(docroot, 'global.asa'), docroot)
    comp = GlobalAsaCompiled()

    # Object declarations outside <script>
    for decl in _parse_object_decls(expanded):
        if decl.scope == 'application':
            comp.app_objects.append(decl)
        elif decl.scope == 'session':
            comp.sess_objects.append(decl)

    # TypeLib metadata (no-op)
    comp.typelibs = _parse_typelib_metadata(expanded)

    # Extract server-side VBScript blocks
    script_text = "\n".join(_extract_script_blocks(expanded))
    comp.app_on_start = _extract_event_body(script_text, 'Application_OnStart')
    comp.app_on_end = _extract_event_body(script_text, 'Application_OnEnd')
    comp.sess_on_start = _extract_event_body(script_text, 'Session_OnStart')
    comp.sess_on_end = _extract_event_body(script_text, 'Session_OnEnd')
    return comp


def _extract_script_blocks(text: str):
    # naive extraction of <script ... runat="server"> ... </script>
    blocks = []
    for m in re.finditer(r"(?is)<script\b([^>]*)>(.*?)</script>", text):
        attrs = m.group(1) or ""
        body = m.group(2) or ""
        if re.search(r"(?is)\brunat\s*=\s*\"server\"", attrs) is None:
            continue
        blocks.append(body)
    return blocks


def _extract_event_body(script_text: str, event_name: str) -> str:
    want = event_name.strip().lower()
    lines = script_text.splitlines(True)
    in_sub = False
    body = []
    # IIS effectively processes Global.asa as a single merged script after includes.
    # To keep behavior pragmatic, allow multiple Sub blocks with the same event name
    # and concatenate their bodies in appearance order.
    for line in lines:
        s = line.strip()
        sl = s.lower()
        if not in_sub:
            if sl.startswith('sub ') and sl[4:].strip().lower() == want:
                in_sub = True
            continue
        if sl == 'end sub':
            in_sub = False
            continue
        body.append(line)
    return "".join(body).strip()


def _parse_object_decls(text: str):
    decls = []
    # <object ...> ... </object>
    for m in re.finditer(r"(?is)<object\b([^>]*)>(.*?)</object>", text):
        attrs = m.group(1) or ""
        if re.search(r"(?is)\brunat\s*=\s*\"server\"", attrs) is None:
            continue
        scope = _attr(attrs, 'scope').lower()
        obj_id = _attr(attrs, 'id')
        progid = _attr(attrs, 'progid')
        if not scope or not obj_id or not progid:
            continue
        decls.append(ObjectDecl(scope=scope, obj_id=obj_id, progid=progid))
    return decls


def _parse_typelib_metadata(text: str):
    out = []
    for m in re.finditer(r"(?is)<!--\s*METADATA\s+TYPE\s*=\s*\"TypeLib\"(.*?)-->", text):
        out.append(m.group(1).strip())
    return out


def _attr(attrs: str, name: str) -> str:
    m = re.search(r"(?is)\b" + re.escape(name) + r"\s*=\s*\"([^\"]*)\"", attrs)
    if not m:
        return ""
    return m.group(1)


def _expand_includes(text: str, current_file: str, docroot: str, _depth: int = 0, _seen: Set[str] | None = None) -> str:
    if _seen is None:
        _seen = set()
    seen: Set[str] = _seen
    if _depth > 10:
        return text

    def repl(m):
        nonlocal seen
        kind = (m.group(1) or '').lower()
        val = (m.group(2) or m.group(3) or m.group(4) or '')

        base_dir = os.path.dirname(os.path.abspath(current_file))
        if kind == 'file':
            path = os.path.abspath(os.path.join(base_dir, val))
        else:
            rel = val.lstrip('/\\')
            path = os.path.abspath(os.path.join(os.path.abspath(docroot), rel))
        if path in seen:
            return ""
        seen.add(path)
        if not os.path.isfile(path):
            return ""
        with open(path, 'r', encoding='utf-8') as f:
            inc = f.read()
        inc = _expand_includes(inc, path, docroot, _depth=_depth + 1, _seen=seen)
        return inc

    # <!--#include file=... --> or <!--#include virtual=... -->
    return re.sub(
        r"(?is)<!--\s*#include\s+(file|virtual)\s*=\s*(?:\"([^\"]+)\"|'([^']+)'|([^\s>]+))\s*-->",
        repl,
        text,
    )
