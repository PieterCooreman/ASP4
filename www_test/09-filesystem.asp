<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<%
Option Explicit
%>
<!--#include file="includes/helpers.asp"-->
<%
' ============================================================================
' 09-filesystem.asp - FileSystemObject (FSO)
' Demonstrates: creating a working folder, writing and reading a text file,
' appending, querying file metadata, and enumerating a directory. All work
' happens inside an app-relative "_appdata" folder created on demand.
' ============================================================================
Dim PageTitle : PageTitle = "FileSystemObject"
%>
<!--#include file="includes/header.asp"-->
<%
Const FOR_READING   = 1
Const FOR_WRITING   = 2
Const FOR_APPENDING = 8

Dim fso, dataDir, logPath
Set fso = Server.CreateObject("Scripting.FileSystemObject")

' Map an app-relative folder to a physical path (never trust user input here).
dataDir = Server.MapPath("_appdata")
logPath = fso.BuildPath(dataDir, "visits.log")

' --- Ensure the working folder exists -------------------------------------
If Not fso.FolderExists(dataDir) Then
    fso.CreateFolder dataDir
End If
%>
<h1>FileSystemObject</h1>
<p class="lead">Create, write, append, read and enumerate files with the Scripting FSO.</p>

<h2>Write &amp; read a text file</h2>
<%
DemoStart "Create a file, write three lines, read them back"
Dim ts, line
' Write (overwrite) a fresh file.
Set ts = fso.OpenTextFile(fso.BuildPath(dataDir, "demo.txt"), FOR_WRITING, True)
ts.WriteLine "Line 1: Classic ASP is alive."
ts.WriteLine "Line 2: Written at " & Now()
ts.WriteLine "Line 3: Goodbye."
ts.Close

' Read it back line by line.
WriteLine "<table class=""kv"">"
Set ts = fso.OpenTextFile(fso.BuildPath(dataDir, "demo.txt"), FOR_READING)
Dim n : n = 0
Do While Not ts.AtEndOfStream
    n = n + 1
    line = ts.ReadLine
    RenderTableRow "Read line " & n, line
Loop
ts.Close
WriteLine "</table>"
DemoEnd
%>

<h2>Append to a log on every visit</h2>
<%
DemoStart "Each page load appends one line to visits.log"
Set ts = fso.OpenTextFile(logPath, FOR_APPENDING, True)
ts.WriteLine FormatDateTime(Now, 0) & " from " & Request.ServerVariables("REMOTE_ADDR")
ts.Close

' Show the last few log lines.
Dim allText, lines, i, startIdx
Set ts = fso.OpenTextFile(logPath, FOR_READING)
allText = ""
If Not ts.AtEndOfStream Then allText = ts.ReadAll
ts.Close
lines = Split(Replace(allText, vbCrLf, vbLf), vbLf)
' Trim a trailing empty element if present.
Dim lastIdx : lastIdx = UBound(lines)
If lastIdx >= 0 And Len(lines(lastIdx)) = 0 Then lastIdx = lastIdx - 1

startIdx = lastIdx - 4
If startIdx < 0 Then startIdx = 0
WriteLine "<p>Total log entries: <strong>" & (lastIdx + 1) & "</strong>. Most recent:</p>"
WriteLine "<pre class=""code""><code>"
For i = startIdx To lastIdx
    WriteLine HtmlEncode(lines(i))
Next
WriteLine "</code></pre>"
DemoEnd
%>

<h2>File metadata</h2>
<%
DemoStart "Inspect the demo.txt file object"
Dim f : Set f = fso.GetFile(fso.BuildPath(dataDir, "demo.txt"))
WriteLine "<table class=""kv"">"
RenderTableRow "Name",          f.Name
RenderTableRow "Size (bytes)",  f.Size
RenderTableRow "Type",          f.Type
RenderTableRow "Created",       f.DateCreated
RenderTableRow "Last modified", f.DateLastModified
RenderTableRow "Extension",     fso.GetExtensionName(f.Path)
WriteLine "</table>"
DemoEnd
%>

<h2>Enumerate a folder</h2>
<%
DemoStart "List every file in this app's _appdata folder"
Dim folder, file
Set folder = fso.GetFolder(dataDir)
WriteLine "<table class=""kv"">"
For Each file In folder.Files
    RenderTableRow file.Name, FormatNumber(file.Size, 0) & " bytes  (" & file.DateLastModified & ")"
Next
WriteLine "</table>"
WriteLine "<p>Folder: <code>" & HtmlEncode(folder.Path) & "</code></p>"
DemoEnd

Set fso = Nothing
%>
<!--#include file="includes/footer.asp"-->
