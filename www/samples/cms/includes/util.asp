<%
Function H(v)
    H = Server.HTMLEncode("" & v)
End Function

Function Q(v)
    Q = Replace("" & v, "'", "''")
End Function

Function Nz(v, fallback)
    If IsNull(v) Then
        Nz = fallback
    ElseIf IsEmpty(v) Then
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

Function IsTruthy(v)
    Dim s
    s = LCase(Trim("" & v))
    IsTruthy = (s = "1" Or s = "true" Or s = "yes" Or s = "on" Or s = "-1")
End Function

Function BoolInt(v)
    If IsTruthy(v) Then
        BoolInt = 1
    Else
        BoolInt = 0
    End If
End Function

Function IsPost()
    IsPost = (UCase("" & Request.ServerVariables("REQUEST_METHOD")) = "POST")
End Function

Sub SetFlash(msg)
    Session("flash_msg") = "" & msg
End Sub

Function GetFlash()
    GetFlash = "" & Session("flash_msg")
    Session("flash_msg") = ""
End Function

Function Slugify(v)
    Dim s, i, ch, out
    s = LCase(Trim("" & v))
    out = ""
    For i = 1 To Len(s)
        ch = Mid(s, i, 1)
        If (ch >= "a" And ch <= "z") Or (ch >= "0" And ch <= "9") Then
            out = out & ch
        ElseIf ch = " " Or ch = "-" Or ch = "_" Then
            out = out & "-"
        End If
    Next
    Do While InStr(out, "--") > 0
        out = Replace(out, "--", "-")
    Loop
    If Left(out, 1) = "-" Then out = Mid(out, 2)
    If Right(out, 1) = "-" Then out = Left(out, Len(out) - 1)
    If out = "" Then out = "page-" & Replace(CStr(Timer()), ".", "")
    Slugify = out
End Function

Function SafeFileName(fileName)
    Dim s, i, ch, out
    s = "" & fileName
    out = ""
    For i = 1 To Len(s)
        ch = Mid(s, i, 1)
        If (ch >= "a" And ch <= "z") Or (ch >= "A" And ch <= "Z") Or (ch >= "0" And ch <= "9") Or ch = "." Or ch = "_" Or ch = "-" Then
            out = out & ch
        Else
            out = out & "_"
        End If
    Next
    SafeFileName = out
End Function

Function AppBasePath()
    Dim p, pos
    p = Replace("" & Request.ServerVariables("SCRIPT_NAME"), "\", "/")
    pos = InStrRev(p, "/")
    If pos > 0 Then
        AppBasePath = Left(p, pos - 1)
    Else
        AppBasePath = ""
    End If
End Function

Function NormalizeRelPath(relPath)
    Dim p, posUploads
    p = Replace(Trim("" & relPath), "\", "/")
    Do While Left(p, 1) = "/"
        p = Mid(p, 2)
    Loop
    posUploads = InStr(LCase(p), "uploads/")
    If posUploads > 1 Then
        p = Mid(p, posUploads)
    End If
    NormalizeRelPath = p
End Function

Function AppUrl(relPath)
    Dim r, base
    r = NormalizeRelPath(relPath)
    base = AppBasePath()
    If base = "" Then
        AppUrl = "/" & r
    Else
        AppUrl = base & "/" & r
    End If
End Function

Function AppMap(relPath)
    AppMap = Server.MapPath(AppUrl(relPath))
End Function

Function PalettePreset(name)
    Dim d : Set d = Server.CreateObject("Scripting.Dictionary")
    name = LCase(Trim("" & name))

    Select Case name
        Case "forest"
            d("name") = "forest"
            d("primary") = "#2f855a"
            d("secondary") = "#4a5568"
            d("success") = "#15803d"
            d("danger") = "#b91c1c"
            d("warning") = "#d97706"
            d("info") = "#0f766e"
            d("light") = "#f7fafc"
            d("dark") = "#1a202c"
        Case "sunset"
            d("name") = "sunset"
            d("primary") = "#ea580c"
            d("secondary") = "#6b7280"
            d("success") = "#16a34a"
            d("danger") = "#dc2626"
            d("warning") = "#f59e0b"
            d("info") = "#0284c7"
            d("light") = "#fff7ed"
            d("dark") = "#1f2937"
        Case "slate"
            d("name") = "slate"
            d("primary") = "#334155"
            d("secondary") = "#64748b"
            d("success") = "#15803d"
            d("danger") = "#b91c1c"
            d("warning") = "#ca8a04"
            d("info") = "#0369a1"
            d("light") = "#f8fafc"
            d("dark") = "#0f172a"
        Case Else
            d("name") = "ocean"
            d("primary") = "#0ea5e9"
            d("secondary") = "#64748b"
            d("success") = "#16a34a"
            d("danger") = "#dc2626"
            d("warning") = "#f59e0b"
            d("info") = "#0891b2"
            d("light") = "#f8fafc"
            d("dark") = "#0f172a"
    End Select

    Set PalettePreset = d
End Function
%>
