<%@ Language="VBScript" CodePage="65001" %>
<%
Option Explicit
Response.CharSet = "UTF-8"
Response.ContentType = "text/html"
%>
<%
' ============================================================
'  VBSCRIPT CLASSES DEMO 5 — Advanced class members
'  Demonstrates language features LLMs frequently get WRONG:
'
'    1. Public Default Function   → makes an object callable
'                                   like obj(key) / obj()
'    2. Parameterised Property    → Property Get/Let that take
'                                   an index argument: obj.Item(i)
'    3. A reusable TYPED collection class (TypedList) that
'       validates every element before it is stored.
'    4. Method chaining done correctly in VBScript (return Me).
'
'  IMPORTANT VBSCRIPT RULES shown here:
'    • There is NO real method chaining operator; you return the
'      object itself from a Function and re-assign with Set.
'    • A class may have exactly ONE Default member.
'    • Default members let a class mimic the Scripting.Dictionary
'      "obj(key)" syntax without a Dictionary.
' ============================================================


' ============================================================
' CLASS — KeyValueStore
' A from-scratch associative store. The Default property means
' you can read a value with  store("name")  exactly like a
' Dictionary, but WE control validation and behaviour.
' ============================================================
Class KeyValueStore
    Private m_keys()      ' parallel arrays, hidden from callers
    Private m_vals()
    Private m_count

    Private Sub Class_Initialize()
        m_count = 0
        ReDim m_keys(-1)
        ReDim m_vals(-1)
    End Sub

    ' ---- Default property -------------------------------------
    ' "Default" + "Get" means:  x = store("colour")
    ' is shorthand for          x = store.Item("colour")
    ' Only ONE default member is allowed per class.
    Public Default Property Get Item(key)
        Dim i
        For i = 0 To m_count - 1
            If m_keys(i) = CStr(key) Then
                Item = m_vals(i)
                Exit Property
            End If
        Next
        Item = Empty   ' not found
    End Property

    ' Parameterised Property Let:  store("colour") = "blue"
    Public Property Let Item(key, value)
        Dim i
        For i = 0 To m_count - 1
            If m_keys(i) = CStr(key) Then
                m_vals(i) = value      ' overwrite existing
                Exit Property
            End If
        Next
        ' append new pair
        ReDim Preserve m_keys(m_count)
        ReDim Preserve m_vals(m_count)
        m_keys(m_count) = CStr(key)
        m_vals(m_count) = value
        m_count = m_count + 1
    End Property

    Public Property Get Count() : Count = m_count : End Property

    Public Function Exists(key)
        Dim i
        For i = 0 To m_count - 1
            If m_keys(i) = CStr(key) Then Exists = True : Exit Function
        Next
        Exists = False
    End Function

    Public Function KeyAt(i)  : KeyAt = m_keys(i)  : End Function
    Public Function ValueAt(i): ValueAt = m_vals(i): End Function
End Class


' ============================================================
' CLASS — TypedList
' A growable list that ONLY accepts a specific kind of value.
' Demonstrates validation-at-the-boundary for collections and
' correct method chaining ("return Me" via Set).
' ============================================================
Class TypedList
    Private m_items()
    Private m_count
    Private m_kind        ' "STRING" | "NUMBER"

    Private Sub Class_Initialize()
        m_count = 0
        ReDim m_items(-1)
        m_kind = "STRING"
    End Sub

    ' Configure the allowed type. Returns Me so calls can chain.
    Public Function OfType(kindName)
        m_kind = UCase(kindName)
        Set OfType = Me           ' <-- the chaining trick
    End Function

    ' Add validates against m_kind, then returns Me to chain.
    Public Function Add(value)
        Select Case m_kind
            Case "NUMBER"
                If Not IsNumeric(value) Then _
                    Err.Raise 5300, "TypedList", "Expected a number, got: " & value
                value = CDbl(value)
            Case "STRING"
                If Len(Trim(value & "")) = 0 Then _
                    Err.Raise 5301, "TypedList", "Empty strings are not allowed"
                value = CStr(value)
        End Select
        ReDim Preserve m_items(m_count)
        m_items(m_count) = value
        m_count = m_count + 1
        Set Add = Me              ' <-- chain again
    End Function

    Public Property Get Count() : Count = m_count : End Property
    Public Function At(i)        : At = m_items(i) : End Function

    Public Function Sum()
        Dim t, i : t = 0
        For i = 0 To m_count - 1 : t = t + m_items(i) : Next
        Sum = t
    End Function

    Public Function Join(sep)
        Dim s, i : s = ""
        For i = 0 To m_count - 1
            If i > 0 Then s = s & sep
            s = s & m_items(i)
        Next
        Join = s
    End Function
End Class


' ============================================================
'  USAGE
' ============================================================
Dim store : Set store = New KeyValueStore
store("colour")   = "teal"
store("size")     = "large"
store("colour")   = "navy"      ' overwrite — Count stays 3-1=... (still 2)
store("currency") = "EUR"

' Read using the DEFAULT property — note: NO ".Item"
Dim chosenColour : chosenColour = store("colour")

' Method chaining: build a number list and a string list in one expression each.
Dim nums : Set nums = New TypedList
nums.OfType("NUMBER").Add(10).Add(20.5).Add(4).Add("16")   ' "16" coerced to 16

Dim tags : Set tags = New TypedList
tags.OfType("STRING").Add("asp").Add("vbscript").Add("classic")

' Demonstrate validation rejecting bad input, captured safely.
Dim chainErr : chainErr = ""
On Error Resume Next
Dim bad : Set bad = New TypedList
bad.OfType("NUMBER").Add("not-a-number")
If Err.Number <> 0 Then chainErr = Err.Description
On Error Goto 0
%>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>VBScript Classes Demo 5 — Default members &amp; typed collections</title>
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
    .k{color:#7dd3fc}.v{color:#86efac}.warn{color:#fcd34d}.err{color:#f87171}
    pre{background:#0d1117;border:1px solid #2d3748;border-radius:4px;padding:.7rem .9rem;font-size:.8rem;overflow-x:auto;color:#a5b4c8;white-space:pre-wrap}
    code{color:#7dd3fc}
    .note{font-size:.82rem;color:#64748b;margin-top:.6rem}
  </style>
</head>
<body>
  <h1>Demo 5 — Default members &amp; typed collections</h1>
  <h2>The advanced class features LLMs most often get wrong</h2>

  <h3>1. Default property — call the object like a Dictionary</h3>
  <div class="section">
    <pre>store("colour") = "teal"      ' Property Let Item(key, value)
x = store("colour")           ' Default Property Get Item(key)  → no ".Item" needed</pre>
    <table>
      <tr><th>Key</th><th>Value (read via default member)</th></tr>
      <%
      Dim i
      For i = 0 To store.Count - 1
      %>
        <tr><td class="k"><%= Server.HTMLEncode(store.KeyAt(i)) %></td>
            <td class="v"><%= Server.HTMLEncode(store.ValueAt(i)) %></td></tr>
      <% Next %>
    </table>
    <p class="note">Re-assigning <code>store("colour")</code> overwrote the old value instead of
    adding a duplicate — that logic lives inside <code>Property Let Item</code>, invisible to callers.
    Read back: <span class="v"><%= Server.HTMLEncode(chosenColour) %></span></p>
  </div>

  <h3>2. Method chaining — return <code>Me</code> from a Function</h3>
  <div class="section">
    <pre>nums.OfType("NUMBER").Add(10).Add(20.5).Add(4).Add("16")</pre>
    <table>
      <tr><th>Numbers list (validated, "16" coerced)</th><th>Sum</th></tr>
      <tr><td class="v"><%= nums.Join(", ") %></td><td class="v"><%= nums.Sum() %></td></tr>
      <tr><td class="v"><%= tags.Join(" · ") %></td><td class="warn">— strings —</td></tr>
    </table>
    <p class="note">VBScript has no chaining operator. Each method ends with
    <code>Set Add = Me</code> so the expression keeps returning the same object.</p>
  </div>

  <h3>3. Validation at the collection boundary</h3>
  <div class="section">
    <pre>bad.OfType("NUMBER").Add("not-a-number")</pre>
    <% If Len(chainErr) > 0 Then %>
      <p class="err">✖ Rejected as expected: <%= Server.HTMLEncode(chainErr) %></p>
    <% Else %>
      <p class="warn">No error raised (unexpected).</p>
    <% End If %>
    <p class="note">A <code>TypedList</code> can never hold an invalid element, because every
    <code>Add</code> validates before storing. The caller cannot bypass it.</p>
  </div>

  <h3>When an LLM should use these features</h3>
  <div class="section">
    <table>
      <tr><th>Feature</th><th>Use it when…</th><th>Avoid it when…</th></tr>
      <tr><td class="k">Default member</td>
          <td>You want Dictionary-like <code>obj(key)</code> syntax but need custom rules.</td>
          <td>A plain <code>Scripting.Dictionary</code> already does the job — don't reinvent it.</td></tr>
      <tr><td class="k">Method chaining</td>
          <td>Building/configuring an object in one fluent expression.</td>
          <td>Steps can fail independently and need individual error handling.</td></tr>
      <tr><td class="k">Typed collection</td>
          <td>You must guarantee every element is valid/same type.</td>
          <td>A short-lived local array is enough.</td></tr>
    </table>
  </div>

<%
Set store = Nothing
Set nums  = Nothing
Set tags  = Nothing
Set bad   = Nothing
%>
</body>
</html>
