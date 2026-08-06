<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<%
Option Explicit
%>
<!--#include file="includes/helpers.asp"-->
<%
' ============================================================================
' 02-control-flow.asp - Decision and looping constructs
' Demonstrates: If/ElseIf/Else, Select Case, For...Next (with Step),
' For Each, Do While, Do Until, and While...Wend.
' ============================================================================
Dim PageTitle : PageTitle = "Control Flow"
%>
<!--#include file="includes/header.asp"-->
<%
' --- Helper used by the demos below ---------------------------------------
Function Classify(ByVal n)
    If n < 0 Then
        Classify = "negative"
    ElseIf n = 0 Then
        Classify = "zero"
    ElseIf n < 10 Then
        Classify = "single digit"
    Else
        Classify = "large"
    End If
End Function

Function DayKind(ByVal d)
    Select Case d
        Case "Sat", "Sun"
            DayKind = "weekend"
        Case "Mon", "Tue", "Wed", "Thu", "Fri"
            DayKind = "weekday"
        Case Else
            DayKind = "unknown"
    End Select
End Function
%>
<h1>Control Flow</h1>
<p class="lead">Branching with If / Select Case and iterating with every loop kind.</p>

<h2>If / ElseIf / Else</h2>
<%
DemoStart "Classify(n) over several inputs"
WriteLine "<table class=""kv"">"
Dim testVals, v
testVals = Array(-4, 0, 7, 99)
For Each v In testVals
    RenderTableRow "Classify(" & v & ")", Classify(v)
Next
WriteLine "</table>"
DemoEnd
%>

<h2>Select Case</h2>
<%
DemoStart "DayKind() mapping short day names"
WriteLine "<table class=""kv"">"
Dim days, d
days = Array("Mon", "Wed", "Sat", "Sun", "Foo")
For Each d In days
    RenderTableRow d, DayKind(d)
Next
WriteLine "</table>"
DemoEnd
%>

<h2>For...Next with Step</h2>
<%
DemoStart "Even numbers 0..10 then a countdown"
Dim i, sb1 : Set sb1 = New StringBuilder
For i = 0 To 10 Step 2
    sb1.Append(i).Append(" ")
Next
WriteLine "<p>Up by 2: <strong>" & HtmlEncode(Trim(sb1.ToString())) & "</strong></p>"

Dim sb2 : Set sb2 = New StringBuilder
For i = 5 To 1 Step -1
    sb2.Append(i).Append(" ")
Next
WriteLine "<p>Down: <strong>" & HtmlEncode(Trim(sb2.ToString())) & "</strong></p>"
DemoEnd
%>

<h2>For Each over a collection</h2>
<%
DemoStart "Iterating an array of fruit"
Dim fruit, f, list : Set list = New StringBuilder
fruit = Array("apple", "banana", "cherry", "date")
For Each f In fruit
    list.AppendLine "<li>" & HtmlEncode(f) & "</li>"
Next
WriteLine "<ul>" & list.ToString() & "</ul>"
DemoEnd
%>

<h2>Do While / Do Until / While...Wend</h2>
<%
DemoStart "Three loops that all sum 1..5"
Dim n, total

' Do While (test at top)
n = 1 : total = 0
Do While n <= 5
    total = total + n
    n = n + 1
Loop
WriteLine "<p>Do While result: <strong>" & total & "</strong></p>"

' Do Until (loop until condition becomes true)
n = 1 : total = 0
Do Until n > 5
    total = total + n
    n = n + 1
Loop
WriteLine "<p>Do Until result: <strong>" & total & "</strong></p>"

' While...Wend (legacy form)
n = 1 : total = 0
While n <= 5
    total = total + n
    n = n + 1
Wend
WriteLine "<p>While...Wend result: <strong>" & total & "</strong></p>"
DemoEnd
%>

<h2>Early exit with Exit For</h2>
<%
DemoStart "Find first value > 100 in a list"
Dim nums, found : found = "none"
nums = Array(3, 27, 64, 150, 8)
For Each n In nums
    If n > 100 Then
        found = n
        Exit For
    End If
Next
WriteLine "<p>First value over 100: <strong>" & HtmlEncode(found) & "</strong></p>"
DemoEnd
%>
<!--#include file="includes/footer.asp"-->
