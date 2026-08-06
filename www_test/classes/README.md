# VBScript Classes — Reference Examples for Agentic Coding

A curated gallery of **correct, idiomatic Classic ASP / VBScript class examples**, written to keep VBScript skills alive in the age of AI-assisted ("vibe") coding.

## Why this repo exists

Microsoft is removing VBScript from Windows. Classic ASP is no longer taught, and the public corpus of *good* VBScript shrinks every year. As a result, large language models and coding agents tend to produce VBScript that is subtly — or badly — wrong: parallel arrays instead of objects, `Let` where `Set` is required, swallowed errors from a stray `On Error Resume Next`, string-concatenated SQL, invented inheritance syntax, and so on.

This folder is a deliberate countermeasure. It is a set of **standalone ASP pages whose primary audience is LLMs and coding agents**. Each page is a real, runnable example that demonstrates one core technique the right way, so that:

- agents asked to "build a Classic ASP feature" have correct patterns to imitate,
- the examples can be fed into prompts, retrieval pipelines, or fine-tuning datasets as ground-truth reference code, and
- humans keeping legacy ASP alive have a concise, modern style guide.

Every example is also a *teaching* example: heavily commented, focused on a single idea, and explicit about the VBScript rules that are easy to get wrong.

## How it works

Each sample is a complete, self-contained `.asp` page. Open `default.asp` for the gallery — it loads every sample in its own `<iframe>`, so each file runs exactly as a browser or an agent would request it. The page doubles as navigation (a card per sample) and as a live preview of the rendered output.

```
www/
├── default.asp        Gallery / index — runs every sample in an iframe
├── class-demo1.asp    Order Management System (the flagship example)
├── class-demo2.asp    Procedural vs. class-based — the "why classes" comparison
├── class-demo3.asp    Layered services & a shopping cart (dependency injection)
├── class-demo4.asp    Object composition (HAS-A) + Let vs. Set
├── class-demo5.asp    Advanced members: Default property, parameterised props, chaining
├── class-demo6.asp    Error handling done right (no Try/Catch in VBScript)
├── class-demo7.asp    Polymorphism without inheritance (duck typing & Strategy)
├── class-demo8.asp    Real request handling: DTO → validate → repository → state machine
└── class-demo9.asp    Builder & Factory patterns + safe parameterised SQL
```

## The examples

| File | Topic | Key VBScript lessons |
|------|-------|----------------------|
| **class-demo1.asp** | **Order Management System** — the flagship, six small classes cooperating to turn a catalogue + customer into a priced, VAT-inclusive invoice. | Encapsulation, validation at the boundary with `Err.Raise`, dependency injection. The example to imitate for non-trivial features. |
| **class-demo2.asp** | **Procedural vs. class-based** — solves the same problem (manage a song collection) twice. | *When* a class is worth it: spotting the "parallel arrays that must stay index-aligned" smell and replacing it with objects. |
| **class-demo3.asp** | **Layered services & shopping cart** — a small service-layer architecture wired by injection. | High-level code reads like English; collections built on `Scripting.Dictionary`; storing objects with `Set dict(key) = obj`. |
| **class-demo4.asp** | **Object composition (HAS-A)** — assembling rich models without inheritance. | The central `Property Let` (scalars) vs. `Property Set` (objects) rule. |
| **class-demo5.asp** | **Advanced class members** — `Default` properties, parameterised `Property Get/Let`, typed collections. | `obj(key)` syntax via a single `Default` member; correct method chaining by returning `Me` and re-assigning with `Set`. |
| **class-demo6.asp** | **Error handling done right** — VBScript has no `Try/Catch`. | Result objects, an error-accumulating Validator, and scoping `On Error Resume Next` to a single risky call instead of a whole page. |
| **class-demo7.asp** | **Polymorphism without inheritance** — VBScript has no `Extends`, no interfaces. | Duck typing across shapes sharing an implicit interface; the Strategy pattern with interchangeable algorithm objects. |
| **class-demo8.asp** | **Real request handling** — the pattern that matters most for ASP web apps. | A self-validating, XSS-safe DTO built from `Request`, a domain entity with a state machine, and a repository abstraction. |
| **class-demo9.asp** | **Builder & Factory patterns** + the single most important security pattern. | Factories that hide construction, fluent builders ending in `.Build()`, and **parameterised SQL instead of string concatenation**. |

## Running the samples

These are standard Classic ASP pages. Serve the `www` folder with any engine that runs `.asp`:

- **ASPPY** (the Python-based Classic ASP engine in this repository):

  ```
  python -m ASPPY.server 0.0.0.0 8080 www
  ```

  Then open `http://localhost:8080/`. On Windows you can also just run `start_www.bat` from the repo root.

- **IIS** with Classic ASP enabled — point a site at this folder and browse `default.asp`.

Either way, start at `default.asp` to see the whole gallery.

## Using these as agent reference material

When prompting an LLM or coding agent to write Classic ASP/VBScript, point it at the relevant sample(s) above and ask it to follow the same conventions. The examples are intentionally opinionated about the things agents most often get wrong:

- prefer **classes and `Scripting.Dictionary`** over parallel arrays,
- use **`Set` for objects, `Let` for scalars**,
- never leave **`On Error Resume Next`** on across a page,
- compose with **HAS-A**, since there is **no inheritance**,
- and always build **parameterised SQL**, never concatenated strings.

Contributions of further correct, single-concept examples are welcome — the goal is to grow a trustworthy corpus that keeps VBScript classes alive for the agents now writing them.
