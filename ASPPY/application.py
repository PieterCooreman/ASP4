"""Classic ASP Application object emulation (global/shared)."""
from __future__ import annotations
import threading
from typing import Any


class _CaseInsensitiveDict:
    """Dict that looks up keys case-insensitively but preserves original casing."""

    def __init__(self):
        # lower_key -> (original_key, value)
        self._store: dict[str, tuple[str, Any]] = {}

    def __len__(self):
        return len(self._store)

    def __contains__(self, key):
        return str(key).lower() in self._store

    def __setitem__(self, key, value):
        k = str(key)
        self._store[k.lower()] = (k, value)

    def __getitem__(self, key):
        return self._store[str(key).lower()][1]

    def get(self, key, default=None):
        entry = self._store.get(str(key).lower())
        return entry[1] if entry is not None else default

    def __delitem__(self, key):
        del self._store[str(key).lower()]

    def clear(self):
        self._store.clear()

    def keys(self):
        return [original for original, _ in self._store.values()]

    def __iter__(self):
        return iter(self.keys())


class ApplicationContents:
    def __init__(self, backing: _CaseInsensitiveDict):
        self._d = backing

    @property
    def Count(self):
        return len(self._d)

    def Remove(self, key):
        if key in self._d:
            del self._d[key]

    def RemoveAll(self):
        self._d.clear()

    def Item(self, key):
        # Missing key -> Empty; a stored Null reads back as Null, like IIS.
        from .vm.values import VBEmpty
        v = self._d.get(key, VBEmpty)
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
        self._d[key] = v  # original casing preserved by _CaseInsensitiveDict

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
    def __init__(self, backing: _CaseInsensitiveDict, lock: threading.RLock):
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
        self._backing = _CaseInsensitiveDict()  # was plain dict
        self.app = Application(self._backing, self._lock)
        self._started = False
        self._global_asa_cache: Any = None

    def ensure_started(self, docroot: str, run_start_fn):
        if self._started:
            return
        with self._lock:
            if self._started:
                return
            run_start_fn(docroot)
            self._started = True

    def run_on_end(self, docroot: str, run_end_fn):
        if not self._started:
            return
        with self._lock:
            if not self._started:
                return
            run_end_fn(docroot)
            self._started = False