<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<%
Option Explicit
%>
<!--#include file="includes/helpers.asp"-->
<%
' ============================================================================
' 01-basics.asp - VBScript language fundamentals
' Demonstrates: variable declaration, the Variant type and its subtypes,
' arithmetic / comparison / logical operators, constants and type tests.
' ============================================================================
Dim PageTitle : PageTitle = "Language Basics"
%>
<!--#include file="includes/header.asp"-->
<%
' --- Constants -------------------------------------------------------------
Const PI = 3.14159265358979
Const APP_NAME = "VBScript Basics"

' --- Variables & subtypes --------------------------------------------------
Dim anInteger, aDouble, aString, aBoolean, aDate, aNull, anEmpty
anInteger = 42
aDouble   = 3.5 * 2
aString   = "Hello, IIS"
aBoolean  = (10 > 3)
aDate     = CDate("2026-06-05 14:30:00")
aNull     = Null
' anEmpty is intentionally left uninitialised (subtype Empty)
%>
<h1>Language Basics</h1>
<p class="lead">Variants, subtypes, operators and constants in <%= HtmlEncode(APP_NAME) %>.</p>

<h2>Variables and their Variant subtypes</h2>
<%
DemoStart "VarType / TypeName of each value"
WriteLine "<table class=""kv"">"
RenderTableRow "anInteger = 42",            TypeName(anInteger) & " (VarType " & VarType(anInteger) & ")"
RenderTableRow "aDouble = 3.5 * 2",         TypeName(aDouble)   & " = " & aDouble
RenderTableRow "aString = ""Hello, IIS""",  TypeName(aString)
RenderTableRow "aBoolean = (10 > 3)",       TypeName(aBoolean)  & " = " & aBoolean
RenderTableRow "aDate",                     TypeName(aDate)     & " = " & aDate
RenderTableRow "aNull",                     TypeName(aNull)     & " (IsNull=" & IsNull(aNull) & ")"
RenderTableRow "anEmpty (uninitialised)",   TypeName(anEmpty)   & " (IsEmpty=" & IsEmpty(anEmpty) & ")"
WriteLine "</table>"
DemoEnd
%>

<h2>Arithmetic operators</h2>
<%
DemoStart "7 and 2 through every arithmetic operator"
Dim x, y : x = 7 : y = 2
WriteLine "<table class=""kv"">"
RenderTableRow "x + y  (add)",          x + y
RenderTableRow "x - y  (subtract)",     x - y
RenderTableRow "x * y  (multiply)",     x * y
RenderTableRow "x / y  (float divide)", x / y
RenderTableRow "x \ y  (integer div)",  x \ y
RenderTableRow "x Mod y (remainder)",   x Mod y
RenderTableRow "x ^ y  (exponent)",     x ^ y
RenderTableRow "x & y  (concatenate)",  x & y
WriteLine "</table>"
DemoEnd
%>

<h2>Comparison and logical operators</h2>
<%
DemoStart "Boolean logic"
WriteLine "<table class=""kv"">"
RenderTableRow "5 = 5",                  (5 = 5)
RenderTableRow "5 <> 6",                 (5 <> 6)
RenderTableRow "(5 > 3) And (2 < 1)",    ((5 > 3) And (2 < 1))
RenderTableRow "(5 > 3) Or (2 < 1)",     ((5 > 3) Or (2 < 1))
RenderTableRow "Not (1 = 1)",            (Not (1 = 1))
RenderTableRow "10 Xor 6 (bitwise)",     (10 Xor 6)
WriteLine "</table>"
DemoEnd
%>

<h2>Constants and conversion functions</h2>
<%
DemoStart "Using Const PI and Cxxx converters"
WriteLine "<table class=""kv"">"
RenderTableRow "PI",                    PI
RenderTableRow "CInt(""123"")",         CInt("123")
RenderTableRow "CDbl(""3.14"")",        CDbl("3.14")
RenderTableRow "CStr(2026)",            CStr(2026)
RenderTableRow "CBool(0) / CBool(5)",   CBool(0) & " / " & CBool(5)
RenderTableRow "Round(PI, 2)",          Round(PI, 2)
RenderTableRow "Int(-2.7) / Fix(-2.7)", Int(-2.7) & " / " & Fix(-2.7)
WriteLine "</table>"
DemoEnd
%>

<h2>Source of the operators demo</h2>
<%
CodeBlock _
    "Dim x, y : x = 7 : y = 2" & vbCrLf & _
    "Response.Write x \ y    ' integer division -> 3" & vbCrLf & _
    "Response.Write x Mod y  ' remainder        -> 1" & vbCrLf & _
    "Response.Write x ^ y    ' exponent         -> 49"
%>
<!--#include file="includes/footer.asp"-->
