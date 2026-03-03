"""IMAP shim for Classic ASP-style usage in ASP4.

Create via:
    Server.CreateObject("ASP4.IMAP")
or:
    Set m = ASP4.imap
"""

from __future__ import annotations

import email
import imaplib

from .pop3 import _decode_header_value, _extract_attachment_names, _extract_attachments, _extract_body_text
from .vb_runtime import vbs_cstr
from .vm.values import VBArray


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


def _imap_decode(value) -> str:
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", errors="replace")
    return vbs_cstr(value)


def _to_vb_array(items: list[str]):
    if not items:
        return VBArray([-1], allocated=True, dynamic=True)
    a = VBArray(len(items) - 1, allocated=True, dynamic=True)
    for i, v in enumerate(items):
        a.__vbs_index_set__(i, v)
    return a


def _extract_rfc822_bytes(data) -> bytes:
    """Best-effort extraction of raw message bytes from imaplib fetch payload."""
    best = b""

    def walk(obj):
        nonlocal best
        if obj is None:
            return
        if isinstance(obj, (bytes, bytearray)):
            b = bytes(obj)
            # Prefer payloads that look like full messages (headers + body).
            if b"\n" in b and b":" in b and len(b) >= len(best):
                best = b
            elif len(best) == 0 and len(b) > 0:
                best = b
            return
        if isinstance(obj, tuple):
            for x in obj:
                walk(x)
            return
        if isinstance(obj, list):
            for x in obj:
                walk(x)
            return

    walk(data)
    return best


class IMAPMessage:
    def __init__(self, uid: str, seq: str, raw_bytes: bytes):
        self.UID = vbs_cstr(uid)
        self.Seq = vbs_cstr(seq)
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


class ASP4IMAP:
    """Simple IMAP client shim for VBScript use."""

    def __init__(self):
        self.Host = ""
        self.Port = 993
        self.UseSSL = True
        self.Timeout = 30
        self.Username = ""
        self.Connected = False
        self.SelectedFolder = ""
        self.ReadOnly = False
        self.MessageCount = 0
        self.LastResponse = ""
        self.LastStatus = ""
        self._mb = None
        self._uid_by_seq: dict[str, str] = {}

    def _require_conn(self):
        if self._mb is None:
            raise Exception("IMAP: not connected")
        return self._mb

    def _set_status(self, status, response):
        self.LastStatus = _imap_decode(status)
        self.LastResponse = _imap_decode(response)

    def Connect(self, host, port=993, use_ssl=True, timeout=30):
        self.Close()
        self.Host = vbs_cstr(host).strip()
        self.Port = _to_int(port, 993)
        self.UseSSL = _to_bool(use_ssl, True)
        self.Timeout = _to_int(timeout, 30)
        if not self.Host:
            raise Exception("IMAP: host is required")

        if bool(self.UseSSL):
            self._mb = imaplib.IMAP4_SSL(self.Host, self.Port, timeout=self.Timeout)
        else:
            self._mb = imaplib.IMAP4(self.Host, self.Port, timeout=self.Timeout)
        self.Connected = True
        self.SelectedFolder = ""
        self.MessageCount = 0
        self._uid_by_seq.clear()
        self.LastStatus = "OK"
        self.LastResponse = "Connected"
        return True

    def Open(self, host, port=993, use_ssl=True, timeout=30):
        return self.Connect(host, port, use_ssl, timeout)

    def Login(self, username, password):
        mb = self._require_conn()
        self.Username = vbs_cstr(username)
        typ, data = mb.login(self.Username, vbs_cstr(password))
        self._set_status(typ, data[0] if data else "")
        return self.LastResponse

    def Select(self, folder="INBOX", readonly=False):
        mb = self._require_conn()
        fld = vbs_cstr(folder).strip() or "INBOX"
        ro = _to_bool(readonly, False)
        typ, data = mb.select(fld, readonly=ro)
        self._set_status(typ, data[0] if data else "")
        if str(typ).upper() != "OK":
            raise Exception(f"IMAP SELECT failed: {self.LastResponse}")
        self.SelectedFolder = fld
        self.ReadOnly = ro
        try:
            self.MessageCount = int(_imap_decode(data[0]))
        except Exception:
            self.MessageCount = 0
        self._uid_by_seq.clear()
        return self.MessageCount

    def Search(self, criteria="ALL"):
        mb = self._require_conn()
        crit = vbs_cstr(criteria).strip() or "ALL"
        typ, data = mb.search(None, crit)
        self._set_status(typ, data[0] if data else "")
        if str(typ).upper() != "OK":
            return _to_vb_array([])
        if not data or not data[0]:
            return _to_vb_array([])
        raw = _imap_decode(data[0]).strip()
        return _to_vb_array([x for x in raw.split() if x])

    def SearchUID(self, criteria="ALL"):
        mb = self._require_conn()
        crit = vbs_cstr(criteria).strip() or "ALL"
        typ, data = getattr(mb, "uid")("SEARCH", "", crit)
        self._set_status(typ, data[0] if data else "")
        if str(typ).upper() != "OK":
            return _to_vb_array([])
        if not data or not data[0]:
            return _to_vb_array([])
        raw = _imap_decode(data[0]).strip()
        return _to_vb_array([x for x in raw.split() if x])

    def _fetch_raw_by_seq(self, seq_num: str) -> bytes:
        mb = self._require_conn()
        typ, data = mb.fetch(vbs_cstr(seq_num), "(RFC822)")
        self._set_status(typ, data[0] if data else "")
        if str(typ).upper() != "OK":
            raise Exception(f"IMAP FETCH failed: {self.LastResponse}")
        raw = _extract_rfc822_bytes(data)
        # Some servers are picky about sequence/UID handling; try UID fallback.
        if not raw:
            try:
                typ2, data2 = mb.uid("FETCH", vbs_cstr(seq_num), "(RFC822)")
                if str(typ2).upper() == "OK":
                    raw = _extract_rfc822_bytes(data2)
            except Exception:
                pass
        return raw

    def _fetch_uid_for_seq(self, seq_num: str) -> str:
        mb = self._require_conn()
        if seq_num in self._uid_by_seq:
            return self._uid_by_seq[seq_num]
        typ, data = mb.fetch(vbs_cstr(seq_num), "(UID)")
        if str(typ).upper() != "OK":
            return ""
        uid = ""
        if isinstance(data, list):
            for item in data:
                if isinstance(item, tuple) and item:
                    hdr = _imap_decode(item[0])
                    p = hdr.upper().find("UID ")
                    if p >= 0:
                        q = p + 4
                        while q < len(hdr) and hdr[q].isdigit():
                            q += 1
                        uid = hdr[p + 4:q]
                        break
        if uid:
            self._uid_by_seq[seq_num] = uid
        return uid

    def Fetch(self, msg_num):
        seq = vbs_cstr(msg_num).strip()
        if not seq:
            raise Exception("IMAP: message sequence number is required")
        raw = self._fetch_raw_by_seq(seq)
        return raw.decode("utf-8", errors="replace")

    def GetMessage(self, msg_num):
        seq = vbs_cstr(msg_num).strip()
        if not seq:
            raise Exception("IMAP: message sequence number is required")
        raw = self._fetch_raw_by_seq(seq)
        uid = self._fetch_uid_for_seq(seq)
        return IMAPMessage(uid=uid, seq=seq, raw_bytes=raw)

    def GetMessageByUID(self, uid):
        mb = self._require_conn()
        uid_s = vbs_cstr(uid).strip()
        if not uid_s:
            raise Exception("IMAP: message UID is required")
        typ, data = mb.uid("FETCH", uid_s, "(RFC822)")
        self._set_status(typ, data[0] if data else "")
        if str(typ).upper() != "OK":
            raise Exception(f"IMAP UID FETCH failed: {self.LastResponse}")
        raw = _extract_rfc822_bytes(data)
        return IMAPMessage(uid=uid_s, seq="", raw_bytes=raw)

    def Store(self, msg_num, flags, mode="+FLAGS"):
        mb = self._require_conn()
        seq = vbs_cstr(msg_num).strip()
        flg = vbs_cstr(flags).strip()
        md = vbs_cstr(mode).strip() or "+FLAGS"
        typ, data = mb.store(seq, md, flg)
        self._set_status(typ, data[0] if data else "")
        return self.LastResponse

    def Delete(self, msg_num):
        return self.Store(msg_num, r"(\Deleted)", "+FLAGS")

    def Dele(self, msg_num):
        # POP3-style alias for parity with ASP4POP3.
        return self.Delete(msg_num)

    def DeleteAll(self):
        ids = self.Search("ALL")
        n = 0
        try:
            ub = int(ids.ubound(1))
        except Exception:
            ub = -1
        for i in range(0, ub + 1):
            seq = vbs_cstr(ids.__vbs_index_get__(i)).strip()
            if not seq:
                continue
            self.Delete(seq)
            n += 1
        self.LastResponse = f"Marked {n} message(s) as \\Deleted"
        return n

    def Expunge(self):
        mb = self._require_conn()
        typ, data = mb.expunge()
        self._set_status(typ, data[0] if data else "")
        return self.LastResponse

    def Noop(self):
        mb = self._require_conn()
        typ, data = mb.noop()
        self._set_status(typ, data[0] if data else "")
        return self.LastResponse

    def Logout(self):
        if self._mb is None:
            self.Connected = False
            return True
        try:
            typ, data = self._mb.logout()
            self._set_status(typ, data[0] if data else "")
        finally:
            self._mb = None
            self.Connected = False
            self.SelectedFolder = ""
            self.MessageCount = 0
            self._uid_by_seq.clear()
        return True

    def Close(self):
        if self._mb is None:
            self.Connected = False
            return True
        try:
            self._mb.logout()
        except Exception:
            pass
        finally:
            self._mb = None
            self.Connected = False
            self.SelectedFolder = ""
            self.MessageCount = 0
            self._uid_by_seq.clear()
        return True
