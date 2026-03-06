<%
Class cls_db
    Public Conn

    Public Sub Open()
        Dim dbPath
        dbPath = Server.MapPath("db/images.db")
        Set Conn = Server.CreateObject("ADODB.Connection")
        Conn.Open "Provider=SQLite;Data Source=" & dbPath
    End Sub

    Public Function Query(sql)
        Set Query = Conn.Execute(sql)
    End Function

    Public Sub Execute(sql)
        Conn.Execute sql
    End Sub

    Public Function Scalar(sql, fallback)
        Dim rs
        Scalar = fallback
        Set rs = Query(sql)
        If Not rs.EOF Then Scalar = Nz(rs(0), fallback)
        rs.Close
        Set rs = Nothing
    End Function

    Public Sub Close()
        On Error Resume Next
        If Not Conn Is Nothing Then Conn.Close
        Set Conn = Nothing
        On Error GoTo 0
    End Sub
End Class
%>
