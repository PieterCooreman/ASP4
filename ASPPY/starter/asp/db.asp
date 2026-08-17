<%
Function OpenSqliteConnection(relativeDbPath)
    Dim dbPath, fso, conn, fileHandle
    dbPath = Server.MapPath(relativeDbPath)

    Set fso = Server.CreateObject("Scripting.FileSystemObject")
    If Not fso.FileExists(dbPath) Then
        Set fileHandle = fso.CreateTextFile(dbPath, True)
        fileHandle.Close
        Set fileHandle = Nothing
    End If

    Set conn = Server.CreateObject("ADODB.Connection")
    conn.Open "Provider=SQLite;Data Source=" & dbPath & ";"
    Set OpenSqliteConnection = conn
End Function

Function OpenAppConnection()
    Set OpenAppConnection = OpenSqliteConnection("data/app.db")
End Function

Function SqlEscape(rawValue)
    If IsNull(rawValue) Then
        SqlEscape = ""
    Else
        SqlEscape = Replace(CStr(rawValue), "'", "''")
    End If
End Function
%>
