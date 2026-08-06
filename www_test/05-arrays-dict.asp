<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<%
Option Explicit
%>
<!--#include file="includes/helpers.asp"-->
<%
' ============================================================================
' 05-arrays-dict.asp - Arrays and the Scripting.Dictionary
' Demonstrates: static arrays, dynamic arrays with ReDim/ReDim Preserve,
' multidimensional arrays, array functions, and a full Dictionary workflow.
' ============================================================================
Dim PageTitle : PageTitle = "Arrays & Dictionary"
%>
<!--#include file="includes/header.asp"-->
<%
' --- A reusable bubble sort (shows passing/returning arrays ByRef) ---------
Sub BubbleSort(ByRef arr)
    Dim i, j, tmp
    For i = 0 To UBound(arr) - 1
        For j = 0 To UBound(arr) - 1 - i
            If arr(j) > arr(j + 1) Then
                tmp = arr(j) : arr(j) = arr(j + 1) : arr(j + 1) = tmp
            End If
        Next
    Next
End Sub
%>
<h1>Arrays &amp; Dictionary</h1>
<p class="lead">Static, dynamic and multidimensional arrays, plus the Scripting.Dictionary.</p>

<h2>Static array + array functions</h2>
<%
DemoStart "Array(), UBound, Join, Filter, sorting"
Dim colors
colors = Array("red", "green", "blue", "amber")
WriteLine "<table class=""kv"">"
RenderTableRow "colors via Join", Join(colors, ", ")
RenderTableRow "UBound(colors)",  UBound(colors)
RenderTableRow "Count",           UBound(colors) + 1
RenderTableRow "Filter for 'e'",  Join(Filter(colors, "e"), ", ")
WriteLine "</table>"

Dim nums : nums = Array(9, 1, 7, 3, 8, 2)
WriteLine "<p>Before sort: <strong>" & Join(nums, " ") & "</strong></p>"
BubbleSort nums
WriteLine "<p>After sort:&nbsp; <strong>" & Join(nums, " ") & "</strong></p>"
DemoEnd
%>

<h2>Dynamic array with ReDim Preserve</h2>
<%
DemoStart "Grow an array at runtime, keeping existing values"
Dim dyn(), count, i
count = 0
ReDim dyn(2)            ' start with room for 3
For i = 1 To 6
    If i - 1 > UBound(dyn) Then
        ReDim Preserve dyn(UBound(dyn) + 3)   ' grow, keep data
    End If
    dyn(i - 1) = i * i
    count = count + 1
Next
ReDim Preserve dyn(count - 1)   ' trim to exact size
WriteLine "<p>Squares: <strong>" & Join(dyn, ", ") & "</strong></p>"
WriteLine "<p>Final UBound: <strong>" & UBound(dyn) & "</strong></p>"
DemoEnd
%>

<h2>Multidimensional array (a grid)</h2>
<%
DemoStart "A 3x3 multiplication grid built with a 2D array"
Dim grid(2, 2), r, c
For r = 0 To 2
    For c = 0 To 2
        grid(r, c) = (r + 1) * (c + 1)
    Next
Next
WriteLine "<table class=""kv"">"
For r = 0 To 2
    Dim rowSb : Set rowSb = New StringBuilder
    For c = 0 To 2
        rowSb.Append(grid(r, c)).Append("  ")
    Next
    RenderTableRow "Row " & r, Trim(rowSb.ToString())
Next
WriteLine "</table>"
DemoEnd
%>

<h2>Scripting.Dictionary</h2>
<%
DemoStart "Key/value store: Add, Exists, Keys, Items, Remove"
Dim dict : Set dict = Server.CreateObject("Scripting.Dictionary")
dict.CompareMode = 1   ' 1 = TextCompare (case-insensitive keys)
dict.Add "name",    "Grace Hopper"
dict.Add "role",    "Computer Scientist"
dict.Add "born",    1906
dict.Add "language","COBOL"

WriteLine "<table class=""kv"">"
Dim key
For Each key In dict.Keys
    RenderTableRow key, dict(key)
Next
WriteLine "</table>"

WriteLine "<p>Exists(""NAME"") [case-insensitive]: <strong>" & dict.Exists("NAME") & "</strong></p>"
dict.Remove "language"
WriteLine "<p>After Remove(""language""), count = <strong>" & dict.Count & "</strong></p>"
WriteLine "<p>All keys: <strong>" & HtmlEncode(Join(dict.Keys, ", ")) & "</strong></p>"
Set dict = Nothing
DemoEnd
%>
<!--#include file="includes/footer.asp"-->
