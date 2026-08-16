<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<%
Option Explicit
%>
<!--#include file="includes/helpers.asp"-->
<%
' ============================================================================
' 21-ado-sqlite.asp - the SQLite provider, end to end
' ----------------------------------------------------------------------------
' ASPPY apps run on SQLite through ADODB, so this page walks the whole
' lifecycle an app depends on and asserts it explicitly:
'
'   * opening a connection to a .db that does NOT exist CREATES the file
'   * DDL, INSERT, SELECT, UPDATE, DELETE
'   * recordset navigation, EOF/BOF, RecordCount, GetRows
'   * Fields access by name, by index, and via the default property
'   * parameterised commands
'   * transactions, including rollback
'   * NULL, Unicode and BLOB round trips
'   * closing and REOPENING keeps the data
'
' It exists because none of that was covered by a test, which made it hard to
' be confident that work on other ADO objects (Stream, Command, Parameter) had
' left the SQLite path alone.
' ============================================================================
Dim PageTitle : PageTitle = "ADODB + SQLite"
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

Dim fso, dbPath, connStr, conn, rs, cmd, i
Set fso = Server.CreateObject("Scripting.FileSystemObject")
dbPath = Server.MapPath("_sqlite_regression.db")

' Start from a clean slate so the "creates the file" check is meaningful.
On Error Resume Next
If fso.FileExists(dbPath) Then fso.DeleteFile dbPath
If fso.FileExists(dbPath & "-wal") Then fso.DeleteFile dbPath & "-wal"
If fso.FileExists(dbPath & "-shm") Then fso.DeleteFile dbPath & "-shm"
Err.Clear
On Error GoTo 0

connStr = "Provider=SQLite;Data Source=" & dbPath
%>
<h1>ADODB + SQLite</h1>
<p class="lead">
  The full lifecycle an ASPPY app depends on, asserted end to end.
</p>

<h2>Opening a database that does not exist creates it</h2>
<table>
<thead><tr><th>Check</th><th>Expected</th><th>Actual</th><th>Result</th></tr></thead>
<tbody>
<%
Expect "file absent before Open", 0, CLng(fso.FileExists(dbPath))
Set conn = Server.CreateObject("ADODB.Connection")
Expect "State before Open (adStateClosed)", 0, conn.State
conn.Open connStr
Expect "State after Open (adStateOpen)", 1, conn.State
Expect "file created by Open", -1, CLng(fso.FileExists(dbPath))
%>
</tbody>
</table>

<h2>DDL, insert, select</h2>
<table>
<thead><tr><th>Check</th><th>Expected</th><th>Actual</th><th>Result</th></tr></thead>
<tbody>
<%
conn.Execute "CREATE TABLE widget (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, qty INTEGER, price REAL, note TEXT)"
Expect "CREATE TABLE", 0, 0
conn.Execute "INSERT INTO widget (name, qty, price, note) VALUES ('alpha', 3, 1.5, 'first')"
conn.Execute "INSERT INTO widget (name, qty, price, note) VALUES ('beta', 7, 2.25, NULL)"
conn.Execute "INSERT INTO widget (name, qty, price, note) VALUES ('caf" & ChrW(233) & "', 0, 0.0, 'unicode')"

Set rs = conn.Execute("SELECT COUNT(*) AS n FROM widget")
Expect "row count after 3 inserts", 3, rs("n")
rs.Close

Set rs = conn.Execute("SELECT id, name, qty, price, note FROM widget ORDER BY id")
Expect "not EOF at start", 0, CLng(rs.EOF)
Expect "not BOF at start", 0, CLng(rs.BOF)
Expect "rs(""name"") by name", "alpha", rs("name")
Expect "rs(0) by index", 1, rs(0)
Expect "rs.Fields(""name"").Value", "alpha", rs.Fields("name").Value
Expect "rs.Fields(""name"") default property", "alpha", rs.Fields("name") & ""
Expect "rs.Fields.Count", 5, rs.Fields.Count
Expect "numeric column type", 3, rs("qty")
Expect "real column", 1.5, rs("price")
rs.MoveNext
Expect "after MoveNext", "beta", rs("name")
Expect "NULL column IsNull", -1, CLng(IsNull(rs("note")))
rs.MoveNext
Expect "Unicode round trip", "caf" & ChrW(233), rs("name")
rs.MoveNext
Expect "EOF after last row", -1, CLng(rs.EOF)
rs.MoveFirst
Expect "MoveFirst returns to row 1", "alpha", rs("name")
rs.Close
%>
</tbody>
</table>

<h2>GetRows, update, delete</h2>
<table>
<thead><tr><th>Check</th><th>Expected</th><th>Actual</th><th>Result</th></tr></thead>
<tbody>
<%
Dim arr
Set rs = conn.Execute("SELECT id, name FROM widget ORDER BY id")
arr = rs.GetRows()
rs.Close
Expect "GetRows IsArray", -1, CLng(IsArray(arr))
Expect "GetRows field count (dim 1)", 1, UBound(arr, 1)
Expect "GetRows row count (dim 2)", 2, UBound(arr, 2)
Expect "GetRows value [1,0]", "alpha", arr(1, 0)

conn.Execute "UPDATE widget SET qty = 99 WHERE name = 'alpha'"
Set rs = conn.Execute("SELECT qty FROM widget WHERE name = 'alpha'")
Expect "UPDATE applied", 99, rs("qty")
rs.Close

conn.Execute "DELETE FROM widget WHERE name = 'beta'"
Set rs = conn.Execute("SELECT COUNT(*) AS n FROM widget")
Expect "DELETE applied", 2, rs("n")
rs.Close
%>
</tbody>
</table>

<h2>Parameterised command</h2>
<table>
<thead><tr><th>Check</th><th>Expected</th><th>Actual</th><th>Result</th></tr></thead>
<tbody>
<%
Set cmd = Server.CreateObject("ADODB.Command")
cmd.ActiveConnection = conn
cmd.CommandText = "INSERT INTO widget (name, qty, price, note) VALUES (?, ?, ?, ?)"
cmd.Parameters.Append cmd.CreateParameter("p1", 200, 1, 50, "gamma")
cmd.Parameters.Append cmd.CreateParameter("p2", 3, 1, 0, 42)
cmd.Parameters.Append cmd.CreateParameter("p3", 5, 1, 0, 9.75)
cmd.Parameters.Append cmd.CreateParameter("p4", 200, 1, 50, "via command")
cmd.Execute
' adStateClosed. A synchronous command is only adStateOpen while it is
' actually executing, so IIS reports 0 here too.
Expect "Command.State after Execute", 0, cmd.State

Set rs = conn.Execute("SELECT qty, price, note FROM widget WHERE name = 'gamma'")
Expect "parameterised insert: qty", 42, rs("qty")
Expect "parameterised insert: price", 9.75, rs("price")
Expect "parameterised insert: note", "via command", rs("note")
rs.Close

' A value that would break naive string concatenation.
Set cmd = Server.CreateObject("ADODB.Command")
cmd.ActiveConnection = conn
cmd.CommandText = "INSERT INTO widget (name, qty) VALUES (?, ?)"
cmd.Parameters.Append cmd.CreateParameter("p1", 200, 1, 100, "O'Brien "" ; DROP TABLE widget --")
cmd.Parameters.Append cmd.CreateParameter("p2", 3, 1, 0, 1)
cmd.Execute
Set rs = conn.Execute("SELECT name FROM widget WHERE qty = 1")
Expect "quotes survive parameter binding", "O'Brien "" ; DROP TABLE widget --", rs("name")
rs.Close
Set rs = conn.Execute("SELECT COUNT(*) AS n FROM widget")
Expect "table still exists after injection attempt", 4, rs("n")
rs.Close
%>
</tbody>
</table>

<h2>Transactions</h2>
<table>
<thead><tr><th>Check</th><th>Expected</th><th>Actual</th><th>Result</th></tr></thead>
<tbody>
<%
conn.BeginTrans
conn.Execute "INSERT INTO widget (name, qty) VALUES ('rolled-back', 1)"
conn.RollbackTrans
Set rs = conn.Execute("SELECT COUNT(*) AS n FROM widget WHERE name = 'rolled-back'")
Expect "RollbackTrans discards the insert", 0, rs("n")
rs.Close

conn.BeginTrans
conn.Execute "INSERT INTO widget (name, qty) VALUES ('committed', 1)"
conn.CommitTrans
Set rs = conn.Execute("SELECT COUNT(*) AS n FROM widget WHERE name = 'committed'")
Expect "CommitTrans keeps the insert", 1, rs("n")
rs.Close
%>
</tbody>
</table>

<h2>BLOB round trip</h2>
<table>
<thead><tr><th>Check</th><th>Expected</th><th>Actual</th><th>Result</th></tr></thead>
<tbody>
<%
Dim stm, blob, back
Set stm = Server.CreateObject("ADODB.Stream")
stm.Type = 2 : stm.Charset = "windows-1252" : stm.Open
stm.WriteText "BINARY-DATA"
stm.Position = 0 : stm.Type = 1 : stm.Position = 0
blob = stm.Read()
stm.Close

conn.Execute "CREATE TABLE blobs (id INTEGER PRIMARY KEY, payload BLOB)"
Set cmd = Server.CreateObject("ADODB.Command")
cmd.ActiveConnection = conn
cmd.CommandText = "INSERT INTO blobs (id, payload) VALUES (?, ?)"
cmd.Parameters.Append cmd.CreateParameter("p1", 3, 1, 0, 1)
cmd.Parameters.Append cmd.CreateParameter("p2", 205, 1, 0, blob)   ' adLongVarBinary
cmd.Execute

Set rs = conn.Execute("SELECT payload FROM blobs WHERE id = 1")
back = rs("payload")
rs.Close
Expect "BLOB comes back as a Byte() array", -1, CLng(IsArray(back))
Expect "BLOB length preserved", 11, LenB(back)
Expect "BLOB first byte", 66, AscB(MidB(back, 1, 1))
%>
</tbody>
</table>

<h2>OpenSchema</h2>
<p>
  Schema rowsets, with OLE DB column names so <code>rs("TABLE_NAME")</code>
  works. This is how ADO code enumerates a database, and it gates
  <code>Recordset.Open</code> in conformance suites.
</p>
<table>
<thead><tr><th>Check</th><th>Expected</th><th>Actual</th><th>Result</th></tr></thead>
<tbody>
<%
Const adSchemaColumns = 4
Const adSchemaIndexes = 12
Const adSchemaTables = 20
Const adSchemaPrimaryKeys = 28

Dim schemaNames, foundWidget, foundBlobs
Set rs = conn.OpenSchema(adSchemaTables)
Expect "OpenSchema(adSchemaTables) opens", 1, rs.State
Expect "  ... TABLE_NAME column present", "TABLE_NAME", rs.Fields("TABLE_NAME").Name
schemaNames = "" : foundWidget = 0 : foundBlobs = 0
Do While Not rs.EOF
    schemaNames = schemaNames & rs("TABLE_NAME") & ";"
    If rs("TABLE_NAME") = "widget" Then foundWidget = 1
    If rs("TABLE_NAME") = "blobs" Then foundBlobs = 1
    rs.MoveNext
Loop
rs.Close
Expect "  ... lists the widget table", 1, foundWidget
Expect "  ... lists the blobs table", 1, foundBlobs

' Restriction array: position 3 is TABLE_NAME.
Set rs = conn.OpenSchema(adSchemaTables, Array(Empty, Empty, "widget"))
Dim nFiltered : nFiltered = 0
Do While Not rs.EOF
    nFiltered = nFiltered + 1
    rs.MoveNext
Loop
rs.Close
Expect "criteria restricts to one table", 1, nFiltered

Set rs = conn.OpenSchema(adSchemaColumns, Array(Empty, Empty, "widget"))
Dim colList : colList = ""
Do While Not rs.EOF
    colList = colList & rs("COLUMN_NAME") & ","
    rs.MoveNext
Loop
rs.Close
Expect "adSchemaColumns lists widget columns", "id,name,qty,price,note,", colList

Set rs = conn.OpenSchema(adSchemaPrimaryKeys, Array(Empty, Empty, "widget"))
Expect "adSchemaPrimaryKeys finds the PK", "id", rs("COLUMN_NAME")
rs.Close

conn.Execute "CREATE INDEX ix_widget_name ON widget(name)"
Set rs = conn.OpenSchema(adSchemaIndexes)
Dim foundIx : foundIx = 0
Do While Not rs.EOF
    If rs("INDEX_NAME") = "ix_widget_name" Then foundIx = 1
    rs.MoveNext
Loop
rs.Close
Expect "adSchemaIndexes finds the index", 1, foundIx

On Error Resume Next
Set rs = conn.OpenSchema(999)
Expect "unsupported QueryType raises", -1, CLng(Err.Number <> 0)
Err.Clear
On Error GoTo 0
%>
</tbody>
</table>

<h2>Close and reopen keeps the data</h2>
<table>
<thead><tr><th>Check</th><th>Expected</th><th>Actual</th><th>Result</th></tr></thead>
<tbody>
<%
conn.Close
Expect "State after Close", 0, conn.State
Set conn = Nothing

Dim conn2
Set conn2 = Server.CreateObject("ADODB.Connection")
conn2.Open connStr
Set rs = conn2.Execute("SELECT COUNT(*) AS n FROM widget")
Expect "rows survive a reopen", 5, rs("n")
rs.Close
Set rs = conn2.Execute("SELECT name FROM widget WHERE name = 'committed'")
Expect "committed row still there", "committed", rs("name")
rs.Close
conn2.Close
Set conn2 = Nothing

' Clean up so the next run starts from nothing again.
On Error Resume Next
If fso.FileExists(dbPath) Then fso.DeleteFile dbPath
If fso.FileExists(dbPath & "-wal") Then fso.DeleteFile dbPath & "-wal"
If fso.FileExists(dbPath & "-shm") Then fso.DeleteFile dbPath & "-shm"
Err.Clear
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
