<%
Class cls_menu
    Public Sub NormalizeOrders(db)
        Dim rs, i, pageId
        i = 1
        Set rs = db.Query("SELECT id FROM pages ORDER BY menu_order ASC, id ASC")
        Do Until rs.EOF
            pageId = ToInt(rs("id"), 0)
            If pageId > 0 Then
                db.Execute "UPDATE pages SET menu_order=" & i & " WHERE id=" & pageId
                i = i + 1
            End If
            rs.MoveNext
        Loop
        rs.Close
        Set rs = Nothing
    End Sub

    Public Function ListForEditor(db)
        Set ListForEditor = db.Query("SELECT id,title,slug,status,menu_order FROM pages ORDER BY menu_order ASC, id ASC")
    End Function

    Public Sub MoveUp(db, id)
        Dim rs, curOrder, prevId
        Call NormalizeOrders(db)
        curOrder = ToInt(db.Scalar("SELECT menu_order FROM pages WHERE id=" & ToInt(id, 0), 0), 0)
        Set rs = db.Query("SELECT id FROM pages WHERE menu_order=" & (curOrder - 1) & " LIMIT 1")
        If Not rs.EOF Then
            prevId = ToInt(rs("id"), 0)
            db.Execute "UPDATE pages SET menu_order=" & (curOrder - 1) & " WHERE id=" & ToInt(id, 0)
            db.Execute "UPDATE pages SET menu_order=" & curOrder & " WHERE id=" & prevId
        End If
        rs.Close
        Set rs = Nothing
    End Sub

    Public Sub MoveDown(db, id)
        Dim rs, curOrder, nextId
        Call NormalizeOrders(db)
        curOrder = ToInt(db.Scalar("SELECT menu_order FROM pages WHERE id=" & ToInt(id, 0), 0), 0)
        Set rs = db.Query("SELECT id FROM pages WHERE menu_order=" & (curOrder + 1) & " LIMIT 1")
        If Not rs.EOF Then
            nextId = ToInt(rs("id"), 0)
            db.Execute "UPDATE pages SET menu_order=" & (curOrder + 1) & " WHERE id=" & ToInt(id, 0)
            db.Execute "UPDATE pages SET menu_order=" & curOrder & " WHERE id=" & nextId
        End If
        rs.Close
        Set rs = Nothing
    End Sub
End Class
%>
