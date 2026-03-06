<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<!-- #include file="includes/includes.asp" -->
<%
Dim mailSvc, action, flashMsg, m
Dim proto, host, port, username, password, useSSL, folder, maxItems, msgId, attIdx
Dim canLoadList, errorMsg

Set mailSvc = New cls_mailclient
action = LCase(Trim("" & Request.Form("action")))
m = LCase(Trim("" & Request.QueryString("m")))
If m = "" Then m = "list"

If action = "clear" Then
    Session("mail_proto") = ""
    Session("mail_host") = ""
    Session("mail_port") = ""
    Session("mail_user") = ""
    Session("mail_pass") = ""
    Session("mail_ssl") = ""
    Session("mail_folder") = ""
    Session("mail_limit") = ""
    SetFlash "Connection settings cleared."
    Response.Redirect "default.asp"
    Response.End
End If

If action = "connect" Then
    proto = LCase(Trim("" & Request.Form("proto")))
    If proto <> "pop3" And proto <> "imap" Then proto = "imap"

    host = Trim("" & Request.Form("host"))
    port = ToInt(Request.Form("port"), 0)
    username = Trim("" & Request.Form("username"))
    password = "" & Request.Form("password")
    useSSL = ToBool(Request.Form("use_ssl"), True)
    folder = Trim("" & Request.Form("folder"))
    maxItems = ToInt(Request.Form("max_items"), 25)
    If maxItems < 1 Then maxItems = 25
    If maxItems > 200 Then maxItems = 200

    If port <= 0 Then
        If proto = "pop3" Then
            port = 995
        Else
            port = 993
        End If
    End If

    If folder = "" Then folder = "INBOX"

    Session("mail_proto") = proto
    Session("mail_host") = host
    Session("mail_port") = CStr(port)
    Session("mail_user") = username
    Session("mail_pass") = password
    If useSSL Then
        Session("mail_ssl") = "1"
    Else
        Session("mail_ssl") = "0"
    End If
    Session("mail_folder") = folder
    Session("mail_limit") = CStr(maxItems)

    SetFlash "Settings saved."
    Response.Redirect "default.asp"
    Response.End
End If

proto = LCase(Trim("" & Session("mail_proto")))
If proto <> "pop3" And proto <> "imap" Then proto = ""
host = Trim("" & Session("mail_host"))
port = ToInt(Session("mail_port"), 0)
username = Trim("" & Session("mail_user"))
password = "" & Session("mail_pass")
useSSL = ToBool(Session("mail_ssl"), True)
folder = Trim("" & Session("mail_folder"))
maxItems = ToInt(Session("mail_limit"), 25)
If maxItems < 1 Then maxItems = 25
If maxItems > 200 Then maxItems = 200
If folder = "" Then folder = "INBOX"
If port <= 0 Then
    If proto = "pop3" Then
        port = 995
    Else
        port = 993
    End If
End If

canLoadList = (proto <> "" And host <> "" And username <> "" And password <> "")
flashMsg = GetFlash()
errorMsg = ""

If canLoadList And m = "download_attachment" Then
    Dim dlClient, dlMsg, dlBytes, dlName, dlType
    msgId = Trim("" & Request.QueryString("msg_id"))
    attIdx = ToInt(Request.QueryString("ai"), 0)

    If msgId = "" Or attIdx <= 0 Then
        Response.Status = "404 Not Found"
        Response.Write "Attachment not found"
        Response.End
    End If

    Set dlClient = Nothing
    On Error Resume Next
    Set dlClient = mailSvc.OpenClient(proto, host, port, username, password, useSSL, folder)
    If Err.Number <> 0 Then
        Err.Clear
        mailSvc.CloseClient dlClient
        Set dlClient = Nothing
        Response.Status = "404 Not Found"
        Response.Write "Attachment unavailable"
        Response.End
    End If

    If proto = "pop3" Then
        Set dlMsg = dlClient.GetMessage(ToInt(msgId, 0))
    Else
        Set dlMsg = dlClient.GetMessage(msgId)
    End If

    If Err.Number <> 0 Then
        Err.Clear
        mailSvc.CloseClient dlClient
        Set dlClient = Nothing
        Response.Status = "404 Not Found"
        Response.Write "Attachment unavailable"
        Response.End
    End If

    dlName = "" & dlMsg.AttachmentName(attIdx)
    dlType = "" & dlMsg.AttachmentContentType(attIdx)
    dlBytes = dlMsg.AttachmentBytes(attIdx)
    If Err.Number <> 0 Then
        Err.Clear
        mailSvc.CloseClient dlClient
        Set dlClient = Nothing
        Response.Status = "404 Not Found"
        Response.Write "Attachment unavailable"
        Response.End
    End If
    mailSvc.CloseClient dlClient
    Set dlClient = Nothing
    Response.FileBytes dlBytes, dlType, dlName, False
    Response.End
End If
%>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mail Reader Sample</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet" crossorigin="anonymous">
  <style>
    body{background:radial-gradient(circle at top,#f3f7ff 0,#f8fafc 45%,#eef2ff 100%)}
    .shell{max-width:1200px;margin:0 auto}
    .mail-table td{vertical-align:top}
    .mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
  </style>
</head>
<body>
<main class="shell py-4">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h1 class="h4 mb-0">ASPpy Mail Reader</h1>
    <span class="text-muted small">POP3 + IMAP</span>
  </div>

  <% If flashMsg <> "" Then %><div class="alert alert-info py-2"><%=H(flashMsg)%></div><% End If %>
  <% If errorMsg <> "" Then %><div class="alert alert-danger py-2"><%=H(errorMsg)%></div><% End If %>

  <div class="card border-0 shadow-sm mb-4">
    <div class="card-body">
      <h2 class="h6 mb-3">Connection</h2>
      <form method="post" action="default.asp" class="row g-2">
        <input type="hidden" name="action" value="connect">
        <div class="col-12 col-md-2">
          <label class="form-label">Protocol</label>
          <select class="form-select" name="proto" id="protoSel">
            <option value="imap" <%If proto="imap" Then Response.Write("selected")%>>IMAP</option>
            <option value="pop3" <%If proto="pop3" Then Response.Write("selected")%>>POP3</option>
          </select>
        </div>
        <div class="col-12 col-md-3">
          <label class="form-label">Mail server</label>
          <input class="form-control" name="host" value="<%=H(host)%>" placeholder="mail.example.com" required>
        </div>
        <div class="col-6 col-md-1">
          <label class="form-label">Port</label>
          <input class="form-control" name="port" id="portInput" value="<%=H(port)%>" placeholder="993" required>
        </div>
        <div class="col-6 col-md-2">
          <label class="form-label">Username</label>
          <input class="form-control" name="username" value="<%=H(username)%>" required>
        </div>
        <div class="col-12 col-md-2">
          <label class="form-label">Password</label>
          <input class="form-control" type="password" name="password" value="<%=H(password)%>" required>
        </div>
        <div class="col-6 col-md-1">
          <label class="form-label">Folder</label>
          <input class="form-control" name="folder" value="<%=H(folder)%>" placeholder="INBOX">
        </div>
        <div class="col-6 col-md-1">
          <label class="form-label">Max</label>
          <input class="form-control" name="max_items" value="<%=H(maxItems)%>" placeholder="25">
        </div>
        <div class="col-12 d-flex justify-content-between align-items-center mt-2">
          <div class="form-check">
            <input class="form-check-input" type="checkbox" name="use_ssl" id="sslChk" value="1" <%If useSSL Then Response.Write("checked")%>>
            <label class="form-check-label" for="sslChk">Use SSL/TLS</label>
          </div>
          <div class="d-flex gap-2">
            <button class="btn btn-primary" type="submit">Connect / Refresh</button>
          </div>
        </div>
      </form>
      <div class="d-flex justify-content-end mt-2">
        <form method="post" action="default.asp" class="m-0">
          <input type="hidden" name="action" value="clear">
          <button class="btn btn-outline-secondary" type="submit">Clear</button>
        </form>
      </div>
    </div>
  </div>

  <% If Not canLoadList Then %>
    <div class="alert alert-secondary">Enter server, credentials and protocol first. Then this page fetches and lists messages.</div>
  <% ElseIf m = "view" Then %>
    <%
    Dim viewClient, viewMsg, viewErr, viewCount, viewI
    viewErr = ""
    msgId = Trim("" & Request.QueryString("msg_id"))
    Set viewClient = Nothing
    Set viewMsg = Nothing
    On Error Resume Next
    Set viewClient = mailSvc.OpenClient(proto, host, port, username, password, useSSL, folder)
    If Err.Number <> 0 Then
        viewErr = "Could not connect: " & Err.Description
        Err.Clear
    ElseIf msgId = "" Then
        viewErr = "Message id is missing."
    Else
        If proto = "pop3" Then
            Set viewMsg = viewClient.GetMessage(ToInt(msgId, 0))
        Else
            Set viewMsg = viewClient.GetMessage(msgId)
        End If
        If Err.Number <> 0 Then
            viewErr = "Could not load message: " & Err.Description
            Err.Clear
        End If
    End If
    On Error GoTo 0
    %>

    <div class="d-flex justify-content-between align-items-center mb-3">
      <a class="btn btn-sm btn-outline-secondary" href="default.asp">Back to list</a>
      <span class="small text-muted mono"><%=H(UCase(proto))%> @ <%=H(host)%>:<%=H(port)%></span>
    </div>

    <% If viewErr <> "" Then %>
      <div class="alert alert-danger"><%=H(viewErr)%></div>
    <% Else %>
      <div class="card border-0 shadow-sm mb-3">
        <div class="card-body">
          <h2 class="h6 mb-3">Message <span class="mono"><%=H(msgId)%></span></h2>
          <div class="row g-2 small">
            <div class="col-12"><strong>From:</strong> <%=H(viewMsg.From)%></div>
            <div class="col-12"><strong>To:</strong> <%=H(viewMsg.To)%></div>
            <div class="col-12"><strong>Subject:</strong> <%=H(viewMsg.Subject)%></div>
            <div class="col-12"><strong>Date:</strong> <%=H(viewMsg.Date)%></div>
          </div>
        </div>
      </div>

      <div class="card border-0 shadow-sm mb-3">
        <div class="card-body">
          <h3 class="h6">Attachments (<%=H(viewMsg.AttachmentCount)%>)</h3>
          <%
          viewCount = ToInt(viewMsg.AttachmentCount, 0)
          If viewCount <= 0 Then
              Response.Write "<div class='text-muted small'>No attachments.</div>"
          Else
              Response.Write "<ul class='list-group list-group-flush'>"
              For viewI = 1 To viewCount
                  Response.Write "<li class='list-group-item px-0 d-flex justify-content-between align-items-center'>"
                  Response.Write "<div>"
                  Response.Write "<div class='fw-medium'>" & H(viewMsg.AttachmentName(viewI)) & "</div>"
                  Response.Write "<div class='small text-muted'>" & H(viewMsg.AttachmentContentType(viewI)) & " - " & H(viewMsg.AttachmentSize(viewI)) & " bytes</div>"
                  Response.Write "</div>"
                  Response.Write "<a class='btn btn-sm btn-outline-primary' href='default.asp?m=download_attachment&msg_id=" & Server.URLEncode(msgId) & "&ai=" & viewI & "'>Download</a>"
                  Response.Write "</li>"
              Next
              Response.Write "</ul>"
          End If
          %>
        </div>
      </div>

      <div class="card border-0 shadow-sm">
        <div class="card-body">
          <h3 class="h6">Body (text preview)</h3>
          <pre class="small mb-0" style="white-space:pre-wrap"><%=H(viewMsg.Body)%></pre>
        </div>
      </div>
    <% End If %>

    <%
    mailSvc.CloseClient viewClient
    Set viewClient = Nothing
    Set viewMsg = Nothing
    %>
  <% Else %>
    <div class="card border-0 shadow-sm">
      <div class="card-body">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <h2 class="h6 mb-0">Messages</h2>
          <span class="small text-muted mono"><%=H(UCase(proto))%> @ <%=H(host)%>:<%=H(port)%></span>
        </div>
        <div class="table-responsive">
          <table class="table table-sm mail-table align-middle mb-0">
            <thead>
              <tr>
                <th style="width:90px">ID</th>
                <th>Subject</th>
                <th style="width:260px">From</th>
                <th style="width:260px">Attachments</th>
                <th style="width:200px">Date</th>
                <th style="width:180px">Actions</th>
              </tr>
            </thead>
            <tbody>
              <%
              Dim client, i, shown, seq, msg, totalCount, lower, delId
              Set client = Nothing
              On Error Resume Next
              Set client = mailSvc.OpenClient(proto, host, port, username, password, useSSL, folder)

              If Err.Number <> 0 Then
                  Response.Write "<tr><td colspan='6' class='text-danger'>Could not connect: " & H(Err.Description) & "</td></tr>"
                  Err.Clear
              Else
                  If IsPost() And LCase(Trim("" & Request.Form("action"))) = "delete" Then
                      delId = Trim("" & Request.Form("msg_id"))
                      If delId <> "" Then
                          mailSvc.DeleteMessage proto, client, delId
                          If Err.Number <> 0 Then
                              Response.Write "<tr><td colspan='6' class='text-danger'>Delete failed: " & H(Err.Description) & "</td></tr>"
                              Err.Clear
                          Else
                              SetFlash "Message " & delId & " deleted."
                              mailSvc.CloseClient client
                              Set client = Nothing
                              Response.Redirect "default.asp"
                              Response.End
                          End If
                      End If
                  End If

                  shown = 0
                  If proto = "pop3" Then
                      totalCount = ToInt(client.Stat(), 0)
                      If totalCount = 0 Then
                          Response.Write "<tr><td colspan='6' class='text-muted'>No messages found.</td></tr>"
                      Else
                          lower = totalCount - maxItems + 1
                          If lower < 1 Then lower = 1
                          For i = totalCount To lower Step -1
                              Set msg = client.GetMessage(i)
                              Response.Write "<tr>"
                              Response.Write "<td class='mono'>" & H(i) & "</td>"
                              Response.Write "<td>" & H(TrimTo(msg.Subject, 160)) & "</td>"
                              Response.Write "<td>" & H(TrimTo(msg.From, 90)) & "</td>"
                              If ToInt(msg.AttachmentCount, 0) > 0 Then
                                  Response.Write "<td><span class='badge text-bg-info-subtle border text-info-emphasis'>" & H(msg.AttachmentCount) & "</span> " & H(TrimTo(msg.AttachmentNamesText, 120)) & "</td>"
                              Else
                                  Response.Write "<td class='text-muted'>-</td>"
                              End If
                              Response.Write "<td>" & H(TrimTo(msg.Date, 70)) & "</td>"
                              Response.Write "<td>"
                              Response.Write "<div class='d-flex gap-2'>"
                              Response.Write "<a class='btn btn-sm btn-outline-primary' href='default.asp?m=view&msg_id=" & i & "'>View</a>"
                              Response.Write "<form method='post' action='default.asp' class='m-0'>"
                              Response.Write "<input type='hidden' name='action' value='delete'>"
                              Response.Write "<input type='hidden' name='msg_id' value='" & H(i) & "'>"
                              Response.Write "<button class='btn btn-sm btn-outline-danger' type='submit' onclick='return confirm(&quot;Delete this message?&quot;)'>Delete</button>"
                              Response.Write "</form>"
                              Response.Write "</div>"
                              Response.Write "</td>"
                              Response.Write "</tr>"
                              shown = shown + 1
                          Next
                      End If
                  Else
                      Dim ids, ub
                      Set ids = client.Search("ALL")
                      ub = -1
                      ub = ids.UBound(1)
                      If Err.Number <> 0 Then
                          ub = -1
                          Err.Clear
                      End If

                      If ub < 0 Then
                          Response.Write "<tr><td colspan='6' class='text-muted'>No messages found.</td></tr>"
                      Else
                          For i = ub To 0 Step -1
                              seq = Trim("" & ids(i))
                              If seq <> "" Then
                                  Set msg = client.GetMessage(seq)
                                  Response.Write "<tr>"
                                  Response.Write "<td class='mono'>" & H(seq) & "</td>"
                                  Response.Write "<td>" & H(TrimTo(msg.Subject, 160)) & "</td>"
                                  Response.Write "<td>" & H(TrimTo(msg.From, 90)) & "</td>"
                                  If ToInt(msg.AttachmentCount, 0) > 0 Then
                                      Response.Write "<td><span class='badge text-bg-info-subtle border text-info-emphasis'>" & H(msg.AttachmentCount) & "</span> " & H(TrimTo(msg.AttachmentNamesText, 120)) & "</td>"
                                  Else
                                      Response.Write "<td class='text-muted'>-</td>"
                                  End If
                                  Response.Write "<td>" & H(TrimTo(msg.Date, 70)) & "</td>"
                                  Response.Write "<td>"
                                  Response.Write "<div class='d-flex gap-2'>"
                                  Response.Write "<a class='btn btn-sm btn-outline-primary' href='default.asp?m=view&msg_id=" & Server.URLEncode(seq) & "'>View</a>"
                                  Response.Write "<form method='post' action='default.asp' class='m-0'>"
                                  Response.Write "<input type='hidden' name='action' value='delete'>"
                                  Response.Write "<input type='hidden' name='msg_id' value='" & H(seq) & "'>"
                                  Response.Write "<button class='btn btn-sm btn-outline-danger' type='submit' onclick='return confirm(&quot;Delete this message?&quot;)'>Delete</button>"
                                  Response.Write "</form>"
                                  Response.Write "</div>"
                                  Response.Write "</td>"
                                  Response.Write "</tr>"
                                  shown = shown + 1
                                  If shown >= maxItems Then Exit For
                              End If
                          Next
                      End If
                  End If
              End If

              mailSvc.CloseClient client
              Set client = Nothing
              On Error GoTo 0
              %>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  <% End If %>
</main>

<script>
  const protoSel = document.getElementById('protoSel');
  const portInput = document.getElementById('portInput');
  if (protoSel && portInput) {
    protoSel.addEventListener('change', () => {
      const v = (protoSel.value || '').toLowerCase();
      if (!portInput.value || portInput.value === '993' || portInput.value === '995' || portInput.value === '143' || portInput.value === '110') {
        portInput.value = v === 'pop3' ? '995' : '993';
      }
    });
  }
</script>
</body>
</html>
