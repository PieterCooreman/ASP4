<%
Function H(v)
    H = Server.HTMLEncode("" & v)
End Function

Function Nz(v, fallback)
    If IsNull(v) Or IsEmpty(v) Then
        Nz = fallback
    Else
        Nz = v
    End If
End Function

Function ToInt(v, fallback)
    Dim s
    s = Trim("" & v)
    If s = "" Then
        ToInt = fallback
    ElseIf IsNumeric(s) Then
        ToInt = CLng(s)
    Else
        ToInt = fallback
    End If
End Function

Function ToBool(v, fallback)
    Dim s
    s = LCase(Trim("" & v))
    If s = "" Then
        ToBool = fallback
    Else
        ToBool = (s = "1" Or s = "true" Or s = "yes" Or s = "on" Or s = "-1")
    End If
End Function

Function IsPost()
    IsPost = (UCase("" & Request.ServerVariables("REQUEST_METHOD")) = "POST")
End Function

Sub SetFlash(msg)
    Session("mail_flash") = "" & msg
End Sub

Function GetFlash()
    GetFlash = "" & Session("mail_flash")
    Session("mail_flash") = ""
End Function

Function TrimTo(s, maxLen)
    Dim t
    t = "" & s
    If Len(t) <= maxLen Then
        TrimTo = t
    Else
        TrimTo = Left(t, maxLen - 3) & "..."
    End If
End Function
%>
