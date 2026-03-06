<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<!-- #include file="includes/includes.asp" -->
<%
Dim svc, errMsg
Set svc = New cls_zip_export
errMsg = ""

If IsPost() Then
    On Error Resume Next
    Dim zipPath
    zipPath = svc.BuildSamplesZip()
    If Err.Number <> 0 Then
        errMsg = "Could not build ZIP: " & Err.Description
        Err.Clear
    Else
        On Error GoTo 0
        Response.BinaryFile zipPath, False, True
        Response.End
    End If
    On Error GoTo 0
End If
%>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ZIP Sample</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet" crossorigin="anonymous">
  <style>
    .shell{max-width:720px;margin:0 auto}
  </style>
</head>
<body>
<main class="shell py-5">
  <div class="card border-0 shadow-sm">
    <div class="card-body">
      <h1 class="h4 mb-3">ZIP Samples Export</h1>
      <p class="text-muted mb-4">Click the button to create a ZIP of the entire <code>www/samples</code> folder and download it.</p>

      <% If errMsg <> "" Then %>
        <div class="alert alert-danger"><%=H(errMsg)%></div>
      <% End If %>

      <form method="post" action="default.asp" class="m-0">
        <button class="btn btn-primary" type="submit">Download Samples ZIP</button>
      </form>
    </div>
  </div>
</main>
</body>
</html>
