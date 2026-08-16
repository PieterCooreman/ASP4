"""Target for 17-python-bridge.asp - echoes ASPPY_ARGS back as JSON.

Demonstrates the shape a real bridge file takes: a plain, importable module
with a `main(params)` entry point, run through
``ASPPY.ExecutePythonFile(path, params)``. Nothing here knows about VBScript.
"""

import json


def main(p):
    if p is None:
        return {"got": None, "type": "none"}
    return {
        "got": p,
        "type": type(p).__name__,
        # Proves the Dictionary/Array conversion really produced live Python
        # containers rather than a string that merely looks like JSON.
        "keys": sorted(p.keys()) if isinstance(p, dict) else None,
        "doubled": (p.get("n") * 2) if isinstance(p, dict) and isinstance(p.get("n"), int) else None,
    }


ASPPY_RETURN(json.dumps(main(ASPPY_ARGS), sort_keys=True))
