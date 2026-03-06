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

Function IsPost()
    IsPost = (UCase("" & Request.ServerVariables("REQUEST_METHOD")) = "POST")
End Function

Function SafeFilePart(v)
    Dim s, i, c, out
    s = Trim("" & v)
    If s = "" Then s = "document"
    out = ""
    For i = 1 To Len(s)
        c = Mid(s, i, 1)
        If (c >= "a" And c <= "z") Or (c >= "A" And c <= "Z") Or (c >= "0" And c <= "9") Or c = "_" Or c = "-" Then
            out = out & c
        ElseIf c = " " Then
            out = out & "_"
        End If
    Next
    If out = "" Then out = "document"
    SafeFilePart = out
End Function
%>
