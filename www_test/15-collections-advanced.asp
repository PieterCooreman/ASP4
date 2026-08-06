<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<%
Option Explicit
%>
<!--#include file="includes/helpers.asp"-->
<%
' ============================================================================
' 15-collections-advanced.asp - Arrays & Dictionary, the deep end
' ----------------------------------------------------------------------------
' Page 05 covered the basics. This page goes after the EDGE CASES and the
' algorithms agents actually need:
'
'   * Multidimensional arrays vs JAGGED arrays (array-of-arrays) - they look
'     similar but index, ReDim and iterate completely differently.
'   * ReDim Preserve only lets you resize the LAST dimension of a multidim
'     array - a hard rule that trips people up.
'   * UBound(a, dim) to measure each dimension; the empty-array problem where
'     UBound returns -1 (so "length" is UBound+1, which is 0 for empty).
'   * The Filter() function (substring include/exclude over a string array) and
'     its case-sensitivity flag.
'   * Array() always builds a 0-based Variant array regardless of Option Base.
'   * Scripting.Dictionary as an ordered map: .Keys/.Items return parallel
'     arrays, CompareMode for case-insensitive keys, and the .Item auto-add
'     gotcha (reading a missing key CREATES it).
'   * A from-scratch Bubble Sort and a Dictionary-based word-frequency counter.
' ============================================================================
Dim PageTitle : PageTitle = "Arrays & Dictionary (Advanced)"
%>
<!--#include file="includes/header.asp"-->
<%
' --- In-place Bubble Sort on a 1D array (ascending) ------------------------
' Classic O(n^2) sort, written out so the swap logic is visible. VBScript passes
' arrays ByRef by default, so this sorts the caller's array in place.
Sub BubbleSort(ByRef arr)
    Dim i, j, tmp
    For i = 0 To UBound(arr) - 1
        For j = 0 To UBound(arr) - 1 - i        ' largest "bubbles" to the end
            If arr(j) > arr(j + 1) Then
                tmp = arr(j) : arr(j) = arr(j + 1) : arr(j + 1) = tmp
            End If
        Next
    Next
End Sub

' --- Word-frequency counter using a Dictionary -----------------------------
' Demonstrates the canonical "count things" pattern: check Exists, then either
' Add or increment. Returns the populated Dictionary.
Function WordFrequencies(ByVal text)
    Dim d : Set d = Server.CreateObject("Scripting.Dictionary")
    d.CompareMode = 1                            ' 1 = TextCompare -> case-insensitive keys
    Dim words, w
    words = Split(LCase(Trim(text)), " ")
    For Each w In words
        w = Trim(w)
        If Len(w) > 0 Then
            If d.Exists(w) Then
                d(w) = d(w) + 1                  ' increment existing
            Else
                d.Add w, 1                       ' first sighting
            End If
        End If
    Next
    Set WordFrequencies = d
End Function
%>
<h1>Arrays &amp; Dictionary (Advanced)</h1>
<p class="lead">
  Multidimensional vs jagged arrays, <code>ReDim Preserve</code> rules,
  <code>Filter</code>, and the <code>Scripting.Dictionary</code> as a real map -
  plus a hand-written sort and a word counter.
</p>

<h2>Multidimensional array (a true grid)</h2>
<p>
  Declared with commas: <code>Dim grid(2, 3)</code> is a rectangular 3&times;4 grid.
  You measure each axis with <code>UBound(grid, 1)</code> and
  <code>UBound(grid, 2)</code>. Every cell exists at once.
</p>
<%
DemoStart "A 3x4 multiplication grid"
Dim grid(2, 3)          ' dimensions are 0..2 and 0..3
Dim r, c
For r = 0 To UBound(grid, 1)
    For c = 0 To UBound(grid, 2)
        grid(r, c) = (r + 1) * (c + 1)
    Next
Next
WriteLine "<pre class=""code"">"
For r = 0 To UBound(grid, 1)
    For c = 0 To UBound(grid, 2)
        Response.Write Right("   " & grid(r, c), 4)
    Next
    Response.Write vbCrLf
Next
WriteLine "</pre>"
WriteLine "<p>Dimension 1 upper bound = " & UBound(grid, 1) & ", dimension 2 = " & UBound(grid, 2) & ".</p>"
DemoEnd
%>

<h2>Jagged array (array of arrays)</h2>
<p>
  A jagged array stores arrays as elements, so each "row" can have a
  <strong>different length</strong>. You index it with chained parentheses:
  <code>jag(1)(2)</code>. This is what <code>Array(Array(...), ...)</code> builds.
</p>
<%
DemoStart "Rows of differing lengths"
Dim jag
jag = Array( _
    Array("a"), _
    Array("b", "c", "d"), _
    Array("e", "f") _
)
WriteLine "<table class=""kv"">"
Dim ji
For ji = 0 To UBound(jag)
    RenderTableRow "jag(" & ji & ") has " & (UBound(jag(ji)) + 1) & " items", Join(jag(ji), ", ")
Next
RenderTableRow "Direct access jag(1)(2)", jag(1)(2)
WriteLine "</table>"
DemoEnd
%>

<h2>ReDim Preserve: only the last dimension</h2>
<p>
  <code>ReDim Preserve</code> can grow a dynamic array <strong>without losing
  data</strong>, but for a multidimensional array you may only resize the
  <em>last</em> dimension - resizing any other dimension raises an error. The demo
  shows a successful 1D grow and a guarded illegal 2D resize.
</p>
<%
DemoStart "Legal vs illegal ReDim Preserve"
Dim dyn()
ReDim dyn(2)
dyn(0) = "x" : dyn(1) = "y" : dyn(2) = "z"
ReDim Preserve dyn(4)            ' legal: grow a 1D array
dyn(3) = "w" : dyn(4) = "!"
WriteLine "<table class=""kv"">"
RenderTableRow "After ReDim Preserve dyn(4)", Join(dyn, ", ")

' Start with a 2x2 grid: m2(1,1). The LAST dimension is the second subscript.
Dim m2()
ReDim m2(1, 1)
On Error Resume Next
ReDim Preserve m2(1, 3)         ' LEGAL: only the last dimension grows (1 -> 3)
RenderTableRow "Preserve LAST dim  m2(1,3)", IIf(Err.Number = 0, "OK - allowed", "ERR: " & Err.Description)
Err.Clear
ReDim Preserve m2(3, 3)         ' ILLEGAL: this also changes the FIRST dimension
RenderTableRow "Preserve FIRST dim m2(3,3)", IIf(Err.Number = 0, "OK", "ERR " & Err.Number & ": " & Err.Description & " (changing a non-last dim is forbidden)")
Err.Clear
On Error Goto 0
WriteLine "</table>"
DemoEnd
%>

<h2>The empty-array trap: UBound = -1</h2>
<p>
  An array with no elements has <code>UBound = -1</code>, so its "length" is
  <code>UBound + 1 = 0</code>. Always compute length as <code>UBound(a) + 1</code>
  and guard loops, or <code>For i = 0 To -1</code> simply won't execute (which is
  actually the desired behaviour).
</p>
<%
DemoStart "Length the safe way"
Dim emptyArr : emptyArr = Array()            ' zero elements
Dim oneArr   : oneArr   = Array("solo")
WriteLine "<table class=""kv"">"
RenderTableRow "UBound(Array())",         UBound(emptyArr) & "  (-1!)"
RenderTableRow "Length = UBound + 1",     (UBound(emptyArr) + 1)
RenderTableRow "UBound(Array(""solo""))", UBound(oneArr) & "  -> length " & (UBound(oneArr) + 1)
WriteLine "</table>"
DemoEnd
%>

<h2>The Filter function</h2>
<p>
  <code>Filter(arr, substr)</code> returns a new array of the elements that
  <strong>contain</strong> a substring; pass <code>False</code> as the third
  argument to invert it (elements that do NOT contain it). A fourth argument sets
  case sensitivity.
</p>
<%
DemoStart "Include and exclude"
Dim files
files = Array("index.asp", "style.css", "app.js", "about.asp", "data.json", "main.js")
WriteLine "<table class=""kv"">"
RenderTableRow "All files",                     Join(files, ", ")
RenderTableRow "Filter(.., "".asp"")",          Join(Filter(files, ".asp"), ", ")
RenderTableRow "Filter(.., "".js"")",           Join(Filter(files, ".js"), ", ")
RenderTableRow "Filter(.., "".asp"", False)",   Join(Filter(files, ".asp", False), ", ") & "  (everything else)"
WriteLine "</table>"
DemoEnd
%>

<h2>Hand-written Bubble Sort</h2>
<%
DemoStart "Sorting an array in place"
Dim toSort : toSort = Array(5, 2, 9, 1, 7, 3, 8, 4, 6)
WriteLine "<table class=""kv"">"
RenderTableRow "Before", Join(toSort, ", ")
BubbleSort toSort           ' sorts in place (arrays are ByRef)
RenderTableRow "After",  Join(toSort, ", ")
WriteLine "</table>"
DemoEnd
%>

<h2>Dictionary as an ordered map</h2>
<p>
  <code>Scripting.Dictionary</code> preserves insertion order and exposes
  <code>.Keys</code> and <code>.Items</code> as <strong>parallel arrays</strong>.
  Set <code>.CompareMode = 1</code> for case-insensitive keys.
</p>
<%
DemoStart "Keys and Items in parallel"
Dim caps : Set caps = Server.CreateObject("Scripting.Dictionary")
caps.Add "France",  "Paris"
caps.Add "Japan",   "Tokyo"
caps.Add "Brazil",  "Brasilia"
Dim keysArr, itemsArr, ix
keysArr  = caps.Keys             ' array of keys, in insertion order
itemsArr = caps.Items            ' array of values, same order
WriteLine "<table class=""kv"">"
For ix = 0 To caps.Count - 1
    RenderTableRow keysArr(ix), itemsArr(ix)
Next
WriteLine "</table>"
DemoEnd
%>

<h2>The Dictionary auto-add gotcha</h2>
<p>
  Reading a <strong>missing</strong> key with <code>d(key)</code> does not error -
  it silently <strong>creates</strong> that key with an Empty value and grows the
  Dictionary. Always guard reads with <code>.Exists()</code> if that side effect
  would surprise you.
</p>
<%
DemoStart "Reading a missing key changes Count"
Dim dd : Set dd = Server.CreateObject("Scripting.Dictionary")
dd.Add "known", 1
WriteLine "<table class=""kv"">"
RenderTableRow "Count before",                 dd.Count
Dim sink : sink = dd("ghost")                  ' merely READING "ghost" adds it!
RenderTableRow "After reading dd(""ghost"")",   "value=[" & sink & "] (Empty)"
RenderTableRow "Count after (grew!)",          dd.Count
RenderTableRow "dd.Exists(""ghost"") now",      dd.Exists("ghost")
WriteLine "</table>"
WriteLine "<p class=""warn"">Guard with: If d.Exists(k) Then v = d(k)</p>"
DemoEnd
%>

<h2>Word-frequency counter</h2>
<%
DemoStart "Counting words with a case-insensitive Dictionary"
Dim sample : sample = "the cat sat on the mat the cat was happy THE END"
Dim freq : Set freq = WordFrequencies(sample)
WriteLine "<p>Input: <em>" & HtmlEncode(sample) & "</em></p>"
WriteLine "<table class=""kv"">"
Dim wkey
For Each wkey In freq.Keys
    RenderTableRow wkey, freq(wkey)
Next
WriteLine "</table>"
WriteLine "<p class=""ok"">" & freq.Count & " distinct words counted (case-insensitive).</p>"
DemoEnd
%>

<h2>Pattern reference</h2>
<%
CodeBlock _
    "' Multidimensional vs jagged:" & vbCrLf & _
    "Dim grid(2,3)          ' rectangular - grid(r,c)" & vbCrLf & _
    "jag = Array(Array(1,2), Array(3,4,5))   ' jagged - jag(0)(1)" & vbCrLf & vbCrLf & _
    "' ReDim Preserve: ONLY the last dimension may change size." & vbCrLf & _
    "ReDim Preserve a(newSize)" & vbCrLf & vbCrLf & _
    "' Empty array length is UBound+1 (UBound alone is -1):" & vbCrLf & _
    "n = UBound(a) + 1" & vbCrLf & vbCrLf & _
    "' Dictionary: guard reads or you auto-create keys!" & vbCrLf & _
    "If d.Exists(k) Then v = d(k)" & vbCrLf & _
    "d.CompareMode = 1      ' case-insensitive keys" & vbCrLf & _
    "keys = d.Keys : items = d.Items   ' parallel arrays"
%>
<!--#include file="includes/footer.asp"-->
