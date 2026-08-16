<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<%
Option Explicit
%>
<!--#include file="includes/helpers.asp"-->
<%
' ============================================================================
' 20-ado-stream.asp - ADODB.Stream byte semantics, and ADO object members
' ----------------------------------------------------------------------------
' Every expected value was captured from a live IIS 10 / ADO installation by
' writing the same bytes and reading the buffer back. See GitHub issue #17.
'
' The headline behaviour is the BYTE ORDER MARK. ADO writes one for the Unicode
' encodings and not for single-byte code pages:
'
'     Charset         Size   first bytes
'     utf-8            20    EF BB BF 48
'     Unicode          36    FF FE 48 00
'     windows-1252     17    48 65 6C 6C
'
' ASPPY used to write no BOM at all - so a UTF-8 file produced the usual way,
' ADODB.Stream + SaveToFile, came out without the BOM its consumers (Excel
' above all) expect - and reported Size as a character count plus a fudge of 2.
' Size, Position, Read, CopyTo and SaveToFile now share one byte view.
'
' Deliberately needs NO database, so it runs everywhere.
' ============================================================================
Dim PageTitle : PageTitle = "ADODB.Stream"
%>
<!--#include file="includes/header.asp"-->
<%
Dim PASSED, FAILED
PASSED = 0 : FAILED = 0

Sub Expect(sLabel, vExpected, vActual)
    Dim ok
    ok = (CStr(vExpected) = CStr(vActual))
    If ok Then PASSED = PASSED + 1 Else FAILED = FAILED + 1
    WriteLine "<tr><th scope=""row"">" & HtmlEncode(sLabel) & "</th><td>" & _
              HtmlEncode(CStr(vExpected)) & "</td><td>" & HtmlEncode(CStr(vActual)) & _
              "</td><td class=""" & IIf(ok, "ok", "err") & """>" & _
              IIf(ok, "PASS", "FAIL") & "</td></tr>"
End Sub

' Returns the first N bytes of a stream's buffer as "EF BB BF ..".
Function HeadBytes(s, n)
    Dim b, i, out
    s.Position = 0
    s.Type = 1                      ' adTypeBinary
    s.Position = 0
    b = s.Read()
    out = ""
    For i = 0 To n - 1
        If i <= LenB(b) - 1 Then out = out & Right("0" & Hex(AscB(MidB(b, i + 1, 1))), 2) & " "
    Next
    HeadBytes = Trim(out)
End Function

' A text stream holding "Hello ADO Stream" + LF in the given charset.
Function MakeStream(charset)
    Dim s
    Set s = Server.CreateObject("ADODB.Stream")
    s.Type = 2                      ' adTypeText
    s.Charset = charset
    s.Open
    s.LineSeparator = 10            ' adLF
    s.WriteText "Hello ADO Stream", 1   ' adWriteLine
    Set MakeStream = s
End Function
%>
<h1>ADODB.Stream</h1>
<p class="lead">
  Expected values captured from live <strong>IIS 10 / ADO</strong>. 16 characters
  plus one LF, written through <code>WriteText ..., adWriteLine</code>.
</p>

<h2>Byte order mark and Size</h2>
<table>
<thead><tr><th>Check</th><th>IIS</th><th>ASPPY</th><th>Result</th></tr></thead>
<tbody>
<%
Dim s, emptyStm
Set emptyStm = Server.CreateObject("ADODB.Stream")
emptyStm.Type = 2 : emptyStm.Charset = "utf-8" : emptyStm.Open
Expect "emptyStm utf-8 stream Size", 0, emptyStm.Size
Expect "LineSeparator default (adCRLF)", -1, emptyStm.LineSeparator
emptyStm.Close

Set s = MakeStream("utf-8")
Expect "utf-8 Size (3 BOM + 16 + 1)", 20, s.Size
Expect "utf-8 Position at EOF", 20, s.Position
Expect "utf-8 first bytes", "EF BB BF 48", HeadBytes(s, 4)
s.Close

Set s = MakeStream("Unicode")
Expect "Unicode Size (2 BOM + 32 + 2)", 36, s.Size
Expect "Unicode Position at EOF", 36, s.Position
Expect "Unicode first bytes", "FF FE 48 00", HeadBytes(s, 4)
s.Close

Set s = MakeStream("windows-1252")
Expect "windows-1252 Size (no BOM)", 17, s.Size
Expect "windows-1252 first bytes", "48 65 6C 6C", HeadBytes(s, 4)
s.Close
%>
</tbody>
</table>

<h2>Position is a byte offset</h2>
<p>At end of stream <code>Position</code> must equal <code>Size</code>; it used to be a character count, so the two disagreed by the width of the BOM.</p>
<table>
<thead><tr><th>Check</th><th>IIS</th><th>ASPPY</th><th>Result</th></tr></thead>
<tbody>
<%
Set s = MakeStream("utf-8")
Expect "Position = Size at EOF", CLng(s.Size), CLng(s.Position)
s.Position = 0
Expect "Position = 0 reads back as 0", 0, s.Position
s.Position = 20
Expect "Position = 20 reads back as 20", 20, s.Position
s.Position = 0
Expect "ReadText round trip", "Hello ADO Stream" & Chr(10), s.ReadText(-1)
s.Position = 0
s.SkipLine
Expect "SkipLine lands past the LF", 20, s.Position
s.Close
%>
</tbody>
</table>

<h2>SetEOS truncates</h2>
<p><code>SetEOS</code> makes the current position the end of the stream. It used to do the opposite &mdash; move the position to the end &mdash; so it never removed anything.</p>
<table>
<thead><tr><th>Check</th><th>IIS</th><th>ASPPY</th><th>Result</th></tr></thead>
<tbody>
<%
Set s = MakeStream("utf-8")
s.Position = 0
s.SetEOS
Expect "SetEOS at Position 0 empties it", 0, s.Size
s.Close

Set s = Server.CreateObject("ADODB.Stream")
s.Type = 2 : s.Charset = "utf-8" : s.Open
s.WriteText "ABCDEFGHIJ"
Expect "Size before (3 BOM + 10)", 13, s.Size
s.Position = 5
s.SetEOS
Expect "SetEOS at byte 5 -> Size", 5, s.Size
s.Position = 0
Expect "  ... 3 BOM bytes + 2 chars", "AB", s.ReadText(-1)
s.Close

' Binary streams truncate on the same byte offset. The six bytes come from a
' windows-1252 text stream (no BOM) switched to binary: Stream.Write needs a
' real byte array, and ChrB() & ChrB() would build a string, which ADO rejects
' with error 3001.
Dim srcStm, sixBytes, bs
Set srcStm = Server.CreateObject("ADODB.Stream")
srcStm.Type = 2 : srcStm.Charset = "windows-1252" : srcStm.Open
srcStm.WriteText "012345"
srcStm.Position = 0 : srcStm.Type = 1 : srcStm.Position = 0
sixBytes = srcStm.Read()
srcStm.Close

Set bs = Server.CreateObject("ADODB.Stream")
bs.Type = 1 : bs.Open
bs.Write sixBytes
Expect "binary Size before", 6, bs.Size
bs.Position = 4
bs.SetEOS
Expect "binary SetEOS at 4 -> Size", 4, bs.Size
bs.Close
%>
</tbody>
</table>

<h2>SaveToFile writes the same bytes</h2>
<table>
<thead><tr><th>Check</th><th>IIS</th><th>ASPPY</th><th>Result</th></tr></thead>
<tbody>
<%
Dim fso, tmpPath, fSize
Set fso = Server.CreateObject("Scripting.FileSystemObject")
tmpPath = Server.MapPath("_ado_stream_test.tmp")
On Error Resume Next
If fso.FileExists(tmpPath) Then fso.DeleteFile tmpPath
Err.Clear
On Error GoTo 0

Set s = MakeStream("utf-8")
s.SaveToFile tmpPath, 2             ' adSaveCreateOverWrite
fSize = 0
If fso.FileExists(tmpPath) Then fSize = fso.GetFile(tmpPath).Size
Expect "file on disk carries the BOM", 20, fSize
s.Close

' And it loads back to the same size.
Set s = Server.CreateObject("ADODB.Stream")
s.Type = 1 : s.Open
s.LoadFromFile tmpPath
Expect "LoadFromFile round trip", 20, s.Size
Expect "  ... starting with the BOM", "EF BB BF 48", HeadBytes(s, 4)
s.Close
On Error Resume Next
fso.DeleteFile tmpPath
Err.Clear
On Error GoTo 0
%>
</tbody>
</table>

<h2>ADO object members</h2>
<p>These raised error 438 or returned emptyStm, which aborted pages outside <code>On Error Resume Next</code>.</p>
<table>
<thead><tr><th>Check</th><th>IIS</th><th>ASPPY</th><th>Result</th></tr></thead>
<tbody>
<%
Dim conn, cmd, prm
Set conn = Server.CreateObject("ADODB.Connection")
Expect "Connection.Version", "10.0", conn.Version
Expect "Connection.IsolationLevel", 4096, conn.IsolationLevel
Expect "Connection.Attributes", 0, conn.Attributes
' NOT asserted: Connection.Properties.Count. IIS reports 14 provider-specific
' properties on an unopened Connection (and ~94 once opened against Jet);
' ASPPY has no OLE DB provider to enumerate and reports 0. Known gap - the
' collection exists so scripts run, it just is not populated.
Expect "Connection.Properties exists", 0, CLng(conn.Properties.Count < 0)

Set cmd = Server.CreateObject("ADODB.Command")
Expect "Command.State (adStateClosed)", 0, cmd.State
Expect "Command.Properties.Count", 0, cmd.Properties.Count

Set prm = cmd.CreateParameter("PTest", 200, 1, 50, "HelloADO")
Expect "Parameter.Name", "PTest", prm.Name
Expect "Parameter.Attributes", 0, prm.Attributes
Expect "Parameter.Properties.Count", 0, prm.Properties.Count
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
