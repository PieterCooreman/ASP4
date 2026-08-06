# ASPPY — Classic ASP/VBScript Runtime for Python

**Run your legacy Classic ASP pages on modern Python infrastructure - no IIS required.**

ASPPY is a Python-based runtime that executes Classic ASP (VBScript) pages on Windows, Linux, and macOS. It implements the full Classic ASP object model (`Request`, `Response`, `Session`, `Application`, `Server`) alongside broad VBScript built-in coverage, so most legacy ASP applications just work.

---

## Why ASPPY?

Classic ASP applications represent decades of business logic. Rewriting them is expensive and risky. ASPPY lets you **keep your existing `.asp` files** and serve them through a lightweight Python HTTP server — no COM, no Windows dependency, no IIS license. Linux typically runs Python 10–30% faster than Windows, increasing the performance advantage of modern frameworks like ASPPY over Classic ASP/VBScript on IIS.

---

## Requirements

### Prerequisites

**Python 3.8 or higher must be installed on your server** (Windows, Linux, or macOS).  
Download Python at [https://www.python.org/downloads/](https://www.python.org/downloads/).

> ASPPY is a Python application — Python is required on any machine that runs it, including your production hosting server.

### Python packages

Install the required packages with pip:

```bash
pip install fpdf2 bcrypt pillow pyodbc
```

> Not all packages are needed for every use case — install only what your application uses.

---

## Quick Start

Once Python and the packages above are in place, click `start_www.bat`, or open a new Powershell/CMD terminal:

```bash
python -m ASPPY.server 0.0.0.0 8080 www
```

Point your browser at `http://localhost:8080` and your `.asp` pages are live.

---

## The ASPPY Ecosystem

- https://pietercooreman.github.io/ASPPY/ (ASPPY Docs)
- [MVC Prompt Builder](https://pietercooreman.github.io/ASPPY/prompt-builder.html) - ASPPY prompt builder when using vibe coding tools
- [SPA (React + ASPPY) Prompt Builder](https://pietercooreman.github.io/ASPPY/prompt-builder-spa.html) - ASPPY prompt builder when using vibe coding tools
- https://github.com/PieterCooreman/ASP-VBScript-sample-code (advanced sample ASP/VBScript code to refer coding agents to)
- https://pietercooreman.github.io/ASPPY/ASPPY_The_Vibe_Coders_Guide.html (ebook for both vibe coding tools and developers)
- https://learnasppy.quickersite.com/ (learn ASPPY coding - very basic site for beginning developers)
- https://pietercooreman.github.io/ASP-Runner/ (run ASP/VBScript code in the browser (WebAssembly) - powered by ASPPY)

---

## The Perfect Prompt ?

Refer AI vibe-coding agents (like OpenCode, Claude Code, Codex agents, Cursor, GitHub Copilot) to the developers.md file, which provides important context and guidelines before starting any development in ASPPY. This reduces development time and cost by 30–40% and significantly improves code quality, even when using free AI coding agents.

The prompt builder comes in two flavours:

- [MVC Prompt Builder](https://pietercooreman.github.io/ASPPY/prompt-builder.html) - ASPPY prompt builder when using vibe coding tools
- [SPA (React + ASPPY) Prompt Builder](https://pietercooreman.github.io/ASPPY/prompt-builder-spa.html) - ASPPY prompt builder when using vibe coding tools

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
