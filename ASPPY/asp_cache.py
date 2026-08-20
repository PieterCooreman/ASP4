"""ASP page caching mechanism (ASTs and Include Trees).

Uses LRU eviction and configurable cache size via ASP_PY_CACHE_SIZE env var.
"""

import os
import threading
from collections import OrderedDict

_cache_lock = threading.RLock()

# Configurable via environment variable (default 1000)
_MAX_CACHE_SIZE = int(os.environ.get('ASP_PY_CACHE_SIZE', '1000'))

# LRU caches using OrderedDict (most-recently-used at end)
_cache: OrderedDict = OrderedDict()           # path -> (mtime_ns, nodes)
_monolithic_cache: OrderedDict = OrderedDict() # path -> (deps_map, nodes)


def _lru_get(cache: OrderedDict, key):
    """Get from LRU cache, moving entry to end (most recent) on hit."""
    val = cache.get(key)
    if val is not None:
        cache.move_to_end(key)
    return val


def _lru_put(cache: OrderedDict, key, value):
    """Put into LRU cache, evicting least-recently-used if over limit."""
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > _MAX_CACHE_SIZE:
        cache.popitem(last=False)  # Remove oldest (least recently used)


def get_cached_asp_nodes(path, parse_fn):
    """Get parsed nodes for an ASP file, using LRU cache if available.

    parse_fn: function(path) -> nodes

    Uses st_mtime_ns (integer nanoseconds) instead of st_mtime (float seconds)
    to avoid floating-point precision issues on Linux filesystems.
    """
    try:
        mtime_ns = os.stat(path).st_mtime_ns
    except OSError:
        return None

    with _cache_lock:
        entry = _lru_get(_cache, path)
        if entry is not None:
            cached_mtime_ns, nodes = entry
            if cached_mtime_ns == mtime_ns:
                return nodes

    # Cache miss or stale — recompile outside the lock
    nodes = parse_fn(path)

    with _cache_lock:
        _lru_put(_cache, path, (mtime_ns, nodes))

    return nodes


def get_cached_monolithic_nodes(path, parse_fn):
    """Get nodes for a monolithic compilation, checking ALL dependencies.

    parse_fn: function(path) -> (nodes, deps_set)
    """
    with _cache_lock:
        entry = _lru_get(_monolithic_cache, path)

    # Validate outside the lock (stat calls can be slow)
    if entry is not None:
        deps_map, nodes = entry
        valid = True
        for dep_path, dep_mtime_ns in deps_map.items():
            try:
                if os.stat(dep_path).st_mtime_ns != dep_mtime_ns:
                    valid = False
                    break
            except OSError:
                valid = False
                break
        if valid:
            return nodes

    # Cache miss or stale — recompile outside the lock
    nodes, deps = parse_fn(path)

    new_deps_map = {}
    for d in deps:
        try:
            new_deps_map[d] = os.stat(d).st_mtime_ns
        except OSError:
            pass

    with _cache_lock:
        _lru_put(_monolithic_cache, path, (new_deps_map, nodes))

    return nodes


def clear_cache():
    with _cache_lock:
        _cache.clear()
        _monolithic_cache.clear()
