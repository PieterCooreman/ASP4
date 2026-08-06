# Classic ASP / VBScript — Working Samples for Humans and Coding Agents

A living catalog of **correct, idiomatic, runnable Classic ASP / VBScript** code,
written to keep VBScript skills alive in the age of AI-assisted ("vibe") coding.
Every page compiles and runs on IIS, renders its own explanation in the browser,
and is heavily commented in the source so it reads as a teaching example.

## Why this repo exists

Microsoft is removing VBScript from Windows, Classic ASP is no longer taught, and
the public corpus of *good* VBScript shrinks every year. As a result, large
language models and coding agents tend to produce VBScript that is subtly — or
badly — wrong: `+` used for string concatenation, `If x = Null` that never fires,
banker's rounding mistaken for arithmetic rounding, `On Error Resume Next` left on
across a whole page, `Let` where `Set` is required, invented inheritance syntax,
and more.

This repository is a deliberate countermeasure. It is a set of **standalone ASP
pages whose primary audience is LLMs and coding agents** (and the humans keeping
legacy ASP alive), so that:

- agents asked to "build a Classic ASP feature" have correct patterns to imitate,
- the examples can be fed into prompts, retrieval pipelines, or fine-tuning
  datasets as ground-truth reference code, and
- the VBScript rules that are easiest to get wrong are made explicit and runnable.

Each page focuses on a coherent topic, is explicit about the edge cases, and
prints its own results so you can see the language actually behave.

## What's inside

Start at **`index.asp`** — the home page lists every sample as a navigable card
and prints the live server environment.

### Core language samples (`01`–`16`)

| File | Topic | Key VBScript lessons |
|------|-------|----------------------|
| **01-basics.asp** | Language basics | Variants and subtypes, operators, constants, `TypeName`/`VarType`. |
| **02-control-flow.asp** | Control flow | `If/ElseIf/Else`, `Select Case`, `For`, `For Each`, `Do While/Until`. |
| **03-procedures.asp** | Subs & functions | Declaring `Sub`/`Function`, `ByVal`/`ByRef`, recursion. |
| **04-classes.asp** | Classes (OOP) | Private fields, `Property Get/Let/Set`, methods, `Me`, lifecycle. |
| **05-arrays-dict.asp** | Arrays & Dictionary | Static/dynamic arrays, `ReDim Preserve`, `Scripting.Dictionary`. |
| **06-strings.asp** | String functions | `Len`/`Mid`/`InStr`/`Replace`/`Split`/`Join` and small algorithms. |
| **07-request-form.asp** | Request & forms | `QueryString`, `Form` posts, server variables, round-trip form. |
| **08-state.asp** | Session & Application | Per-user `Session` and shared `Application` state, hit counter. |
| **09-filesystem.asp** | FileSystemObject | Create, write, read and enumerate files/folders with the FSO. |
| **10-errors.asp** | Error handling | `On Error Resume Next`, the `Err` object, `Err.Raise`, guarded calls. |
| **11-dates-time.asp** | Dates & time | A `Date` is a `Double`; `DateSerial`/`DateAdd`/`DateDiff`; the month-clamp and boundary-crossing traps; `#literal#` vs `CDate` locale trap; leap years. |
| **12-conversion-edge.asp** | Coercion edge cases | `+` vs `&`; `Empty`/`Null`/`""`/`0` truth table; why `If x = Null` never fires; `True` is `-1`; no short-circuit; `=` vs `Is`; banker's rounding; `Int` vs `Fix`. |
| **13-regexp.asp** | Regular expressions | `VBScript.RegExp`: `.Test`/`.Execute`/`.Replace`, capture groups & `SubMatches`, `$1` backreferences, the `.Global` default-False trap, dialect gotchas. |
| **14-metaprogramming.asp** | Recursion, Eval & GetRef | Recursion with `Dictionary` memoisation; `Eval` vs `Execute` vs `ExecuteGlobal`; `GetRef` function pointers powering `Map`/`Reduce` and a dispatch table. |
| **15-collections-advanced.asp** | Collections (advanced) | Multidimensional vs jagged arrays; the `ReDim Preserve` last-dimension rule; the `UBound = -1` empty-array trap; `Filter`; a Dictionary auto-add gotcha; a hand-written sort. |
| **16-session-objects.asp** | Objects in Session | Storing a `Scripting.Dictionary` object reference in `Session` state; the `Set Session("x") = obj` pattern; guarding every read with `IsObject()` so a broken engine reports FAIL instead of crashing with "Object required"; the `Application` apartment-threading trap (ASP 0197 on IIS). |

### Advanced classes gallery (`classes/`)

A dedicated deep-dive into real-world Classic ASP/VBScript **class design** —
encapsulation, dependency injection, object composition, default and parameterised
members, method chaining, polymorphism without inheritance, and correct error
handling. Open `classes/default.asp` for the gallery and see
[`classes/README.md`](classes/README.md) for the full breakdown.

### Shared library (`includes/`)

| File | Purpose |
|------|---------|
| **includes/header.asp** | Common page `<head>`, styling and breadcrumb nav. |
| **includes/footer.asp** | Common page footer with live server info. |
| **includes/helpers.asp** | Reusable `Sub`/`Function` helpers (`HtmlEncode`, `WriteLine`, `Coalesce`, `IIf`, `DemoStart`/`DemoEnd`, `CodeBlock`, …) and a `StringBuilder` class. |

## How it works

Each sample is a complete, self-contained `.asp` page that:

1. sets the UTF-8 code page and `Option Explicit`,
2. includes the shared helper library and the common header/footer,
3. defines the relevant procedures/classes at the top (heavily commented), then
4. runs them inside labelled demo panels that print the results to the page.

Because every page renders its own output and explanation, you can read the source
*and* see exactly how VBScript behaves on this server — including locale-specific
results (this catalog has been verified on a non-US locale, which is itself a
useful edge case for the date and `IsNumeric` examples).

## Running the samples

These are standard Classic ASP pages. Serve this folder with any engine that runs
`.asp`:

- **IIS** with Classic ASP enabled — point a site at this folder and browse
  `index.asp` (or `default.asp` under `classes/`).
- **ASPPY** — the Python-based Classic ASP/VBScript engine at
  [PieterCooreman/ASPPY](https://github.com/PieterCooreman/ASPPY). Point it at
  this folder and browse `index.asp`.

Then open `http://localhost/` and start at `index.asp`.

> **Tested on both engines.** Every page in this catalog has been verified to run
> on Microsoft IIS (Classic ASP) **and** on
> [ASPPY](https://github.com/PieterCooreman/ASPPY), so the samples are portable
> reference code rather than IIS-only snippets.

## Using these as agent reference material

When prompting an LLM or coding agent to write Classic ASP/VBScript, point it at
the relevant sample(s) above and ask it to follow the same conventions. The
examples are intentionally opinionated about what agents most often get wrong:

- use **`&` for string concatenation**, never `+`;
- test for "no value" with **`IsNull` / `IsEmpty` / `Is Nothing`**, never `= Null`;
- remember there is **no short-circuit** in `And`/`Or`, so guard with nested `If`s;
- use **`Set` for objects, `Let` for scalars**;
- prefer **classes and `Scripting.Dictionary`** over parallel arrays;
- never leave **`On Error Resume Next`** on across a page;
- never `Eval`/`Execute` anything from `Request.*` (code injection);
- and remember `Round` uses **banker's rounding** and `ReDim Preserve` may only
  resize an array's **last** dimension.

Contributions of further correct, single-concept examples are welcome — the goal
is to grow a trustworthy corpus that keeps Classic ASP/VBScript alive for the
agents now writing it.
