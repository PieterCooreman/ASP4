<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<%
Option Explicit
%>
<!--#include file="includes/helpers.asp"-->
<%
' ============================================================================
' 03-procedures.asp - Subs and Functions
' Demonstrates: Sub vs Function, ByVal vs ByRef, returning values,
' default ByRef behaviour, and recursion (factorial + Fibonacci).
' ============================================================================
Dim PageTitle : PageTitle = "Subs & Functions"
%>
<!--#include file="includes/header.asp"-->
<%
' --- A Sub performs an action and returns nothing --------------------------
Sub Greet(ByVal who)
    Response.Write "<p>Hello, <strong>" & HtmlEncode(who) & "</strong>!</p>" & vbCrLf
End Sub

' --- A Function returns a value -------------------------------------------
Function AddNumbers(ByVal a, ByVal b)
    AddNumbers = a + b
End Function

' --- ByRef (default) lets a procedure modify the caller's variable --------
Sub DoubleInPlace(ByRef value)
    value = value * 2
End Sub

' --- ByVal protects the caller's variable ---------------------------------
Sub TryToChange(ByVal value)
    value = -999    ' affects only the local copy
End Sub

' --- Recursion: factorial -------------------------------------------------
Function Factorial(ByVal n)
    If n <= 1 Then
        Factorial = 1
    Else
        Factorial = n * Factorial(n - 1)
    End If
End Function

' --- Recursion: Fibonacci -------------------------------------------------
Function Fib(ByVal n)
    If n < 2 Then
        Fib = n
    Else
        Fib = Fib(n - 1) + Fib(n - 2)
    End If
End Function

' --- A Function with simulated "optional" argument via IsMissing pattern ---
' VBScript has no Optional keyword; emulate with a sentinel default.
Function PowerOf(ByVal base, ByVal exp)
    If IsEmpty(exp) Then exp = 2     ' default to squaring
    PowerOf = base ^ exp
End Function
%>
<h1>Subs &amp; Functions</h1>
<p class="lead">Procedures that do work (Subs) and procedures that return values (Functions).</p>

<h2>Calling a Sub</h2>
<%
DemoStart "Greet(name)"
Greet "World"
Greet "ASP Developer"
DemoEnd
%>

<h2>Calling a Function</h2>
<%
DemoStart "AddNumbers(a, b)"
WriteLine "<p>AddNumbers(15, 27) = <strong>" & AddNumbers(15, 27) & "</strong></p>"
WriteLine "<p>AddNumbers(2.5, 0.5) = <strong>" & AddNumbers(2.5, 0.5) & "</strong></p>"
DemoEnd
%>

<h2>ByRef vs ByVal</h2>
<%
DemoStart "How the argument-passing mode changes the caller"
Dim m : m = 10
DoubleInPlace m          ' ByRef -> m is modified
WriteLine "<p>After DoubleInPlace(m): m = <strong>" & m & "</strong> (was 10, ByRef)</p>"

Dim k : k = 10
TryToChange k            ' ByVal -> k is untouched
WriteLine "<p>After TryToChange(k): k = <strong>" & k & "</strong> (still 10, ByVal)</p>"
DemoEnd
%>

<h2>Recursion</h2>
<%
DemoStart "Factorial and Fibonacci computed recursively"
WriteLine "<table class=""kv"">"
Dim j
For j = 1 To 7
    RenderTableRow "Factorial(" & j & ")", Factorial(j)
Next
WriteLine "</table>"

Dim seq : Set seq = New StringBuilder
For j = 0 To 10
    seq.Append(Fib(j)).Append(" ")
Next
WriteLine "<p>Fibonacci(0..10): <strong>" & HtmlEncode(Trim(seq.ToString())) & "</strong></p>"
DemoEnd
%>

<h2>Emulating an optional parameter</h2>
<%
DemoStart "PowerOf(base [, exp]) with an Empty sentinel default"
Dim noExp : ' noExp stays Empty
WriteLine "<p>PowerOf(9, Empty) = <strong>" & PowerOf(9, noExp) & "</strong> (defaulted exp to 2)</p>"
WriteLine "<p>PowerOf(2, 10) = <strong>" & PowerOf(2, 10) & "</strong></p>"
DemoEnd
%>
<!--#include file="includes/footer.asp"-->
