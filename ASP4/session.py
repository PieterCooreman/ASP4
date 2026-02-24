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
        from .vm.values import VBEmpty
        v = self._d.get(self._norm(key), VBEmpty)
        try:
            from .vm.values import VBNull, VBNothing
            if v is None or v in (VBEmpty, VBNull, VBNothing):
                return VBEmpty
        except Exception:
            if v is None:
                return VBEmpty
        return v

    def __vbs_index_get__(self, key):
        return self.Item(key)

    def __vbs_index_set__(self, key, value):
        v = value
        try:
            from .vm.values import VBEmpty, VBNull, VBNothing
        except Exception:
            VBEmpty = None
            VBNull = None
            VBNothing = None
        if v is None or v in (VBEmpty, VBNothing):
            v = VBEmpty
        elif v is VBNull:
            v = VBNull
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
        from ASP4.application import StaticObjectsCollection
        self.StaticObjects = StaticObjectsCollection(self._static_objects)
        self.LCID_ = 0

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
        self._abandoned = True
        self._backing.clear()

    def _set_static_object(self, obj_id: str, obj):
        self._static_objects[str(obj_id)] = obj

    @property
    def CodePage(self):
        return 65001

    @CodePage.setter
    def CodePage(self, value):
        # No-op (cross-platform)
        pass

    @property
    def LCID(self):
        return self.LCID_

    @LCID.setter
    def LCID(self, value):
        # Stores the value but does not enforce it, as requested for legacy compatibility.
        try:
            self.LCID_ = int(value)
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
