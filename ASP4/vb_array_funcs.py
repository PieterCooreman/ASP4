"""VBScript array-related built-ins (minimal, ISO/portable)."""

from __future__ import annotations

from .vb_runtime import vbs_cstr
from .vm.values import VBArray


def IsArray(v):
    return isinstance(v, VBArray)


def LBound(arr, dimension=1):
    if not isinstance(arr, VBArray):
        raise Exception("Type mismatch")
    return arr.lbound(int(dimension))


def UBound(arr, dimension=1):
    if not isinstance(arr, VBArray):
        raise Exception("Type mismatch")
    return arr.ubound(int(dimension))


def Array(*args):
    a = VBArray(len(args) - 1, allocated=True, dynamic=True)
    for i, v in enumerate(args):
        a.__vbs_index_set__(i, v)
    return a


def Split(s, delimiter=" ", count=-1, compare=0):
    txt = vbs_cstr(s)
    delim = vbs_cstr(delimiter)
    try:
        cnt = int(count)
    except Exception:
        cnt = -1
    cmp_mode = int(compare)

    if cnt == 0:
        return VBArray(-1, allocated=True, dynamic=True)

    def _split_chars(t, limit):
        if limit is None or limit < 0:
            return list(t)
        if limit <= 1:
            return [t]
        if limit >= len(t):
            return list(t)
        out = list(t[:limit - 1])
        out.append(t[limit - 1:])
        return out

    def _split_textual(t, d, limit):
        tl = t.lower()
        dl = d.lower()
        out = []
        start = 0
        n = 0
        while True:
            if limit > 0 and n >= limit - 1:
                break
            idx = tl.find(dl, start)
            if idx == -1:
                break
            out.append(t[start:idx])
            start = idx + len(d)
            n += 1
        out.append(t[start:])
        return out

    if delim == "":
        parts = _split_chars(txt, cnt)
    else:
        if cmp_mode == 1:
            parts = _split_textual(txt, delim, cnt)
        else:
            maxsplit = cnt - 1 if cnt > 0 else -1
            parts = txt.split(delim, maxsplit=maxsplit)

    a = VBArray(len(parts) - 1, allocated=True, dynamic=True)
    for i, p in enumerate(parts):
        a.__vbs_index_set__(i, p)
    return a


def Join(arr, delimiter=" "):
    if not isinstance(arr, VBArray):
        raise Exception("Type mismatch")
    delim = vbs_cstr(delimiter)
    return delim.join(vbs_cstr(x) for x in arr)


def Filter(stringarray, value, include=True, compare=0):
    # VBScript Filter: returns zero-based array of matching elements.
    if not isinstance(stringarray, VBArray):
        raise Exception("Type mismatch")
    needle = vbs_cstr(value)
    inc = bool(include)
    cmp_mode = int(compare)

    out = []
    if cmp_mode == 1:
        needle_cmp = needle.lower()
        for x in stringarray:
            s = vbs_cstr(x)
            ok = (needle_cmp in s.lower())
            if ok == inc:
                out.append(s)
    else:
        for x in stringarray:
            s = vbs_cstr(x)
            ok = (needle in s)
            if ok == inc:
                out.append(s)

    a = VBArray(len(out) - 1, allocated=True, dynamic=True)
    for i, v in enumerate(out):
        a.__vbs_index_set__(i, v)
    return a
