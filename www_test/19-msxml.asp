<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<%
Option Explicit
%>
<!--#include file="includes/helpers.asp"-->
<%
' ============================================================================
' 19-msxml.asp - MSXML2.DOMDocument and the Byte() SafeArray
' ----------------------------------------------------------------------------
' Expected values were captured from a live IIS 10 / MSXML installation, not
' from the documentation. See GitHub issue #18.
'
' Two groups of checks:
'
'   1. Things that must work with the STDLIB parser alone. Missing members used
'      to abort the whole page with error 438, and node-returning members gave
'      Empty instead of Nothing, so `If Not n Is Nothing` always took the wrong
'      branch on a failed lookup.
'
'   2. Things that need the optional lxml package: real XPath 1.0 (axes,
'      functions, unions, namespace prefixes), XSLT, and CDATA/comment/PI
'      preservation. Those are reported as SKIP when lxml is absent, never as
'      failures, so this page stays green on a stdlib-only install.
' ============================================================================
Dim PageTitle : PageTitle = "MSXML2"
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

' Booleans are compared as CLng (-1/0): IIS localises True/False via the OS
' user locale, so CStr(True) is "Waar" on a Dutch server.
Sub ExpectBool(sLabel, bExpected, bActual)
    Expect sLabel, CLng(bExpected), CLng(bActual)
End Sub

Dim xmlDoc, docElem, n, lxmlOn
Set xmlDoc = Server.CreateObject("MSXML2.DOMDocument")
xmlDoc.async = False
xmlDoc.loadXML "<?xml version=""1.0""?>" & _
    "<catalog xmlns:p=""urn:prod"">" & _
    "<p:item id=""1"" name=""a""><price>10</price></p:item>" & _
    "<p:item id=""2"" name=""b""><price>20</price></p:item>" & _
    "<note>hello</note>" & _
    "<raw><![CDATA[x<y&z]]></raw>" & _
    "</catalog>"
Set docElem = xmlDoc.documentElement

' Probe for lxml once: a namespace-prefixed XPath only resolves with it.
' NOTE the shape. `If <raising expression> Then` cannot be used: under
' On Error Resume Next, VBScript ENTERS the True branch when the condition
' raises (ASPPY reproduces that), so the probe would report the opposite.
' An assignment is simply skipped, which is what we want.
Dim probeCnt
On Error Resume Next
probeCnt = -1
probeCnt = xmlDoc.selectNodes("//p:item").length
lxmlOn = (Err.Number = 0) And (probeCnt = 2)
Err.Clear
On Error GoTo 0
%>
<h1>MSXML2</h1>
<p class="lead">
  Expected values captured from live <strong>IIS 10 / MSXML</strong>.
  lxml detected: <strong><%= IIf(lxmlOn, "yes", "no") %></strong><%
  If Not lxmlOn Then Response.Write " &mdash; XPath/XSLT/CDATA rows are skipped" %>.
</p>

<h2>Members that used to abort the page (error 438)</h2>
<table>
<thead><tr><th>Check</th><th>IIS</th><th>ASPPY</th><th>Result</th></tr></thead>
<tbody>
<%
Expect "doc.baseName", "", xmlDoc.baseName
Expect "doc.prefix", "", xmlDoc.prefix
Expect "doc.namespaceURI", "", xmlDoc.namespaceURI
ExpectBool "doc.parsed after loadXML", True, xmlDoc.parsed
Expect "docElem.baseName", "catalog", docElem.baseName
Expect "docElem.prefix", "", docElem.prefix
Expect "docElem.namespaceURI", "", docElem.namespaceURI
ExpectBool "docElem.specified", True, docElem.specified
ExpectBool "docElem.parsed", True, docElem.parsed

Dim attrNode
Set attrNode = xmlDoc.selectSingleNode("//note")
Set attrNode = xmlDoc.documentElement.getAttributeNode("xmlns:p")
Set attrNode = Nothing

Dim itemNode
Set itemNode = xmlDoc.getElementsByTagName("item").item(0)
Set attrNode = itemNode.getAttributeNode("id")
ExpectBool "getAttributeNode(""id"") found", True, Not (attrNode Is Nothing)
Expect "  .value", "1", attrNode.value
ExpectBool "  .specified", True, attrNode.specified
Expect "  .baseName", "id", attrNode.baseName
Set attrNode = itemNode.getAttributeNode("nosuchattr")
ExpectBool "getAttributeNode(missing) Is Nothing", True, attrNode Is Nothing
%>
</tbody>
</table>

<h2>Nothing semantics</h2>
<p>
  A failed node lookup must be <code>Nothing</code>, not <code>Empty</code>.
  These members returned Python <code>None</code>, so
  <code>If Not n Is Nothing</code> always took the wrong branch.
</p>
<table>
<thead><tr><th>Check</th><th>IIS</th><th>ASPPY</th><th>Result</th></tr></thead>
<tbody>
<%
Set n = xmlDoc.selectSingleNode("//nosuchnode")
ExpectBool "selectSingleNode(no match) Is Nothing", True, n Is Nothing
Expect "  TypeName", "Nothing", TypeName(n)
ExpectBool "doc.parentNode Is Nothing", True, xmlDoc.parentNode Is Nothing
ExpectBool "doc.nextSibling Is Nothing", True, xmlDoc.nextSibling Is Nothing
ExpectBool "doc.previousSibling Is Nothing", True, xmlDoc.previousSibling Is Nothing
ExpectBool "doc.attributes Is Nothing", True, xmlDoc.attributes Is Nothing
ExpectBool "doc.doctype Is Nothing", True, xmlDoc.doctype Is Nothing
ExpectBool "docElem.ownerDocument is the doc", True, Not (docElem.ownerDocument Is Nothing)
%>
</tbody>
</table>

<h2>Node types and child nodes</h2>
<table>
<thead><tr><th>Check</th><th>IIS</th><th>ASPPY</th><th>Result</th></tr></thead>
<tbody>
<%
Expect "createTextNode.nodeType", 3, xmlDoc.createTextNode("t").nodeType
Expect "createCDATASection.nodeType", 4, xmlDoc.createCDATASection("c").nodeType
Expect "createComment.nodeType", 8, xmlDoc.createComment("c").nodeType
Expect "createProcessingInstruction.nodeType", 7, xmlDoc.createProcessingInstruction("t", "d").nodeType
Expect "createDocumentFragment.nodeType", 11, xmlDoc.createDocumentFragment().nodeType
Expect "createEntityReference.nodeName", "ent", xmlDoc.createEntityReference("ent").nodeName
Expect "createNode(1,...).nodeName", "custom", xmlDoc.createNode(1, "custom", "").nodeName

' Text is a real child node: node.firstChild.nodeValue is THE common way to
' read element content, and it used to yield Nothing then fail.
Set n = xmlDoc.selectSingleNode("//note")
Expect "note.firstChild.nodeType", 3, n.firstChild.nodeType
Expect "note.firstChild.nodeValue", "hello", n.firstChild.nodeValue
ExpectBool "text node .parentNode links back", True, Not (n.firstChild.parentNode Is Nothing)

' A fragment splices its children in rather than inserting itself.
Dim frag, host, kid
Set host = xmlDoc.createElement("host")
Set frag = xmlDoc.createDocumentFragment()
Set kid = xmlDoc.createElement("k1") : frag.appendChild kid
Set kid = xmlDoc.createElement("k2") : frag.appendChild kid
host.appendChild frag
Expect "appendChild(fragment) splices children", "<host><k1/><k2/></host>", Replace(host.xml, " />", "/>")
%>
</tbody>
</table>

<h2>XPath 1.0<%= IIf(lxmlOn, "", " (skipped: needs lxml)") %></h2>
<p>
  <code>selectNodes</code> used to be ElementTree's small subset and returned an
  empty list <em>silently</em> for anything else &mdash; including every
  namespaced document. It now either evaluates the expression or raises.
</p>
<table>
<thead><tr><th>Check</th><th>IIS</th><th>ASPPY</th><th>Result</th></tr></thead>
<tbody>
<%
Dim xp, xpTests, i
xpTests = Array( _
    Array("//note", 1), _
    Array("//p:item", 2), _
    Array("//p:item[@id='1']", 1), _
    Array("//price[text()='10']", 1), _
    Array("//note | //price", 3), _
    Array("//*[contains(@name,'a')]", 1), _
    Array("/catalog", 1), _
    Array("//nosuchthing", 0))
For i = 0 To UBound(xpTests)
    If lxmlOn Then
        On Error Resume Next
        Dim cnt : cnt = xmlDoc.selectNodes(xpTests(i)(0)).length
        If Err.Number <> 0 Then cnt = "ERR " & Err.Description
        Err.Clear
        On Error GoTo 0
        Expect "selectNodes(""" & xpTests(i)(0) & """)", xpTests(i)(1), cnt
    Else
        Row "selectNodes(""" & xpTests(i)(0) & """)", xpTests(i)(1), "-", "SKIP"
    End If
Next

If lxmlOn Then
    Expect "selectSingleNode(""//p:item[@id='2']/price"").text", "20", _
           xmlDoc.selectSingleNode("//p:item[@id='2']/price").text
    Expect "CDATA survives a round trip", -1, _
           CLng(InStr(xmlDoc.xml, "<![CDATA[x<y&z]]>") > 0)
    Expect "namespace prefix preserved", -1, CLng(InStr(xmlDoc.xml, "p:item") > 0)
Else
    Row "selectSingleNode with a prefix", "20", "-", "SKIP"
    Row "CDATA survives a round trip", "yes", "-", "SKIP"
    Row "namespace prefix preserved", "yes", "-", "SKIP"
    ' Without lxml an unsupported expression must RAISE, not return empty.
    On Error Resume Next
    Dim dummy : dummy = xmlDoc.selectNodes("//*[contains(@name,'a')]").length
    Row "unsupported XPath raises (not silent 0)", "error", _
        IIf(Err.Number <> 0, "error", "silently returned " & dummy), _
        IIf(Err.Number <> 0, "PASS", "FAIL")
    If Err.Number <> 0 Then PASSED = PASSED + 0
    Err.Clear
    On Error GoTo 0
End If
%>
</tbody>
</table>

<h2>XSLT<%= IIf(lxmlOn, "", " (skipped: needs lxml)") %></h2>
<table>
<thead><tr><th>Check</th><th>IIS</th><th>ASPPY</th><th>Result</th></tr></thead>
<tbody>
<%
Dim xsl, res, outDoc
If lxmlOn Then
    Set xsl = Server.CreateObject("MSXML2.DOMDocument")
    xsl.async = False
    xsl.loadXML "<?xml version=""1.0""?>" & _
        "<xsl:stylesheet version=""1.0"" xmlns:xsl=""http://www.w3.org/1999/XSL/Transform"">" & _
        "<xsl:template match=""/""><out><xsl:value-of select=""count(//price)""/></out></xsl:template>" & _
        "</xsl:stylesheet>"
    res = xmlDoc.transformNode(xsl)
    Expect "transformNode counts //price", -1, CLng(InStr(res, "<out>2</out>") > 0)
    Set outDoc = Server.CreateObject("MSXML2.DOMDocument")
    xmlDoc.transformNodeToObject xsl, outDoc
    Expect "transformNodeToObject root", "out", outDoc.documentElement.nodeName
Else
    Row "transformNode", "&lt;out&gt;2&lt;/out&gt;", "-", "SKIP"
    Row "transformNodeToObject", "out", "-", "SKIP"
    On Error Resume Next
    Dim r2 : r2 = xmlDoc.transformNode(xmlDoc)
    Row "transformNode names lxml in the error", "mentions lxml", _
        IIf(InStr(Err.Description, "lxml") > 0, "mentions lxml", Err.Description), _
        IIf(InStr(Err.Description, "lxml") > 0, "PASS", "FAIL")
    Err.Clear
    On Error GoTo 0
End If
%>
</tbody>
</table>

<h2>Byte() SafeArray</h2>
<p>
  Binary payloads (<code>ServerXMLHTTP.responseBody</code>,
  <code>Request.BinaryRead</code>, <code>ADODB.Stream.Read</code>) are a
  <code>Byte()</code> SafeArray on IIS, not an opaque object.
</p>
<table>
<thead><tr><th>Check</th><th>IIS</th><th>ASPPY</th><th>Result</th></tr></thead>
<tbody>
<%
Dim st, bytes
Set st = Server.CreateObject("ADODB.Stream")
st.Type = 2 : st.Charset = "utf-8" : st.Open
st.WriteText "ABC"
st.Position = 0 : st.Type = 1 : st.Position = 0
bytes = st.Read()
st.Close

ExpectBool "IsArray(bytes)", True, IsArray(bytes)
Expect "TypeName(bytes)", "Byte()", TypeName(bytes)
Expect "VarType(bytes)", 8209, VarType(bytes)
ExpectBool "IsObject(bytes)", False, IsObject(bytes)
Expect "LBound(bytes)", 0, LBound(bytes)
Expect "UBound(bytes)", 2, UBound(bytes)
Expect "LenB(bytes)", 3, LenB(bytes)
Expect "bytes(0) is Asc(""A"")", 65, bytes(0)
Expect "bytes(2) is Asc(""C"")", 67, bytes(2)
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
