"""Classic ASP Application object emulation (global/shared)."""

from __future__ import annotations

import threading
from typing import Any


class ApplicationContents:
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
        return iter(self._d.keys())


class StaticObjectsCollection:
    def __init__(self, backing: dict):
        self._d = backing

    @property
    def Count(self):
        return len(self._d)

    def __iter__(self):
        return iter(self._d.keys())

    def __vbs_index_get__(self, key):
        return self._d.get(str(key), "")


class Application:
    def __init__(self, backing: dict, lock: threading.RLock):
        self._backing = backing
        self._lock = lock
        self._lock_owner = None
        self.Contents = ApplicationContents(self._backing)
        self._static_objects = {}
        self.StaticObjects = StaticObjectsCollection(self._static_objects)

    def Lock(self):
        self._lock.acquire()
        self._lock_owner = threading.get_ident()

    def Unlock(self):
        # Best-effort: only unlock if current thread owns the lock.
        if self._lock_owner == threading.get_ident():
            self._lock_owner = None
            try:
                self._lock.release()
            except RuntimeError:
                pass

    def __vbs_index_get__(self, key):
        return self.Contents.__vbs_index_get__(key)

    def __vbs_index_set__(self, key, value):
        return self.Contents.__vbs_index_set__(key, value)

    def _set_static_object(self, obj_id: str, obj):
        self._static_objects[str(obj_id)] = obj


class ApplicationStore:
    def __init__(self):
        self._lock = threading.RLock()
        self._backing = {}
        self.app = Application(self._backing, self._lock)
        self._started = False
        self._global_asa_cache: Any = None  # populated by server (GlobalAsaCompiled)

    def ensure_started(self, docroot: str, run_start_fn):
        if self._started:
            return
        with self._lock:
            if self._started:
                return
            run_start_fn(docroot)
            self._started = True

    def run_on_end(self, docroot: str, run_end_fn):
        # Run once
        if not self._started:
            return
        with self._lock:
            if not self._started:
                return
            run_end_fn(docroot)
            self._started = False
