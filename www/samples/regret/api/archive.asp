<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<!-- #include file="../includes/includes.asp" -->
<%
Response.CodePage = 65001
Response.Charset = "UTF-8"
Response.ContentType = "application/json"
Response.AddHeader "Access-Control-Allow-Origin", "*"

Dim db, regretSvc, rs, archives(), i
Set db = New cls_db
db.Open
Set regretSvc = New cls_regret

i = 0
Set rs = regretSvc.GetDailyArchive(db)
Do While Not rs.EOF
    ReDim Preserve archives(i)
    archives(i) = Array("" & rs("date"), CLng(Nz(rs("total_regrets"), 0)), "" & Nz(rs("top_category"), ""), _
        CLng(Nz(rs("total_me_too"), 0)), CLng(Nz(rs("total_not_alone"), 0)))
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
    json = json & """date"":""" & H(archives(j)(0)) & ""","
    json = json & """total_regrets"":" & archives(j)(1) & ","
    json = json & """top_category"":""" & GetCategoryEmoji(H(archives(j)(2))) & " " & H(archives(j)(2)) & ""","
    json = json & """total_me_too"":" & archives(j)(3) & ","
    json = json & """total_not_alone"":" & archives(j)(4)
    json = json & "}"
Next
json = json & "]"

Response.Write json

db.Close
Set db = Nothing
%>
