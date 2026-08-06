<%@ Language="VBScript" CodePage="65001" %>
<%
Option Explicit
Response.CharSet = "UTF-8"
Response.ContentType = "text/html"
%>
<%
' ============================================================
'  VBSCRIPT CLASSES DEMO 9 — Builder & Factory patterns
'
'  Two creational patterns that make VBScript code dramatically
'  cleaner, plus the single most important SECURITY pattern in
'  Classic ASP: building parameterised SQL instead of string
'  concatenation.
'
'  Shown here:
'    1. FACTORY — a class whose job is to CREATE other objects
'       from raw data (e.g. a DB row / a config string), hiding
'       the construction details from callers.
'    2. FLUENT BUILDER — assemble a complex object/string step
'       by step with chained calls, ending in .Build().
'    3. SqlBuilder — a SAFE query builder that collects
'       parameters separately (no string-concatenated values),
'       the correct way to talk to a database from ASP.
'    4. HtmlBuilder — compose markup safely with auto-encoding.
' ============================================================


' ============================================================
' FACTORY — UserFactory
' Turns a raw "CSV row" (as you'd get from a recordset or file)
' into a fully-formed User object, applying defaults and type
' conversion in ONE place. Callers never call New User directly.
' ============================================================
Class User
    Public Id
    Public FullName
    Public Role
    Public IsActive
    Public Function Badge()
        If IsActive Then Badge = "●" Else Badge = "○"
    End Function
End Class

Class UserFactory
    ' Build a User from a delimited string: "id|name|role|active"
    Public Function FromRow(row)
        Dim parts : parts = Split(row, "|")
        Dim u : Set u = New User
        u.Id       = CLng(parts(0))
        u.FullName = parts(1)
        ' Default role if blank — the factory owns the business default.
        If Len(Trim(parts(2))) = 0 Then u.Role = "member" Else u.Role = LCase(parts(2))
        u.IsActive = (UCase(parts(3)) = "Y")
        Set FromRow = u
    End Function

    ' Build many at once.
    Public Function FromRows(rows)
        Dim arr() : ReDim arr(UBound(rows))
        Dim i
        For i = 0 To UBound(rows)
            Set arr(i) = FromRow(rows(i))
        Next
        FromRows = arr
    End Function
End Class


' ============================================================
' FLUENT BUILDER — HtmlBuilder
' Builds an HTML fragment with chained calls. Text content is
' auto-encoded so callers can't introduce XSS by accident.
' Every method returns Me; .Build() returns the final string.
' ============================================================
Class HtmlBuilder
    Private m_buf

    Private Sub Class_Initialize() : m_buf = "" : End Sub

    Public Function OpenTag(tag)
        m_buf = m_buf & "<" & tag & ">" : Set OpenTag = Me
    End Function
    Public Function CloseTag(tag)
        m_buf = m_buf & "</" & tag & ">" : Set CloseTag = Me
    End Function
    ' Text is ENCODED — safe by default.
    Public Function Text(content)
        m_buf = m_buf & Server.HTMLEncode(content) : Set Text = Me
    End Function
    ' Raw is the explicit opt-out (use sparingly, never on user data).
    Public Function Raw(html)
        m_buf = m_buf & html : Set Raw = Me
    End Function
    Public Function Build() : Build = m_buf : End Function
End Class


' ============================================================
' SAFE SQL BUILDER — SqlBuilder
' THE pattern every coding agent must use for ASP + databases.
' Values are NEVER concatenated into the SQL text. They are
' collected as separate parameters, so SQL injection is
' structurally impossible. (Here we just render the parameter
' list; in production you'd feed these to an ADODB.Command.)
' ============================================================
Class SqlBuilder
    Private m_table
    Private m_wheres()
    Private m_params()
    Private m_count

    Private Sub Class_Initialize()
        m_count = 0 : ReDim m_wheres(-1) : ReDim m_params(-1)
    End Sub

    Public Function From(tableName)
        m_table = tableName : Set From = Me
    End Function

    ' Add "column = ?" and stash the value separately. Chainable.
    Public Function WhereEquals(column, value)
        ReDim Preserve m_wheres(m_count)
        ReDim Preserve m_params(m_count)
        m_wheres(m_count) = column & " = ?"
        m_params(m_count) = value
        m_count = m_count + 1
        Set WhereEquals = Me
    End Function

    ' Produce the parameterised SQL (note the ? placeholders).
    Public Function Build()
        Dim sql : sql = "SELECT * FROM " & m_table
        If m_count > 0 Then
            sql = sql & " WHERE "
            Dim i
            For i = 0 To m_count - 1
                If i > 0 Then sql = sql & " AND "
                sql = sql & m_wheres(i)
            Next
        End If
        Build = sql
    End Function

    Public Property Get ParamCount() : ParamCount = m_count : End Property
    Public Function ParamAt(i)       : ParamAt = m_params(i) : End Function
End Class


' ============================================================
'  USAGE
' ============================================================

' --- Factory: rows as you'd get from a recordset ---
Dim rows(2)
rows(0) = "1|Ada Lovelace|admin|Y"
rows(1) = "2|Alan Turing||Y"          ' blank role → factory defaults to 'member'
rows(2) = "3|Grace Hopper|editor|N"

Dim factory : Set factory = New UserFactory
Dim users : users = factory.FromRows(rows)

' --- Builder: compose a small user card with chaining ---
' Capture the chain's returned object with Set (each method returns Me).
' A discarded chain whose calls take arguments triggers a VBScript compile
' error ("can't use parentheses when calling a Sub"); assigning avoids it.
Dim hb : Set hb = New HtmlBuilder
Dim hbChain
Set hbChain = hb.OpenTag("strong").Text("Ada <admin>").CloseTag("strong") _
                .Raw(" — ").OpenTag("em").Text("encoded & safe").CloseTag("em")
Dim cardHtml : cardHtml = hb.Build()

' --- SqlBuilder: a safe parameterised query ---
Dim qb : Set qb = New SqlBuilder
Dim qbChain
Set qbChain = qb.From("Users").WhereEquals("Role", "admin").WhereEquals("IsActive", "Y")
Dim safeSql : safeSql = qb.Build()

' Show what the DANGEROUS naive version would have produced:
Dim evilInput : evilInput = "x' OR '1'='1"
Dim badSql : badSql = "SELECT * FROM Users WHERE Role = '" & evilInput & "'"
%>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>VBScript Classes Demo 9 — Builder &amp; Factory</title>
  <style>
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Courier New',monospace;background:#0f1117;color:#e2e8f0;padding:2rem;line-height:1.6}
    h1{font-size:1.5rem;color:#7dd3fc;margin-bottom:.25rem}
    h2{font-size:1rem;color:#94a3b8;font-weight:normal;margin-bottom:1.75rem}
    h3{font-size:1rem;color:#7dd3fc;margin:1.25rem 0 .6rem;border-left:3px solid #7dd3fc;padding-left:.6rem}
    .section{background:#1e2330;border:1px solid #2d3748;border-radius:6px;padding:1.1rem 1.4rem;margin-bottom:1.25rem}
    table{width:100%;border-collapse:collapse;font-size:.9rem}
    th{text-align:left;color:#94a3b8;font-weight:normal;padding:.4rem .6rem;border-bottom:1px solid #2d3748}
    td{padding:.4rem .6rem;border-bottom:1px solid #1a2035}
    .ok{color:#86efac}.err{color:#f87171}.k{color:#7dd3fc}.active{color:#86efac}.inactive{color:#64748b}
    pre{background:#0d1117;border:1px solid #2d3748;border-radius:4px;padding:.7rem .9rem;font-size:.8rem;overflow-x:auto;color:#a5b4c8;white-space:pre-wrap}
    code{color:#7dd3fc}
    .note{font-size:.82rem;color:#64748b;margin-top:.6rem}
    .danger{background:#450a0a;border:1px solid #7f1d1d;border-radius:4px;padding:.7rem .9rem;color:#fca5a5;font-size:.8rem;white-space:pre-wrap}
  </style>
</head>
<body>
  <h1>Demo 9 — Builder &amp; Factory patterns</h1>
  <h2>Clean object creation, fluent assembly, and injection-proof SQL</h2>

  <h3>1. Factory — raw rows in, real objects out</h3>
  <div class="section">
    <pre>Set u = factory.FromRow("2|Alan Turing||Y")   ' blank role defaulted inside the factory</pre>
    <table>
      <tr><th>ID</th><th>Name</th><th>Role</th><th>Status</th></tr>
      <%
      Dim i
      For i = 0 To UBound(users)
      %>
        <tr>
          <td class="k"><%= users(i).Id %></td>
          <td><%= Server.HTMLEncode(users(i).FullName) %></td>
          <td><%= Server.HTMLEncode(users(i).Role) %></td>
          <td class="<%= IIf(users(i).IsActive, "active", "inactive") %>">
            <%= users(i).Badge() %> <%= IIf(users(i).IsActive, "active", "inactive") %>
          </td>
        </tr>
      <% Next %>
    </table>
    <p class="note">Alan Turing's blank role became <code>member</code> — the default lives in the
    factory, so every caller gets consistent objects without repeating that logic.</p>
  </div>

  <h3>2. Fluent builder — chained, auto-encoded HTML</h3>
  <div class="section">
    <pre>hb.OpenTag("strong").Text("Ada &lt;admin&gt;").CloseTag("strong")
  .Raw(" — ").OpenTag("em").Text("encoded &amp; safe").CloseTag("em")</pre>
    <p>Rendered output: <%= cardHtml %></p>
    <p class="note">The <code>&lt;</code>, <code>&gt;</code> and <code>&amp;</code> in the text were
    encoded automatically by <code>.Text()</code>. Only <code>.Raw()</code> bypasses encoding — an
    explicit, searchable opt-out.</p>
  </div>

  <h3>3. SqlBuilder — parameterised &amp; injection-proof</h3>
  <div class="section">
    <pre>qb.From("Users").WhereEquals("Role","admin").WhereEquals("IsActive","Y")</pre>
    <table>
      <tr><th>Generated SQL (placeholders only)</th></tr>
      <tr><td class="ok"><%= Server.HTMLEncode(safeSql) %></td></tr>
    </table>
    <table style="margin-top:.6rem">
      <tr><th>#</th><th>Parameter value (kept separate)</th></tr>
      <%
      Dim p
      For p = 0 To qb.ParamCount - 1
      %>
        <tr><td><%= p + 1 %></td><td class="ok"><%= Server.HTMLEncode(qb.ParamAt(p)) %></td></tr>
      <% Next %>
    </table>
    <p class="note">Values never touch the SQL string — they travel as parameters, so injection is
    structurally impossible. Feed these to an <code>ADODB.Command</code> with appended
    <code>Parameters</code> in production.</p>

    <p class="note" style="margin-top:1rem">Contrast: the naive concatenated query an LLM should
    <strong>never</strong> generate, with attacker input <code>x' OR '1'='1</code>:</p>
    <div class="danger"><%= Server.HTMLEncode(badSql) %>

    ↑ This returns EVERY row. The builder pattern above makes this class of bug impossible.</div>
  </div>

  <h3>When to reach for each pattern</h3>
  <div class="section">
    <table>
      <tr><th>Pattern</th><th>Use when…</th></tr>
      <tr><td class="k">Factory</td><td>Object creation involves parsing, defaults, or type conversion you don't want duplicated.</td></tr>
      <tr><td class="k">Fluent builder</td><td>You assemble a complex value (markup, query, config) in steps and want readable, chainable code.</td></tr>
      <tr><td class="k">SqlBuilder</td><td>ALWAYS, whenever user input reaches a database. Never concatenate values into SQL.</td></tr>
    </table>
  </div>

<%
' VBScript has no ternary; helper for the view.
Function IIf(c, a, b)
    If c Then IIf = a Else IIf = b
End Function

Dim z
For z = 0 To UBound(users) : Set users(z) = Nothing : Next
Set factory = Nothing : Set hb = Nothing : Set qb = Nothing
%>
</body>
</html>
