<!--#include file="includes/core.asp" -->
<%
Dim token, errMsg, inviteRs, email, roleName, tenantId, nameVal, pass1, pass2, uid
Set db = PortalOpen()
Call PortalInit(db)
Call PortalHydrateSession(db)

token = Trim("" & Request.QueryString("token"))
errMsg = ""

If token = "" Then
    errMsg = "Invalid invite link."
Else
    Set inviteRs = db.Execute("SELECT i.tenant_id,i.email,i.role,i.accepted_at,i.expires_at,t.name AS tenant_name FROM invitations i JOIN tenants t ON t.id=i.tenant_id WHERE i.token=" & SqlQ(token) & " AND i.expires_at > datetime('now') LIMIT 1")
    If inviteRs.EOF Then
        If CLng(0 & PortalScalar(db, "SELECT COUNT(*) FROM invitations WHERE token=" & SqlQ(token), 0)) > 0 Then
            errMsg = "Invitation expired."
        Else
            errMsg = "Invitation not found."
        End If
    ElseIf "" & inviteRs("accepted_at") <> "" Then
        errMsg = "This invitation is already used."
    End If
End If

If errMsg = "" And UCase("" & Request.ServerVariables("REQUEST_METHOD")) = "POST" Then
    Call PortalRequirePostCsrf()
    nameVal = Trim("" & Request.Form("name"))
    pass1 = "" & Request.Form("password")
    pass2 = "" & Request.Form("password2")

    email = LCase("" & inviteRs("email"))
    roleName = LCase("" & inviteRs("role"))
    tenantId = CLng(0 & inviteRs("tenant_id"))
    If nameVal = "" Then nameVal = Split(email, "@")(0)

    If Not PortalIsStrongPassword(pass1) Then
        errMsg = "Password must be 10+ chars and include upper, lower, and number."
    ElseIf pass1 <> pass2 Then
        errMsg = "Passwords do not match."
    Else
        uid = CLng(0 & PortalScalar(db, "SELECT id FROM users WHERE tenant_id=" & tenantId & " AND lower(email)=" & SqlQ(email) & " LIMIT 1", 0))
        If uid <= 0 Then
            Call PortalExec(db, "INSERT INTO users(tenant_id,name,email,password_hash,role,status,timezone) VALUES(" & tenantId & "," & SqlQ(nameVal) & "," & SqlQ(email) & "," & SqlQ(ASP4.Crypto.Hash(pass1,10)) & "," & SqlQ(roleName) & ",'active','UTC')")
            uid = CLng(0 & PortalScalar(db, "SELECT id FROM users ORDER BY id DESC LIMIT 1", 0))
            Call PortalExec(db, "INSERT OR IGNORE INTO user_apps(user_id,app_id,enabled) SELECT " & uid & ",app_id,1 FROM app_catalog WHERE is_enabled=1")
        Else
            Call PortalExec(db, "UPDATE users SET name=" & SqlQ(nameVal) & ",password_hash=" & SqlQ(ASP4.Crypto.Hash(pass1,10)) & ",status='active',role=" & SqlQ(roleName) & " WHERE id=" & uid)
        End If

        Call PortalExec(db, "UPDATE invitations SET accepted_at=CURRENT_TIMESTAMP WHERE token=" & SqlQ(token) & " AND accepted_at IS NULL AND expires_at > datetime('now')")
        Call PortalLoadUserSession(db, uid)
        Call PortalSetFlash("Welcome to your organization workspace.", "success")
        Response.Redirect PortalHomeUrl()
        Response.End
    End If
End If

pageTitle = "Accept invite"
%>
<!--#include file="includes/layout_top.asp" -->

<div class="row justify-content-center">
  <div class="col-md-8 col-lg-6">
    <div class="card p-4">
      <h1 class="h4 mb-3">Accept invitation</h1>
      <% If errMsg <> "" Then %>
        <div class="alert alert-danger"><%=H(errMsg)%></div>
      <% Else %>
        <p class="text-muted">You are joining <strong><%=H(inviteRs("tenant_name"))%></strong> as <strong><%=H(inviteRs("role"))%></strong>.</p>
        <form method="post" action="<%=H(PortalUrl("invite.asp"))%>?token=<%=H(token)%>">
          <%=PortalCsrfField()%>
          <div class="mb-3">
            <label class="form-label">Display name</label>
            <input class="form-control" type="text" name="name" required>
            <div class="invalid-feedback">Please enter your display name.</div>
          </div>
          <div class="mb-3">
            <label class="form-label">Password</label>
            <input id="invitePassword" class="form-control" type="password" name="password" data-rule="password-strong" required>
            <div class="form-text">10+ chars, uppercase, lowercase, number.</div>
            <div class="invalid-feedback">Password does not meet policy.</div>
          </div>
          <div class="mb-3">
            <label class="form-label">Confirm password</label>
            <input class="form-control" type="password" name="password2" data-match="invitePassword" required>
            <div class="invalid-feedback">Passwords must match.</div>
          </div>
          <button class="btn btn-primary" type="submit">Activate account</button>
        </form>
      <% End If %>
    </div>
  </div>
</div>

<!--#include file="includes/layout_bottom.asp" -->
<%
If errMsg = "" Then
    inviteRs.Close
    Set inviteRs = Nothing
End If
db.Close
Set db = Nothing
%>
