<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<!-- #include file="../includes/includes.asp" -->
<%
Response.CodePage = 65001
Response.Charset = "UTF-8"
Response.ContentType = "application/json"
Response.AddHeader "Access-Control-Allow-Origin", "*"
Response.AddHeader "Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS"
Response.AddHeader "Access-Control-Allow-Headers", "Content-Type"

If Request.ServerVariables("REQUEST_METHOD") = "OPTIONS" Then
    Response.End
End If

Dim db, bpSvc, method
Set db = New cls_db
db.Open
Set bpSvc = New cls_blueprint

method = UCase(Request.ServerVariables("REQUEST_METHOD"))

If method = "GET" Then
    Dim id, sortBy, search, category, status
    
    id = Request.QueryString("id")
    sortBy = Request.QueryString("sort")
    search = Trim("" & Request.QueryString("search"))
    category = Trim("" & Request.QueryString("category"))
    status = Trim("" & Request.QueryString("status"))
    
    If id <> "" Then
        Dim rs, bp
        Set rs = bpSvc.GetBlueprintById(db, id)
        
        If Not rs.EOF Then
            Response.Write "{"
            Response.Write """id"":""" & H(rs("id")) & ""","
            Response.Write """name"":""" & H(rs("name")) & ""","
            Response.Write """one_liner"":""" & H(rs("one_liner")) & ""","
            Response.Write """problem"":""" & H(rs("problem")) & ""","
            Response.Write """user_target"":""" & H(rs("user_target")) & ""","
            Response.Write """hook"":""" & H(rs("hook")) & ""","
            Response.Write """risk"":""" & H(rs("risk")) & ""","
            Response.Write """spark_score"":" & rs("spark_score") & ","
            Response.Write """category"":""" & H(rs("category")) & ""","
            Response.Write """tags"":""" & H(rs("tags")) & ""","
            Response.Write """status"":""" & H(rs("status")) & ""","
            Response.Write """notes"":""" & H(rs("notes")) & ""","
            Response.Write """created_at"":""" & H(rs("created_at")) & ""","
            Response.Write """updated_at"":""" & H(rs("updated_at")) & """"
            Response.Write "}"
        Else
            Response.Write "{""error"":""Blueprint not found""}"
        End If
        rs.Close
        Set rs = Nothing
    Else
        Dim rsList, blueprints(), i
        i = 0
        Set rsList = bpSvc.GetAllBlueprints(db, sortBy, search, category, status)
        Do While Not rsList.EOF
            ReDim Preserve blueprints(i)
            blueprints(i) = Array("" & rsList("id"), "" & rsList("name"), "" & rsList("one_liner"), _
                "" & rsList("category"), CInt(rsList("spark_score")), "" & rsList("status"), "" & rsList("tags"), "" & rsList("created_at"))
            rsList.MoveNext
            i = i + 1
        Loop
        rsList.Close
        Set rsList = Nothing
        
        Dim json, j
        json = "["
        For j = 0 To i - 1
            If j > 0 Then json = json & ","
            json = json & "{"
            json = json & """id"":""" & H(blueprints(j)(0)) & ""","
            json = json & """name"":""" & H(blueprints(j)(1)) & ""","
            json = json & """one_liner"":""" & H(blueprints(j)(2)) & ""","
            json = json & """category"":""" & H(blueprints(j)(3)) & ""","
            json = json & """spark_score"":" & blueprints(j)(4) & ","
            json = json & """status"":""" & H(blueprints(j)(5)) & ""","
            json = json & """tags"":""" & H(blueprints(j)(6)) & ""","
            json = json & """created_at"":""" & H(blueprints(j)(7)) & """"
            json = json & "}"
        Next
        json = json & "]"
        
        Response.Write json
    End If
    
ElseIf method = "POST" Then
    If Request.QueryString("action") = "revisit" Then
        Dim revisitId, newScore
        revisitId = Request.QueryString("id")
        newScore = ToInt(Request.Form("score"), 3)
        
        If revisitId = "" Then
            Response.Status = 400
            Response.Write "{""error"":""Blueprint ID required""}"
            db.Close: Set db = Nothing
            Response.End
        End If
        
        bpSvc.AddSparkRevisit db, revisitId, newScore
        Response.Write "{""success"":true}"
    ElseIf Request.QueryString("action") = "delete" Then
        Dim deleteId
        deleteId = Request.QueryString("id")
        
        If deleteId = "" Then
            Response.Status = 400
            Response.Write "{""error"":""ID is required""}"
            db.Close: Set db = Nothing
            Response.End
        End If
        
        bpSvc.DeleteBlueprint db, deleteId
        Response.Write "{""success"":true}"
    Else
        Dim name, oneLiner, problem, userTarget, hook, risk, sparkScore, cat, tags, bpStatus, notes
        
        name = Trim("" & Request.Form("name"))
        oneLiner = Trim("" & Request.Form("one_liner"))
        problem = Trim("" & Request.Form("problem"))
        userTarget = Trim("" & Request.Form("user_target"))
        hook = Trim("" & Request.Form("hook"))
        risk = Trim("" & Request.Form("risk"))
        sparkScore = ToInt(Request.Form("spark_score"), 3)
        cat = Trim("" & Request.Form("category"))
        tags = Trim("" & Request.Form("tags"))
        bpStatus = Trim("" & Request.Form("status"))
        notes = Trim("" & Request.Form("notes"))
        
        If name = "" Then
            Response.Status = 400
            Response.Write "{""error"":""Name is required""}"
            db.Close: Set db = Nothing
            Response.End
        End If
        
        If Len(name) > 60 Then name = Left(name, 60)
        If Len(oneLiner) > 120 Then oneLiner = Left(oneLiner, 120)
        If Len(problem) > 300 Then problem = Left(problem, 300)
        If Len(userTarget) > 200 Then userTarget = Left(userTarget, 200)
        If Len(hook) > 300 Then hook = Left(hook, 300)
        If Len(risk) > 200 Then risk = Left(risk, 200)
        
        If cat = "" Then cat = "app"
        If bpStatus = "" Then bpStatus = "idea"
        
        Dim newId
        newId = bpSvc.CreateBlueprint(db, name, oneLiner, problem, userTarget, hook, risk, sparkScore, cat, tags, bpStatus, notes)
        
        Response.Write "{""id"":""" & H(newId) & """}"
    End If
    
ElseIf method = "PUT" Then
    Dim updateId, upName, upOneLiner, upProblem, upUserTarget, upHook, upRisk, upSparkScore, upCategory, upTags, upStatus, upNotes
    
    updateId = Request.QueryString("id")
    upName = Trim("" & Request.Form("name"))
    upOneLiner = Trim("" & Request.Form("one_liner"))
    upProblem = Trim("" & Request.Form("problem"))
    upUserTarget = Trim("" & Request.Form("user_target"))
    upHook = Trim("" & Request.Form("hook"))
    upRisk = Trim("" & Request.Form("risk"))
    upSparkScore = ToInt(Request.Form("spark_score"), 3)
    upCategory = Trim("" & Request.Form("category"))
    upTags = Trim("" & Request.Form("tags"))
    upStatus = Trim("" & Request.Form("status"))
    upNotes = Trim("" & Request.Form("notes"))
    
    If updateId = "" Or upName = "" Then
        Response.Status = 400
        Response.Write "{""error"":""ID and name are required""}"
        db.Close: Set db = Nothing
        Response.End
    End If
    
    bpSvc.UpdateBlueprint db, updateId, upName, upOneLiner, upProblem, upUserTarget, upHook, upRisk, upSparkScore, upCategory, upTags, upStatus, upNotes
    
    Response.Write "{""success"":true}"
    
ElseIf method = "POST" Then
    If Request.QueryString("action") = "delete" Then
        Dim deleteId
        deleteId = Request.QueryString("id")
        
        If deleteId = "" Then
            Response.Status = 400
            Response.Write "{""error"":""ID is required""}"
            db.Close: Set db = Nothing
            Response.End
        End If
        
        bpSvc.DeleteBlueprint db, deleteId
        Response.Write "{""success"":true}"
    Else
        Response.Status = 400
        Response.Write "{""error"":""Unknown action""}"
    End If
    
Else
    Response.Status = 405
    Response.Write "{""error"":""Method not allowed""}"
End If

db.Close
Set db = Nothing
%>
