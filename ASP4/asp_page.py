"""ASP page parsing/execution (HTML + VBScript blocks) without Python exec."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import List

from .parser import Parser, ParseError
from .ast_nodes import SubDef, FuncDef, ClassDef, OptionExplicitStmt
from .vm.interpreter import VBScriptRuntimeError
from .vb_errors import VBScriptCompilationError
from .asp_include import _INCLUDE_RE, resolve_include_path, _read_text_best_effort, expand_includes_with_deps
from .asp_cache import get_cached_monolithic_nodes


@dataclass
class HtmlNode:
    text: str
    start_line: int = 0
    start_col: int = 0


@dataclass
class ScriptNode:
    code: str
    start_line: int
    start_col: int
    program: List[object] | None = None  # Cached AST


@dataclass
class ExprNode:
    expr: str
    start_line: int
    start_col: int


@dataclass
class IncludeNode:
    path: str  # absolute physical path
    virtual: str  # virtual path
    start_line: int = 0
    start_col: int = 0


# ---------------------------------------------------------------------------
# Module-level granular AST cache: source_hash -> (prog, vbs_src)
# Avoids re-parsing unchanged pages on every request.
# ---------------------------------------------------------------------------

_granular_ast_cache: dict[str, tuple[list, str]] = {}


def _hash_nodes(nodes) -> str:
    """Produce a stable hash key from a list of ASP nodes."""
    h = hashlib.md5()
    for n in nodes:
        if isinstance(n, ScriptNode):
            h.update(b'S')
            h.update(n.code.encode('utf-8', errors='replace'))
        elif isinstance(n, ExprNode):
            h.update(b'E')
            h.update(n.expr.encode('utf-8', errors='replace'))
        elif isinstance(n, HtmlNode):
            h.update(b'H')
            h.update(n.text.encode('utf-8', errors='replace'))
    return h.hexdigest()


def compile_asp_nodes_cached(nodes) -> tuple[list, str]:
    """Cache-aware wrapper around compile_asp_nodes.

    IncludeNodes are excluded from hashing since flush_block_granular flushes
    the current block before each include, so each compiled unit never contains
    IncludeNodes directly.
    """
    key = _hash_nodes(nodes)
    cached = _granular_ast_cache.get(key)
    if cached is not None:
        return cached
    result = compile_asp_nodes(nodes)
    _granular_ast_cache[key] = result
    return result


def _find_asp_block_end(text: str, start: int) -> int:
    i = start + 2
    in_str = False
    in_comment = False
    while i < len(text) - 1:
        ch = text[i]
        if in_comment:
            if ch == '%' and text[i + 1] == '>':
                return i
            if ch == '\n':
                in_comment = False
            i += 1
            continue
        if in_str:
            if ch == '"':
                if i + 1 < len(text) and text[i + 1] == '"':
                    i += 2
                    continue
                in_str = False
            elif ch == '\n' or ch == '\r':
                # VBScript strings cannot span lines; if we hit a newline,
                # we assume the string ended (with an error) to allow finding '%>'.
                in_str = False
            i += 1
            continue

        if ch == '"':
            in_str = True
            i += 1
            continue
        if ch == "'":
            in_comment = True
            i += 1
            continue
        if (ch == 'R' or ch == 'r') and text[i:i + 3].lower() == 'rem':
            prev = text[i - 1] if i > start + 2 else ''
            nxt = text[i + 3] if i + 3 < len(text) else ''
            if (i == start + 2 or prev in ' \t\r\n:') and (nxt in ' \t\r\n'):
                in_comment = True
                i += 3
                continue
        if ch == '%' and text[i + 1] == '>':
            return i
        i += 1
    return -1


def parse_asp_file_to_nodes(path: str, docroot: str, current_virtual: str) -> List[object]:
    """Read file and parse into nodes (HTML, Script, Expr, Include)."""
    text = _read_text_best_effort(path)
    nodes = parse_asp_page(text)

    # Post-process HTML nodes to find Includes
    final_nodes = []

    def advance_loc(txt, ln, cl):
        for ch in txt:
            if ch == '\n':
                ln += 1
                cl = 1
            else:
                cl += 1
        return ln, cl

    for n in nodes:
        if isinstance(n, HtmlNode):
            # Split by include regex
            parts = []
            last_pos = 0

            cur_line = n.start_line
            cur_col = n.start_col

            for m in _INCLUDE_RE.finditer(n.text):
                # Add text before include
                pre_text = n.text[last_pos:m.start()]

                if pre_text:
                    # Strip leading whitespace-only content before an IncludeNode
                    # (to match IIS behavior of stripping whitespace around includes)
                    stripped_pre = pre_text.lstrip(' \t\r\n')
                    if stripped_pre:
                        parts.append(HtmlNode(pre_text, cur_line, cur_col))
                    # else: whitespace-only, drop it

                # Resolve include

                # Resolve include
                kind = m.group(1)
                val = m.group(2) or m.group(3) or m.group(4) or ""
                try:
                    phys, virt = resolve_include_path(kind, val, path, docroot, current_virtual)
                    parts.append(IncludeNode(phys, virt, cur_line, cur_col))
                except Exception:
                    raise

                # Advance over include text
                match_text = m.group(0)
                cur_line, cur_col = advance_loc(match_text, cur_line, cur_col)

                last_pos = m.end()

            # Add remaining text
            tail = n.text[last_pos:]
            if tail:
                # Strip whitespace-only tail that follows an IncludeNode
                # (to match the IIS behavior of stripping whitespace after includes)
                if not tail.strip(' \t\r\n'):
                    # Only whitespace - skip it
                    pass
                else:
                    parts.append(HtmlNode(tail, cur_line, cur_col))

            final_nodes.extend(parts)
        elif isinstance(n, ScriptNode):
            # Pre-parse VBScript AST
            try:
                # We do not parse AST here for ScriptNodes initially.
                # We wait until we group them into blocks.
                pass
            except Exception:
                pass
            final_nodes.append(n)
        else:
            final_nodes.append(n)



    # Attempt Granular Compilation
    # If any block fails to compile, we fallback to Monolithic Compilation (expand includes).

    merged_nodes = []
    current_block = []

    # We define a helper to handle compilation.
    # If it raises, we catch and fallback.

    def flush_block_granular():
        if current_block:
            prog, src = compile_asp_nodes_cached(current_block)
            merged_nodes.append(ScriptNode(src, 0, 0, program=prog))
            current_block.clear()

    try:
        # Clone list logic for test: if strict checking is needed, we could verify blocks first.
        # But compile_asp_nodes performs parsing.

        # NOTE: If we are here, we are assuming we can link granularly.
        # If 'path' is a root file, we process its includes.
        # If the includes have split blocks, 'flush_block_granular' might not detect it
        # until the include itself is parsed?
        # Actually, granular execution parses includes *separately*.
        # So we only care if *this file* has syntax errors (incomplete blocks).

        for n in final_nodes:
            if isinstance(n, IncludeNode):
                flush_block_granular()
                merged_nodes.append(n)
            else:
                current_block.append(n)
        flush_block_granular()
        return merged_nodes

    except (ParseError, VBScriptRuntimeError, Exception):
        # Fallback: The file is not granular-compatible (e.g. split blocks across includes).
        # We must expand includes fully and compile monolithically.
        # Use Cached Monolithic Compilation to solve performance issues for QS.

        def monolithic_parser(p):
            # Expands includes recursively and tracks dependencies
            exp_text, deps = expand_includes_with_deps(text, current_phys=p, docroot=docroot, current_virtual=current_virtual)
            exp_nodes = parse_asp_page(exp_text)
            prog, src = compile_asp_nodes(exp_nodes)
            # Return list with single ScriptNode, and deps set
            return [ScriptNode(src, 0, 0, program=prog)], deps

        # We need to use 'path' as the cache key.
        # However, 'text' argument to expand_includes is passed from above.
        # Since 'parse_asp_file_to_nodes' is called with 'path', we can use that.
        # But wait, 'text' was already read. If we rely on cache, we don't need 'text'.
        # 'monolithic_parser' re-reads text implicitly? No, expand_includes_with_deps uses 'text' for root.
        # For simplicity, we can pass the text we already have.

        return get_cached_monolithic_nodes(path, monolithic_parser)


def parse_asp_page(text: str) -> List[object]:
    """Split an .asp page into HTML/Script/Expr nodes.

    Implements IIS quirk: whitespace-only lines between consecutive shorthand
    expression blocks do not emit CR/LF (and indentation on those blank lines are dropped).
    """
    nodes: List[object] = []
    pos = 0
    line = 1
    col = 1
    prev_was_expr = False
    prev_was_code = False
    prev_was_directive = False
    while True:
        start = text.find('<%', pos)
        if start == -1:
            tail = text[pos:]
            if tail:
                nodes.append(HtmlNode(tail, line, col))
            break

        html = text[pos:start]
        # record start of html segment
        html_start_line = line
        html_start_col = col

        # advance line/col over html segment
        if html:
            for ch in html:
                if ch == '\n':
                    line += 1
                    col = 1
                else:
                    col += 1
        end = _find_asp_block_end(text, start)
        if end == -1:
            # Treat remainder as HTML
            nodes.append(HtmlNode(text[pos:], line, col))
            break

        # record start position of script block (after '<%')
        block_line = line
        block_col = col + 2

        code = text[start + 2:end]
        code_stripped = code.strip()
        cur_is_expr = bool(code_stripped.startswith('='))
        cur_is_directive = bool(code_stripped.startswith('@'))

        if html:
            if (prev_was_code or prev_was_directive) and (cur_is_expr or (not cur_is_expr and not cur_is_directive)) and html.strip(' \t\r\n') == '':
                # Only whitespace between code blocks: drop any lines entirely.
                if ('\r' not in html) and ('\n' not in html):
                    # inline spaces: keep
                    nodes.append(HtmlNode(html, html_start_line, html_start_col))
                # else: drop
            else:
                nodes.append(HtmlNode(html, html_start_line, html_start_col))

        if cur_is_directive:
            # ASP directive like: <%@ Language="VBScript" %>
            prev_was_expr = False
            prev_was_code = False
            prev_was_directive = True
        elif cur_is_expr:
            expr_src = code_stripped[1:].strip()
            nodes.append(ExprNode(expr_src, block_line, block_col))
            prev_was_expr = True
            prev_was_code = True
            prev_was_directive = False
        else:
            nodes.append(ScriptNode(code_stripped, block_line, block_col))
            prev_was_expr = False
            prev_was_code = True
            prev_was_directive = False

        # advance line/col over full block including '<%' .. '%>'
        raw_block = text[start:end + 2]
        for ch in raw_block:
            if ch == '\n':
                line += 1
                col = 1
            else:
                col += 1

        pos = end + 2

    return nodes


def exec_asp_nodes(nodes, interpreter):
    """Execute parsed ASP nodes.

    To match Classic ASP, we compile the whole page into a single VBScript program
    (with HTML and <%= %> nodes translated into Response.Write statements) and then
    interpret it. This allows loops/ifs to span multiple <% ... %> blocks.
    """
    prog, vbs_src = compile_asp_nodes_cached(nodes)
    exec_vbscript_program(prog, interpreter, vbs_src=vbs_src)


def compile_asp_nodes(nodes) -> tuple[list[object], str]:
    """Compile an ASP unit to a VBScript AST program.

    This is the expensive part (build VBScript source, parse to AST, and perform
    IIS-like Option Explicit placement validation). It's safe to cache.
    """

    # Validate Option Explicit placement (IIS-like): it must appear before any
    # other VBScript statements or <%= %> blocks in the page/unit.
    saw_any_exec = False
    saw_option_explicit = False
    for n in nodes:
        if isinstance(n, ExprNode) and n.expr:
            saw_any_exec = True
            continue
        if isinstance(n, ScriptNode) and n.code:
            try:
                prog_local = Parser(n.code).parse_program()
            except Exception:
                # Let the full compilation path raise the parse error.
                prog_local = []
            opt_idx = [i for i, s in enumerate(prog_local) if isinstance(s, OptionExplicitStmt)]
            if opt_idx:
                if saw_any_exec or saw_option_explicit:
                    raise VBScriptRuntimeError("Statement expected")
                if len(opt_idx) != 1 or opt_idx[0] != 0:
                    raise VBScriptRuntimeError("Statement expected")
                saw_option_explicit = True
                if len(prog_local) > 1:
                    saw_any_exec = True
            else:
                if len(prog_local) > 0:
                    saw_any_exec = True

    vbs_src = build_vbscript_from_nodes(nodes)
    try:
        prog = Parser(vbs_src).parse_program()
    except (ParseError, VBScriptCompilationError) as e:
        # Ensure we have position info attached so _attach_location can use it
        if not hasattr(e, 'vbs_pos'):
            m = re.search(r"position\s+(\d+)", str(e))
            if m:
                try:
                    setattr(e, 'vbs_pos', int(m.group(1)))
                except ValueError:
                    pass

        # Attach source context (line, col, snippet) to the exception
        _attach_location(e, None, 1, 1, vbs_src)
        raise
    return prog, vbs_src


def exec_vbscript_program(prog, interpreter, *, vbs_src: str = ""):
    """Execute a pre-parsed VBScript program for an ASP unit."""

    prev_option_explicit = getattr(interpreter, 'option_explicit', False)
    prev_on_error = getattr(interpreter, 'on_error_resume_next', False)
    try:
        try:
            interpreter._current_vbs_src = vbs_src
            interpreter._current_asp_path = getattr(getattr(interpreter, 'ctx', None), 'response', None)
            if interpreter._current_asp_path is not None:
                interpreter._current_asp_path = getattr(interpreter._current_asp_path, '_current_path', '')
        except Exception:
            pass
        # Each Server.Execute'd ASP is its own compilation unit in IIS.
        interpreter.option_explicit = False
        interpreter.on_error_resume_next = False

        # Compile-time: OPTION EXPLICIT affects the whole unit.
        for s in prog:
            if isinstance(s, OptionExplicitStmt):
                interpreter.exec_stmt(s)
                break

        # If enabled, predeclare all Dim'd variables so use-before-Dim works.
        if getattr(interpreter, 'option_explicit', False):
            decls = []
            interpreter._collect_dim_decls(prog, decls)
            interpreter._predeclare_dim_decls(interpreter.env, decls)

        defs = []
        interpreter._collect_proc_defs(prog, defs)
        for s in defs:
            if isinstance(s, (ClassDef, SubDef, FuncDef)):
                interpreter.exec_stmt(s)
        for s in prog:
            if isinstance(s, OptionExplicitStmt):
                continue
            if not isinstance(s, (ClassDef, SubDef, FuncDef)):
                interpreter.exec_stmt(s)
    except Exception as e:
        _attach_location(e, interpreter, 1, 1, vbs_src)
        raise
    finally:
        try:
            interpreter.option_explicit = prev_option_explicit
        except Exception:
            pass
        try:
            interpreter.on_error_resume_next = prev_on_error
        except Exception:
            pass


def build_vbscript_from_nodes(nodes) -> str:
    def _vb_str_literal(s: str) -> str:
        return '"' + s.replace('"', '""') + '"'

    out_lines = []
    for n in nodes:
        if isinstance(n, ScriptNode):
            if n.code:
                out_lines.append(n.code)
            continue
        if isinstance(n, ExprNode):
            if n.expr:
                out_lines.append(f"Response.Write ({n.expr})")
            continue
        if isinstance(n, HtmlNode):
            if not n.text:
                continue
            # Preserve original newline style (\r\n vs \n vs \r).
            t = n.text
            i = 0
            expr_parts = []
            while i < len(t):
                # Find next newline char
                j = i
                while j < len(t) and t[j] not in ('\r', '\n'):
                    j += 1
                chunk = t[i:j]
                if chunk:
                    expr_parts.append(_vb_str_literal(chunk))
                if j >= len(t):
                    break
                # Emit newline token
                if t[j] == '\r':
                    if j + 1 < len(t) and t[j + 1] == '\n':
                        expr_parts.append("Chr(13)")
                        expr_parts.append("Chr(10)")
                        j += 2
                    else:
                        expr_parts.append("Chr(13)")
                        j += 1
                else:
                    expr_parts.append("Chr(10)")
                    j += 1
                i = j
            if expr_parts:
                # Avoid extremely deep concat ASTs which can hit Python recursion limits
                # on large HTML pages; emit multiple Response.Write statements instead.
                max_parts = 200
                for i in range(0, len(expr_parts), max_parts):
                    chunk = expr_parts[i:i + max_parts]
                    out_lines.append("Response.Write " + " & ".join(chunk))
            continue
        raise Exception("Unknown ASP node")

    return "\n".join(out_lines) + "\n"


def _attach_location(exc: Exception, interpreter, start_line: int, start_col: int, src: str):
    # Best-effort location info; stored on the exception object.
    if hasattr(exc, 'asp_location_attached'):
        return
    setattr(exc, 'asp_location_attached', True)
    pos = getattr(exc, 'vbs_pos', None)
    if pos is not None and isinstance(src, str) and 0 <= int(pos) <= len(src):
        pos = int(pos)
        line = src.count('\n', 0, pos) + 1
        last_nl = src.rfind('\n', 0, pos)
        col = pos + 1 if last_nl == -1 else pos - last_nl
        line_start = 0 if last_nl == -1 else last_nl + 1
        line_end = src.find('\n', pos)
        if line_end == -1:
            line_end = len(src)
        src_line = src[line_start:line_end]
        setattr(exc, 'asp_start_line', int(line))
        setattr(exc, 'asp_start_col', int(col))
        setattr(exc, 'asp_source_block', src_line)
        return
    setattr(exc, 'asp_start_line', int(start_line))
    setattr(exc, 'asp_start_col', int(start_col))
    setattr(exc, 'asp_source_block', src)
