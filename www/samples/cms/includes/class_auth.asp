<%
Class cls_auth
    Public Function IsLoggedIn()
        IsLoggedIn = (CLng(0 & Session("uid")) > 0)
    End Function

    Public Sub RequireLogin()
        If Not IsLoggedIn() Then
            Response.Redirect "admin.asp?m=login"
            Response.End
        End If
    End Sub

    Public Sub RequireAdmin()
        If CInt(0 & Session("is_admin")) <> 1 Then
            Response.Redirect "admin.asp?m=dashboard"
            Response.End
        End If
    End Sub

    Public Function Login(db, email, password)
        Dim rs, sql, stored
        Login = False
        sql = "SELECT id,name,email,is_admin,password_hash FROM users WHERE email='" & Q(LCase(Trim(email))) & "' LIMIT 1"
        Set rs = db.Query(sql)
        If Not rs.EOF Then
            stored = "" & rs("password_hash")
            If Left(stored, 4) = "$2b$" Then
                If ASP4.Crypto.Verify("" & password, stored) Then
                    Session("uid") = ToInt(rs("id"), 0)
                    Session("name") = "" & rs("name")
                    Session("email") = "" & rs("email")
                    Session("is_admin") = BoolInt(rs("is_admin"))
                    Login = True
                End If
            ElseIf stored = "" & password Then
                db.Execute "UPDATE users SET password_hash='" & Q(ASP4.Crypto.Hash("" & password, 12)) & "',updated_at=datetime('now') WHERE id=" & ToInt(rs("id"), 0)
                Session("uid") = ToInt(rs("id"), 0)
                Session("name") = "" & rs("name")
                Session("email") = "" & rs("email")
                Session("is_admin") = BoolInt(rs("is_admin"))
                Login = True
            End If
        End If
        rs.Close
        Set rs = Nothing
    End Function

    Public Sub Logout()
        Session("uid") = ""
        Session("name") = ""
        Session("email") = ""
        Session("is_admin") = 0
    End Sub
End Class
%>
