"""PDF utility shim for VBScript (fpdf2)."""

from __future__ import annotations

try:
    from fpdf import FPDF as _FPDF
except Exception:  # pragma: no cover
    _FPDF = None

from .vb_runtime import VBScriptRuntimeError, vbs_cstr
from .vm.values import VBEmpty, VBNull, VBNothing


def _require_fpdf():
    global _FPDF
    if _FPDF is None:
        try:
            from fpdf import FPDF as _FPDF
        except Exception:
            import sys
            exe = getattr(sys, "executable", "python")
            raise VBScriptRuntimeError(
                "fpdf2 is not available. Install with: "
                + exe
                + " -m pip install fpdf2"
            )


def _to_float(v, name):
    try:
        return float(v)
    except Exception:
        raise VBScriptRuntimeError(f"Invalid {name}")


def _to_int(v, name):
    try:
        return int(v)
    except Exception:
        raise VBScriptRuntimeError(f"Invalid {name}")


class PdfDoc:
    def __init__(self, orientation="P", unit="mm", format="A4"):
        _require_fpdf()
        self._pdf = _FPDF(orientation=orientation, unit=unit, format=format)

    def add_page(self, orientation=""):
        if orientation is None:
            orientation = ""
        self._pdf.add_page(orientation=orientation)
        return self

    def set_margins(self, left, top, right=None):
        l = _to_float(left, "left")
        t = _to_float(top, "top")
        r = _to_float(right, "right") if right is not None else l
        self._pdf.set_margins(l, t, r)
        return self

    def set_auto_page_break(self, auto, margin=0):
        m = _to_float(margin, "margin")
        self._pdf.set_auto_page_break(bool(auto), margin=m)
        return self

    def set_font(self, family, style="", size=12):
        fam = vbs_cstr(family)
        if fam == "":
            raise VBScriptRuntimeError("Pdf.set_font: family is required")
        st = vbs_cstr(style)
        sz = _to_int(size, "size")
        self._pdf.set_font(fam, style=st, size=sz)
        return self

    def set_text_color(self, r, g=None, b=None):
        if g is None and b is None:
            self._pdf.set_text_color(_to_int(r, "r"))
        else:
            self._pdf.set_text_color(_to_int(r, "r"), _to_int(g, "g"), _to_int(b, "b"))
        return self

    def set_draw_color(self, r, g=None, b=None):
        if g is None and b is None:
            self._pdf.set_draw_color(_to_int(r, "r"))
        else:
            self._pdf.set_draw_color(_to_int(r, "r"), _to_int(g, "g"), _to_int(b, "b"))
        return self

    def set_fill_color(self, r, g=None, b=None):
        if g is None and b is None:
            self._pdf.set_fill_color(_to_int(r, "r"))
        else:
            self._pdf.set_fill_color(_to_int(r, "r"), _to_int(g, "g"), _to_int(b, "b"))
        return self

    def set_line_width(self, width):
        self._pdf.set_line_width(_to_float(width, "width"))
        return self

    def fill_page(self, r, g=None, b=None):
        if g is None and b is None:
            color = (_to_int(r, "r"), _to_int(r, "r"), _to_int(r, "r"))
        else:
            color = (_to_int(r, "r"), _to_int(g, "g"), _to_int(b, "b"))
        self._pdf.set_fill_color(*color)
        w = getattr(self._pdf, "w", 0)
        h = getattr(self._pdf, "h", 0)
        self._pdf.rect(0, 0, w, h, style="F")
        return self

    def text(self, x, y, text):
        self._pdf.text(_to_float(x, "x"), _to_float(y, "y"), vbs_cstr(text))
        return self

    def cell(self, w, h=0, text="", border=0, ln=0, align="", fill=False, link=""):
        self._pdf.cell(
            w=_to_float(w, "w"),
            h=_to_float(h, "h"),
            txt=vbs_cstr(text),
            border=border,
            ln=_to_int(ln, "ln"),
            align=vbs_cstr(align),
            fill=bool(fill),
            link=vbs_cstr(link),
        )
        return self

    def multi_cell(self, w, h, text, border=0, align="", fill=False):
        self._pdf.multi_cell(
            w=_to_float(w, "w"),
            h=_to_float(h, "h"),
            txt=vbs_cstr(text),
            border=border,
            align=vbs_cstr(align),
            fill=bool(fill),
        )
        return self

    def set_xy(self, x, y):
        self._pdf.set_xy(_to_float(x, "x"), _to_float(y, "y"))
        return self

    def ln(self, h=0):
        self._pdf.ln(_to_float(h, "h"))
        return self

    def image(self, path, x=None, y=None, w=0, h=0):
        p = vbs_cstr(path)
        if p == "":
            raise VBScriptRuntimeError("Pdf.image: path is required")
        kwargs = {}
        if x is not None and x is not VBEmpty and x is not VBNull and x is not VBNothing:
            kwargs["x"] = _to_float(x, "x")
        if y is not None and y is not VBEmpty and y is not VBNull and y is not VBNothing:
            kwargs["y"] = _to_float(y, "y")
        if w is not None and w is not VBEmpty and w is not VBNull and w is not VBNothing:
            kwargs["w"] = _to_float(w, "w")
        if h is not None and h is not VBEmpty and h is not VBNull and h is not VBNothing:
            kwargs["h"] = _to_float(h, "h")
        self._pdf.image(p, **kwargs)
        return self

    def output(self, path):
        p = vbs_cstr(path)
        if p == "":
            raise VBScriptRuntimeError("Pdf.output: path is required")
        self._pdf.output(p)
        return p


class PdfShim:
    def New(self, orientation="P", unit="mm", format="A4"):
        return PdfDoc(orientation=orientation, unit=unit, format=format)


ASP4_PDF = PdfShim()
