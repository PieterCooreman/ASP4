"""POP3 shim for Classic ASP-style usage in ASP4.

Create via:
    Server.CreateObject("ASP4.POP3")
"""

from __future__ import annotations

import email
import poplib
from email.header import decode_header

from .vb_runtime import vbs_cstr


def _to_int(v, default: int) -> int:
    try:
        s = vbs_cstr(v).strip()
        if s == "":
            return int(default)
        return int(float(s))
    except Exception:
        return int(default)


def _to_bool(v, default: bool = False) -> bool:
    s = vbs_cstr(v).strip().lower()
    if s == "":
        return bool(default)
    return s in ("1", "true", "yes", "on", "-1")


def _decode_header_value(v) -> str:
    if not v:
        return ""
    try:
        parts = decode_header(str(v))
        out = []
        for part, enc in parts:
            if isinstance(part, bytes):
                cs = enc or "utf-8"
                try:
                    out.append(part.decode(cs, errors="replace"))
                except Exception:
                    out.append(part.decode("utf-8", errors="replace"))
            else:
                out.append(str(part))
        return "".join(out)
    except Exception:
        return vbs_cstr(v)


def _extract_body_text(msg) -> str:
    if msg is None:
        return ""
    plain_parts: list[str] = []
    html_parts: list[str] = []
    try:
        if msg.is_multipart():
            for part in msg.walk():
                ctype = (part.get_content_type() or "").lower()
                disp = (part.get("Content-Disposition") or "").lower()
                if "attachment" in disp:
                    continue
                payload = part.get_payload(decode=True)
                if payload is None:
                    txt = vbs_cstr(part.get_payload())
                else:
                    cs = part.get_content_charset() or "utf-8"
                    try:
                        txt = payload.decode(cs, errors="replace")
                    except Exception:
                        txt = payload.decode("utf-8", errors="replace")
                if ctype == "text/plain":
                    plain_parts.append(txt)
                elif ctype == "text/html":
                    html_parts.append(txt)
        else:
            payload = msg.get_payload(decode=True)
            if payload is None:
                return vbs_cstr(msg.get_payload())
            cs = msg.get_content_charset() or "utf-8"
            try:
                return payload.decode(cs, errors="replace")
            except Exception:
                return payload.decode("utf-8", errors="replace")
    except Exception:
        return ""
    if plain_parts:
        return "\n".join(plain_parts)
    if html_parts:
        return "\n".join(html_parts)
    return ""


def _extract_attachment_names(msg) -> list[str]:
    names: list[str] = []
    if msg is None:
        return names
    try:
        if msg.is_multipart():
            for part in msg.walk():
                disp = (part.get("Content-Disposition") or "").lower()
                fn = part.get_filename()
                if "attachment" not in disp and not fn:
                    continue
                dec = _decode_header_value(fn)
                if dec:
                    names.append(dec)
        else:
            fn = msg.get_filename()
            if fn:
                dec = _decode_header_value(fn)
                if dec:
                    names.append(dec)
    except Exception:
        return names
    return names


def _extract_attachments(msg) -> list[dict]:
    items: list[dict] = []
    if msg is None:
        return items
    try:
        seq = 0
        if msg.is_multipart():
            for part in msg.walk():
                disp = (part.get("Content-Disposition") or "").lower()
                fn = part.get_filename()
                if "attachment" not in disp and not fn:
                    continue
                seq += 1
                name = _decode_header_value(fn)
                if not name:
                    name = f"attachment_{seq}.bin"
                ctype = (part.get_content_type() or "application/octet-stream").strip() or "application/octet-stream"
                data = part.get_payload(decode=True)
                if data is None:
                    data = b""
                items.append({"name": name, "content_type": ctype, "data": bytes(data)})
        else:
            fn = msg.get_filename()
            if fn:
                name = _decode_header_value(fn) or "attachment_1.bin"
                ctype = (msg.get_content_type() or "application/octet-stream").strip() or "application/octet-stream"
                data = msg.get_payload(decode=True)
                if data is None:
                    data = b""
                items.append({"name": name, "content_type": ctype, "data": bytes(data)})
    except Exception:
        return items
    return items


class POP3Message:
    def __init__(self, raw_bytes: bytes):
        self.Raw = bytes(raw_bytes or b"")
        self.Text = self.Raw.decode("utf-8", errors="replace")

        parsed = None
        try:
            parsed = email.message_from_bytes(self.Raw)
        except Exception:
            parsed = None

        self.From = _decode_header_value(parsed.get("From")) if parsed else ""
        self.To = _decode_header_value(parsed.get("To")) if parsed else ""
        self.Cc = _decode_header_value(parsed.get("Cc")) if parsed else ""
        self.Subject = _decode_header_value(parsed.get("Subject")) if parsed else ""
        self.Date = _decode_header_value(parsed.get("Date")) if parsed else ""
        self.MessageID = _decode_header_value(parsed.get("Message-ID")) if parsed else ""
        self.Body = _extract_body_text(parsed)
        self.AttachmentNames = _extract_attachment_names(parsed)
        self.AttachmentCount = len(self.AttachmentNames)
        self.AttachmentNamesText = ", ".join(self.AttachmentNames)
        self._attachments = _extract_attachments(parsed)

    def _att_at(self, index):
        try:
            i = int(float(vbs_cstr(index).strip()))
        except Exception:
            i = 0
        if i < 1 or i > len(self._attachments):
            raise Exception("Attachment index out of range")
        return self._attachments[i - 1]

    def AttachmentName(self, index):
        return self._att_at(index).get("name", "attachment.bin")

    def AttachmentContentType(self, index):
        return self._att_at(index).get("content_type", "application/octet-stream")

    def AttachmentSize(self, index):
        data = self._att_at(index).get("data", b"")
        return len(data)

    def AttachmentBytes(self, index):
        return self._att_at(index).get("data", b"")

    def Header(self, name):
        nm = vbs_cstr(name)
        if not nm:
            return ""
        try:
            parsed = email.message_from_bytes(self.Raw)
            return _decode_header_value(parsed.get(nm, ""))
        except Exception:
            return ""


class ASP4POP3:
    """Simple POP3 client shim for VBScript use."""

    def __init__(self):
        self.Host = ""
        self.Port = 995
        self.UseSSL = True
        self.Timeout = 30
        self.Username = ""
        self.Connected = False
        self.MessageCount = 0
        self.TotalSize = 0
        self.LastResponse = ""
        self._mb = None

    def _require_conn(self):
        if self._mb is None:
            raise Exception("POP3: not connected")
        return self._mb

    def Connect(self, host, port=995, use_ssl=True, timeout=30):
        self.Close()
        self.Host = vbs_cstr(host).strip()
        self.Port = _to_int(port, 995)
        self.UseSSL = _to_bool(use_ssl, True)
        self.Timeout = _to_int(timeout, 30)
        if not self.Host:
            raise Exception("POP3: host is required")

        if bool(self.UseSSL):
            self._mb = poplib.POP3_SSL(self.Host, self.Port, timeout=self.Timeout)
        else:
            self._mb = poplib.POP3(self.Host, self.Port, timeout=self.Timeout)
        self.Connected = True
        self.LastResponse = "Connected"
        return True

    def Open(self, host, port=995, use_ssl=True, timeout=30):
        return self.Connect(host, port, use_ssl, timeout)

    def User(self, username):
        mb = self._require_conn()
        self.Username = vbs_cstr(username)
        resp = mb.user(self.Username)
        self.LastResponse = vbs_cstr(resp)
        return self.LastResponse

    def Pass(self, password):
        mb = self._require_conn()
        resp = mb.pass_(vbs_cstr(password))
        self.LastResponse = vbs_cstr(resp)
        return self.LastResponse

    def Login(self, username, password):
        self.User(username)
        return self.Pass(password)

    def Stat(self):
        mb = self._require_conn()
        count, total = mb.stat()
        self.MessageCount = int(count)
        self.TotalSize = int(total)
        return self.MessageCount

    def List(self):
        mb = self._require_conn()
        _resp, lines, _octets = mb.list()
        out = []
        for line in lines:
            if isinstance(line, (bytes, bytearray)):
                out.append(bytes(line).decode("ascii", errors="replace"))
            else:
                out.append(vbs_cstr(line))
        return out

    def UIDL(self, msg_num=None):
        mb = self._require_conn()
        if msg_num is None or vbs_cstr(msg_num).strip() == "":
            _resp, lines, _octets = mb.uidl()
            out = []
            for line in lines:
                if isinstance(line, (bytes, bytearray)):
                    out.append(bytes(line).decode("ascii", errors="replace"))
                else:
                    out.append(vbs_cstr(line))
            return out
        _resp, line, _octets = mb.uidl(_to_int(msg_num, 0))
        if isinstance(line, (bytes, bytearray)):
            return bytes(line).decode("ascii", errors="replace")
        return vbs_cstr(line)

    def Retr(self, msg_num):
        mb = self._require_conn()
        _resp, lines, _octets = mb.retr(_to_int(msg_num, 0))
        raw = b"\r\n".join(lines)
        return raw.decode("utf-8", errors="replace")

    def GetMessage(self, msg_num):
        mb = self._require_conn()
        _resp, lines, _octets = mb.retr(_to_int(msg_num, 0))
        raw = b"\r\n".join(lines)
        return POP3Message(raw)

    def Dele(self, msg_num):
        mb = self._require_conn()
        resp = mb.dele(_to_int(msg_num, 0))
        self.LastResponse = vbs_cstr(resp)
        return self.LastResponse

    def Delete(self, msg_num):
        # Alias for VBScript callers that prefer .Delete(n)
        return self.Dele(msg_num)

    def DeleteAll(self):
        mb = self._require_conn()
        count, _total = mb.stat()
        n = int(count)
        for i in range(1, n + 1):
            mb.dele(i)
        self.LastResponse = f"Marked {n} message(s) for deletion"
        return n

    def Noop(self):
        mb = self._require_conn()
        resp = mb.noop()
        self.LastResponse = vbs_cstr(resp)
        return self.LastResponse

    def Rset(self):
        mb = self._require_conn()
        resp = mb.rset()
        self.LastResponse = vbs_cstr(resp)
        return self.LastResponse

    def Quit(self):
        if self._mb is None:
            self.Connected = False
            return True
        try:
            self.LastResponse = vbs_cstr(self._mb.quit())
        finally:
            self._mb = None
            self.Connected = False
        return True

    def Close(self):
        if self._mb is None:
            self.Connected = False
            return True
        try:
            self._mb.quit()
        except Exception:
            try:
                self._mb.close()
            except Exception:
                pass
        finally:
            self._mb = None
            self.Connected = False
        return True
