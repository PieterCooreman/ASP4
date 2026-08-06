<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<%
Option Explicit
%>
<!--#include file="includes/helpers.asp"-->
<%
' ============================================================================
' 12-conversion-edge.asp - Variant coercion, truthiness and comparison traps
' ----------------------------------------------------------------------------
' This is the "here be dragons" page. VBScript has ONE data type - the Variant -
' and it silently coerces values between subtypes. That implicit conversion is
' the source of most real-world bugs. A coding agent that internalises this page
' will avoid a whole class of mistakes.
'
' EDGE CASES covered:
'   * + vs & : "1" + 2 is 3 (numeric add) but "1" & 2 is "12" (concatenation).
'     And "a" + 2 RAISES a type-mismatch error - the demo guards it.
'   * Empty vs Null vs "" vs 0 - four different "nothings" with different rules.
'   * Comparisons with Null always yield Null (not True/False), so a naive
'     If x = Null Then ... is ALWAYS false. Use IsNull().
'   * Boolean coercion: True is -1, not 1; any non-zero number is "truthy".
'   * = (value equality) vs Is (object identity / Nothing test).
'   * CInt uses banker's rounding (round-half-to-even); Int vs Fix on negatives.
'   * VarType / TypeName to inspect what you actually have.
' ============================================================================
Dim PageTitle : PageTitle = "Conversion & Coercion Edge Cases"
%>
<!--#include file="includes/header.asp"-->
<%
' --- A tiny helper that performs an operation but never lets it crash -------
' Many cells in the tables below could raise a type mismatch. We wrap each
' expression in a function that returns either the result or the error text,
' so the whole page still renders. (We pass a string and Eval it - see page 14
' for the metaprogramming behind Eval.)
Function Try(ByVal expr)
    On Error Resume Next
    Dim v
    v = Eval(expr)
    If Err.Number <> 0 Then
        Try = "<span class=""err"">ERR " & Err.Number & ": " & Err.Description & "</span>"
        Err.Clear
    Else
        ' Show the subtype too, because that is the whole point of this page.
        Try = HtmlEncode(CStr(v)) & " <span class=""tag"">" & TypeName(v) & "</span>"
    End If
    On Error Goto 0
End Function

' Render a raw (already-HTML) value row, bypassing HtmlEncode so our
' colour-coded <span> markup survives.
Sub RawRow(ByVal label, ByVal htmlValue)
    WriteLine "<tr><th scope=""row"">" & HtmlEncode(label) & "</th><td>" & htmlValue & "</td></tr>"
End Sub
%>
<h1>Conversion &amp; Coercion Edge Cases</h1>
<p class="lead">
  VBScript has exactly one type - the <strong>Variant</strong> - and it converts
  between subtypes behind your back. These are the traps that produce the
  hardest-to-find bugs. Read every row carefully.
</p>

<h2>The classic: <code>+</code> vs <code>&amp;</code></h2>
<p>
  <code>&amp;</code> is the dedicated concatenation operator and converts both
  sides to strings. <code>+</code> is overloaded: with two numbers it adds, with
  two strings it concatenates, but with a string-that-looks-numeric and a number
  it <strong>adds</strong>, and with a non-numeric string and a number it
  <strong>raises a type mismatch</strong>. Use <code>&amp;</code> for text. Always.
</p>
<%
DemoStart "Watch + change its mind"
WriteLine "<table class=""kv"">"
RawRow "1 + 2",        Try("1 + 2")
RawRow """1"" + 2",    Try("""1"" + 2")
RawRow """1"" & 2",    Try("""1"" & 2")
RawRow """a"" + 2",    Try("""a"" + 2")
RawRow """a"" & 2",    Try("""a"" & 2")
RawRow """10"" + ""5""", Try("""10"" + ""5""")
RawRow """10"" & ""5""", Try("""10"" & ""5""")
WriteLine "</table>"
DemoEnd
%>

<h2>Four kinds of "nothing": Empty, Null, "" and 0</h2>
<p>
  These are <em>not</em> interchangeable. <strong>Empty</strong> is an
  uninitialised variable. <strong>Null</strong> is a deliberate "no value"
  (think database NULL). <strong>""</strong> is a real, zero-length string.
  <strong>0</strong> is the number zero. Each answers the type-test functions
  differently.
</p>
<%
DemoStart "Truth table of the four nothings"
Dim vEmpty            ' declared, never assigned -> Empty
Dim vNull   : vNull = Null
Dim vStr    : vStr  = ""
Dim vZero   : vZero = 0
WriteLine "<table class=""kv"">"
WriteLine "<tr><th scope=""row"">value &rarr;</th><td><strong>Empty</strong> | <strong>Null</strong> | <strong>&quot;&quot;</strong> | <strong>0</strong></td></tr>"
RenderTableRow "IsEmpty()",   IsEmpty(vEmpty)   & " | " & IsEmpty(vNull)   & " | " & IsEmpty(vStr)   & " | " & IsEmpty(vZero)
RenderTableRow "IsNull()",    IsNull(vEmpty)    & " | " & IsNull(vNull)    & " | " & IsNull(vStr)    & " | " & IsNull(vZero)
RenderTableRow "TypeName()",  TypeName(vEmpty)  & " | " & TypeName(vNull)  & " | " & TypeName(vStr)  & " | " & TypeName(vZero)
RenderTableRow "VarType()",   VarType(vEmpty)   & " | " & VarType(vNull)   & " | " & VarType(vStr)   & " | " & VarType(vZero)
RenderTableRow "Len()",       Len(vEmpty)       & " | " & "(Null->Null)"   & " | " & Len(vStr)       & " | " & Len(vZero)
RenderTableRow "value = 0 ?", (vEmpty = 0)      & " | " & "(Null)"         & " | " & "(type err)"    & " | " & (vZero = 0)
RenderTableRow "value = """" ?", (vEmpty = "")  & " | " & "(Null)"         & " | " & (vStr = "")     & " | " & "(0='' is False)"
WriteLine "</table>"
DemoEnd
%>

<h2>Comparisons with Null are contagious</h2>
<p>
  ANY comparison involving <code>Null</code> evaluates to <code>Null</code>, which
  is neither True nor False. So <code>If x = Null Then</code> is a bug that is
  <strong>always false</strong> - even when x really is Null. The only correct
  test is <code>IsNull(x)</code>.
</p>
<%
DemoStart "Why If x = Null never fires"
Dim x : x = Null
' If (x = Null) never enters the True branch because the test is Null, which
' VBScript treats as False for branching. We record which branch actually ran.
Dim branchTaken
If x = Null Then
    branchTaken = "TRUE branch (this never happens)"
Else
    branchTaken = "ELSE branch (always - even though x really is Null)"
End If
WriteLine "<table class=""kv"">"
RenderTableRow "TypeName(x = Null)",            TypeName(x = Null) & "  (the comparison is Null, not Boolean)"
RenderTableRow "If (x = Null) Then ... ran:",   branchTaken
RenderTableRow "IsNull(x)  (the correct test)", IsNull(x)
WriteLine "</table>"
WriteLine "<p class=""warn"">Lesson: never compare to Null with =, &lt;&gt;, &lt; or &gt;. Use IsNull().</p>"
DemoEnd
%>

<h2>Boolean coercion: True is -1</h2>
<p>
  When a Boolean becomes a number, <code>True</code> is <strong>-1</strong> (all
  bits set) and <code>False</code> is <strong>0</strong>. Conversely, when a number
  becomes a Boolean, <strong>any non-zero value is True</strong>. This matters for
  <code>And</code>/<code>Or</code>, which are <em>bitwise</em>, not short-circuit,
  operators.
</p>
<%
DemoStart "Numeric face of Booleans"
WriteLine "<table class=""kv"">"
RenderTableRow "CInt(True)",            CInt(True)  & "  (not 1!)"
RenderTableRow "CInt(False)",           CInt(False)
RenderTableRow "CBool(0) / CBool(5)",   CBool(0) & " / " & CBool(5)
RenderTableRow "CBool(-273)",           CBool(-273) & "  (any non-zero -> True)"
RenderTableRow "True + True",           (True + True) & "  (-1 + -1)"
RenderTableRow "5 And 3 (bitwise)",     (5 And 3) & "  (0101 AND 0011 = 0001)"
RenderTableRow "4 Or 1 (bitwise)",      (4 Or 1)  & "  (100 OR 001 = 101)"
WriteLine "</table>"
WriteLine "<p class=""warn"">And/Or are bitwise: <code>If (obj Is Nothing) Or obj.Ready</code> will STILL evaluate obj.Ready and crash. There is no short-circuit in VBScript.</p>"
DemoEnd
%>

<h2><code>=</code> (value) vs <code>Is</code> (identity)</h2>
<p>
  For primitives you compare with <code>=</code>. For objects you compare
  reference identity with <code>Is</code>, and you test "no object" with
  <code>Is Nothing</code>. Using <code>=</code> on objects invokes their default
  property (or errors), which is rarely what you want.
</p>
<%
DemoStart "Object identity"
Dim a, b, c
Set a = New StringBuilder
Set b = a                      ' b points at the SAME object as a
Set c = New StringBuilder      ' a brand-new, different object
WriteLine "<table class=""kv"">"
RenderTableRow "a Is b  (same instance)",      (a Is b)
RenderTableRow "a Is c  (different instance)", (a Is c)
RenderTableRow "c Is Nothing",                 (c Is Nothing)
Set c = Nothing
RenderTableRow "after Set c = Nothing: c Is Nothing", (c Is Nothing)
WriteLine "</table>"
DemoEnd
%>

<h2>Rounding traps: banker's rounding and Int vs Fix</h2>
<p>
  <code>CInt</code>/<code>CLng</code>/<code>Round</code> use <strong>banker's
  rounding</strong> (round-half-to-<em>even</em>), so 0.5 and 2.5 both round to
  the nearest even number. And on negatives, <code>Int</code> rounds <em>down</em>
  (toward -&infin;) while <code>Fix</code> truncates toward zero.
</p>
<%
DemoStart "Rounding is not what you learned in school"
WriteLine "<table class=""kv"">"
RenderTableRow "Round(0.5)",   Round(0.5)  & "  (-> 0, nearest even)"
RenderTableRow "Round(1.5)",   Round(1.5)  & "  (-> 2, nearest even)"
RenderTableRow "Round(2.5)",   Round(2.5)  & "  (-> 2, nearest even!)"
RenderTableRow "Round(3.5)",   Round(3.5)  & "  (-> 4)"
RenderTableRow "CInt(2.5)",    CInt(2.5)   & "  (banker's too)"
RenderTableRow "Int(-2.7)",    Int(-2.7)   & "  (floor, toward -inf)"
RenderTableRow "Fix(-2.7)",    Fix(-2.7)   & "  (truncate toward zero)"
RenderTableRow "Int(2.7) / Fix(2.7)", Int(2.7) & " / " & Fix(2.7) & "  (same for positives)"
WriteLine "</table>"
DemoEnd
%>

<h2>IsNumeric: looser than you think</h2>
<p>
  <code>IsNumeric</code> accepts leading/trailing spaces, scientific notation
  and VBScript hex literals (<code>&amp;hFF</code>) - but rejects C-style hex
  (<code>0xFF</code>). Crucially it is <strong>locale-sensitive</strong>: whether
  <code>"$1,234.50"</code> counts as numeric depends on the server's currency,
  decimal and thousands separators. (On this Dutch-locale server it is rejected,
  because <code>,</code> is the decimal sign and <code>.</code> the thousands
  sign here.) Don't assume <code>IsNumeric</code> means "all digits".
</p>
<%
DemoStart "Surprising IsNumeric results"
Dim probes, pr
probes = Array("123", "  123  ", "$1,234.50", "1E3", "&hFF", "0xFF", "12abc", "", "-.5", "1.2.3")
WriteLine "<table class=""kv"">"
For Each pr In probes
    RenderTableRow "IsNumeric(""" & pr & """)", IsNumeric(pr)
Next
WriteLine "</table>"
DemoEnd
%>

<h2>Pattern reference</h2>
<%
CodeBlock _
    "' Concatenate with & (never + for text):" & vbCrLf & _
    "msg = ""Total: "" & total            ' safe" & vbCrLf & _
    "msg = ""Total: "" + total            ' BUG if total is numeric-looking" & vbCrLf & vbCrLf & _
    "' Test for ""no value"" the right way:" & vbCrLf & _
    "If IsNull(x) Then ...                ' NOT  If x = Null" & vbCrLf & _
    "If IsEmpty(x) Then ...               ' uninitialised variable" & vbCrLf & _
    "If obj Is Nothing Then ...           ' missing object" & vbCrLf & vbCrLf & _
    "' VBScript has no short-circuit - guard in nested Ifs:" & vbCrLf & _
    "If Not (obj Is Nothing) Then" & vbCrLf & _
    "    If obj.Ready Then ...            ' only reached when obj exists" & vbCrLf & _
    "End If" & vbCrLf & vbCrLf & _
    "' Round() is banker's rounding (half-to-even):" & vbCrLf & _
    "Round(2.5)   ' = 2, not 3"
%>
<!--#include file="includes/footer.asp"-->
