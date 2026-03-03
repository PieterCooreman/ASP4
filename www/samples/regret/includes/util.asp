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

Function IsPost()
    IsPost = (UCase("" & Request.ServerVariables("REQUEST_METHOD")) = "POST")
End Function

Function GetClientIP()
    Dim ip
    ip = Request.ServerVariables("HTTP_X_FORWARDED_FOR")
    If ip = "" Then ip = Request.ServerVariables("REMOTE_ADDR")
    GetClientIP = Split(ip, ",")(0)
End Function

Function GenerateUUID()
    Randomize
    GenerateUUID = "" & _
        Hex(Int(Rnd * 65535)) & "-" & _
        Hex(Int(Rnd * 65535)) & "-" & _
        Hex(Int(Rnd * 65535)) & "-" & _
        Hex(Int(Rnd * 65535)) & "-" & _
        Hex(Int(Rnd * 65535) * 65535)
End Function

Function GetTimestamp()
    GetTimestamp = Now()
End Function

Function GetUTCMidnight()
    GetUTCMidnight = DateAdd("h", -8, Date() + 1)
End Function

Function GetTodayUTC()
    GetTodayUTC = DateValue(Now())
End Function

Function GetCategories()
    Dim cats(6)(1)
    cats(0)(0) = "love": cats(0)(1) = "💔"
    cats(1)(0) = "career": cats(1)(1) = "💼"
    cats(2)(0) = "family": cats(2)(1) = "👨‍👩‍👧"
    cats(3)(0) = "education": cats(3)(1) = "🎓"
    cats(4)(0) = "money": cats(4)(1) = "💰"
    cats(5)(0) = "life": cats(5)(1) = "🌍"
    cats(6)(0) = "unsaid": cats(6)(1) = "😶"
    GetCategories = cats
End Function

Function GetCategoryEmoji(category)
    Select Case LCase(category)
        Case "love": GetCategoryEmoji = "💔"
        Case "career": GetCategoryEmoji = "💼"
        Case "family": GetCategoryEmoji = "👨‍👩‍👧"
        Case "education": GetCategoryEmoji = "🎓"
        Case "money": GetCategoryEmoji = "💰"
        Case "life": GetCategoryEmoji = "🌍"
        Case "unsaid": GetCategoryEmoji = "😶"
        Case Else: GetCategoryEmoji = "💭"
    End Select
End Function

Function ContainsProfanity(text)
    Dim profanity(15)
    profanity(0) = "fuck"
    profanity(1) = "shit"
    profanity(2) = "ass"
    profanity(3) = "bitch"
    profanity(4) = "damn"
    profanity(5) = "hell"
    profanity(6) = "crap"
    profanity(7) = "dick"
    profanity(8) = "cock"
    profanity(9) = "piss"
    profanity(10) = "cunt"
    profanity(11) = "nigger"
    profanity(12) = "faggot"
    profanity(13) = "retard"
    profanity(14) = "whore"
    profanity(15) = "slut"
    
    Dim i, lowerText
    lowerText = LCase(text)
    For i = 0 To UBound(profanity)
        If InStr(lowerText, profanity(i)) > 0 Then
            ContainsProfanity = True
            Exit Function
        End If
    Next
    ContainsProfanity = False
End Function

Function ContainsCrisisKeywords(text)
    Dim keywords(10)
    keywords(0) = "suicide"
    keywords(1) = "kill myself"
    keywords(2) = "end my life"
    keywords(3) = "want to die"
    keywords(4) = "better off dead"
    keywords(5) = "hurt myself"
    keywords(6) = "self harm"
    keywords(7) = "cut myself"
    keywords(8) = "overdose"
    keywords(9) = "no point"
    keywords(10) = "nothing matters"
    
    Dim i, lowerText
    lowerText = LCase(text)
    For i = 0 To UBound(keywords)
        If InStr(lowerText, keywords(i)) > 0 Then
            ContainsCrisisKeywords = True
            Exit Function
        End If
    Next
    ContainsCrisisKeywords = False
End Function

Function GetTimeUntilMidnight()
    Dim nowUTC, midnight
    nowUTC = Now()
    midnight = DateValue(nowUTC) + 1
    GetTimeUntilMidnight = DateDiff("n", nowUTC, midnight)
End Function

Function FormatTimeRemaining(minutes)
    If minutes < 60 Then
        FormatTimeRemaining = minutes & " min"
    Else
        FormatTimeRemaining = Round(minutes / 60, 1) & " hours"
    End If
End Function
%>
