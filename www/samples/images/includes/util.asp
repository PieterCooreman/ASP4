<%
Function H(v)
    H = Server.HTMLEncode("" & v)
End Function

Function Q(v)
    Q = Replace("" & v, "'", "''")
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

Function SafeBaseName(fileName)
    Dim s, p, b, i, ch, out
    s = "" & fileName
    p = InStrRev(s, ".")
    If p > 1 Then
        b = Left(s, p - 1)
    Else
        b = s
    End If
    out = ""
    For i = 1 To Len(b)
        ch = Mid(b, i, 1)
        If (ch >= "a" And ch <= "z") Or (ch >= "A" And ch <= "Z") Or (ch >= "0" And ch <= "9") Or ch = "_" Or ch = "-" Then
            out = out & ch
        Else
            out = out & "_"
        End If
    Next
    If Len(out) > 80 Then out = Left(out, 80)
    If out = "" Then out = "img"
    SafeBaseName = out
End Function

Sub SetFlash(msg)
    Session("images_flash") = "" & msg
End Sub

Function GetFlash()
    GetFlash = "" & Session("images_flash")
    Session("images_flash") = ""
End Function
%>
