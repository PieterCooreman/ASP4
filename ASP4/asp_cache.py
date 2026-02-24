"""ASP page caching mechanism (ASTs and Include Trees)."""

import os
import threading

_cache_lock = threading.RLock()
_cache = {}            # path -> (mtime_ns, nodes)
_monolithic_cache = {} # path -> (deps_map: dict[path, mtime_ns], nodes)


def get_cached_asp_nodes(path, parse_fn):
    """Get parsed nodes for an ASP file, using cache if available.

    parse_fn: function(path) -> nodes

    Uses st_mtime_ns (integer nanoseconds) instead of st_mtime (float seconds)
    to avoid floating-point precision issues on Linux filesystems.
    """
    try:
        mtime_ns = os.stat(path).st_mtime_ns
    except OSError:
        return None

    with _cache_lock:
        entry = _cache.get(path)

    if entry is not None:
        cached_mtime_ns, nodes = entry
        if cached_mtime_ns == mtime_ns:
            return nodes

    # Cache miss or stale — recompile outside the lock
    nodes = parse_fn(path)

    with _cache_lock:
        _cache[path] = (mtime_ns, nodes)

    return nodes


def get_cached_monolithic_nodes(path, parse_fn):
    """Get nodes for a monolithic compilation, checking ALL dependencies.

    parse_fn: function(path) -> (nodes, deps_set)

    Uses st_mtime_ns (integer nanoseconds) instead of st_mtime (float seconds)
    to avoid floating-point precision issues on Linux filesystems.
    """
    # Read snapshot outside the lock
    with _cache_lock:
        entry = _monolithic_cache.get(path)

    # Validate outside the lock (no need to hold it during stat calls)
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
            pass  # Should not happen if parsing succeeded

    with _cache_lock:
        _monolithic_cache[path] = (new_deps_map, nodes)

    return nodes


def clear_cache():
    with _cache_lock:
        _cache.clear()
        _monolithic_cache.clear()
