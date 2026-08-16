<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<%
Option Explicit
%>
<!--#include file="includes/helpers.asp"-->
<%
' ============================================================================
' 22-wsh-shortcuts.asp - WScript.Shell shortcuts/registry, and FSO Drive names
' ----------------------------------------------------------------------------
' Covers the members that used to raise error 438:
'
'   WScript.Shell : CreateShortcut (.lnk and .url), RegRead, SpecialFolders
'   Scripting     : File.Drive / Folder.Drive, ShortName vs ShortPath
'
' The .lnk writer builds a real [MS-SHLLINK] file rather than going through the
' Shell COM object. It was checked by writing a shortcut here and reading it
' back with Windows' own WScript.Shell COM - all properties round-trip and
' Explorer resolves the target.
'
' NOTE what is deliberately NOT here: Run and Exec. Executing arbitrary shell
' commands from a web request contradicts the sandboxing ASPPY applies
' elsewhere, so they still raise a catchable 429.
' ============================================================================
Dim PageTitle : PageTitle = "WScript.Shell + FSO"
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

Dim wsh, fso, isWindows
Set fso = Server.CreateObject("Scripting.FileSystemObject")
On Error Resume Next
Set wsh = Server.CreateObject("WScript.Shell")
Err.Clear
On Error GoTo 0
isWindows = (InStr(UCase(wsh.ExpandEnvironmentStrings("%SystemRoot%")), ":\") > 0)
%>
<h1>WScript.Shell + FileSystemObject</h1>
<p class="lead">
  Members that used to raise error 438. Windows-only rows are skipped elsewhere.
</p>

<h2>CreateShortcut &mdash; .lnk</h2>
<table>
<thead><tr><th>Check</th><th>Expected</th><th>Actual</th><th>Result</th></tr></thead>
<tbody>
<%
Dim tmpDir, lnkPath, sc
tmpDir = Server.MapPath(".")
lnkPath = tmpDir & "\_wsh_regression.lnk"
On Error Resume Next
If fso.FileExists(lnkPath) Then fso.DeleteFile lnkPath
Err.Clear
On Error GoTo 0

Set sc = wsh.CreateShortcut(lnkPath)
Expect "CreateShortcut returns an object", -1, CLng(Not (sc Is Nothing))
sc.TargetPath = "C:\Windows\System32\cmd.exe"
sc.Arguments = "/c echo hello"
sc.WindowStyle = 3
sc.Hotkey = "CTRL+ALT+T"
sc.IconLocation = "notepad.exe, 0"
sc.Description = "Regression Shortcut"
sc.WorkingDirectory = tmpDir
Expect "TargetPath round trip", "C:\Windows\System32\cmd.exe", sc.TargetPath
Expect "Arguments round trip", "/c echo hello", sc.Arguments
Expect "WindowStyle round trip", 3, sc.WindowStyle
Expect "Hotkey round trip", "CTRL+ALT+T", sc.Hotkey
Expect "IconLocation round trip", "notepad.exe, 0", sc.IconLocation
Expect "Description round trip", "Regression Shortcut", sc.Description
Expect "WorkingDirectory round trip", tmpDir, sc.WorkingDirectory
Expect "FullName is the target path", lnkPath, sc.FullName

sc.Save
Expect "Save writes the file", -1, CLng(fso.FileExists(lnkPath))
If fso.FileExists(lnkPath) Then
    ' A shortcut with only a LinkInfo block parses but will not resolve; the
    ' LinkTargetIDList is what makes it usable, and it makes the file big.
    Expect "  ... and it is a real shell link", -1, CLng(fso.GetFile(lnkPath).Size > 300)
    fso.DeleteFile lnkPath
End If

' WSH accepts only .lnk and .url.
On Error Resume Next
Dim bad
Set bad = wsh.CreateShortcut(tmpDir & "\nope.txt")
Expect "a non-shortcut extension raises", -1, CLng(Err.Number <> 0)
Err.Clear
On Error GoTo 0
%>
</tbody>
</table>

<h2>CreateShortcut &mdash; .url</h2>
<table>
<thead><tr><th>Check</th><th>Expected</th><th>Actual</th><th>Result</th></tr></thead>
<tbody>
<%
Dim urlPath, us, ts, urlBody
urlPath = tmpDir & "\_wsh_regression.url"
On Error Resume Next
If fso.FileExists(urlPath) Then fso.DeleteFile urlPath
Err.Clear
On Error GoTo 0

Set us = wsh.CreateShortcut(urlPath)
us.TargetPath = "https://example.com/x"
Expect "url TargetPath round trip", "https://example.com/x", us.TargetPath
us.Save
Expect "url Save writes the file", -1, CLng(fso.FileExists(urlPath))
If fso.FileExists(urlPath) Then
    Set ts = fso.OpenTextFile(urlPath, 1)
    urlBody = ts.ReadAll()
    ts.Close
    Expect "  ... is an InternetShortcut", -1, CLng(InStr(urlBody, "[InternetShortcut]") > 0)
    Expect "  ... carries the URL", -1, CLng(InStr(urlBody, "URL=https://example.com/x") > 0)

    ' Reopening an existing .url reads the target back.
    Dim us2
    Set us2 = wsh.CreateShortcut(urlPath)
    Expect "reopening reads TargetPath back", "https://example.com/x", us2.TargetPath
    fso.DeleteFile urlPath
End If
%>
</tbody>
</table>

<h2>RegRead and SpecialFolders</h2>
<table>
<thead><tr><th>Check</th><th>Expected</th><th>Actual</th><th>Result</th></tr></thead>
<tbody>
<%
Dim prod, build, sf
If Not isWindows Then
    Row "RegRead(ProductName)", "non-empty", "-", "SKIP"
    Row "RegRead(CurrentBuild)", "numeric", "-", "SKIP"
    Row "RegRead of a missing key raises", "error", "-", "SKIP"
    Row "SpecialFolders(""Windows"")", "a directory", "-", "SKIP"
    Row "SpecialFolders(""System"")", "a directory", "-", "SKIP"
Else
    On Error Resume Next
    prod = wsh.RegRead("HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProductName")
    Expect "RegRead(ProductName)", -1, CLng(Err.Number = 0 And Len(prod) > 0)
    Err.Clear
    build = wsh.RegRead("HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\CurrentBuild")
    Expect "RegRead(CurrentBuild)", -1, CLng(Err.Number = 0 And Len(build) > 0)
    Err.Clear
    Dim junk
    junk = wsh.RegRead("HKLM\SOFTWARE\_ASPPY_NoSuchKey_\Nope")
    Expect "RegRead of a missing key raises", -1, CLng(Err.Number <> 0)
    Err.Clear
    On Error GoTo 0

    ' Checked as strings, not with FolderExists: the FileSystemObject is
    ' sandboxed to the docroot, so it correctly reports C:\Windows as absent.
    Set sf = wsh.SpecialFolders
    Expect "SpecialFolders(""Windows"") is a path", -1, CLng(InStr(sf("Windows"), ":\") > 0)
    Expect "SpecialFolders(""System"") is a path", -1, CLng(InStr(sf("System"), ":\") > 0)
    Expect "  ... System is under Windows", -1, _
           CLng(InStr(LCase(sf("System")), LCase(sf("Windows"))) = 1)
End If
On Error Resume Next
Set sf = wsh.SpecialFolders
Expect "unknown special folder is """"", "", sf("NoSuchFolder")
Err.Clear
On Error GoTo 0
%>
</tbody>
</table>

<h2>FSO: Drive, ShortName and ShortPath</h2>
<table>
<thead><tr><th>Check</th><th>Expected</th><th>Actual</th><th>Result</th></tr></thead>
<tbody>
<%
Dim testDir, testFile, f, fo, tsw
testDir = tmpDir & "\_wsh_fso_test"
testFile = testDir & "\a_long_file_name.txt"
On Error Resume Next
If Not fso.FolderExists(testDir) Then fso.CreateFolder testDir
Set tsw = fso.CreateTextFile(testFile, True)
tsw.Write "x"
tsw.Close
Err.Clear
On Error GoTo 0

Set f = fso.GetFile(testFile)
Set fo = fso.GetFolder(testDir)

' Drive is an object whose default property is Path, so it concatenates.
Expect "File.Drive reads as the drive spec", Left(testDir, 2), "" & f.Drive
Expect "Folder.Drive reads as the drive spec", Left(testDir, 2), "" & fo.Drive
Expect "Drive.Path has no trailing separator", Left(testDir, 2), f.Drive.Path
Expect "Drive.RootFolder.Path does", Left(testDir, 2) & "\", f.Drive.RootFolder.Path

' ShortName is a NAME; ShortPath is a full path.
Expect "File.ShortName has no separator", 0, CLng(InStr(f.ShortName, "\") > 0)
Expect "File.ShortPath is a full path", -1, CLng(InStr(f.ShortPath, "\") > 0)
Expect "Folder.ShortName has no separator", 0, CLng(InStr(fo.ShortName, "\") > 0)
Expect "ShortPath ends with ShortName", -1, _
       CLng(Right(f.ShortPath, Len(f.ShortName)) = f.ShortName)

On Error Resume Next
fso.DeleteFile testFile
fso.DeleteFolder testDir
Err.Clear
On Error GoTo 0
%>
</tbody>
</table>

<h2>Still deliberately unavailable</h2>
<table>
<thead><tr><th>Check</th><th>Expected</th><th>Actual</th><th>Result</th></tr></thead>
<tbody>
<%
On Error Resume Next
Dim rc
rc = wsh.Run("cmd.exe /c exit", 0, True)
Expect "Run raises 429 (sandbox)", 429, Err.Number
Err.Clear
Dim ex
Set ex = wsh.Exec("cmd.exe /c echo hi")
Expect "Exec raises 429 (sandbox)", 429, Err.Number
Err.Clear
On Error GoTo 0
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
