<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<%
Option Explicit
%>
<!--#include file="includes/helpers.asp"-->
<%
' ============================================================================
' index.asp - Home page. Lists every sample as a navigable card.
' The catalog is data-driven: each sample is one row in a 2D array so the
' markup is generated in a loop (demonstrates arrays + For loops).
' ============================================================================
Dim PageTitle : PageTitle = "Home"
%>
<!--#include file="includes/header.asp"-->
<%
Dim samples, i

' Columns: file, title, blurb, tag
samples = Array( _
    Array("01-basics.asp",      "Language Basics",      "Variables, data types, operators, Variant subtypes and type tests.", "core"), _
    Array("02-control-flow.asp","Control Flow",         "If/ElseIf/Else, Select Case, For, For Each, Do While/Until loops.",   "core"), _
    Array("03-procedures.asp",  "Subs & Functions",     "Declaring Subs and Functions, ByVal/ByRef, optional logic, recursion.", "core"), _
    Array("04-classes.asp",     "Classes (OOP)",        "Class with private fields, Property Get/Let/Set, methods, Me, lifecycle.", "core"), _
    Array("05-arrays-dict.asp", "Arrays & Dictionary",  "Static/dynamic arrays, ReDim Preserve, multidimensional, Scripting.Dictionary.", "data"), _
    Array("06-strings.asp",     "String Functions",     "Len, Mid, InStr, Replace, Split, Join, formatting and a palindrome demo.", "data"), _
    Array("07-request-form.asp","Request & Forms",      "Reading QueryString and Form posts, server variables, round-trip form.", "web"), _
    Array("08-state.asp",       "Session & Application","Per-user Session state and shared Application state with a hit counter.", "web"), _
    Array("09-filesystem.asp",  "FileSystemObject",     "Create, write, read and enumerate files/folders with the FSO.",        "io"), _
    Array("10-errors.asp",      "Error Handling",       "On Error Resume Next, the Err object, Err.Raise and a guarded division.", "core"), _
    Array("11-dates-time.asp",  "Dates & Time",         "Date-as-Double, DateSerial/DateAdd/DateDiff, leap years and locale traps.", "core"), _
    Array("12-conversion-edge.asp","Coercion Edge Cases","Variant coercion, + vs &, Empty/Null/0 truth tables, Is vs =, banker's rounding.", "core"), _
    Array("13-regexp.asp",      "Regular Expressions",  "VBScript.RegExp: Test/Execute/Replace, capture groups, $1 backrefs, dialect gotchas.", "data"), _
    Array("14-metaprogramming.asp","Recursion, Eval & GetRef","Recursion with memoisation, Eval/Execute/ExecuteGlobal, GetRef callbacks, Map/Reduce.", "core"), _
    Array("15-collections-advanced.asp","Collections (Advanced)","Multidim vs jagged arrays, ReDim Preserve rules, Filter, Dictionary maps, sort.", "data"), _
    Array("16-session-objects.asp","Objects in Session",   "Storing a Dictionary reference in Session with guarded pass/fail checks - plus the Application apartment-threading trap (ASP 0197).", "web"), _
    Array("17-python-bridge.asp","Python Bridge",         "ASPPY.ExecutePython / ExecutePythonFile: passing a Dictionary in as ASPPY_ARGS, per-call timeouts, and subprocess isolation.", "io"), _
    Array("18-error-parity.asp","Error Parity",          "Err.Number asserted against values captured from live IIS 10: ReDim rules, default-property semantics, CBool, MapPath and HRESULT signedness.", "core"), _
    Array("19-msxml.asp",      "MSXML2",                "DOMDocument node model, Nothing semantics, XPath 1.0 and XSLT (via optional lxml), and the Byte() SafeArray.", "data") _
)
%>
<h1>Classic ASP / VBScript &mdash; Working Samples</h1>
<p class="lead">
  A living catalog of Classic ASP code that compiles and runs on IIS. Every page
  uses real VBScript: <strong>subs, functions, classes</strong> and
  <strong>control-flow</strong> constructs. View each page, then read its source.
</p>

<h2>Sample catalog</h2>
<ul class="cards">
<%
For i = 0 To UBound(samples)
    Dim file, title, blurb, tag
    file  = samples(i)(0)
    title = samples(i)(1)
    blurb = samples(i)(2)
    tag   = samples(i)(3)
    WriteLine "  <li>"
    WriteLine "    <a href=""" & HtmlEncode(file) & """>" & HtmlEncode(title) & _
              "</a><span class=""tag"">" & HtmlEncode(tag) & "</span>"
    WriteLine "    <p>" & HtmlEncode(blurb) & "</p>"
    WriteLine "  </li>"
Next
%>
</ul>

<h2>Advanced VBScript classes <span class="tag">deep dive</span></h2>
<p class="lead">
  A dedicated gallery of <strong>advanced VBScript class</strong> examples &mdash;
  written as idiomatic reference code for LLMs and coding agents to crawl and learn from.
  Covers encapsulation, dependency injection, object composition, default members,
  parameterised properties, method chaining, polymorphism without inheritance, and
  correct error-handling patterns.
</p>
<ul class="cards">
  <li>
    <a href="classes/default.asp">Advanced Classes Gallery &raquo;</a><span class="tag">classes</span>
    <p>Nine standalone, runnable demos of real-world Classic ASP/VBScript class design and syntax.</p>
  </li>
</ul>

<h2>Environment</h2>
<table class="kv">
<%
RenderTableRow "Server software",  Request.ServerVariables("SERVER_SOFTWARE")
RenderTableRow "Script language",  "VBScript " & ScriptEngineMajorVersion() & "." & ScriptEngineMinorVersion() & "." & ScriptEngineBuildVersion()
RenderTableRow "Server name",      Request.ServerVariables("SERVER_NAME")
RenderTableRow "HTTPS",            Coalesce(Request.ServerVariables("HTTPS"), "off")
RenderTableRow "Current time",     Now()
%>
</table>
<%
' Show off the StringBuilder class from the helper library.
Dim sb : Set sb = New StringBuilder
sb.Append("Built ").Append(CStr(UBound(samples) + 1)).Append(" samples in a fluent chain.")
%>
<p class="ok"><%= HtmlEncode(sb.ToString()) %> (StringBuilder fragments: <%= sb.Count %>)</p>
<!--#include file="includes/footer.asp"-->
