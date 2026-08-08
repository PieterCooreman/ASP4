# ASPPY App Rules

Read this before building any new app in `www`.

Start every new app from `www_starter`.

- Do not begin from a blank `www` folder when creating a new app
- Copy the starter into `www`, then build from that structure
- The rules below still apply to the final app in `www`

## Hard Rules

- Build inside `www`
- Do not modify `ASPPY\*.py`
- Do not modify `www_starter\*.*`
- Use ASPPY only
- Do not add IIS requirements
- Run the dev server on port `8080`
- No server restart needed after editing `.asp` files (including includes): ASPPY detects file changes automatically (mtime check) and recompiles on the next request

```bash
python -m ASPPY.server 0.0.0.0 8080 www
```

## CLI Runner: Test ASP Pages Without the Server (IMPORTANT FOR AI AGENTS)

ASPPY ships a command-line runner, `asppycli.py` (repo root), that renders a
single `.asp` file directly to stdout **without starting the HTTP server**.
It uses the exact same VM render pipeline as `ASPPY/server.py` (including
`global.asa`, Application/Session state, includes, and `Server.Execute`), so
the output matches the HTTP server byte-for-byte.

**If you are an AI model or automation script working on an ASPPY app, use
this tool to verify every page you create or edit.** It is much faster than
starting the server and fetching a URL, and the process exit code tells you
immediately whether the page rendered cleanly.

```bash
# Render a demo/test page to stdout (sample pages live in www_test)
python asppycli.py www_test/index.asp

# Save output to a file (for diffing against a known-good baseline)
python asppycli.py www_test/01-basics.asp -o out.html

# Simulate a form POST
python asppycli.py www_test/07-request-form.asp --method POST --body "username=Ann&color=blue"

# Pass a query string (page from your own app in www)
python asppycli.py www/report.asp --query "id=42&mode=edit"

# Test an MVC front-controller route (Request.Path sees /contacts/1/edit)
python asppycli.py www/default.asp --docroot www --path /contacts/1/edit

# Show the HTTP status line and response headers (printed to stderr)
python asppycli.py www_test/index.asp --show-headers
```

Exit codes (use these in scripts and CI):

| Exit code | Meaning |
|-----------|---------|
| `0` | page rendered with HTTP status < 400 |
| `1` | page rendered with HTTP status >= 400 (e.g. `500` ASP runtime error, `404` route) |
| `2` | usage error / `.asp` file not found |

### Batch check a whole folder: asppycheck.py

To check every `.asp` page in a folder recursively with one command, use
`asppycheck.py` (repo root). It renders each page through the same pipeline
and prints a summary plus the file, line and error description for every
failing page:

```bash
# Check all sample/test pages
python asppycheck.py www_test

# Check your own app
python asppycheck.py www

# Also list passing pages / stop at first failure
python asppycheck.py www --verbose
python asppycheck.py www --fail-fast
```

Example failure output:

```text
FAIL  zz-broken.asp  [500] Variable is undefined: 'MISSINGVAR' (/zz-broken.asp, line 2)

checked 28 page(s): 27 ok, 0 warning(s), 1 failure(s)
```

- Exit code `0` = all pages ok, `1` = at least one failure (5xx or engine
  exception), `2` = folder not found
- Pages returning `4xx` are reported as warnings only (routers legitimately
  return `404` for unknown routes)
- Directories named `includes` and directories starting with `_` are skipped
  by default (include fragments cannot render standalone); use
  `--exclude DIR` to skip more, or `--no-default-excludes` to scan everything
- For MVC apps, exclude the fragment folder: `python asppycheck.py www
  --exclude asp` - controllers, models and views in `www/asp/` are include
  fragments, not standalone pages. The front controller will WARN with `404`
  (no route given); verify real routes with
  `python asppycli.py www/default.asp --docroot www --path /contacts/1`
- **AI agents: run `python asppycheck.py www` after any multi-file change**
  to catch regressions across the whole app in one command

Notes:

- `--docroot` defaults to the directory containing the `.asp` file; pass it
  explicitly for MVC apps so includes and `Server.MapPath()` resolve the same
  way as under the HTTP server (e.g. `--docroot www`)
- A runtime error renders the same IIS-style error page the server would
  return, with file, line number and source caret - read it from stdout
- Each invocation is a fresh process: the ASP compilation cache is empty, so
  there is no need to restart anything after editing includes
- Verification loop for agents: edit the `.asp` file, run
  `python asppycli.py <file> --docroot www`, check exit code is `0`, and
  inspect stdout for the expected HTML

Credit: the CLI runner was contributed by
[Jeffrey (@jeffreyheping)](https://github.com/jeffreyheping) in
[issue #10](https://github.com/PieterCooreman/ASPPY/issues/10).

## Use One App Model Only

Pick one model and stay consistent.

### MVC app
- Use `www/default.asp` as the router
- Use `www/index.asp` to include `default.asp`
- Use `Request.Path` for routing
- Keep app pages in ASP/VBScript
- Keep server-side `Sub` and `Function` blocks inside ASP script tags; do not close `%>` before executable VBScript definitions

## MVC Structure Rules

For MVC apps, `www/default.asp` is only the front controller and router.

Required separation:

- `www/default.asp` may normalize routes, parse route params, choose a handler, and return `404`s
- Route handlers/controllers should live in `www/asp/`
- Database access should live in dedicated model/data files in `www/asp/`
- Page rendering should live in dedicated view/template files or included ASP view files
- Create `www/asp/views/` for every MVC app that renders pages
- Controllers should prepare data and choose a view; they should not contain full-page HTML built from long `Response.Write` sequences
- Do not build full pages with large `Response.Write` blocks inside `www/default.asp`
- Do not put page-specific SQL statements directly in `www/default.asp`
- Do not create tables, run migrations, or perform other app initialization in `www/default.asp` on every request
- `default.asp` should dispatch; controllers should coordinate; models should read/write data; views should render output

Rendering ownership:

- Pick one layout ownership model and keep it consistent
- Either `default.asp` owns `RenderHeader()` and `RenderFooter()`, or each controller action owns them
- Do not call `RenderFooter()` in both `default.asp` and the controller for the same request

Bad MVC example:
- one `default.asp` file that routes requests, runs SQL, handles `POST` bodies, and prints all HTML

Good MVC example:
- `default.asp` routes `/contacts/1/edit` to a contacts controller
- `asp/controllers/contacts.asp` handles request logic
- `asp/models/contacts.asp` reads and writes the database
- `asp/views/contact_edit.asp` renders the form

Minimal pattern:

```text
www/
  default.asp
  index.asp
  asp/
    controllers/
      contacts.asp
    models/
      contacts.asp
    views/
      contacts_list.asp
      contact_edit.asp
```

```asp
' default.asp
If RouteIs("/contacts") Then
    Call ContactsIndex()
End If
```

```asp
' asp/controllers/contacts.asp
Sub ContactsIndex()
    contacts = ContactAll()
    <!--#include file="../views/contacts_list.asp"-->
End Sub
```

```asp
' asp/models/contacts.asp
<!--#include file="../db.asp"-->
```

### Static app
- Use plain `.html`, `.css`, `.js`
- Do not mix it with ASP MVC routing

Do not mix both models in one app.

Bad:
- public site in `index.html`
- posts saved by ASP
- public content loaded from JavaScript `localStorage`

That creates two different apps that do not share the same data.

## Mandatory MVC Rules

For every new ASPPY MVC app:

- `www/default.asp` is the front controller
- extensionless routes like `/posts/hello` must be handled by `www/default.asp`
- unknown routes must return `Response.Status = "404 Not Found"`
- missing `.asp` files must stay real `404`s
- do not bypass MVC by linking directly to internal `/asp/*.asp` files unless truly needed
- verify every include path from the perspective of the file that contains the include
- verify that layout rendering is owned by one place only

## Path Rules

There are 3 different path types. Do not mix them.

1. Route path  
   Example: `/posts/hello`

2. Include path  
   Example: `db.asp` or `../asp/db.asp`

3. `Server.MapPath()` path  
   Example: `data/app.db`

## Very Important `MapPath()` Rule

`Server.MapPath("...")` is relative to the ASP file that is executing.

That means the same path string can point to different folders in different files.

Example:
- in `www/default.asp`, `Server.MapPath("data/posts.txt")` points to `www/data/posts.txt`
- in `www/asp/save_post.asp`, `Server.MapPath("data/posts.txt")` points to `www/asp/data/posts.txt`

This is a common source of broken apps.

So:

- never guess where `Server.MapPath()` points
- never assume the same relative path means the same file everywhere
- use one consistent strategy for shared files

## Safe Path Rules

- Always use relative include paths
- Include paths are relative to the file that contains the include
- Always use `Server.MapPath("...")` for files and databases
- Never use a leading slash in `Server.MapPath`
- Never hardcode physical paths
- Never pass route URLs into `Server.MapPath()`

Common include examples by file location:

- from `www/default.asp` to `www/asp/helpers.asp`: `<!--#include file="asp/helpers.asp"-->`
- from `www/asp/controllers/contacts.asp` to `www/asp/models/contacts.asp`: `<!--#include file="../models/contacts.asp"-->`
- from `www/asp/models/contacts.asp` to `www/asp/db.asp`: `<!--#include file="../db.asp"-->`
- from `www/asp/views/contact_edit.asp` to `www/asp/layout.asp`: `<!--#include file="../layout.asp"-->`

Correct:
```asp
<!--#include file="asp/db.asp"-->
<!--#include file="../asp/db.asp"-->
<!--#include file="../db.asp"-->
dbPath = Server.MapPath("data/app.db")
```

Wrong:
```asp
<!--#include file="db.asp"-->
<!-- inside asp/models/*.asp when the real file is one folder up -->
<!--#include file="db.asp"-->
dbPath = Server.MapPath("/data/app.db")
dbPath = "C:\ASPPY\www\data\app.db"
dbPath = Server.MapPath("/posts")
```

## Files And Folders

Use this structure:

```text
www/
  default.asp
  index.asp
  asp/
  assets/
  data/
  uploads/
```

Rules:
- CSS, JS, and app-used images go in `www/assets`
- user uploads go in `www/uploads`
- shared ASP helpers go in `www/asp`
- shared data files go in `www/data`

## Do Not Make These Mistakes

- Do not redirect `index.asp` to `/`
- Do not create both `index.html` and MVC `default.asp` as competing homepages
- Do not mix ASP server-side storage with browser `localStorage` for the same feature
- Do not save data in one place and read it from another
- Do not use `IIf(...)` for nullable SQL values or request logic
- Do not write output before `Response.Redirect`
- Do not concatenate raw request IDs directly into SQL

## Development Rules

- Read browser error messages fully
- Fix current errors before moving on
- Handle `POST` logic before writing page output
- If a page redirects, redirect before writing output
- Validate numeric IDs with `IsNumeric()` and `CInt()`
- HTML-encode user output with `Server.HTMLEncode()`
- Avoid `On Error Resume Next` in routing or page setup; fix the first real error directly
- For dynamic routes, prefer splitting path segments over manual string-length math when extracting IDs or actions

Dynamic route example:

```asp
Dim routeParts, contactId, actionName
routeParts = Split(Trim(CurrentRoute(), "/"), "/")

' /contacts/12/edit -> contacts, 12, edit
If UBound(routeParts) = 2 Then
    contactId = routeParts(1)
    actionName = routeParts(2)
End If
```

## CRITICAL: Subscript Out Of Range in Route Arrays

VBScript `And` does **not** short-circuit. Every operand is evaluated regardless of the result of the first.

This means the following code **crashes** when the route has fewer segments than expected:

```asp
' BROKEN: parts(2) is evaluated even when UBound(parts) is 0
If UBound(parts) = 2 And parts(0) = "contacts" And IsNumeric(parts(1)) And parts(2) = "edit" Then
```

The error you will see is `Subscript out of range`, and it will point to a line that looks correct. The real cause is VBScript evaluating `parts(1)` or `parts(2)` on a shorter array because `And` checked all operands.

**Workaround: use nested `If` blocks so array indices are only accessed after the length is confirmed.**

```asp
Dim parts, partCount
parts = RouteParts()
partCount = UBound(parts)

' 2-segment route: /contacts/1
If partCount = 1 Then
    If parts(0) = "contacts" Then
        If IsNumeric(parts(1)) Then
            Call ContactsShow(parts(1))
        End If
    End If
End If

' 3-segment route: /contacts/1/edit
If partCount = 2 Then
    If parts(0) = "contacts" Then
        If IsNumeric(parts(1)) Then
            Select Case parts(2)
                Case "edit"
                    Call ContactsEdit(parts(1))
                Case "delete"
                    Call ContactsDelete(parts(1))
            End Select
        End If
    End If
End If
```

The outer `If partCount = N` guarantees `parts(0)` through `parts(N)` exist before any inner line touches them. Never combine segment count checks and segment value checks in a single `And` expression.

Initialization rule:

- Do not run schema creation or app setup in `www/default.asp`
- Put setup in a dedicated script, admin-only route, or clearly isolated bootstrap helper that is not triggered on every request
- If setup must run conditionally, make that condition explicit and limited

## Frontend Framework Rule

- The developer must explicitly choose one frontend framework before building UI
- Allowed choices: Bootstrap 5 (latest version) or Tailwind
- Do not leave styling undecided or mix both frameworks in one app
- If the user does not specify a framework, choose Bootstrap 5 and state that choice clearly while building

## Final Checklist

Before finishing, verify:

- the app uses one model only: MVC or static
- `www/default.asp` handles MVC routes
- `www/default.asp` only dispatches routes and does not contain page-specific SQL or large HTML rendering blocks
- `www/index.asp` does not create a redirect loop
- extensionless routes work through `Request.Path`
- dynamic routes are verified with real examples like `/contacts/1`, `/contacts/1/edit`, and `/contacts/1/delete`
- missing `.asp` files return real `404`
- includes use correct relative paths
- every include target exists relative to the including file
- layout rendering is owned by one place only
- shared files in `www/data` are read and written from the same real location
- assets are in `www/assets`
- uploads are in `www/uploads`
- pages load without ASPPY runtime errors
- every new or edited page was verified with the CLI runner: `python asppycli.py <file> --docroot www` exits `0`
- the whole app passes the batch checker: `python asppycheck.py www` exits `0`
