<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<%
Option Explicit
%>
<!--#include file="includes/helpers.asp"-->
<%
' ============================================================================
' 17-python-bridge.asp - ASPPY.ExecutePython / ExecutePythonFile
' ----------------------------------------------------------------------------
' The Python bridge runs real CPython in an isolated subprocess and hands a
' string back through the injected builtin ASPPY_RETURN. Both methods take the
' same two optional arguments:
'
'     ASPPY.ExecutePython(code [, args] [, timeout])
'     ASPPY.ExecutePythonFile(path [, args] [, timeout])
'
'   * args    - any JSON-encodable VBScript value (string, number, boolean,
'               Array, Scripting.Dictionary, or a nesting of those). Python
'               reads it as the builtin ASPPY_ARGS, already decoded. This is
'               what lets a bridge live in a real .py file instead of being
'               rebuilt as a VBScript string on every request.
'   * timeout - seconds, for THIS call only, overriding ASP_PY_PYTHON_TIMEOUT.
'               Use it when one page mixes fast polling calls with a slow one.
'
' The bridge is DISABLED unless ASP_PY_ALLOW_PYTHON=1 is set in the server
' environment, so every check below is guarded: with the feature off the page
' reports SKIP rather than failing. That keeps `asppycheck www_test` green on
' a default install and is the same guard your own pages should use.
' ============================================================================
Dim PageTitle : PageTitle = "Python Bridge"
%>
<!--#include file="includes/header.asp"-->
<%
Dim RESULTS_PASS, RESULTS_FAIL, RESULTS_SKIP
RESULTS_PASS = 0 : RESULTS_FAIL = 0 : RESULTS_SKIP = 0

' Emits a label / actual / verdict row. Verdict is "PASS", "FAIL" or "SKIP".
Sub CheckRow(ByVal sLabel, ByVal vActual, ByVal sVerdict)
    Dim cls
    Select Case sVerdict
        Case "PASS" : cls = "ok"  : RESULTS_PASS = RESULTS_PASS + 1
        Case "FAIL" : cls = "err" : RESULTS_FAIL = RESULTS_FAIL + 1
        Case Else   : cls = ""    : RESULTS_SKIP = RESULTS_SKIP + 1
    End Select
    WriteLine "<tr><th scope=""row"">" & HtmlEncode(sLabel) & "</th><td>" & _
              HtmlEncode(vActual) & "</td><td class=""" & cls & """>" & sVerdict & "</td></tr>"
End Sub

Sub Check(ByVal sLabel, ByVal vActual, ByVal bPass)
    CheckRow sLabel, vActual, IIf(bPass, "PASS", "FAIL")
End Sub

' Is the bridge switched on? Probing with a trivial snippet is more honest than
' reading the environment variable, because it also catches a missing or
' unusable interpreter.
Dim bridgeOn, probeErr
bridgeOn = False : probeErr = ""
On Error Resume Next
Dim probe : probe = ASPPY.ExecutePython("ASPPY_RETURN('up')")
If Err.Number = 0 And probe = "up" Then
    bridgeOn = True
Else
    probeErr = Err.Description
End If
Err.Clear
On Error GoTo 0
%>
<h1>ASPPY.ExecutePython / ExecutePythonFile</h1>
<p class="lead">
  Runs real CPython in an isolated subprocess. <code>args</code> travels in as
  the builtin <code>ASPPY_ARGS</code>; <code>timeout</code> caps this call only.
</p>

<% If Not bridgeOn Then %>
<p class="lead">
  <strong>Bridge is off.</strong> Every check below reports
  <span>SKIP</span>. Start the server with
  <code>ASP_PY_ALLOW_PYTHON=1</code> to run them for real.
  <% If Len(probeErr) > 0 Then %><br /><code><%= HtmlEncode(probeErr) %></code><% End If %>
</p>
<% End If %>

<h2>Basics</h2>
<table>
<thead><tr><th>Check</th><th>Value</th><th>Result</th></tr></thead>
<tbody>
<%
Dim r
If Not bridgeOn Then
    CheckRow "ASPPY_RETURN returns a string", "-", "SKIP"
    CheckRow "no ASPPY_RETURN yields empty string", "-", "SKIP"
    CheckRow "non-ASCII survives the round trip", "-", "SKIP"
Else
    On Error Resume Next
    r = ASPPY.ExecutePython("ASPPY_RETURN(2 + 40)")
    Check "ASPPY_RETURN returns a string", r, (Err.Number = 0 And r = "42")
    Err.Clear

    r = ASPPY.ExecutePython("x = 1")
    Check "no ASPPY_RETURN yields empty string", "[" & r & "]", (Err.Number = 0 And r = "")
    Err.Clear

    r = ASPPY.ExecutePython("ASPPY_RETURN('caf\u00e9 \u4e2d\u6587')")
    Check "non-ASCII survives the round trip", r, (Err.Number = 0 And r = "caf" & ChrW(233) & " " & ChrW(20013) & ChrW(25991))
    Err.Clear
    On Error GoTo 0
End If
%>
</tbody>
</table>

<h2>The <code>args</code> argument</h2>
<p>
  A <code>Scripting.Dictionary</code> arrives in Python as a <code>dict</code>
  and an <code>Array</code> as a <code>list</code> &mdash; real containers, not
  a string that happens to look like JSON.
</p>
<table>
<thead><tr><th>Check</th><th>Value</th><th>Result</th></tr></thead>
<tbody>
<%
Dim bag, arr(2), decoded
If Not bridgeOn Then
    CheckRow "omitted args -> ASPPY_ARGS is None", "-", "SKIP"
    CheckRow "string args", "-", "SKIP"
    CheckRow "Dictionary args -> Python dict", "-", "SKIP"
    CheckRow "nested Array inside Dictionary -> list", "-", "SKIP"
    CheckRow "ExecutePythonFile receives args", "-", "SKIP"
Else
    On Error Resume Next

    r = ASPPY.ExecutePython("ASPPY_RETURN(repr(ASPPY_ARGS))")
    Check "omitted args -> ASPPY_ARGS is None", r, (Err.Number = 0 And r = "None")
    Err.Clear

    r = ASPPY.ExecutePython("ASPPY_RETURN(ASPPY_ARGS.upper())", "hello")
    Check "string args", r, (Err.Number = 0 And r = "HELLO")
    Err.Clear

    arr(0) = 10 : arr(1) = 20 : arr(2) = 30
    Set bag = Server.CreateObject("Scripting.Dictionary")
    bag("n") = 21
    bag("label") = "widget"
    bag("nums") = arr

    r = ASPPY.ExecutePython("ASPPY_RETURN(type(ASPPY_ARGS).__name__ + ':' + str(ASPPY_ARGS['n'] * 2))", bag)
    Check "Dictionary args -> Python dict", r, (Err.Number = 0 And r = "dict:42")
    Err.Clear

    r = ASPPY.ExecutePython("ASPPY_RETURN(type(ASPPY_ARGS['nums']).__name__ + ':' + str(sum(ASPPY_ARGS['nums'])))", bag)
    Check "nested Array inside Dictionary -> list", r, (Err.Number = 0 And r = "list:60")
    Err.Clear

    ' The same params, but against a real .py file on disk. This is the pattern
    ' to prefer for anything non-trivial: the bridge stays a normal module.
    r = ASPPY.ExecutePythonFile(Server.MapPath("python/args_echo.py"), bag)
    Set decoded = Nothing
    If Err.Number = 0 Then Set decoded = ASPPY.json.Decode(r)
    Check "ExecutePythonFile receives args", r, _
          (Err.Number = 0 And IsObject(decoded) And decoded("type") = "dict" And decoded("doubled") = 42)
    Err.Clear

    On Error GoTo 0
End If
%>
</tbody>
</table>

<h2>The <code>timeout</code> argument</h2>
<p>
  A per-call budget, in seconds, that overrides
  <code>ASP_PY_PYTHON_TIMEOUT</code>. Exceeding it raises a trappable VBScript
  error rather than hanging the request.
</p>
<table>
<thead><tr><th>Check</th><th>Value</th><th>Result</th></tr></thead>
<tbody>
<%
Dim t0, elapsed, msg
If Not bridgeOn Then
    CheckRow "generous timeout does not interfere", "-", "SKIP"
    CheckRow "exceeded timeout raises a trappable error", "-", "SKIP"
    CheckRow "timeout is enforced promptly", "-", "SKIP"
    CheckRow "zero / negative timeout is rejected", "-", "SKIP"
Else
    On Error Resume Next

    r = ASPPY.ExecutePython("ASPPY_RETURN('quick')", Empty, 120)
    Check "generous timeout does not interfere", r, (Err.Number = 0 And r = "quick")
    Err.Clear

    t0 = Timer()
    r = ASPPY.ExecutePython("import time" & vbLf & "time.sleep(30)", Empty, 1)
    elapsed = Timer() - t0
    msg = Err.Description
    Check "exceeded timeout raises a trappable error", msg, _
          (Err.Number <> 0 And InStr(msg, "timed out") > 0)
    Err.Clear

    ' Timer() rolls over at midnight; treat a negative delta as unmeasurable.
    Check "timeout is enforced promptly", FormatNumber(elapsed, 1) & "s", _
          (elapsed < 0 Or elapsed < 10)

    r = ASPPY.ExecutePython("ASPPY_RETURN('x')", Empty, 0)
    Check "zero / negative timeout is rejected", Err.Description, (Err.Number <> 0)
    Err.Clear

    On Error GoTo 0
End If
%>
</tbody>
</table>

<h2>Isolation and errors</h2>
<table>
<thead><tr><th>Check</th><th>Value</th><th>Result</th></tr></thead>
<tbody>
<%
If Not bridgeOn Then
    CheckRow "Python exception surfaces to VBScript", "-", "SKIP"
    CheckRow "stray print() cannot corrupt the payload", "-", "SKIP"
    CheckRow "each call gets a fresh interpreter", "-", "SKIP"
    CheckRow "missing file is reported, not swallowed", "-", "SKIP"
Else
    On Error Resume Next

    r = ASPPY.ExecutePython("raise ValueError('boom')")
    Check "Python exception surfaces to VBScript", Err.Description, _
          (Err.Number <> 0 And InStr(Err.Description, "boom") > 0)
    Err.Clear

    r = ASPPY.ExecutePython("print('noise')" & vbLf & "ASPPY_RETURN('clean')")
    Check "stray print() cannot corrupt the payload", r, (Err.Number = 0 And r = "clean")
    Err.Clear

    ' Nothing a snippet does can leak into the next call.
    r = ASPPY.ExecutePython("import sys" & vbLf & "sys.leaked = 1" & vbLf & "ASPPY_RETURN('a')")
    Err.Clear
    r = ASPPY.ExecutePython("import sys" & vbLf & "ASPPY_RETURN(str(hasattr(sys, 'leaked')))")
    Check "each call gets a fresh interpreter", r, (Err.Number = 0 And r = "False")
    Err.Clear

    r = ASPPY.ExecutePythonFile(Server.MapPath("python/does_not_exist.py"))
    Check "missing file is reported, not swallowed", Err.Description, (Err.Number <> 0)
    Err.Clear

    On Error GoTo 0
End If
%>
</tbody>
</table>

<h2>Summary</h2>
<p>
  <span class="ok"><%= RESULTS_PASS %> passed</span> &middot;
  <span class="<%= IIf(RESULTS_FAIL > 0, "err", "") %>"><%= RESULTS_FAIL %> failed</span> &middot;
  <%= RESULTS_SKIP %> skipped
</p>

<h2>The pattern worth copying</h2>
<%
CodeBlock _
    "' Build the request as a Dictionary - no string-concatenated Python." & vbCrLf & _
    "Dim params, result, data" & vbCrLf & _
    "Set params = Server.CreateObject(""Scripting.Dictionary"")" & vbCrLf & _
    "params(""op"") = ""report""" & vbCrLf & _
    "params(""month"") = 3" & vbCrLf & vbCrLf & _
    "' 180s for this call only; other calls keep ASP_PY_PYTHON_TIMEOUT." & vbCrLf & _
    "On Error Resume Next" & vbCrLf & _
    "result = ASPPY.ExecutePythonFile(Server.MapPath(""bridge.py""), params, 180)" & vbCrLf & _
    "If Err.Number <> 0 Then" & vbCrLf & _
    "    ' Bridge disabled, interpreter missing, timeout, or an uncaught" & vbCrLf & _
    "    ' Python exception - Err.Description carries the reason." & vbCrLf & _
    "    Response.Write ""bridge failed: "" & Err.Description" & vbCrLf & _
    "End If" & vbCrLf & _
    "On Error GoTo 0" & vbCrLf & vbCrLf & _
    "Set data = ASPPY.json.Decode(result)" & vbCrLf & vbCrLf & _
    "' ...and bridge.py stays an ordinary, lintable module:" & vbCrLf & _
    "'     import json" & vbCrLf & _
    "'     def main(p):" & vbCrLf & _
    "'         return {""ok"": True, ""month"": p.get(""month"")}" & vbCrLf & _
    "'     ASPPY_RETURN(json.dumps(main(ASPPY_ARGS or {})))"
%>
<!--#include file="includes/footer.asp"-->
