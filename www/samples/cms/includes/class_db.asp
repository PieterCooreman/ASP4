<%
Class cls_db
    Public Conn

    Public Sub Open()
        Dim dbPath
        dbPath = AppMap("db/cms.db")
        Set Conn = Server.CreateObject("ADODB.Connection")
        Conn.Open "Data Source=" & dbPath
    End Sub

    Public Function Query(sql)
        Set Query = Conn.Execute(sql)
    End Function

    Public Sub Execute(sql)
        Conn.Execute sql
    End Sub

    Public Function Scalar(sql, fallback)
        Dim rs
        On Error Resume Next
        Scalar = fallback
        Set rs = Query(sql)
        If Err.Number = 0 Then
            If Not rs.EOF Then
                Scalar = rs(0)
                If IsNull(Scalar) Or IsEmpty(Scalar) Then Scalar = fallback
            End If
        End If
        Err.Clear
        If Not rs Is Nothing Then
            rs.Close
            Set rs = Nothing
        End If
        On Error GoTo 0
    End Function

    Public Sub Close()
        On Error Resume Next
        If Not Conn Is Nothing Then Conn.Close
        Set Conn = Nothing
        On Error GoTo 0
    End Sub
End Class
%>
