<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<%
Option Explicit
%>
<!--#include file="includes/helpers.asp"-->
<%
' ============================================================================
' 23-includes.asp - SSI #include resolution and expansion semantics
' ----------------------------------------------------------------------------
' Every behaviour asserted here was compared against IIS 10 serving the same
' folder, over 27 generated cases. Highlights:
'
'   file="x"      resolves relative to the file holding the directive, so a
'                 nested .inc picks up its OWN siblings, not the page's.
'   virtual="/x"  always resolves from the site root, at any nesting depth.
'   twice         including the same file twice EXPANDS IT TWICE. ASPPY used to
'                 carry one "visited" set for the whole request, which silently
'                 dropped the second copy; cycle detection now walks the current
'                 include chain instead, so repeats survive and loops still fail.
'
' A genuine cycle (a includes b includes a) is a hard 500 on both runtimes, so
' it cannot be asserted from inside a page - it is covered by the external
' comparison harness rather than here.
'
' The directives below are deliberately written in awkward ways (backslashes,
' "./", odd spacing) because IIS accepts all of them.
' ============================================================================
Dim PageTitle : PageTitle = "SSI Includes"
%>
<!--#include file="includes/header.asp"-->
<%
Dim PASSED, FAILED, SKIPPED
PASSED = 0 : FAILED = 0 : SKIPPED = 0

Sub Row(sLabel, sExpected, sActual, sVerdict)
    Dim cls
    Select Case sVerdict
        Case "PASS" : cls = "ok"  : PASSED = PASSED + 1
        Case "FAIL" : cls = "err" : FAILED = FAILED + 1
        Case Else   : cls = ""    : SKIPPED = SKIPPED + 1
    End Select
    WriteLine "<tr><th scope=""row"">" & HtmlEncode(sLabel) & "</th><td>" & _
              HtmlEncode(CStr(sExpected)) & "</td><td>" & HtmlEncode(CStr(sActual)) & _
              "</td><td class=""" & cls & """>" & sVerdict & "</td></tr>"
End Sub

Sub Expect(sLabel, vExpected, vActual)
    Row sLabel, vExpected, vActual, IIf(CStr(vExpected) = CStr(vActual), "PASS", "FAIL")
End Sub

' The fixtures write into the response, so each case is captured by buffering
' a fresh chunk: Flush is not available here, so instead the .inc files append
' to a module-level collector that we read and reset between cases.
Dim COLLECT
COLLECT = ""
%>
<h1>SSI Includes</h1>
<p class="lead">
  Resolution of <code>file=</code> vs <code>virtual=</code>, and the expansion
  rules for repeated includes. Verified against IIS 10 on the same folder.
</p>

<h2>Resolution base</h2>
<table>
<thead><tr><th>Check</th><th>Expected</th><th>Actual</th><th>Result</th></tr></thead>
<tbody>
<%
' --- file= is relative to THIS page -----------------------------------------
COLLECT = ""
%><!--#include file="inctest/mark.inc"--><%
Expect "file= relative to the page", "[M]", COLLECT

' --- file= inside an .inc is relative to that .inc, not the page ------------
' sub/nest.inc says  file="leaf.inc"  and must find sub/leaf.inc.
COLLECT = ""
%><!--#include file="inctest/sub/nest.inc"--><%
Expect "file= inside an include uses the include's folder", "[N:[LEAF]]", COLLECT

' --- backslashes are accepted as separators ---------------------------------
COLLECT = ""
%><!--#include file="inctest\mark.inc"--><%
Expect "backslash separator", "[M]", COLLECT

' --- a leading ./ is accepted ------------------------------------------------
COLLECT = ""
%><!--#include file="./inctest/mark.inc"--><%
Expect "./ prefix", "[M]", COLLECT

' --- .. climbs out of a subfolder and back in -------------------------------
COLLECT = ""
%><!--#include file="inctest/sub/../mark.inc"--><%
Expect ".. inside the path", "[M]", COLLECT

' --- virtual= is site-root relative, so it reaches a DIFFERENT which.inc ----
' There are two which.inc files: www_test/which.inc and www_test/inctest/which.inc.
COLLECT = ""
%><!--#include file="inctest/which.inc"--><%
Expect "file= picks the sibling which.inc", "[WHICH-inctest]", COLLECT

COLLECT = ""
%><!--#include virtual="/which.inc"--><%
Expect "virtual= picks the site-root-relative which.inc", "[WHICH-wwwtest-root]", COLLECT

' --- whitespace variations IIS tolerates ------------------------------------
COLLECT = ""
%><!--   #include   file = "inctest/mark.inc"   --><%
Expect "loose spacing around the directive", "[M]", COLLECT
%>
</tbody>
</table>

<h2>Repeated includes</h2>
<p>
  Classic ASP expands a directive wherever it appears, so the same file included
  twice runs twice. Suppressing the repeat is the bug this section guards.
</p>
<table>
<thead><tr><th>Check</th><th>Expected</th><th>Actual</th><th>Result</th></tr></thead>
<tbody>
<%
COLLECT = ""
%><!--#include file="inctest/mark.inc"--><!--#include file="inctest/mark.inc"--><%
Expect "same file twice expands twice", "[M][M]", COLLECT

COLLECT = ""
%><!--#include file="inctest/mark.inc"--><!--#include file="inctest/sub/nest.inc"--><!--#include file="inctest/mark.inc"--><%
Expect "repeat either side of a nested include", "[M][N:[LEAF]][M]", COLLECT

' Reached by two different spellings of the same physical file: still two copies.
COLLECT = ""
%><!--#include file="inctest/mark.inc"--><!--#include virtual="/inctest/mark.inc"--><%
Expect "same file via file= then virtual=", "[M][M]", COLLECT

' leaf.inc is pulled in directly AND through nest.inc.
COLLECT = ""
%><!--#include file="inctest/sub/leaf.inc"--><!--#include file="inctest/sub/nest.inc"--><%
Expect "a file included directly and transitively", "[LEAF][N:[LEAF]]", COLLECT
%>
</tbody>
</table>

<h2>Directives that must NOT be expanded</h2>
<p>
  The scanner runs over raw markup, so it has to leave lookalike text alone
  when it sits inside a string literal or an ASP comment.
</p>
<table>
<thead><tr><th>Check</th><th>Expected</th><th>Actual</th><th>Result</th></tr></thead>
<tbody>
<%
Dim s
s = "<!--#include file=""inctest/mark.inc""-->"
Expect "directive inside a string literal is inert", 39, Len(s)
Expect "string literal keeps its text", -1, CLng(InStr(s, "#include") > 0)

COLLECT = ""
' <!--#include file="inctest/mark.inc"-->
Expect "directive inside an ASP comment is inert", "", COLLECT
%>
</tbody>
</table>

<h2>Summary</h2>
<p>
  <span class="ok"><%= PASSED %> passed</span> &middot;
  <span class="<%= IIf(FAILED > 0, "err", "") %>"><%= FAILED %> failed</span> &middot;
  <%= SKIPPED %> skipped
</p>
<% If FAILED > 0 Then Response.Status = "500 Internal Server Error" %>
<!--#include file="includes/footer.asp"-->
