"""Pillow image shim for VBScript."""

from __future__ import annotations

from typing import Any

try:
    from PIL import Image as _PILImage
    from PIL import ImageDraw as _PILImageDraw
    from PIL import ImageFilter as _PILImageFilter
    from PIL import ImageEnhance as _PILImageEnhance
except Exception:  # pragma: no cover
    _PILImage = None
    _PILImageDraw = None
    _PILImageFilter = None
    _PILImageEnhance = None

from .vb_runtime import VBScriptRuntimeError, vbs_cstr
from .vm.values import VBArray, VBEmpty, VBNull, VBNothing


def _require_pillow():
    global _PILImage, _PILImageDraw, _PILImageFilter, _PILImageEnhance
    if _PILImage is None:
        try:
            from PIL import Image as _PILImage
            from PIL import ImageDraw as _PILImageDraw
            from PIL import ImageFilter as _PILImageFilter
            from PIL import ImageEnhance as _PILImageEnhance
        except Exception:
            import sys
            exe = getattr(sys, "executable", "python")
            raise VBScriptRuntimeError(
                "Pillow is not available. Install with: "
                + exe
                + " -m pip install pillow"
            )


def _to_int(v, name):
    try:
        return int(v)
    except Exception:
        raise VBScriptRuntimeError(f"Invalid {name}")


def _to_float(v, name):
    try:
        return float(v)
    except Exception:
        raise VBScriptRuntimeError(f"Invalid {name}")


def _to_tuple2(value, name):
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return (_to_int(value[0], name), _to_int(value[1], name))
    if isinstance(value, VBArray):
        try:
            return (_to_int(value.__vbs_index_get__(0), name), _to_int(value.__vbs_index_get__(1), name))
        except Exception:
            pass
    raise VBScriptRuntimeError(f"Invalid {name}")


def _to_box(value, name):
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return tuple(_to_int(x, name) for x in value)
    if isinstance(value, VBArray):
        try:
            return tuple(_to_int(value.__vbs_index_get__(i), name) for i in range(4))
        except Exception:
            pass
    raise VBScriptRuntimeError(f"Invalid {name}")


def _to_color(value):
    if value is VBEmpty or value is VBNull or value is VBNothing or value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return tuple(int(x) for x in value)
    if isinstance(value, VBArray):
        return tuple(int(value.__vbs_index_get__(i)) for i in range(value.ubound(1) + 1))
    return value


def _unwrap_image(obj):
    if isinstance(obj, ImageInstance):
        return obj._img
    return obj


class ImageInstance:
    def __init__(self, img):
        self._img = img

    @property
    def size(self):
        return self._img.size

    @property
    def width(self):
        return self._img.width

    @property
    def height(self):
        return self._img.height

    @property
    def mode(self):
        return self._img.mode

    @property
    def format(self):
        return self._img.format

    def save(self, path):
        p = vbs_cstr(path)
        if p == "":
            raise VBScriptRuntimeError("Image.save: path is required")
        self._img.save(p)
        return p

    def resize(self, size):
        sz = _to_tuple2(size, "size")
        return ImageInstance(self._img.resize(sz))

    def thumbnail(self, size):
        sz = _to_tuple2(size, "size")
        self._img.thumbnail(sz)
        return self

    def crop(self, box):
        bx = _to_box(box, "box")
        return ImageInstance(self._img.crop(bx))

    def rotate(self, angle):
        a = _to_float(angle, "angle")
        return ImageInstance(self._img.rotate(a))

    def transpose(self, method):
        return ImageInstance(self._img.transpose(method))

    def convert(self, mode):
        m = vbs_cstr(mode)
        if m == "":
            raise VBScriptRuntimeError("Image.convert: mode is required")
        return ImageInstance(self._img.convert(m))

    def split(self):
        bands = self._img.split()
        a = VBArray(len(bands) - 1, allocated=True, dynamic=True)
        for i, b in enumerate(bands):
            a.__vbs_index_set__(i, ImageInstance(b))
        return a

    def getpixel(self, xy):
        pt = _to_tuple2(xy, "xy")
        return self._img.getpixel(pt)

    def putpixel(self, xy, value):
        pt = _to_tuple2(xy, "xy")
        self._img.putpixel(pt, _to_color(value))
        return self

    def load(self):
        return PixelAccessInstance(self._img.load())

    def filter(self, filter_obj):
        return ImageInstance(self._img.filter(filter_obj))

    def paste(self, other_img, box, mask=None):
        other = _unwrap_image(other_img)
        bx = _to_tuple2(box, "box")
        if mask is None or mask is VBEmpty or mask is VBNull or mask is VBNothing:
            self._img.paste(other, bx)
        else:
            self._img.paste(other, bx, _unwrap_image(mask))
        return self


class PixelAccessInstance:
    def __init__(self, access):
        self._access = access

    def getpixel(self, xy):
        pt = _to_tuple2(xy, "xy")
        return self._access[pt[0], pt[1]]

    def putpixel(self, xy, value):
        pt = _to_tuple2(xy, "xy")
        self._access[pt[0], pt[1]] = _to_color(value)
        return self

    def __vbs_index_get__(self, xy):
        return self.getpixel(xy)

    def __vbs_index_set__(self, xy, value):
        self.putpixel(xy, value)


class ImageModuleShim:
    FLIP_LEFT_RIGHT = getattr(_PILImage, "FLIP_LEFT_RIGHT", 0)
    FLIP_TOP_BOTTOM = getattr(_PILImage, "FLIP_TOP_BOTTOM", 1)
    ROTATE_90 = getattr(_PILImage, "ROTATE_90", 2)
    ROTATE_180 = getattr(_PILImage, "ROTATE_180", 3)
    ROTATE_270 = getattr(_PILImage, "ROTATE_270", 4)

    def open(self, path):
        _require_pillow()
        p = vbs_cstr(path)
        if p == "":
            raise VBScriptRuntimeError("Image.open: path is required")
        return ImageInstance(_PILImage.open(p))

    def new(self, mode, size, color=None):
        _require_pillow()
        m = vbs_cstr(mode)
        if m == "":
            raise VBScriptRuntimeError("Image.new: mode is required")
        sz = _to_tuple2(size, "size")
        return ImageInstance(_PILImage.new(m, sz, _to_color(color)))

    def merge(self, mode, bands):
        _require_pillow()
        m = vbs_cstr(mode)
        if m == "":
            raise VBScriptRuntimeError("Image.merge: mode is required")
        band_list = _coerce_band_list(bands)
        return ImageInstance(_PILImage.merge(m, band_list))

    def blend(self, img1, img2, alpha):
        _require_pillow()
        a = _to_float(alpha, "alpha")
        return ImageInstance(_PILImage.blend(_unwrap_image(img1), _unwrap_image(img2), a))

    def composite(self, img1, img2, mask):
        _require_pillow()
        return ImageInstance(_PILImage.composite(_unwrap_image(img1), _unwrap_image(img2), _unwrap_image(mask)))


class ImageDrawShim:
    def Draw(self, img):
        _require_pillow()
        base = _unwrap_image(img)
        return DrawInstance(_PILImageDraw.Draw(base))


class DrawInstance:
    def __init__(self, draw):
        self._draw = draw

    def text(self, xy, text, fill=None):
        pt = _to_tuple2(xy, "xy")
        self._draw.text(pt, vbs_cstr(text), fill=_to_color(fill))
        return self

    def rectangle(self, box, outline=None, fill=None):
        bx = _to_box(box, "box")
        self._draw.rectangle(bx, outline=_to_color(outline), fill=_to_color(fill))
        return self

    def ellipse(self, box, outline=None, fill=None):
        bx = _to_box(box, "box")
        self._draw.ellipse(bx, outline=_to_color(outline), fill=_to_color(fill))
        return self

    def line(self, xy, fill=None, width=1):
        self._draw.line(_coerce_xy_list(xy), fill=_to_color(fill), width=_to_int(width, "width"))
        return self


class ImageFilterShim:
    BLUR = getattr(_PILImageFilter, "BLUR", None)
    CONTOUR = getattr(_PILImageFilter, "CONTOUR", None)
    DETAIL = getattr(_PILImageFilter, "DETAIL", None)
    EDGE_ENHANCE = getattr(_PILImageFilter, "EDGE_ENHANCE", None)
    EDGE_ENHANCE_MORE = getattr(_PILImageFilter, "EDGE_ENHANCE_MORE", None)
    EMBOSS = getattr(_PILImageFilter, "EMBOSS", None)
    FIND_EDGES = getattr(_PILImageFilter, "FIND_EDGES", None)
    SHARPEN = getattr(_PILImageFilter, "SHARPEN", None)
    SMOOTH = getattr(_PILImageFilter, "SMOOTH", None)
    SMOOTH_MORE = getattr(_PILImageFilter, "SMOOTH_MORE", None)

    def GaussianBlur(self, radius):
        _require_pillow()
        r = _to_float(radius, "radius")
        if _PILImageFilter is None:
            raise VBScriptRuntimeError("Pillow is not available")
        return _PILImageFilter.GaussianBlur(r)


class ImageEnhanceShim:
    def Brightness(self, img):
        _require_pillow()
        return EnhanceInstance(_PILImageEnhance.Brightness(_unwrap_image(img)))

    def Contrast(self, img):
        _require_pillow()
        return EnhanceInstance(_PILImageEnhance.Contrast(_unwrap_image(img)))


class EnhanceInstance:
    def __init__(self, enhancer):
        self._enhancer = enhancer

    def enhance(self, factor):
        f = _to_float(factor, "factor")
        return ImageInstance(self._enhancer.enhance(f))


def _coerce_band_list(bands):
    out = []
    if isinstance(bands, VBArray):
        try:
            for i in range(bands.ubound(1) + 1):
                out.append(_unwrap_image(bands.__vbs_index_get__(i)))
            return out
        except Exception:
            pass
    if isinstance(bands, (list, tuple)):
        return [_unwrap_image(b) for b in bands]
    raise VBScriptRuntimeError("Image.merge: bands must be an array")


def _coerce_xy_list(xy):
    if isinstance(xy, VBArray):
        try:
            vals = [xy.__vbs_index_get__(i) for i in range(xy.ubound(1) + 1)]
            return [(int(vals[i]), int(vals[i + 1])) for i in range(0, len(vals), 2)]
        except Exception:
            pass
    if isinstance(xy, (list, tuple)):
        if len(xy) >= 2 and isinstance(xy[0], (list, tuple)):
            return [(int(p[0]), int(p[1])) for p in xy]
        if len(xy) % 2 == 0:
            return [(int(xy[i]), int(xy[i + 1])) for i in range(0, len(xy), 2)]
    raise VBScriptRuntimeError("Invalid xy list")


class ImageNamespace:
    def __init__(self):
        self.Image = ImageModuleShim()
        self.ImageDraw = ImageDrawShim()
        self.ImageFilter = ImageFilterShim()
        self.ImageEnhance = ImageEnhanceShim()


ASP4_IMAGE = ImageNamespace()
