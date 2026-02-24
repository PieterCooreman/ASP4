"""HTTP request and Classic ASP Request object emulation (minimal)."""

from __future__ import annotations

import urllib.parse


class NameValueCollection:
    """A minimal Classic ASP-like name/value collection.

    - Item("k") returns a string (joins multiple values with ', ')
    - Count, Key(i) are provided for basic compatibility
    """

    def __init__(self, mapping=None):
        # mapping: dict[str, list[str]]
        self._m = mapping or {}
        # case-insensitive key map
        self._kmap = {}
        for k in self._m.keys():
            lk = str(k).lower()
            if lk not in self._kmap:
                self._kmap[lk] = k

    @property
    def Count(self):
        return len(self._m)

    def Key(self, index):
        i = int(index)
        if i < 1 or i > len(self._m):
            # Classic ASP raises an error (index out of range).
            raise IndexError("Index out of range")
        return list(self._m.keys())[i - 1]

    def Exists(self, key) -> bool:
        lk = str(key).lower()
        return lk in self._kmap

    def Item(self, key):
        k = str(key)
        # Case-insensitive lookup
        lk = k.lower()
        if lk in self._kmap:
            k = self._kmap[lk]
        vals = self._m.get(k)
        if not vals:
            return ""
        if len(vals) == 1:
            # Request collections should be stringly-typed.
            return "" if vals[0] is None else str(vals[0])
        # IIS Classic ASP joins multi-valued keys with comma+space.
        return ", ".join(["" if v is None else str(v) for v in vals])

    def __vbs_index_get__(self, key):
        return self.Item(key)

    def __iter__(self):
        # For Each over collection yields keys
        return iter(self._m.keys())


class Request:
    def __init__(self, method: str, path: str, query_string: str, headers: dict, body: bytes, remote_addr: str = ""):
        self._method = method.upper()
        self._path = path
        self._query_string = query_string or ""
        self._headers = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
        self._body = body or b""
        self._binpos = 0
        self._remote_addr = remote_addr or ""

        self._query = NameValueCollection(_parse_qs(self._query_string))
        self._form = NameValueCollection({})
        self._cookies = CookiesCollection(_parse_cookie_header(self._headers.get('cookie', '')))
        self._server_vars = NameValueCollection(_build_server_vars(self))

        self._parse_form_if_needed()

    def _parse_form_if_needed(self):
        if self._method != "POST":
            return
        ctype = self._headers.get('content-type', '')
        if ctype.startswith('application/x-www-form-urlencoded'):
            try:
                txt = self._body.decode('utf-8', errors='replace')
            except Exception:
                txt = ''
            self._form = NameValueCollection(_parse_qs(txt))
            return

        if ctype.startswith('multipart/form-data'):
            # Minimal multipart parser: populates Request.Form with non-file fields.
            boundary = None
            for part in ctype.split(';'):
                part = part.strip()
                if part.lower().startswith('boundary='):
                    boundary = part.split('=', 1)[1].strip().strip('"')
                    break
            if not boundary:
                return

            b = self._body
            sep = ("--" + boundary).encode('utf-8', errors='ignore')
            end = ("--" + boundary + "--").encode('utf-8', errors='ignore')
            items: dict[str, list[str]] = {}

            # split on boundary markers
            parts = b.split(sep)
            for p in parts:
                if not p:
                    continue
                if p.startswith(b'--'):
                    break
                if p.startswith(b"\r\n"):
                    p = p[2:]
                # headers/body separator
                hdr_end = p.find(b"\r\n\r\n")
                if hdr_end == -1:
                    continue
                hdr_blob = p[:hdr_end].decode('utf-8', errors='replace')
                body = p[hdr_end+4:]
                if body.endswith(b"\r\n"):
                    body = body[:-2]

                headers = {}
                for line in hdr_blob.split("\r\n"):
                    if ':' in line:
                        k, v = line.split(':', 1)
                        headers[k.strip().lower()] = v.strip()

                cd = headers.get('content-disposition', '')
                if 'form-data' not in cd.lower():
                    continue
                name = None
                filename = None
                for seg in cd.split(';'):
                    seg = seg.strip()
                    if seg.lower().startswith('name='):
                        name = seg.split('=', 1)[1].strip().strip('"')
                    if seg.lower().startswith('filename='):
                        filename = seg.split('=', 1)[1].strip().strip('"')
                if not name:
                    continue
                # Ignore file payloads for now; keep only normal fields.
                if filename:
                    continue

                try:
                    val = body.decode('utf-8', errors='replace')
                except Exception:
                    val = ''
                items.setdefault(name, []).append(val)

            self._form = NameValueCollection(items)

    @property
    def TotalBytes(self):
        return len(self._body)

    def BinaryRead(self, count):
        # Classic ASP BinaryRead reads from request body and advances the read cursor.
        # Some legacy upload scripts rely on BinaryRead updating the requested byte
        # count via ByRef. We support that when `count` is a ByRef wrapper.
        byref = None
        try:
            from .vm.interpreter import _ByRef  # local import to avoid cycle
            byref = count if isinstance(count, _ByRef) else None
        except Exception:
            byref = None
        n_raw = byref.get() if byref is not None else count
        try:
            n = int(str(n_raw).strip() or '0')
        except Exception:
            n = 0
        if n < 0:
            n = 0
        if self._binpos >= len(self._body):
            chunk = b""
        else:
            chunk = self._body[self._binpos:self._binpos + n]
        self._binpos += len(chunk)
        if byref is not None:
            try:
                byref.set(len(chunk))
            except Exception:
                pass
        return chunk

    @property
    def QueryString(self):
        return self._query

    @property
    def Form(self):
        return self._form

    @property
    def Cookies(self):
        return self._cookies

    @property
    def ServerVariables(self):
        return self._server_vars

    @property
    def HttpMethod(self):
        return self._method

    @property
    def Path(self):
        return self._path

    @property
    def RawBody(self):
        return self._body

    def Item(self, key):
        # Classic ASP: Request("x") searches across collections.
        k = str(key)
        # Order per IIS docs: QueryString, Form, Cookies, ClientCertificate, ServerVariables
        if self._query.Exists(k):
            return self._query.Item(k)
        if self._form.Exists(k):
            return self._form.Item(k)
        if self._cookies.Exists(k):
            return self._cookies.Item(k)
        cc = self.ClientCertificate
        if hasattr(cc, 'Exists') and cc.Exists(k):
            return cc.Item(k)
        if self._server_vars.Exists(k):
            return self._server_vars.Item(k)
        # ASP returns EMPTY; we currently represent this as empty string.
        return ""

    def __vbs_index_get__(self, key):
        v = self.Item(key)
        # Never return None/null from Request()
        return "" if v is None else v

    @property
    def ClientCertificate(self):
        # Not implemented; return empty collection for compatibility.
        return NameValueCollection({})


class CookieIn:
    def __init__(self, name: str, value: str, keys=None):
        self.Name = name
        self._value = value or ""
        # keys: list[(k,v)] in insertion order
        self._keys = keys or []
        self._kmap = {}
        for (k, v) in self._keys:
            lk = str(k).lower()
            if lk not in self._kmap:
                self._kmap[lk] = (k, v)

    @property
    def HasKeys(self):
        return len(self._keys) > 0

    def __iter__(self):
        return iter([k for (k, _v) in self._keys])

    def __vbs_index_get__(self, key):
        k = str(key)
        # case-insensitive
        lk = k.lower()
        if lk in self._kmap:
            return self._kmap[lk][1]
        return ""

    def __str__(self):
        return self._value


class CookiesCollection:
    """Request.Cookies collection.

    Iterates cookie names. Indexing returns a CookieIn object.
    """

    def __init__(self, mapping: dict):
        # mapping: name -> list[str]
        # Canonicalize cookie names by percent-decoding and merging duplicates.
        raw = mapping or {}
        merged = {}
        for k, vals in raw.items():
            nk = str(k)
            try:
                nk = urllib.parse.unquote(nk)
            except Exception:
                pass
            if nk not in merged:
                merged[nk] = []
            merged[nk].extend([str(v) for v in (vals or [])])

        self._m = merged
        self._kmap = {}
        for k in self._m.keys():
            lk = str(k).lower()
            if lk not in self._kmap:
                self._kmap[lk] = k

    def Exists(self, name) -> bool:
        return str(name).lower() in self._kmap

    def Item(self, name) -> str:
        c = self.__vbs_index_get__(name)
        return str(c)

    @property
    def Count(self):
        return len(self._m)

    def Key(self, index):
        i = int(index)
        if i < 1 or i > len(self._m):
            raise IndexError("Index out of range")
        return list(self._m.keys())[i - 1]

    def __iter__(self):
        return iter(self._m.keys())

    def __vbs_index_get__(self, name):
        n = str(name)
        lk = n.lower()
        if lk in self._kmap:
            n = self._kmap[lk]
        vals = self._m.get(n) or []
        v = vals[0] if vals else ""
        keys = _try_parse_cookie_keys(v)
        return CookieIn(n, v, keys=keys)


def _try_parse_cookie_keys(v: str):
    # Heuristic: treat as keys only if it looks like key=value[&key=value]*
    if not isinstance(v, str):
        return []
    if "=" not in v:
        return []
    segments = v.split("&")
    if not segments:
        return []
    for seg in segments:
        if seg == "":
            return []
        if "=" not in seg:
            return []
    out = []
    try:
        from urllib.parse import parse_qsl
        for k, val in parse_qsl(v, keep_blank_values=True, strict_parsing=False):
            out.append((str(k), str(val)))
    except Exception:
        return []
    return out


def _parse_qs(qs: str) -> dict:
    parsed = urllib.parse.parse_qs(qs, keep_blank_values=True, strict_parsing=False)
    out = {}
    for k, vals in parsed.items():
        out[str(k)] = [str(v) for v in vals]
    return out


def _parse_cookie_header(cookie_header: str) -> dict:
    out = {}
    if not cookie_header:
        return out
    parts = cookie_header.split(';')
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if '=' not in p:
            continue
        k, v = p.split('=', 1)
        k = k.strip()
        v = v.strip()
        # Decode percent-encoding in cookie name to avoid duplicates like asp%5Fpy vs asp_py.
        try:
            k = urllib.parse.unquote(k)
        except Exception:
            pass
        if k not in out:
            out[k] = []
        out[k].append(v)
    return out


def _build_server_vars(req: Request) -> dict:
    h = req._headers
    host = h.get('host', '') or ''
    server_name = host
    server_port = ''
    if host:
        if host.count(':') == 1 and host.rsplit(':', 1)[1].isdigit():
            server_name, server_port = host.rsplit(':', 1)
        else:
            server_name = host

    xf_proto = (h.get('x-forwarded-proto', '') or '').split(',')[0].strip().lower()
    xf_for = (h.get('x-forwarded-for', '') or '').split(',')[0].strip()
    is_https = xf_proto == 'https'
    https_val = 'on' if is_https else 'off'

    server_protocol = 'HTTP/1.1'

    if not server_port:
        server_port = '443' if is_https else '80'

    remote_addr = req._remote_addr
    remote_host = xf_for or remote_addr
    remote_port = ''

    http_headers = {}
    for k, v in h.items():
        k_upper = k.upper().replace('-', '_')
        http_headers[f'HTTP_{k_upper}'] = v

    all_http_parts = []
    for k, v in h.items():
        all_http_parts.append(f'{k}: {v}')
    all_http = '\r\n'.join(all_http_parts)
    all_raw = '\r\n'.join(f'{k}: {v}' for k, v in h.items())

    vars = {
        'ALL_HTTP': [all_http],
        'ALL_RAW': [all_raw],
        'REQUEST_METHOD': [req._method],
        'QUERY_STRING': [req._query_string],
        'PATH_INFO': [req._path],
        'SCRIPT_NAME': [req._path],
        'REMOTE_ADDR': [remote_addr],
        'REMOTE_HOST': [remote_host],
        'REMOTE_PORT': [remote_port],
        'SERVER_NAME': [server_name],
        'SERVER_PORT': [server_port],
        'SERVER_PROTOCOL': [server_protocol],
        'HTTPS': [https_val],
        'SERVER_PORT_SECURE': ['1' if is_https else '0'],
        'GATEWAY_INTERFACE': ['CGI/1.1'],
        'SERVER_SOFTWARE': ['asp.py'],
        'INSTANCE_ID': ['1'],
        'INSTANCE_META_PATH': ['/LM/W3SVC/1/ROOT'],
        'LOCAL_ADDR': [server_name],
        'APPL_MD_PATH': ['/LM/W3SVC/1/ROOT'],
        'APPL_PHYSICAL_PATH': [''],
        'PATH_TRANSLATED': [''],
        'URL': [req._path],
        'CONTENT_TYPE': [h.get('content-type', '')],
        'CONTENT_LENGTH': [h.get('content-length', '')],
    }

    for k, v in http_headers.items():
        if k not in vars:
            vars[k] = [v]

    return vars
