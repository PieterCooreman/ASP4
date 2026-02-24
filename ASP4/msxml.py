"""Minimal MSXML shims (aspLite-focused, stdlib-only).

Implements:
- MSXML2.ServerXMLHTTP
- MSXML2.DOMDocument / Msxml2.DOMDocument.6.0

Scope:
- No XPath (selectNodes/selectSingleNode) yet.
- No external entity resolution; resolveExternals is forced off.
"""

from __future__ import annotations

import gzip
import io
import os
import re
import socket
import ssl
import zlib
from dataclasses import dataclass
from typing import Any, cast
from urllib.parse import urljoin, urlparse

import http.client
import ipaddress
import xml.etree.ElementTree as ET


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    s = str(v).strip().lower()
    return s in ("1", "true", "yes", "on")


def _env_csv(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    if not raw.strip():
        return []
    out = []
    for part in raw.split(','):
        p = part.strip()
        if p:
            out.append(p)
    return out


def _is_host_allowed_by_allowlist(host: str, allow_hosts: list[str]) -> bool:
    if not allow_hosts:
        return False
    h = host.strip().lower().rstrip('.')
    for ent in allow_hosts:
        e = ent.strip().lower().rstrip('.')
        if not e:
            continue
        # Exact match only (simple and predictable)
        if h == e:
            return True
    return False


def _is_ip_blocked(ip: ipaddress._BaseAddress, allow_localhost: bool, allow_private: bool) -> bool:
    ip2 = cast(ipaddress.IPv4Address | ipaddress.IPv6Address, ip)
    # Loopback
    if ip2.is_loopback:
        return not allow_localhost
    # Private (RFC1918 / ULA)
    if ip2.is_private:
        return not allow_private
    # Link-local, multicast, unspecified, reserved
    if ip2.is_link_local or ip2.is_multicast or ip2.is_unspecified or ip2.is_reserved:
        return True
    return False


def _ssrf_guard(url: str) -> None:
    u = urlparse(url)
    scheme = (u.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise Exception("MSXML: only http/https URLs are allowed")

    host = (u.hostname or "").strip()
    if not host:
        raise Exception("MSXML: URL missing host")

    host_l = host.lower().rstrip('.')
    if host_l == "localhost":
        if not _env_bool("ASP_PY_ALLOW_LOCALHOST", False):
            raise Exception("MSXML: localhost is blocked (set ASP_PY_ALLOW_LOCALHOST=1 to allow)")
        return

    allow_hosts = _env_csv("ASP_PY_HTTP_ALLOW_HOSTS")
    if _is_host_allowed_by_allowlist(host, allow_hosts):
        return

    allow_localhost = _env_bool("ASP_PY_ALLOW_LOCALHOST", False)
    allow_private = _env_bool("ASP_PY_ALLOW_PRIVATE_NETS", False)

    # If literal IP, validate directly.
    try:
        ip = ipaddress.ip_address(host_l)
        if _is_ip_blocked(ip, allow_localhost=allow_localhost, allow_private=allow_private):
            raise Exception("MSXML: target IP is blocked")
        return
    except ValueError:
        pass

    # Resolve and validate all addresses.
    port = u.port
    if port is None:
        port = 443 if scheme == "https" else 80
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except Exception as e:
        raise Exception(f"MSXML: DNS resolution failed for {host}: {e}")

    # Block if any resolved IP is disallowed.
    for info in infos:
        sockaddr = info[4]
        ip_s = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_s)
        except ValueError:
            continue
        if _is_ip_blocked(ip, allow_localhost=allow_localhost, allow_private=allow_private):
            raise Exception(
                "MSXML: target resolves to a blocked IP "
                f"({ip_s}). Set ASP_PY_ALLOW_PRIVATE_NETS=1 / ASP_PY_ALLOW_LOCALHOST=1 or ASP_PY_HTTP_ALLOW_HOSTS."
            )


def _decode_body(content_encoding: str, body: bytes) -> bytes:
    ce = (content_encoding or "").strip().lower()
    if not ce:
        return body
    if ce == "gzip":
        return gzip.decompress(body)
    if ce == "deflate":
        # Try zlib wrapper, then raw DEFLATE
        try:
            return zlib.decompress(body)
        except Exception:
            return zlib.decompress(body, -zlib.MAX_WBITS)
    # Unknown encoding: return raw
    return body


_CHARSET_RE = re.compile(r"charset\s*=\s*([^;\s]+)", re.I)


def _guess_charset(content_type: str) -> str:
    ct = content_type or ""
    m = _CHARSET_RE.search(ct)
    if not m:
        return "utf-8"
    cs = m.group(1).strip().strip('"').strip("'")
    return cs or "utf-8"


def _decode_text(body: bytes, content_type: str) -> str:
    # BOM
    if body.startswith(b"\xef\xbb\xbf"):
        try:
            return body[3:].decode("utf-8", errors="replace")
        except Exception:
            pass

    cs = _guess_charset(content_type)
    try:
        return body.decode(cs, errors="replace")
    except Exception:
        try:
            return body.decode("utf-8", errors="replace")
        except Exception:
            return body.decode("cp1252", errors="replace")


def _max_bytes() -> int:
    v = os.environ.get("ASP_PY_HTTP_MAX_BYTES", "")
    if v.strip():
        try:
            n = int(v)
            if n > 0:
                return n
        except Exception:
            pass
    return 10 * 1024 * 1024


@dataclass
class _HTTPResponse:
    status: int
    reason: str
    headers: dict[str, str]
    body: bytes
    url: str


def _http_request(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout_s: float = 15.0,
    max_redirects: int = 10,
) -> _HTTPResponse:
    hdrs = {str(k): str(v) for k, v in (headers or {}).items()}
    m = str(method or "GET").upper()
    cur_url = str(url)

    maxb = _max_bytes()

    for _i in range(max_redirects + 1):
        _ssrf_guard(cur_url)
        u = urlparse(cur_url)
        scheme = (u.scheme or "").lower()
        host = u.hostname
        if not host:
            raise Exception("MSXML: URL missing host")
        port = u.port
        if port is None:
            port = 443 if scheme == "https" else 80
        path = u.path or "/"
        if u.query:
            path = path + "?" + u.query

        # Defaults
        req_headers = dict(hdrs)
        if not any(k.lower() == "accept-encoding" for k in req_headers.keys()):
            req_headers["Accept-Encoding"] = "gzip, deflate"
        if not any(k.lower() == "user-agent" for k in req_headers.keys()):
            req_headers["User-Agent"] = "asp.py-msxml/0"

        if scheme == "https":
            ctx = ssl.create_default_context()
            conn: http.client.HTTPConnection = http.client.HTTPSConnection(host, port, timeout=timeout_s, context=ctx)
        else:
            conn = http.client.HTTPConnection(host, port, timeout=timeout_s)

        try:
            conn.request(m, path, body=body, headers=req_headers)
            resp = conn.getresponse()
            raw_headers = {k.lower(): v for (k, v) in resp.getheaders()}
            status = int(resp.status)
            reason = str(resp.reason or "")

            # Redirect
            if status in (301, 302, 303, 307, 308) and "location" in raw_headers:
                loc = raw_headers.get("location") or ""
                next_url = urljoin(cur_url, loc)
                # 303 switches to GET
                if status == 303:
                    m = "GET"
                    body = None
                cur_url = next_url
                continue

            # Read body with cap
            chunks: list[bytes] = []
            total = 0
            while True:
                part = resp.read(65536)
                if not part:
                    break
                total += len(part)
                if total > maxb:
                    raise Exception("MSXML: response exceeds ASP_PY_HTTP_MAX_BYTES")
                chunks.append(part)
            raw_body = b"".join(chunks)

            ce = raw_headers.get("content-encoding", "")
            out_body = _decode_body(ce, raw_body)
            return _HTTPResponse(status=status, reason=reason, headers=raw_headers, body=out_body, url=cur_url)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    raise Exception("MSXML: too many redirects")


class ServerXMLHTTP:
    def __init__(self):
        self._method = "GET"
        self._url = ""
        self._async = False
        self._req_headers: dict[str, str] = {}

        self.readyState = 0
        self.status = 0
        self.statusText = ""
        self._resp_headers: dict[str, str] = {}
        self.responseBody = b""
        self.responseText = ""
        self._responseXML = None

        # Timeouts (msxml provides setTimeouts in ms)
        self._timeout_s = 15.0
        self._aborted = False

    def setTimeouts(self, resolve_ms, connect_ms, send_ms, receive_ms):
        # Best-effort: use receive timeout as total.
        try:
            r = int(receive_ms)
            if r > 0:
                self._timeout_s = max(0.001, r / 1000.0)
        except Exception:
            pass

    def open(self, method, url, async_=False, user=None, password=None):
        self._aborted = False
        self._method = str(method or "GET").upper()
        self._url = str(url)
        # Classic ASP server-side code is effectively synchronous. Do not start
        # background/async network activity from the request thread.
        self._async = False
        self.readyState = 1

    def abort(self):
        self._aborted = True

    def setRequestHeader(self, name, value):
        self._req_headers[str(name)] = str(value)

    def getResponseHeader(self, name):
        k = str(name).lower()
        return self._resp_headers.get(k, "")

    def getAllResponseHeaders(self):
        # IIS/MSXML returns CRLF-separated headers.
        out = []
        for k, v in self._resp_headers.items():
            out.append(f"{k}: {v}")
        return "\r\n".join(out) + ("\r\n" if out else "")

    def send(self, body: Any = None):
        if self._aborted:
            raise Exception("ServerXMLHTTP: aborted")
        self.readyState = 2

        b: bytes | None
        if body is None or body == "":
            b = None
        elif isinstance(body, (bytes, bytearray)):
            b = bytes(body)
        else:
            b = str(body).encode("utf-8", errors="replace")

        self.readyState = 3
        r = _http_request(self._method, self._url, headers=self._req_headers, body=b, timeout_s=self._timeout_s)
        if self._aborted:
            raise Exception("ServerXMLHTTP: aborted")

        self.status = int(r.status)
        self.statusText = str(r.reason)
        self._resp_headers = dict(r.headers)
        self.responseBody = bytes(r.body)

        ct = self._resp_headers.get("content-type", "")
        self.responseText = _decode_text(self.responseBody, ct)
        self._responseXML = None
        self.readyState = 4

    @property
    def responseXML(self):
        """Parse response body as XML and return a DOMDocument.

        Commonly used on both XMLHTTP and ServerXMLHTTP.
        """
        if self._responseXML is not None:
            return self._responseXML
        try:
            doc = DOMDocument()
            ok = doc.LoadXML(self.responseText)
            self._responseXML = doc if ok else doc
            return self._responseXML
        except Exception:
            doc = DOMDocument()
            doc.parseError.errorCode = 1
            doc.parseError.reason = "responseXML parse failed"
            self._responseXML = doc
            return doc


class XMLHTTP(ServerXMLHTTP):
    """Alias for MSXML2.XMLHTTP.* ProgIDs.

    The client XMLHTTP object is close enough to ServerXMLHTTP for the subset
    used by Classic ASP.
    """

    pass


class DOMParseError:
    def __init__(self):
        self.errorCode = 0
        self.reason = ""
        self.line = 0
        self.linepos = 0
        self.srcText = ""


class _Attr:
    def __init__(self, name: str, text: str):
        self.name = name
        self.text = text


class _AttrList:
    def __init__(self, attrs: list[_Attr]):
        self._attrs = list(attrs)

    def __iter__(self):
        return iter(self._attrs)


class _NodeList:
    def __init__(self, nodes: list["_Node"]):
        self._nodes = list(nodes)

    @property
    def length(self):
        return len(self._nodes)

    @property
    def Length(self):
        return len(self._nodes)

    def __vbs_index_get__(self, idx):
        return self._nodes[int(idx)]

    def __iter__(self):
        return iter(self._nodes)

    def item(self, idx):
        return self._nodes[int(idx)]

    def Item(self, idx):
        return self.item(idx)


class _Node:
    def __init__(self, elem: Any, ns_uri_to_prefix: dict[str, str], doc=None):
        self._e = elem
        self._ns = ns_uri_to_prefix
        self._doc = doc

    def _node_kind(self):
        if self._e.tag is ET.Comment:
            return "comment"
        if self._e.tag is ET.ProcessingInstruction:
            return "processinginstruction"
        return "element"

    def _qname(self, tag: str) -> str:
        if tag.startswith('{'):
            uri, local = tag[1:].split('}', 1)
            pref = self._ns.get(uri, "")
            return f"{pref}:{local}" if pref else local
        return tag

    def _local(self, tag: str) -> str:
        if tag.startswith('{'):
            return tag.split('}', 1)[1]
        return tag

    @property
    def nodeName(self):
        kind = self._node_kind()
        if kind == "comment":
            return "#comment"
        if kind == "processinginstruction":
            return "#processing-instruction"
        return self._qname(str(self._e.tag))

    @property
    def nodeType(self):
        kind = self._node_kind()
        if kind == "comment":
            return 8
        if kind == "processinginstruction":
            return 7
        return 1

    @property
    def nodeTypeString(self):
        kind = self._node_kind()
        if kind == "comment":
            return "comment"
        if kind == "processinginstruction":
            return "processinginstruction"
        return "element"

    @property
    def nodeValue(self):
        kind = self._node_kind()
        if kind in ("comment", "processinginstruction"):
            return self._e.text or ""
        return None

    @property
    def nodeTypedValue(self):
        return self.nodeValue

    @property
    def text(self):
        kind = self._node_kind()
        if kind in ("comment", "processinginstruction"):
            return self._e.text or ""
        return "".join(self._e.itertext())

    @property
    def xml(self):
        try:
            return ET.tostring(self._e, encoding='unicode')
        except Exception:
            return ""

    @property
    def childNodes(self):
        kids = [
            _Node(ch, self._ns, self._doc)
            for ch in list(self._e)
            if isinstance(ch.tag, str)
        ]
        return _NodeList(kids)

    @property
    def firstChild(self):
        nl = self.childNodes
        return nl.item(0) if nl.length > 0 else None

    @property
    def lastChild(self):
        nl = self.childNodes
        return nl.item(nl.length - 1) if nl.length > 0 else None

    @property
    def parentNode(self):
        if self._doc is None:
            return None
        return self._doc._find_parent_node(self)

    @property
    def ownerDocument(self):
        return self._doc

    @property
    def nextSibling(self):
        if self._doc is None:
            return None
        return self._doc._find_sibling_node(self, forward=True)

    @property
    def previousSibling(self):
        if self._doc is None:
            return None
        return self._doc._find_sibling_node(self, forward=False)

    @property
    def attributes(self):
        attrs: list[_Attr] = []
        for k, v in self._e.attrib.items():
            nm = self._qname(str(k))
            attrs.append(_Attr(nm, str(v)))
        return _AttrList(attrs)

    def hasChildNodes(self):
        return len(list(self._e)) > 0

    def appendChild(self, newChild):
        if isinstance(newChild, _TextNode):
            self._append_text_node(newChild)
            return newChild
        if isinstance(newChild, _Node):
            self._e.append(newChild._e)
            return newChild
        raise Exception("MSXML: appendChild expects a node")

    def insertBefore(self, newChild, refChild):
        if isinstance(refChild, _Node):
            ref = refChild._e
        else:
            ref = refChild
        if isinstance(newChild, _TextNode):
            self._append_text_node(newChild)
            return newChild
        if isinstance(newChild, _Node):
            new_e = newChild._e
        else:
            raise Exception("MSXML: insertBefore expects a node")

        kids = list(self._e)
        for i, k in enumerate(kids):
            if k is ref:
                self._e.insert(i, new_e)
                return newChild
        self._e.append(new_e)
        return newChild

    def removeChild(self, childNode):
        if isinstance(childNode, _Node):
            ch = childNode._e
        else:
            ch = childNode
        self._e.remove(ch)
        return childNode

    def replaceChild(self, newChild, oldChild):
        if isinstance(oldChild, _Node):
            old_e = oldChild._e
        else:
            old_e = oldChild
        if isinstance(newChild, _Node):
            new_e = newChild._e
        elif isinstance(newChild, _TextNode):
            self._append_text_node(newChild)
            return newChild
        else:
            raise Exception("MSXML: replaceChild expects a node")
        kids = list(self._e)
        for i, k in enumerate(kids):
            if k is old_e:
                self._e.remove(old_e)
                self._e.insert(i, new_e)
                return newChild
        raise Exception("MSXML: oldChild not found")

    def cloneNode(self, deep=False):
        if bool(deep):
            try:
                data = ET.tostring(self._e, encoding='unicode')
                new_e = ET.fromstring(data)
            except Exception:
                new_e = ET.Element(self._e.tag)
        else:
            new_e = ET.Element(self._e.tag)
            new_e.attrib = dict(self._e.attrib)
            new_e.text = self._e.text
        return _Node(new_e, dict(self._ns), self._doc)

    def _append_text_node(self, tn):
        kids = list(self._e)
        if not kids:
            self._e.text = (self._e.text or "") + tn.text
        else:
            last = kids[-1]
            last.tail = (last.tail or "") + tn.text

    def GetAttribute(self, name):
        want = str(name)
        want_local = want.split(':', 1)[-1]
        for k, v in self._e.attrib.items():
            kn = str(k)
            if self._local(kn).lower() == want_local.lower():
                return str(v)
        return ""

    def selectNodes(self, xpath):
        # Minimal XPath support via ElementTree ElementPath.
        # MSXML often uses "//tag"; ElementTree expects ".//tag".
        xp = str(xpath or "")
        if xp.startswith("//"):
            xp = "." + xp
        try:
            found = self._e.findall(xp)
        except Exception:
            found = []
        nodes = [_Node(e, self._ns, self._doc) for e in found if isinstance(getattr(e, 'tag', None), str)]
        return _NodeList(nodes)

    def selectSingleNode(self, xpath):
        nl = self.selectNodes(xpath)
        try:
            return nl.item(0) if nl.length > 0 else None
        except Exception:
            return None


class _TextNode:
    def __init__(self, text: str):
        self.text = str(text)
        self.nodeName = "#text"
        self.nodeType = 3
        self.nodeTypeString = "text"
        self.nodeValue = self.text
        self.nodeTypedValue = self.text


class DOMDocument:
    def __init__(self, docroot: str | None = None):
        self._async = False
        self.readyState = 0
        self.onreadystatechange = None
        self.preserveWhiteSpace = False
        self.validateOnParse = False
        self.resolveExternals = False
        self.parseError = DOMParseError()
        self._docroot = os.path.abspath(docroot) if docroot else None
        self._url = ""
        self._aborted = False

        # XPath selection properties (accepted, best-effort)
        self._selection_language = "XPath"
        self._selection_namespaces = ""

        self._ns_uri_to_prefix: dict[str, str] = {}
        self._tree: ET.ElementTree | None = None

    def _root(self):
        if not self._tree:
            return None
        return self._tree.getroot()

    def __getattr__(self, name: str):
        # VBScript uses `.async`, but `async` is a Python keyword.
        if str(name).lower() == 'async':
            return bool(self._async)
        raise AttributeError(name)

    def __setattr__(self, name: str, value):
        # VBScript uses `.async`, but `async` is a Python keyword.
        if str(name).lower() == 'async':
            # Treat async loads as unsupported in this server runtime; keep sync.
            object.__setattr__(self, '_async', False)
            return
        object.__setattr__(self, name, value)

    def setProperty(self, name, value):
        nm = str(name or "").strip().lower()
        if nm == "serverhttprequest":
            return
        if nm == "selectionlanguage":
            self._selection_language = str(value)
            return
        if nm == "selectionnamespaces":
            self._selection_namespaces = str(value)
            return
        return

    def abort(self):
        self._aborted = True
        self.readyState = 0
        self._fire_ready_state()

    @property
    def documentElement(self):
        root = self._root()
        if root is None:
            return None
        root = cast(ET.Element, root)
        return _Node(root, self._ns_uri_to_prefix, self)

    @property
    def attributes(self):
        return None

    @property
    def childNodes(self):
        root = self._root()
        if root is None:
            return _NodeList([])
        root = cast(ET.Element, root)
        return _NodeList([_Node(root, self._ns_uri_to_prefix, self)])

    @property
    def doctype(self):
        return None

    @property
    def firstChild(self):
        nl = self.childNodes
        return nl.item(0) if nl.length > 0 else None

    @property
    def implementation(self):
        return None

    @property
    def lastChild(self):
        nl = self.childNodes
        return nl.item(nl.length - 1) if nl.length > 0 else None

    @property
    def namespaces(self):
        return []

    @property
    def nextSibling(self):
        return None

    @property
    def nodeName(self):
        return "#document"

    @property
    def nodeType(self):
        return 9

    @property
    def nodeTypedValue(self):
        return None

    @property
    def nodeTypeString(self):
        return "document"

    @property
    def nodeValue(self):
        return None

    @property
    def ownerDocument(self):
        return None

    @property
    def parentNode(self):
        return None

    @property
    def previousSibling(self):
        return None

    @property
    def text(self):
        root = self._root()
        if root is None:
            return ""
        root = cast(ET.Element, root)
        try:
            return "".join(root.itertext())
        except Exception:
            return ""

    @property
    def url(self):
        return self._url

    @property
    def xml(self):
        root = self._root()
        if root is None:
            return ""
        root = cast(ET.Element, root)
        try:
            return ET.tostring(root, encoding='unicode')
        except Exception:
            return ""

    def hasChildNodes(self):
        return self.firstChild is not None

    def appendChild(self, newChild):
        if isinstance(newChild, _Node):
            if not self._tree:
                self._tree = ET.ElementTree(newChild._e)
                return newChild
            root = self._root()
            if root is None:
                self._tree = ET.ElementTree(newChild._e)
                return newChild
            root = cast(ET.Element, root)
            root.append(newChild._e)
            return newChild
        if isinstance(newChild, _TextNode):
            if not self._tree:
                raise Exception("MSXML: cannot append text to empty document")
            root = self._root()
            if root is None:
                raise Exception("MSXML: document has no root")
            root = cast(ET.Element, root)
            if root.text:
                root.text += newChild.text
            else:
                root.text = newChild.text
            return newChild
        raise Exception("MSXML: appendChild expects a node")

    def insertBefore(self, newChild, refChild):
        if not self._tree:
            return self.appendChild(newChild)
        root = self._root()
        if root is None:
            return self.appendChild(newChild)
        root = cast(ET.Element, root)
        if isinstance(refChild, _Node) and refChild._e is root:
            if isinstance(newChild, _Node):
                self._tree = ET.ElementTree(newChild._e)
                return newChild
            raise Exception("MSXML: insertBefore expects a node")
        if isinstance(newChild, _Node):
            root.insert(0, newChild._e)
            return newChild
        if isinstance(newChild, _TextNode):
            root.text = (newChild.text + (root.text or ""))
            return newChild
        raise Exception("MSXML: insertBefore expects a node")

    def removeChild(self, childNode):
        if not self._tree:
            raise Exception("MSXML: document has no children")
        root = self._root()
        if root is None:
            raise Exception("MSXML: document has no root")
        root = cast(ET.Element, root)
        if isinstance(childNode, _Node) and childNode._e is root:
            self._tree = None
            return childNode
        root.remove(childNode._e if isinstance(childNode, _Node) else childNode)
        return childNode

    def replaceChild(self, newChild, oldChild):
        if not self._tree:
            return self.appendChild(newChild)
        root = self._root()
        if root is None:
            return self.appendChild(newChild)
        root = cast(ET.Element, root)
        if isinstance(oldChild, _Node) and oldChild._e is root:
            if isinstance(newChild, _Node):
                self._tree = ET.ElementTree(newChild._e)
                return newChild
            raise Exception("MSXML: replaceChild expects a node")
        root.remove(oldChild._e if isinstance(oldChild, _Node) else oldChild)
        if isinstance(newChild, _Node):
            root.append(newChild._e)
            return newChild
        if isinstance(newChild, _TextNode):
            root.text = (root.text or "") + newChild.text
            return newChild
        raise Exception("MSXML: replaceChild expects a node")

    def cloneNode(self, deep=False):
        new_doc = DOMDocument(self._docroot)
        if self._tree is None:
            return new_doc
        root0 = self._root()
        if root0 is None:
            return new_doc
        root0 = cast(ET.Element, root0)
        if bool(deep):
            try:
                data = ET.tostring(root0, encoding='unicode')
                root = ET.fromstring(data)
            except Exception:
                root = ET.Element(root0.tag)
        else:
            root = ET.Element(root0.tag)
            root.attrib = dict(root0.attrib)
            root.text = root0.text
        new_doc._tree = ET.ElementTree(root)
        return new_doc

    def createElement(self, tagName):
        return _Node(ET.Element(str(tagName)), self._ns_uri_to_prefix, self)

    def createAttribute(self, name):
        return _Attr(str(name), "")

    def createCDATASection(self, data):
        return _TextNode(str(data))

    def createComment(self, data):
        return _Node(cast(Any, ET.Comment(str(data))), self._ns_uri_to_prefix, self)

    def createDocumentFragment(self):
        return _Node(ET.Element("_fragment"), self._ns_uri_to_prefix, self)

    def createEntityReference(self, name):
        return _TextNode(f"&{str(name)};")

    def createNode(self, nodeType, name, namespaceURI=None):
        t = int(nodeType)
        if t == 1:
            return self.createElement(name)
        if t == 2:
            return self.createAttribute(name)
        if t == 3:
            return self.createTextNode("")
        if t == 4:
            return self.createCDATASection("")
        if t == 7:
            return self.createProcessingInstruction(name, "")
        if t == 8:
            return self.createComment("")
        if t == 9:
            return DOMDocument(self._docroot)
        raise Exception("MSXML: unsupported node type")

    def createProcessingInstruction(self, target, data):
        return _Node(cast(Any, ET.ProcessingInstruction(str(target), str(data))), self._ns_uri_to_prefix, self)

    def createTextNode(self, data):
        return _TextNode(str(data))

    def getElementsByTagName(self, name):
        root = self._root()
        if root is None:
            return _NodeList([])
        root = cast(ET.Element, root)
        want = str(name)
        want_local = want.split(':', 1)[-1].lower()
        nodes: list[_Node] = []
        for e in root.iter():  # type: ignore[union-attr]
            if not isinstance(e.tag, str):
                continue
            tag = e.tag
            local = tag.split('}', 1)[1] if tag.startswith('{') else tag
            if local.lower() == want_local:
                nodes.append(_Node(e, self._ns_uri_to_prefix, self))
        return _NodeList(nodes)

    def save(self, filename):
        # Save XML to local file. Restricted to docroot unless explicitly allowed.
        path = str(filename)
        if not _env_bool("ASP_PY_XML_ALLOW_LOCAL", False):
            raise Exception("MSXML: local paths blocked (set ASP_PY_XML_ALLOW_LOCAL=1 to allow)")
        if self._docroot and not os.path.isabs(path):
            path = os.path.abspath(os.path.join(self._docroot, path.lstrip("/\\")))
        data = self.xml
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(data)
        return True

    def selectNodes(self, xpath):
        de = self.documentElement
        if de is None:
            return _NodeList([])
        return de.selectNodes(xpath)

    def selectSingleNode(self, xpath):
        de = self.documentElement
        if de is None:
            return None
        return de.selectSingleNode(xpath)

    def _parse_xml_bytes(self, data: bytes) -> bool:
        # Capture namespaces while parsing.
        self._ns_uri_to_prefix = {}
        try:
            ns_events = ("start", "start-ns")
            bio = io.BytesIO(data)
            # iterparse builds the tree incrementally
            it = ET.iterparse(bio, events=ns_events)
            for ev, obj in it:
                if ev == "start-ns":
                    pref, uri = obj
                    uri = str(uri)
                    if uri not in self._ns_uri_to_prefix:
                        self._ns_uri_to_prefix[uri] = str(pref or "")
            root = it.root  # type: ignore[attr-defined]
            if root is None:
                raise Exception("MSXML: empty document")
            self._tree = ET.ElementTree(root)
            self.readyState = 4
            self._fire_ready_state()
            return True
        except Exception as e:
            self._tree = None
            self.parseError.errorCode = 1
            self.parseError.reason = str(e)
            self.readyState = 4
            self._fire_ready_state()
            return False

    def Load(self, url):
        self.parseError = DOMParseError()
        self.readyState = 1
        self._fire_ready_state()
        u = str(url)
        pu = urlparse(u)
        scheme = (pu.scheme or "").lower()
        if scheme in ("http", "https"):
            try:
                r = _http_request("GET", u)
            except Exception as e:
                self.parseError.errorCode = 1
                self.parseError.reason = str(e)
                self.readyState = 4
                self._fire_ready_state()
                return False
            self._url = r.url
            return self._parse_xml_bytes(r.body)

        # Local file paths are blocked by default (SSRF / sandbox).
        if not _env_bool("ASP_PY_XML_ALLOW_LOCAL", False):
            self.parseError.errorCode = 1
            self.parseError.reason = "MSXML: local paths blocked (set ASP_PY_XML_ALLOW_LOCAL=1 to allow)"
            self.readyState = 4
            self._fire_ready_state()
            return False

        # If explicitly allowed, read from docroot if provided, else from absolute path.
        try:
            path = u
            if self._docroot and not os.path.isabs(path):
                path = os.path.abspath(os.path.join(self._docroot, path.lstrip("/\\")))
            with open(path, "rb") as f:
                data = f.read(_max_bytes())
            self._url = path
            return self._parse_xml_bytes(data)
        except Exception as e:
            self.parseError.errorCode = 1
            self.parseError.reason = str(e)
            self.readyState = 4
            self._fire_ready_state()
            return False

    def LoadXML(self, xml_text):
        self.parseError = DOMParseError()
        self.readyState = 1
        self._fire_ready_state()
        try:
            data = str(xml_text).encode("utf-8", errors="replace")
        except Exception:
            data = b""
        return self._parse_xml_bytes(data)

    def load(self, xmlSource):
        return self.Load(xmlSource)

    def loadXML(self, xmlString):
        return self.LoadXML(xmlString)

    def nodeFromID(self, idString):
        root = self._root()
        if root is None:
            return None
        root = cast(ET.Element, root)
        want = str(idString)
        for e in root.iter():
            if not isinstance(e.tag, str):
                continue
            if e.attrib.get("id") == want or e.attrib.get("ID") == want:
                return _Node(e, self._ns_uri_to_prefix, self)
        return None

    def transformNode(self, stylesheet):
        raise Exception("MSXML: transformNode not implemented")

    def transformNodeToObject(self, stylesheet, output):
        raise Exception("MSXML: transformNodeToObject not implemented")

    def _fire_ready_state(self):
        try:
            cb = getattr(self, "onreadystatechange", None)
            if callable(cb):
                cb()
        except Exception:
            pass

    def _find_parent_node(self, node: _Node):
        root = self._root()
        if root is None:
            return None
        root = cast(ET.Element, root)
        target = node._e
        for parent in root.iter():
            for ch in list(parent):
                if ch is target:
                    return _Node(parent, self._ns_uri_to_prefix, self)
        return self

    def _find_sibling_node(self, node: _Node, forward: bool = True):
        root = self._root()
        if root is None:
            return None
        root = cast(ET.Element, root)
        target = node._e
        for parent in root.iter():
            kids = list(parent)
            for i, ch in enumerate(kids):
                if ch is target:
                    j = i + 1 if forward else i - 1
                    if 0 <= j < len(kids):
                        return _Node(kids[j], self._ns_uri_to_prefix, self)
                    return None
        return None
