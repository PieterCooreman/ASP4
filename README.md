# ASPPY — Classic ASP/VBScript Runtime for Python

**Run your legacy Classic ASP pages on modern infrastructure — no IIS required.**

ASPPY is a Python-based runtime that executes Classic ASP (VBScript) pages on Windows, Linux, and macOS. It implements the full Classic ASP object model (`Request`, `Response`, `Session`, `Application`, `Server`) alongside broad VBScript built-in coverage, so most legacy ASP applications just work.

---

## Why ASPPY?

Classic ASP applications represent decades of business logic. Rewriting them is expensive and risky. ASPPY lets you **keep your existing `.asp` files** and serve them through a lightweight Python HTTP server — no COM, no Windows dependency, no IIS license. Linux typically runs Python 10–30% faster than Windows, increasing the performance advantage of modern frameworks like ASPPY over Classic ASP/VBScript on IIS.

---

## Quick Start

```bash
pip install fpdf2 bcrypt pillow pyodbc
python -m ASPPY.server 0.0.0.0 8080 www
```

Point your browser at `http://localhost:8080` and your `.asp` pages are live.

---

## What's Supported

| Area | Coverage |
|------|----------|
| VBScript built-ins (strings, dates, math, arrays) | Near-complete |
| `Request` / `Response` / `Session` / `Application` / `Server` | Near-complete |
| `Scripting.Dictionary` / `Scripting.FileSystemObject` | Supported |
| `ADODB.Connection` / `Recordset` / `Command` / `Stream` | Partial |
| Database backends | SQLite, Access, Excel (read-only), ODBC, PostgreSQL |
| `VBScript.RegExp` | Supported |
| MSXML HTTP & DOM | Partial (security-sandboxed) |
| `CDO.Message` (SMTP) | Partial |
| POP3 / IMAP | Partial |
| `Global.asa` events | Supported |

ASPPY also ships extended helpers beyond classic ASP — JSON encode/decode, ZIP, PDF generation, image processing, and bcrypt password hashing — all accessible from VBScript via the global `ASPPY` object.

---

## Requirements

- Python 3.8+
- `fpdf2`, `bcrypt`, `pillow`, `pyodbc` (install as needed for the features you use)

---

## Platform Support

Windows · Linux · macOS

---

## Compatibility Notes

ASPPY targets practical app-level compatibility, not byte-for-byte IIS parity. Locale-specific formatting, edge-case type coercion, and COM-level quirks may differ. SQL is executed as-is by the underlying driver — no dialect translation is performed.

If you're migrating a critical application, run your own regression tests against ASPPY alongside IIS before cutting over.

---

## License

See [LICENSE](LICENSE) for details.

---

## Legal Disclaimer

**Disclaimer of Affiliation**

ASPPY is an independent software project developed by Pieter Cooreman. 

ASPPY is not affiliated, associated, authorized, endorsed by, or in any way officially connected with Microsoft Corporation, or any of its subsidiaries or its affiliates. The official Microsoft website can be found at https://www.microsoft.com.

The names "Microsoft," "Active Server Pages," "ASP," and "VBScript," as well as related names, marks, emblems, and images, are registered trademarks of Microsoft Corporation. The use of these trademarks within this project is purely for descriptive, identification, and reference purposes to indicate technical compatibility, and does not imply any association with, or endorsement by, the trademark holder.
