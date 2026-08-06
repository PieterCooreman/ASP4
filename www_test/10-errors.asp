<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<%
Option Explicit
%>
<!--#include file="includes/helpers.asp"-->
<%
' ============================================================================
' 10-errors.asp - Error handling in VBScript
' Demonstrates: On Error Resume Next, inspecting the Err object, clearing it,
' re-enabling normal error flow with On Error Goto 0, raising custom errors
' with Err.Raise, and a reusable "safe" wrapper function.
' ============================================================================
Dim PageTitle : PageTitle = "Error Handling"
%>
<!--#include file="includes/header.asp"-->
<%
' --- A guarded division that reports problems instead of crashing ---------
Function SafeDivide(ByVal a, ByVal b, ByRef outResult)
    On Error Resume Next
    outResult = a / b
    If Err.Number <> 0 Then
        SafeDivide = "ERROR " & Err.Number & ": " & Err.Description
        Err.Clear
    Else
        SafeDivide = "OK"
    End If
    On Error Goto 0
End Function

' --- A validator that RAISES a custom error -------------------------------
Dim ERR_BASE : ERR_BASE = vbObjectError    ' base for user-defined error numbers
Sub RequirePositive(ByVal n)
    If Not IsNumeric(n) Then
        Err.Raise ERR_BASE + 1, "RequirePositive", "Value must be numeric."
    ElseIf n <= 0 Then
        Err.Raise ERR_BASE + 2, "RequirePositive", "Value must be greater than zero."
    End If
End Sub
%>
<h1>Error Handling</h1>
<p class="lead">VBScript uses <code>On Error Resume Next</code> plus the <code>Err</code> object.</p>

<h2>Catching a runtime error</h2>
<%
DemoStart "Divide by zero, caught and reported"
Dim result, status
status = SafeDivide(10, 2, result)
WriteLine "<p>10 / 2 -> status <strong>" & HtmlEncode(status) & "</strong>, result <strong>" & HtmlEncode(result) & "</strong></p>"

status = SafeDivide(10, 0, result)
WriteLine "<p>10 / 0 -> status <strong class=""err"">" & HtmlEncode(status) & "</strong></p>"
DemoEnd
%>

<h2>Inspecting the Err object</h2>
<%
DemoStart "Trigger an error and read every Err property"
On Error Resume Next
Dim bad
bad = CInt("not a number")     ' raises a type mismatch
If Err.Number <> 0 Then
    WriteLine "<table class=""kv"">"
    RenderTableRow "Err.Number",      Err.Number
    RenderTableRow "Err.Source",      Err.Source
    RenderTableRow "Err.Description",  Err.Description
    WriteLine "</table>"
End If
Err.Clear
On Error Goto 0
DemoEnd
%>

<h2>Raising custom errors with Err.Raise</h2>
<%
DemoStart "RequirePositive() rejects bad input via Err.Raise"
Dim tests, t
tests = Array(5, -3, 0, "abc")
WriteLine "<table class=""kv"">"
For Each t In tests
    On Error Resume Next
    Err.Clear
    RequirePositive t
    If Err.Number <> 0 Then
        RenderTableRow "RequirePositive(" & TypeName(t) & " " & t & ")", _
                       "Raised " & (Err.Number - ERR_BASE) & ": " & Err.Description
    Else
        RenderTableRow "RequirePositive(" & t & ")", "accepted"
    End If
    On Error Goto 0
Next
WriteLine "</table>"
DemoEnd
%>

<h2>Pattern reference</h2>
<%
CodeBlock _
    "On Error Resume Next        ' start guarding" & vbCrLf & _
    "risky = a / b" & vbCrLf & _
    "If Err.Number <> 0 Then" & vbCrLf & _
    "    ' handle it" & vbCrLf & _
    "    Err.Clear" & vbCrLf & _
    "End If" & vbCrLf & _
    "On Error Goto 0            ' stop guarding (errors crash again)" & vbCrLf & vbCrLf & _
    "' Raise your own:" & vbCrLf & _
    "Err.Raise vbObjectError + 1, ""MySource"", ""Something went wrong."""
%>
<!--#include file="includes/footer.asp"-->
