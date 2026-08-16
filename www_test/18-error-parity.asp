<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<%
Option Explicit
%>
<!--#include file="includes/helpers.asp"-->
<%
' ============================================================================
' 18-error-parity.asp - Err.Number must match IIS exactly
' ----------------------------------------------------------------------------
' Every expected value on this page was captured from a live IIS 10 /
' VBScript 10.8 server, not from the documentation. Err.NUMBER is the contract:
' it is locale-independent and it is what real code branches on. Err.Description
' is NOT checked, because IIS localises it - a Dutch server answers error 9 with
' "Het subscript valt buiten het bereik" - so there is no single correct string.
'
' The interesting cases are the ones where a permissive engine would silently
' succeed. Code that runs clean here but dies on IIS is the worst possible
' outcome for a compatibility runtime, so those get the most attention:
'
'   ReDim on a fixed-size array ......... 10, not "quietly resize it"
'   ReDim a(-2) ........................  7, not "treat as empty"
'   obj & "" ...........................450, not "stringify the object"
'   CBool("xyz") .......................  13, not False
'   Server.MapPath("") ................. E_FAIL, not the app root
'
' And the mirror image - things that are LEGAL on IIS and must not be broken by
' over-eager strictness: ReDim a(-1) is the idiomatic empty growable array.
' ============================================================================
Dim PageTitle : PageTitle = "Error Parity"
%>
<!--#include file="includes/header.asp"-->
<%
Dim PASSED, FAILED
PASSED = 0 : FAILED = 0

' Asserts Err.Number and clears it. Call immediately after the guarded line.
Sub ExpectErr(ByVal sLabel, ByVal nExpected)
    Dim actual, ok
    actual = Err.Number
    ok = (actual = nExpected)
    If ok Then PASSED = PASSED + 1 Else FAILED = FAILED + 1
    WriteLine "<tr><th scope=""row"">" & HtmlEncode(sLabel) & "</th><td>" & _
              nExpected & "</td><td>" & actual & "</td><td class=""" & _
              IIf(ok, "ok", "err") & """>" & IIf(ok, "PASS", "FAIL") & "</td></tr>"
    Err.Clear
End Sub

' Compares values. Booleans are asserted as CLng(...) - i.e. -1 / 0 - never as
' CStr(...), because IIS renders boolean literals through the OS user locale
' ("Waar"/"Onwaar" on a Dutch server) while ASPPY always writes "True"/"False".
Sub ExpectVal(ByVal sLabel, ByVal vExpected, ByVal vActual)
    Dim ok
    ok = (CStr(vExpected) = CStr(vActual))
    If ok Then PASSED = PASSED + 1 Else FAILED = FAILED + 1
    WriteLine "<tr><th scope=""row"">" & HtmlEncode(sLabel) & "</th><td>" & _
              HtmlEncode(CStr(vExpected)) & "</td><td>" & HtmlEncode(CStr(vActual)) & _
              "</td><td class=""" & IIf(ok, "ok", "err") & """>" & _
              IIf(ok, "PASS", "FAIL") & "</td></tr>"
    Err.Clear
End Sub
%>
<h1>Runtime Error Parity</h1>
<p class="lead">
  Expected values captured from live <strong>IIS 10 / VBScript 10.8</strong>.
  <code>Err.Number</code> only &mdash; <code>Err.Description</code> is localised
  by IIS and is deliberately not compared.
</p>

<h2>Arrays and ReDim</h2>
<table>
<thead><tr><th>Case</th><th>IIS</th><th>ASPPY</th><th>Result</th></tr></thead>
<tbody>
<%
Dim dynArr(), fixedArr(1), undim(), emptyArr, i, r
On Error Resume Next

ReDim dynArr(-1)
ExpectErr "ReDim a(-1) is legal", 0
ExpectVal "  ... and UBound is -1", -1, UBound(dynArr)

ExpectVal "UBound(Array())", -1, UBound(Array())
ExpectVal "UBound(Split(""""))", -1, UBound(Split(""))

' Growing the empty array: the standard VBScript list idiom.
For i = 0 To 2
    ReDim Preserve dynArr(UBound(dynArr) + 1)
    dynArr(UBound(dynArr)) = i
Next
ExpectErr "ReDim Preserve growth loop", 0
ExpectVal "  ... contents", "0 1 2", Join(dynArr)

r = UBound(undim)
ExpectErr "UBound() on un-ReDim'd Dim a()", 9

ReDim fixedArr(5)
ExpectErr "ReDim on fixed-size Dim a(1)", 10
ReDim Preserve fixedArr(5)
ExpectErr "ReDim Preserve on fixed-size array", 10

ReDim dynArr(-2)
ExpectErr "ReDim a(-2)", 7
ReDim dynArr(-5)
ExpectErr "ReDim a(-5)", 7

' Split/Filter results stay resizable.
emptyArr = Split("a,b", ",")
ReDim Preserve emptyArr(4)
ExpectErr "ReDim Preserve on a Split() result", 0
%>
</tbody>
</table>

<h2>Objects in expressions (default property)</h2>
<p>
  An operator reads an object's <strong>default property</strong> first. A
  <code>Scripting.Dictionary</code>'s default is <code>Item(key)</code>, which
  needs an argument &mdash; hence 450 rather than a silently stringified object.
</p>
<table>
<thead><tr><th>Case</th><th>IIS</th><th>ASPPY</th><th>Result</th></tr></thead>
<tbody>
<%
Dim d, o
Set d = Server.CreateObject("Scripting.Dictionary")
r = d + 1    : ExpectErr "dict + 1", 450
r = d - 1    : ExpectErr "dict - 1", 450
r = d * 2    : ExpectErr "dict * 2", 450
r = d & ""   : ExpectErr "dict & """"", 450
r = "" & d   : ExpectErr """"" & dict", 450
If d = 1 Then : End If
ExpectErr "dict = 1", 450

' Objects that DO have a parameterless default property keep working.
ExpectVal "Request.QueryString (no index)", "", Request.QueryString & ""
ExpectErr "  ... raises nothing", 0
ExpectVal "Request.Cookies(""missing"")", "", Request.Cookies("missing") & ""
ExpectErr "  ... raises nothing", 0
%>
</tbody>
</table>

<h2>Conversions, members and paths</h2>
<table>
<thead><tr><th>Case</th><th>IIS</th><th>ASPPY</th><th>Result</th></tr></thead>
<tbody>
<%
r = 1/0             : ExpectErr "1 / 0", 11
r = CInt(99999999)  : ExpectErr "CInt(99999999)", 6
r = CInt("abc")     : ExpectErr "CInt(""abc"")", 13
r = CBool("xyz")    : ExpectErr "CBool(""xyz"")", 13
r = CBool("")       : ExpectErr "CBool("""")", 13
ExpectVal "CBool(""True"")", -1, CLng(CBool("True"))
ExpectVal "CBool(""-1"")", -1, CLng(CBool("-1"))
ExpectVal "CBool(0)", 0, CLng(CBool(0))
Set o = Nothing
r = o.Anything      : ExpectErr "Nothing.Anything", 424
d.NoSuchMethod      : ExpectErr "dict.NoSuchMethod", 438
' 0x800401F3 CO_E_CLASSSTRING - NOT 429, which is what the docs suggest.
Set o = Server.CreateObject("No.Such.ProgID")
ExpectErr "CreateObject(""No.Such.ProgID"")", -2147221005
r = Server.MapPath("")
ExpectErr "Server.MapPath("""")", -2147467259

' Host-side internals must not be reachable from VBScript.
r = Response.finalize_headers : ExpectErr "Response.finalize_headers", 438
r = Session.CodePage_         : ExpectErr "Session.CodePage_", 438
ExpectVal "Session.CodePage still works", -1, CLng(IsNumeric(Session.CodePage))

' Err.Number is a signed Long: an HRESULT is never above 2147483647.
Err.Raise &H80004005
ExpectErr "Err.Raise &H80004005", -2147467259

' Session/Application are Variant stores: Null round-trips as Null.
Session("t_null") = Null
ExpectVal "Session stores Null as Null", "Null", TypeName(Session("t_null"))
ExpectVal "Session missing key is Empty", "Empty", TypeName(Session("t_never_set"))
Application("t_null") = Null
ExpectVal "Application stores Null as Null", "Null", TypeName(Application("t_null"))
Session.Contents.Remove("t_null")
Application.Contents.Remove("t_null")
Err.Clear

' Zero-argument builtins usable without parentheses.
ExpectVal "ScriptEngine (no parens)", "VBScript", ScriptEngine
ExpectVal "ScriptEngineMajorVersion", -1, CLng(IsNumeric(ScriptEngineMajorVersion))
ExpectVal "Now (no parens)", -1, CLng(IsDate(Now))
On Error GoTo 0
%>
</tbody>
</table>

<h2>Summary</h2>
<p>
  <span class="ok"><%= PASSED %> passed</span> &middot;
  <span class="<%= IIf(FAILED > 0, "err", "") %>"><%= FAILED %> failed</span>
</p>
<% If FAILED > 0 Then Response.Status = "500 Internal Server Error" %>
<!--#include file="includes/footer.asp"-->
