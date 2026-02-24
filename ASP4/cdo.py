"""Minimal shims for common CDO (CDOSYS) COM objects.

Currently implements a pragmatic subset of:
- CDO.Message

Goal: support Classic ASP/VBScript code patterns like aspLite's cdomessage plugin.
"""

from __future__ import annotations

import os
import time
import uuid
import smtplib
from email.message import EmailMessage
from email.utils import formatdate

from .vb_runtime import vbs_cstr


def _to_int(v, default: int) -> int:
    try:
        s = vbs_cstr(v).strip()
        if s == "":
            return int(default)
        return int(float(s))
    except Exception:
        return int(default)


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return bool(default)
    return v.strip().lower() in ("1", "true", "yes", "on")


def _split_addr_list(s: str) -> list[str]:
    # Accept "a@b", "Name <a@b>", and semicolon/comma separated.
    raw = vbs_cstr(s).strip()
    if not raw:
        return []
    parts = []
    for chunk in raw.replace(";", ",").split(","):
        c = chunk.strip()
        if c:
            parts.append(c)
    return parts


class CDOBodyPart:
    def __init__(self):
        self.ContentMediaType = ""
        self.Charset = ""
        self.ContentTransferEncoding = ""


class _FieldsItemAccessor:
    def __init__(self, fields: "CDOFields"):
        self._fields = fields

    def __call__(self, key):
        return self._fields.__vbs_index_get__(key)

    def __vbs_index_get__(self, key):
        return self._fields.__vbs_index_get__(key)

    def __vbs_index_set__(self, key, value):
        return self._fields.__vbs_index_set__(key, value)


class CDOFields:
    """A minimal CDO.Fields collection.

In Classic ASP, a common pattern is:
  msg.Configuration.Fields.Item("schema") = value
  msg.Configuration.Fields.Update

We store values as strings/ints/bools as provided.
"""

    def __init__(self):
        self._map: dict[str, object] = {}
        self.Item = _FieldsItemAccessor(self)

    def __vbs_index_get__(self, key):
        return self._map.get(vbs_cstr(key), "")

    def __vbs_index_set__(self, key, value):
        self._map[vbs_cstr(key)] = value

    def Update(self):
        # In COM this commits the field changes.
        return


class CDOConfiguration:
    def __init__(self):
        self.Fields = CDOFields()


class CDOMessage:
    """A pragmatic CDO.Message shim.

Supported (commonly used in Classic ASP):
- Configuration.Fields.Item(key)=value; Fields.Update
- To, Cc, Bcc, From, ReplyTo, Subject
- HtmlBody, TextBody
- BodyPart, HTMLBodyPart (body part metadata)
- AddAttachment(path)
- Send
"""

    def __init__(self, docroot: str | None = None):
        self._docroot = os.path.abspath(docroot) if docroot else None
        self.Configuration = CDOConfiguration()

        self.To = ""
        self.Cc = ""
        self.Bcc = ""
        self.From = ""
        self.ReplyTo = ""
        self.Subject = ""
        self.HtmlBody = ""
        self.TextBody = ""

        # Body parts (metadata)
        self.BodyPart = CDOBodyPart()
        self.HTMLBodyPart = CDOBodyPart()
        self.TextBodyPart = CDOBodyPart()

        self._attachments: list[str] = []

        # When True, Send becomes a no-op success. Useful for dev/testing.
        self.DisableSend = False

    def _ensure_attachment_allowed(self, path: str) -> str:
        p = os.path.abspath(path)
        if self._docroot and not _env_bool("ASP_PY_CDO_ALLOW_OUTSIDE_DOCROOT", False):
            if os.path.commonpath([self._docroot, p]) != self._docroot:
                raise Exception("CDO.Message: attachment path outside docroot")
        return p

    def AddAttachment(self, path, *args):
        # CDO supports additional args; ignore for now.
        p = self._ensure_attachment_allowed(vbs_cstr(path))
        self._attachments.append(p)

    def Send(self):
        if bool(self.DisableSend) or _env_bool("ASP_PY_CDO_DISABLE_SEND", False):
            # Dev-safe: treat as successful send.
            return True

        f = self.Configuration.Fields
        # Common config keys
        smtpserver = vbs_cstr(f._map.get("http://schemas.microsoft.com/cdo/configuration/smtpserver", "")).strip()
        smtpport = _to_int(f._map.get("http://schemas.microsoft.com/cdo/configuration/smtpserverport", 25), 25)
        timeout = _to_int(f._map.get("http://schemas.microsoft.com/cdo/configuration/smtpconnectiontimeout", 30), 30)
        sendusing = _to_int(f._map.get("http://schemas.microsoft.com/cdo/configuration/sendusing", 2), 2)
        pickupdir = vbs_cstr(f._map.get("http://schemas.microsoft.com/cdo/configuration/smtpserverpickupdirectory", "")).strip()

        smtpauth = _to_int(f._map.get("http://schemas.microsoft.com/cdo/configuration/smtpauthenticate", 0), 0)
        username = vbs_cstr(f._map.get("http://schemas.microsoft.com/cdo/configuration/sendusername", "")).strip()
        password = vbs_cstr(f._map.get("http://schemas.microsoft.com/cdo/configuration/sendpassword", ""))
        use_ssl = bool(f._map.get("http://schemas.microsoft.com/cdo/configuration/smtpusessl", False))

        msg = EmailMessage()
        msg["Date"] = formatdate(localtime=True)
        if vbs_cstr(self.Subject):
            msg["Subject"] = vbs_cstr(self.Subject)
        if vbs_cstr(self.From):
            msg["From"] = vbs_cstr(self.From)
        if vbs_cstr(self.ReplyTo):
            msg["Reply-To"] = vbs_cstr(self.ReplyTo)
        to_list = _split_addr_list(self.To)
        cc_list = _split_addr_list(self.Cc)
        bcc_list = _split_addr_list(self.Bcc)
        if to_list:
            msg["To"] = ", ".join(to_list)
        if cc_list:
            msg["Cc"] = ", ".join(cc_list)

        # Body
        html = vbs_cstr(self.HtmlBody)
        text = vbs_cstr(self.TextBody)
        if html:
            # Provide a plain fallback if not explicitly set.
            if not text:
                text = "(HTML message)"
            msg.set_content(text)
            msg.add_alternative(html, subtype="html")
        else:
            msg.set_content(text)

        # Attachments
        for p in list(self._attachments):
            if not os.path.isfile(p):
                raise Exception("CDO.Message: attachment not found")
            with open(p, "rb") as fobj:
                data = fobj.read()
            fname = os.path.basename(p)
            msg.add_attachment(data, maintype="application", subtype="octet-stream", filename=fname)

        # Delivery
        if sendusing == 1:
            # Pickup directory
            if not pickupdir:
                raise Exception("CDO.Message: pickup directory not set")
            outdir = os.path.abspath(pickupdir)
            if self._docroot and not _env_bool("ASP_PY_CDO_ALLOW_OUTSIDE_DOCROOT", False):
                if os.path.commonpath([self._docroot, outdir]) != self._docroot:
                    raise Exception("CDO.Message: pickup directory outside docroot")
            os.makedirs(outdir, exist_ok=True)
            name = f"cdo_{int(time.time())}_{uuid.uuid4().hex}.eml"
            outpath = os.path.join(outdir, name)
            with open(outpath, "wb") as fobj:
                fobj.write(msg.as_bytes())
            return True

        # SMTP
        if not smtpserver:
            raise Exception("CDO.Message: smtpserver not set")
        recipients = to_list + cc_list + bcc_list
        if not recipients:
            raise Exception("CDO.Message: no recipients")

        # CDO's smtpusessl usually implies TLS. We support both SMTPS (465) and STARTTLS.
        if use_ssl and smtpport == 465:
            smtp: smtplib.SMTP = smtplib.SMTP_SSL(smtpserver, smtpport, timeout=timeout)
        else:
            smtp = smtplib.SMTP(smtpserver, smtpport, timeout=timeout)
        try:
            smtp.ehlo()
            if use_ssl and smtpport != 465:
                smtp.starttls()
                smtp.ehlo()
            if smtpauth == 1 and username:
                smtp.login(username, password)
            smtp.send_message(msg, to_addrs=recipients)
        finally:
            try:
                smtp.quit()
            except Exception:
                pass
        return True
