<%
Class cls_user
    Public Function ListAll(db)
        Set ListAll = db.Query("SELECT id,name,email,is_admin,created_at,updated_at FROM users ORDER BY id DESC")
    End Function

    Public Function AdminCount(db)
        AdminCount = CLng(db.Scalar("SELECT COUNT(*) FROM users WHERE is_admin=1", 0))
    End Function

    Public Sub CreateUser(db, name, email, password, isAdmin)
        Dim sql, hashed
        hashed = ASP4.Crypto.Hash("" & password, 12)
        sql = "INSERT INTO users(name,email,password_hash,is_admin,created_at) VALUES ('" & Q(name) & "','" & Q(LCase(email)) & "','" & Q(hashed) & "'," & CInt(isAdmin) & ",datetime('now'))"
        db.Execute sql
    End Sub

    Public Sub UpdateUser(db, id, name, email, isAdmin)
        Dim sql
        sql = "UPDATE users SET name='" & Q(name) & "',email='" & Q(LCase(email)) & "',is_admin=" & CInt(isAdmin) & ",updated_at=datetime('now') WHERE id=" & CLng(id)
        db.Execute sql
    End Sub

    Public Sub SetPassword(db, id, password)
        Dim hashed
        hashed = ASP4.Crypto.Hash("" & password, 12)
        db.Execute "UPDATE users SET password_hash='" & Q(hashed) & "',updated_at=datetime('now') WHERE id=" & CLng(id)
    End Sub

    Public Sub DeleteUser(db, id)
        db.Execute "DELETE FROM users WHERE id=" & CLng(id)
    End Sub
End Class
%>
