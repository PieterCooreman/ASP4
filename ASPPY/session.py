"""Classic ASP Session object emulation (minimal, in-memory)."""

from __future__ import annotations

import time
import threading
import secrets


class SessionContents:
    def __init__(self, backing: dict):
        self._d = backing

    def _norm(self, key):
        return str(key).lower()

    @property
    def Count(self):
        return len(self._d)

    def Remove(self, key):
        k = self._norm(key)
        if k in self._d:
            del self._d[k]

    def RemoveAll(self):
        self._d.clear()

    def Item(self, key):
        # A MISSING key reads as Empty; a key explicitly set to Null reads back
        # as Null, exactly as on IIS. (This used to flatten Null to Empty, so
        # `Session("x") = Null` then `IsNull(Session("x"))` was False here and
        # True on IIS.)
        from .vm.values import VBEmpty
        v = self._d.get(self._norm(key), VBEmpty)
        if v is None:
            return VBEmpty
        return v

    def __vbs_index_get__(self, key):
        return self.Item(key)

    def __vbs_index_set__(self, key, value):
        from .vm.values import VBEmpty
        v = VBEmpty if value is None else value
        self._d[self._norm(key)] = v

    def __iter__(self):
        return iter(self._d)


class Session:
    def __init__(self, cookie_id: str, session_id: int, backing: dict, timeout_minutes: int = 20):
        # cookie_id is the value stored in the ASP_PY_SESSIONID cookie (our session key).
        # session_id mimics Classic ASP's Session.SessionID (numeric).
        self._cookie_id = str(cookie_id)
        self._id = int(session_id)
        self._backing = backing
        self._timeout = int(timeout_minutes)
        self._abandoned = False
        self._last_access = time.time()
        self.Contents = SessionContents(self._backing)
        self._static_objects = {}
        from ASPPY.application import StaticObjectsCollection
        self.StaticObjects = StaticObjectsCollection(self._static_objects)
        self._lcid = 0
        # ASPPY renders as UTF-8, so 65001 is the default code page.
        self._code_page = 65001

    @property
    def SessionID(self):
        return str(self._id)

    @property
    def CookieID(self):
        return self._cookie_id

    @property
    def Timeout(self):
        return self._timeout

    @Timeout.setter
    def Timeout(self, value):
        self._timeout = int(value)

    def Abandon(self):
        # IIS: Abandon only MARKS the session for destruction; its values
        # remain readable for the remainder of the current request. The
        # session store drops abandoned sessions before serving the next
        # request (see SessionStore.get_or_create).
        self._abandoned = True

    def _set_static_object(self, obj_id: str, obj):
        self._static_objects[str(obj_id)] = obj

    @property
    def CodePage(self):
        return self._code_page

    @CodePage.setter
    def CodePage(self, value):
        # Store the value so a page can read back what it set (IIS does).
        # ASPPY still emits UTF-8 regardless: the code page is not used to
        # re-encode output, it is remembered for compatibility only.
        try:
            self._code_page = int(value)
        except Exception:
            pass

    @property
    def LCID(self):
        return self._lcid

    @LCID.setter
    def LCID(self, value):
        # Setting Session.LCID takes effect immediately for the current request
        # and is re-applied at the start of every later request in this session
        # (see runner_vm), matching how IIS seeds the script engine locale.
        try:
            self._lcid = int(value)
        except Exception:
            return
        try:
            from .vb_runtime import vbs_set_lcid
            vbs_set_lcid(self._lcid)
        except Exception:
            pass

    def __vbs_index_get__(self, key):
        return self.Contents.__vbs_index_get__(key)

    def __vbs_index_set__(self, key, value):
        return self.Contents.__vbs_index_set__(key, value)

    def _touch(self):
        self._last_access = time.time()

    def _is_expired(self):
        return (time.time() - self._last_access) > (self._timeout * 60)

    def __iter__(self):
        return iter(self.Contents)


class SessionStore:
    def __init__(self):
        # cookie_id -> Session
        self._sessions = {}
        self._lock = threading.RLock()
        # Numeric SessionID should be hard to guess (aspLite uses it as a
        # same-session token). Keep within signed 32-bit range.

    def _alloc_session_id(self) -> int:
        # Best-effort uniqueness among currently alive sessions.
        existing = {getattr(s, 'SessionID', None) for s in self._sessions.values()}
        for _ in range(50):
            sid = 1 + secrets.randbelow(2_000_000_000)
            if sid not in existing:
                return sid
        # Extremely unlikely fallback: allow a collision if we somehow can't find a free one.
        return 1 + secrets.randbelow(2_000_000_000)

    def get_or_create(self, session_id: str, new_id_fn):
        with self._lock:
            # purge expired sessions (simple)
            to_del = []
            for sid, sess in list(self._sessions.items()):
                if sess._is_expired() or sess._abandoned:
                    to_del.append(sid)
            for sid in to_del:
                self._sessions.pop(sid, None)

            if session_id and session_id in self._sessions:
                sess = self._sessions[session_id]
                sess._touch()
                return sess, False

            cookie_id = new_id_fn()
            numeric_sid = self._alloc_session_id()
            backing = {}
            sess = Session(cookie_id, numeric_sid, backing)
            self._sessions[str(cookie_id)] = sess
            return sess, True
