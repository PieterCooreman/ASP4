"""HTTP response building for ASPPY

This module holds the Response implementation that ASP/VBScript interacts with.
It is shared between different execution engines (exec-based and VM-based).
"""

from __future__ import annotations

import datetime as dt
import email.utils
import urllib.parse

from .vb_runtime import vbs_cstr, vbs_set_lcid
from .vm.values import VBNull


def _nul_terminate(s: str) -> str:
    """Truncate a string at the first NUL, the way IIS does on output.

    ASP hands VBScript strings to Windows as NUL-terminated buffers, so a
    embedded Chr(0) ends the string: on IIS,
    ``Response.Write "a" & vbNullChar & "b"`` emits just ``a`` - the NUL *and
    everything after it in that call* are dropped, not merely the NUL itself.
    Verified against IIS for Response.Write, Response.AddHeader and
    Response.Cookies.

    Beyond parity this is a hard requirement for header values: emitting a raw
    NUL into a header produces a malformed response that clients reject with a
    protocol error rather than rendering the page.

    Deliberately NOT applied to BinaryWrite, where NUL bytes are legitimate
    payload data.
    """
    if not s:
        return s
    i = s.find('\x00')
    return s if i < 0 else s[:i]


class ResponseEndException(Exception):
    pass


class RenderResult:
    def __init__(self):
        self.status_code = 200
        self.status_message = "OK"
        self.headers = []  # list[(name, value)]
        self.body = b""
        self.charset = "utf-8"
        self.log_tail = []        



class Response:
    def __init__(self, res: RenderResult, body_out: bytearray):
        self._res = res
        self._body_out = body_out

        self._buffer_enabled = True
        self._buf_chunks: list[bytes] = []
        self._buf_str_parts: list[str] = []
        self._buf_str_limit = 8192
        self._sent_first_output = False

        self._content_type = "text/html"
        self._charset = "utf-8"
        self._cache_control = None
        self._expires = None
        self._status = None
        self._extra_headers = []
        self._cookies = {}  # name -> ResponseCookie
        self._current_path = ""
        self._lcid = 0
        # IIS: Response.CodePage defaults from Session.CodePage / @CODEPAGE.
        # ASPPY always emits UTF-8 (codepage 65001) unless Charset is changed,
        # so 65001 is the honest default (matches Session.CodePage).
        self._codepage = 65001
        self._pics = None
        self._is_file_response = False

    @property
    def LCID(self):
        return self._lcid

    @LCID.setter
    def LCID(self, value):
        self.SetProperty("LCID", value)

    @property
    def CodePage(self):
        return self._codepage

    @CodePage.setter
    def CodePage(self, value):
        self.SetProperty("CODEPAGE", value)

    @property
    def PICS(self):
        # IIS treats PICS as write-only; we are permissive and return the
        # stored label (or empty string) instead of raising.
        return self._pics or ""

    @PICS.setter
    def PICS(self, value):
        self.SetProperty("PICS", value)

    @property
    def Cookies(self):
        return ResponseCookiesCollection(self)

    @property
    def Buffer(self):
        return self._buffer_enabled

    @Buffer.setter
    def Buffer(self, value):
        new_val = bool(value)
        if self._buffer_enabled and not new_val:
            self.Flush()
        self._buffer_enabled = new_val

    def _write_raw_bytes(self, b: bytes):
        self._body_out.extend(b)

    def Write(self, s):
        txt = _nul_terminate(vbs_cstr(s))
        if not self._sent_first_output:
            txt = txt.lstrip("\r\n")
            if not txt:
                return
            self._sent_first_output = True
        if self._buffer_enabled:
            parts = self._buf_str_parts
            parts.append(txt)
            count = len(parts)
            if count >= self._buf_str_limit:
                self._buf_chunks.append("".join(parts).encode(self._charset or "utf-8", errors="replace"))
                parts.clear()
        else:
            self._write_raw_bytes(txt.encode(self._charset or "utf-8", errors="replace"))

    def BinaryWrite(self, data):
        if isinstance(data, (bytes, bytearray)):
            b = bytes(data)
        else:
            t = vbs_cstr(data)
            try:
                b = t.encode("latin-1")
            except Exception:
                b = t.encode(self._charset or "utf-8", errors="replace")
        if self._buffer_enabled:
            if self._buf_str_parts:
                txt = "".join(self._buf_str_parts)
                self._buf_chunks.append(txt.encode(self._charset or "utf-8", errors="replace"))
                self._buf_str_parts.clear()
            self._buf_chunks.append(b)
        else:
            self._write_raw_bytes(b)

    def Clear(self):
        self._buf_chunks.clear()
        self._buf_str_parts.clear()

    def Flush(self):
        if self._buffer_enabled:
            if self._buf_str_parts:
                txt = "".join(self._buf_str_parts)
                self._buf_chunks.append(txt.encode(self._charset or "utf-8", errors="replace"))
                self._buf_str_parts.clear()
            if self._buf_chunks:
                self._write_raw_bytes(b"".join(self._buf_chunks))
                self._buf_chunks.clear()
                
    def File(self, path: str, inline=False):
        import os
        import mimetypes
        
        path = str(path)
        if not os.path.isfile(path):
            self._res.status_code = 404
            self._res.status_message = "Not Found"
            return
        
        mime, _ = mimetypes.guess_type(path)
        if not mime:
            mime = 'application/octet-stream'
        
        filename = os.path.basename(path)
        self._is_file_response = True
        self.ContentType = mime
        disposition = 'inline' if inline else 'attachment'
        self.AddHeader('Content-Disposition', f'{disposition}; filename="{filename}"')
        self.AddHeader('Content-Length', str(os.path.getsize(path)))
        
        with open(path, 'rb') as f:
            data = f.read()
        
        if self._buffer_enabled:
            if self._buf_str_parts:
                txt = "".join(self._buf_str_parts)
                self._buf_chunks.append(txt.encode(self._charset or "utf-8", errors="replace"))
                self._buf_str_parts.clear()
            self._buf_chunks.append(data)
        else:
            self._write_raw_bytes(data)

        raise ResponseEndException()

    def BinaryFile(self, path: str, inline=False, delete_after=False):
        import os
        import mimetypes

        path = str(path)
        if not os.path.isfile(path):
            self._res.status_code = 404
            self._res.status_message = "Not Found"
            return

        mime, _ = mimetypes.guess_type(path)
        if not mime:
            mime = "application/octet-stream"

        filename = os.path.basename(path)
        self._is_file_response = True
        self.ContentType = mime
        disposition = "inline" if inline else "attachment"
        self.AddHeader("Content-Disposition", f'{disposition}; filename="{filename}"')

        data = b""
        try:
            with open(path, "rb") as f:
                data = f.read()
        finally:
            if bool(delete_after):
                try:
                    os.remove(path)
                except Exception:
                    pass

        self.AddHeader("Content-Length", str(len(data)))

        if self._buffer_enabled:
            if self._buf_str_parts:
                txt = "".join(self._buf_str_parts)
                self._buf_chunks.append(txt.encode(self._charset or "utf-8", errors="replace"))
                self._buf_str_parts.clear()
            self._buf_chunks.append(data)
        else:
            self._write_raw_bytes(data)

        raise ResponseEndException()

    def FileBytes(self, data, content_type="application/octet-stream", filename="download.bin", inline=False):
        import mimetypes
        import os

        if isinstance(data, (bytes, bytearray)):
            b = bytes(data)
        else:
            t = vbs_cstr(data)
            try:
                b = t.encode("latin-1")
            except Exception:
                b = t.encode(self._charset or "utf-8", errors="replace")

        ct = vbs_cstr(content_type).strip()
        if not ct:
            ct = "application/octet-stream"

        fn = vbs_cstr(filename).strip()
        if not fn:
            fn = "download.bin"
        fn = os.path.basename(fn)
        if not fn:
            ext = mimetypes.guess_extension(ct) or ".bin"
            fn = "download" + ext

        self._is_file_response = True
        self.ContentType = ct
        disposition = "inline" if inline else "attachment"
        self.AddHeader("Content-Disposition", f'{disposition}; filename="{fn}"')
        self.AddHeader("Content-Length", str(len(b)))

        if self._buffer_enabled:
            if self._buf_str_parts:
                txt = "".join(self._buf_str_parts)
                self._buf_chunks.append(txt.encode(self._charset or "utf-8", errors="replace"))
                self._buf_str_parts.clear()
            self._buf_chunks.append(b)
        else:
            self._write_raw_bytes(b)

        raise ResponseEndException()
        

    def End(self):
        self.Flush()
        raise ResponseEndException()

    def AddHeader(self, name, value):
        self._extra_headers.append((_nul_terminate(str(name)),
                                    _nul_terminate(vbs_cstr(value))))

    def AppendToLog(self, s):
        msg = vbs_cstr(s)
        self._res.log_tail.append(msg)

    def Redirect(self, url):
        u = vbs_cstr(url)
        #print(f"[Redirect] raw url={u!r} current_path={getattr(self, '_current_path', 'NOT SET')!r}", flush=True)
        try:
            if not (u.startswith('/') or urllib.parse.urlsplit(u).scheme):
                base = getattr(self, '_current_path', '') or ''
                base = base.split('?', 1)[0]
                #print(f"[Redirect] base={base!r}", flush=True)
                if base:
                    if u.startswith('?') or u.startswith('#'):
                        u = base + u
                    else:
                        if not base.endswith('/'):
                            base = base.rsplit('/', 1)[0] + '/'
                        u = urllib.parse.urljoin(base, u)
        except Exception as e:
            print(f"[Redirect] exception: {e!r}", flush=True)
        #print(f"[Redirect] final url={u!r} status={self.Status!r}", flush=True)
        self.Status = "302 Found"
        self.AddHeader("Location", u)
        self.End()

    def Call(self, method_name: str, *args):
        m = str(method_name).upper()
        if m == "ADDHEADER":
            if len(args) != 2:
                raise Exception("Response.AddHeader expects 2 arguments")
            return self.AddHeader(args[0], args[1])
        if m == "APPENDTOLOG":
            if len(args) != 1:
                raise Exception("Response.AppendToLog expects 1 argument")
            return self.AppendToLog(args[0])
        if m == "BINARYWRITE":
            if len(args) != 1:
                raise Exception("Response.BinaryWrite expects 1 argument")
            return self.BinaryWrite(args[0])
        if m == "BINARYFILE":
            if len(args) < 1 or len(args) > 3:
                raise Exception("Response.BinaryFile expects 1 to 3 arguments")
            return self.BinaryFile(
                args[0],
                args[1] if len(args) >= 2 else False,
                args[2] if len(args) == 3 else False,
            )
        if m == "REDIRECT":
            if len(args) != 1:
                raise Exception("Response.Redirect expects 1 argument")
            return self.Redirect(args[0])
        if m == "WRITE":
            if len(args) != 1:
                raise Exception("Response.Write expects 1 argument")
            return self.Write(args[0])
        if m == "CLEAR":
            return self.Clear()
        if m == "FLUSH":
            return self.Flush()
        if m == "FILE":
            if len(args) not in (1, 2):
                raise Exception("Response.File expects 1 or 2 arguments")
            return self.File(args[0], args[1] if len(args) == 2 else False)
        if m == "FILEBYTES":
            if len(args) < 1 or len(args) > 4:
                raise Exception("Response.FileBytes expects 1 to 4 arguments")
            return self.FileBytes(
                args[0],
                args[1] if len(args) >= 2 else "application/octet-stream",
                args[2] if len(args) >= 3 else "download.bin",
                args[3] if len(args) == 4 else False,
            )
        if m == "END":
            return self.End()
        if m == "ISCLIENTCONNECTED":
            return bool(self.IsClientConnected())
        raise Exception("Unsupported Response method")

    def SetProperty(self, name: str, value):
        n = str(name).upper()
        if n == "CACHECONTROL":
            self._cache_control = vbs_cstr(value)
            return
        if n == "CHARSET":
            self._charset = vbs_cstr(value) or "utf-8"
            return
        if n == "CODEPAGE":
            # Store the value so scripts can read it back (IIS semantics).
            # Output byte-encoding remains driven by Charset for backwards
            # compatibility (ASPPY has always emitted per _charset).
            try:
                self._codepage = int(value)
            except Exception:
                pass
            return
        if n == "CONTENTTYPE":
            self._content_type = vbs_cstr(value) or "text/html"
            return
        if n == "EXPIRES":
            self._expires = ("REL", int(value))
            return
        if n == "EXPIRESABSOLUTE":
            self._expires = ("ABS", value)
            return
        if n == "LCID":
            try:
                self._lcid = int(value)
            except Exception:
                self._lcid = 0
            vbs_set_lcid(self._lcid)
            return
        if n == "PICS":
            # IIS: Response.PICS adds a PICS-Label header (replace any prior).
            self._pics = vbs_cstr(value)
            self._extra_headers = [
                (hn, hv) for (hn, hv) in self._extra_headers
                if str(hn).lower() != "pics-label"
            ]
            self._extra_headers.append(("PICS-Label", self._pics))
            return
        if n == "STATUS":
            self.Status = value
            return
        raise Exception("Unsupported Response property")

    def _cookies_get_or_create(self, name):
        n = vbs_cstr(name)
        c = self._cookies.get(n)
        if c is None:
            c = ResponseCookie(n)
            self._cookies[n] = c
        return c

    def SetCookie(self, name, value):
        c = self._cookies_get_or_create(name)
        c.Value = value

    def SetCookieKey(self, name, key, value):
        c = self._cookies_get_or_create(name)
        c.SetKey(key, value)

    @property
    def Status(self):
        # IIS reports the CURRENT status line, defaulting to "200 OK" rather
        # than an empty string when the page has not set one.
        if self._status is None:
            code = getattr(self._res, 'status_code', 200) or 200
            msg = getattr(self._res, 'status_message', '') or ''
            if not msg:
                import http
                try:
                    msg = http.HTTPStatus(int(code)).phrase
                except Exception:
                    msg = ''
            return f"{code} {msg}".strip()
        return self._status

    @Status.setter
    def Status(self, value):
        s = vbs_cstr(value).strip()
        self._status = s
        parts = s.split(None, 1)
        try:
            self._res.status_code = int(parts[0])
            self._res.status_message = parts[1] if len(parts) > 1 else ""
        except Exception:
            pass

    @property
    def Charset(self):
        return self._charset

    @Charset.setter
    def Charset(self, value):
        self._charset = vbs_cstr(value) or "utf-8"

    @property
    def ContentType(self):
        return self._content_type

    @ContentType.setter
    def ContentType(self, value):
        self._content_type = vbs_cstr(value) or "text/html"

    @property
    def CacheControl(self):
        return self._cache_control

    @CacheControl.setter
    def CacheControl(self, value):
        self._cache_control = vbs_cstr(value)

    # IIS keeps ONE expiry internally and exposes it through both properties:
    # setting either one makes the other reflect it. Verified against IIS:
    #   unset                              -> Expires = Null, ExpiresAbsolute = #00:00:00#
    #   Expires = 45                       -> Expires = 45 (Long)
    #   ExpiresAbsolute = #2030-01-01 12:00# -> Expires = 1783593 (minutes from now)
    #   Expires = -1                       -> Expires = 0 (never negative)

    def _expires_absolute_dt(self):
        """The pending expiry as a naive LOCAL datetime, or None if never set."""
        if self._expires is None:
            return None
        kind, val = self._expires
        if kind == "REL":
            return dt.datetime.now() + dt.timedelta(minutes=int(val))
        try:
            from .vb_datetime import CDate
            return CDate(val)
        except Exception:
            return None

    def _expires_absolute_utc(self):
        """The pending expiry as an aware UTC datetime, or None if never set.

        A VBScript Date is a LOCAL time, so it must be converted rather than
        simply relabelled as UTC. The offset that applies at the TARGET date is
        used, which is what IIS does: setting #2030-01-01 12:00:00# in a
        UTC+1-in-winter zone emits "01 Jan 2030 11:00:00 GMT" even when the
        request happens during summer time (UTC+2).
        """
        when = self._expires_absolute_dt()
        if when is None:
            return None
        if when.tzinfo is None:
            when = when.astimezone()  # attach the offset in effect at `when`
        return when.astimezone(dt.timezone.utc)

    @property
    def Expires(self):
        # Never set: IIS reports Null (prints as an empty string).
        if self._expires is None:
            return VBNull
        from .vb_runtime import VBLong
        kind, val = self._expires
        if kind == "REL":
            return VBLong(max(0, int(val)))
        when = self._expires_absolute_utc()
        if when is None:
            return VBLong(0)
        now_utc = dt.datetime.now(dt.timezone.utc)
        minutes = int((when - now_utc).total_seconds() // 60)
        return VBLong(max(0, minutes))

    @Expires.setter
    def Expires(self, value):
        self._expires = ("REL", int(value))

    @property
    def ExpiresAbsolute(self):
        when = self._expires_absolute_dt()
        if when is None:
            # Never set: IIS reports the OA zero date, i.e. #00:00:00#.
            return dt.datetime(1899, 12, 30)
        return when

    @ExpiresAbsolute.setter
    def ExpiresAbsolute(self, value):
        self._expires = ("ABS", value)

    def IsClientConnected(self):
        return True

    def finalize_headers(self):
        # Content-Type with charset — use already-stored values directly to
        # avoid repeated .lower() allocations on the hot path.
        ct = self._content_type or "text/html"
        cs = self._charset or "utf-8"
        ct_lower = ct.lower()
        if (not self._is_file_response) and ("charset=" not in ct_lower):
            ct = f"{ct}; charset={cs}"
        self._res.charset = "" if self._is_file_response else cs
        self._res.headers.append(("Content-Type", ct))

        # Prevent browsers from caching HTML by default.
        # (This is intentionally aggressive for Classic ASP dev/test parity.)
        if ct_lower.startswith("text/html"):
            if self._cache_control is None and self._expires is None:
                self._res.headers.append(("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0"))
                self._res.headers.append(("Pragma", "no-cache"))
                self._res.headers.append(("Expires", "0"))

        if self._cache_control is not None:
            self._res.headers.append(("Cache-Control", self._cache_control))

        if self._expires is not None:
            # A VBScript Date is LOCAL time, so convert it to UTC instead of
            # relabelling it (which used to emit 12:00 GMT for a local 12:00).
            when = self._expires_absolute_utc()
            if when is None:
                when = dt.datetime.now(dt.timezone.utc)
            self._res.headers.append(("Expires", email.utils.format_datetime(when, usegmt=True)))

        for (hn, hv) in self._extra_headers:
            self._res.headers.append((hn, hv))
        for c in self._cookies.values():
            self._res.headers.append(("Set-Cookie", c.to_set_cookie_header()))

        # Final guard on every header, whatever produced it. A NUL is never a
        # legal header character: emitting one yields a malformed response that
        # clients reject outright with a protocol error instead of rendering the
        # page. IIS truncates at the NUL (verified for AddHeader and Cookies),
        # so do the same here rather than escaping or dropping the header.
        self._res.headers[:] = [
            (_nul_terminate(str(hn)), _nul_terminate(str(hv)))
            for (hn, hv) in self._res.headers
        ]


class ResponseCookiesCollection:
    """Response.Cookies collection."""

    def __init__(self, resp: Response):
        self._resp = resp

    def __vbs_index_get__(self, name):
        return self._resp._cookies_get_or_create(name)


class ResponseCookie:
    """A cookie being set in the response.

    Supports:
    - Response.Cookies(name) = value
    - Response.Cookies(name)(key) = value
    - Response.Cookies(name).Expires = datetime
    """

    def __init__(self, name: str):
        self.Name = name
        self.Value = ""
        self._keys = []  # list[(k,v)] preserves insertion
        self._kmap = {}  # lower -> index into _keys
        self.Expires = None
        self.Domain = None
        self.Path = "/"
        self.Secure = False
        self.HttpOnly = False

    def vbs_get_prop(self, name: str):
        n = str(name).upper()
        for attr in ("EXPIRES", "DOMAIN", "PATH", "SECURE", "HTTPONLY", "HASKEYS"):
            if attr == n:
                return getattr(self, attr.title() if attr not in ("HTTPONLY", "HASKEYS") else ("HttpOnly" if attr == "HTTPONLY" else "HasKeys"))
        raise AttributeError(name)

    def vbs_set_prop(self, name: str, value):
        n = str(name).upper()
        if n == "EXPIRES":
            self.Expires = value
            return
        if n == "DOMAIN":
            self.Domain = vbs_cstr(value)
            return
        if n == "PATH":
            self.Path = vbs_cstr(value)
            return
        if n == "SECURE":
            self.Secure = bool(value)
            return
        if n == "HTTPONLY":
            self.HttpOnly = bool(value)
            return
        raise AttributeError(name)

    @property
    def HasKeys(self):
        return len(self._keys) > 0

    def SetKey(self, key, value):
        k = vbs_cstr(key)
        lk = k.lower()
        v = vbs_cstr(value)
        if lk in self._kmap:
            idx = self._kmap[lk]
            orig_k, _orig_v = self._keys[idx]
            self._keys[idx] = (orig_k, v)
            return
        self._kmap[lk] = len(self._keys)
        self._keys.append((k, v))

    def __vbs_index_set__(self, key, value):
        self.SetKey(key, value)

    def __vbs_index_get__(self, key):
        k = vbs_cstr(key)
        lk = k.lower()
        if lk in self._kmap:
            return self._keys[self._kmap[lk]][1]
        return ""

    def __iter__(self):
        return iter([k for (k, _v) in self._keys])

    def __str__(self):
        return vbs_cstr(self.Value)

    def to_set_cookie_header(self) -> str:
        name = self.Name
        if self.HasKeys:
            # Encode keys as querystring
            # IIS/VBScript enumerates cookie keys in reverse assignment order.
            val = urllib.parse.urlencode(list(reversed(self._keys)), doseq=False, safe="")
        else:
            val = vbs_cstr(self.Value)
        parts = [f"{name}={val}"]

        if self.Expires is not None:
            when = _coerce_datetime(self.Expires)
            when = when.replace(tzinfo=dt.timezone.utc)
            parts.append("Expires=" + email.utils.format_datetime(when, usegmt=True))
        if self.Domain:
            parts.append("Domain=" + vbs_cstr(self.Domain))
        if self.Path:
            parts.append("Path=" + vbs_cstr(self.Path))
        if self.Secure:
            parts.append("Secure")
        if self.HttpOnly:
            parts.append("HttpOnly")

        return "; ".join(parts)


def _coerce_datetime(v):
    if isinstance(v, dt.datetime):
        return v
    if isinstance(v, dt.date) and not isinstance(v, dt.datetime):
        return dt.datetime(v.year, v.month, v.day)
    # Accept strict ISO strings via vb_datetime.CDate if available
    try:
        from .vb_datetime import CDate
        return CDate(v)
    except Exception:
        return dt.datetime.utcnow()
