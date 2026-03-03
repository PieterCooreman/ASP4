<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<!-- #include file="../includes/includes.asp" -->
<%
Response.CodePage = 65001
Response.Charset = "UTF-8"
Response.ContentType = "application/json"
Response.AddHeader "Access-Control-Allow-Origin", "*"
Response.AddHeader "Access-Control-Allow-Methods", "GET, POST, OPTIONS"
Response.AddHeader "Access-Control-Allow-Headers", "Content-Type"

If Request.ServerVariables("REQUEST_METHOD") = "OPTIONS" Then
    Response.End
End If

Dim db, regretSvc, method
Set db = New cls_db
db.Open
Set regretSvc = New cls_regret

regretSvc.PurgeExpiredRegrets db

method = UCase(Request.ServerVariables("REQUEST_METHOD"))

If method = "GET" Then
    Dim sortBy, rs, regrets(), i
    sortBy = Request.QueryString("sort")
    If sortBy = "" Then sortBy = "newest"
    
    i = 0
    Set rs = regretSvc.GetActiveRegrets(db, sortBy)
    Do While Not rs.EOF
        ReDim Preserve regrets(i)
        regrets(i) = Array("" & rs("id"), "" & rs("text"), "" & rs("category"), _
            CInt(rs("me_too")), CInt(rs("not_alone")), "" & rs("created_at"))
        rs.MoveNext
        i = i + 1
    Loop
    rs.Close
    Set rs = Nothing
    
    Dim json, j
    json = "["
    For j = 0 To i - 1
        If j > 0 Then json = json & ","
        json = json & "{"
        json = json & """id"":""" & H(regrets(j)(0)) & ""","
        json = json & """text"":""" & H(regrets(j)(1)) & ""","
        json = json & """category"":""" & H(regrets(j)(2)) & ""","
        json = json & """me_too"":" & regrets(j)(3) & ","
        json = json & """not_alone"":" & regrets(j)(4) & ","
        json = json & """created_at"":""" & H(regrets(j)(5)) & """"
        json = json & "}"
    Next
    json = json & "]"
    
    Response.Write json
    
ElseIf method = "POST" Then
    Dim action, regretId
    
    action = Request.QueryString("action")
    
    If action = "vote" Then
        regretId = Trim("" & Request.QueryString("id"))
        Dim voteType
        voteType = Trim("" & Request.Form("vote"))
        
        If regretId = "" Or (voteType <> "me_too" And voteType <> "not_alone") Then
            Response.Status = 400
            Response.Write "{""error"":""Invalid request""}"
            db.Close: Set db = Nothing
            Response.End
        End If
        
        Dim canVote
        canVote = regretSvc.CheckVoteLimit(db, GetClientIP())
        
        If Not canVote Then
            Response.Status = 429
            Response.Write "{""error"":""Vote limit exceeded. Max 20 votes per day.""}"
            db.Close: Set db = Nothing
            Response.End
        End If
        
        regretSvc.Vote db, regretId, voteType
        regretSvc.IncrementVoteCount db, GetClientIP()
        
        Response.Write "{""success"":true}"
        
    Else
        Dim text, category, clientIP, canPost
        clientIP = GetClientIP()
        canPost = regretSvc.CheckRegretLimit(db, clientIP)
        
        If Not canPost Then
            Response.Status = 429
            Response.Write "{""error"":""You can only drop one regret per day. Make it count.""}"
            db.Close: Set db = Nothing
            Response.End
        End If
        
        text = Trim("" & Request.Form("text"))
        category = Trim("" & Request.Form("category"))
        
        If text = "" Then
            Response.Status = 400
            Response.Write "{""error"":""Regret cannot be empty""}"
            db.Close: Set db = Nothing
            Response.End
        End If
        
        If Len(text) > 160 Then
            text = Left(text, 160)
        End If
        
        If ContainsProfanity(text) Then
            Response.Status = 400
            Response.Write "{""error"":""Your regret contains inappropriate content""}"
            db.Close: Set db = Nothing
            Response.End
        End If
        
        If ContainsCrisisKeywords(text) Then
            Response.Write "{""crisis"":true,""message"":""If you're carrying something heavy, you don't have to carry it alone."",""helpline"":""988""}"
            db.Close: Set db = Nothing
            Response.End
        End If
        
        If category = "" Then category = "life"
        
        Dim newId
        newId = regretSvc.CreateRegret(db, text, category)
        regretSvc.IncrementRegretCount db, clientIP
        
        Response.Write "{"
        Response.Write """id"":""" & H(newId) & """"
        Response.Write "}"
    End If
    
Else
    Response.Status = 405
    Response.Write "{""error"":""Method not allowed""}"
End If

db.Close
Set db = Nothing
%>
