<!--#include file="../includes/core.asp" -->
<%
Dim tid, uid, actionName, email, roleName, inviteToken, inviteUrl, errMsg
Set db = PortalOpen()
Call PortalInit(db)
Call PortalHydrateSession(db)
Call PortalRequireTenantAdmin()

tid = PortalCurrentTenantId()
uid = PortalCurrentUserId()
errMsg = ""
inviteUrl = ""

If UCase("" & Request.ServerVariables("REQUEST_METHOD")) = "POST" Then
    Call PortalRequirePostCsrf()
    actionName = LCase(Trim("" & Request.Form("action")))

    If actionName = "invite" Then
        email = LCase(Trim("" & Request.Form("email")))
        roleName = LCase(Trim("" & Request.Form("role")))
        If roleName = "" Then roleName = "end_user"
        If Not PortalValidRole(roleName) Then roleName = "end_user"

        If Not PortalLooksLikeEmail(email) Then
            errMsg = "Enter a valid email."
        Else
            inviteToken = PortalNewToken(db)
            Call PortalExec(db, "INSERT INTO invitations(tenant_id,email,role,token,expires_at,created_by) VALUES(" & tid & "," & SqlQ(email) & "," & SqlQ(roleName) & "," & SqlQ(inviteToken) & ",datetime('now','+7 day')," & uid & ")")
            inviteUrl = PortalUrl("invite.asp") & "?token=" & inviteToken
            Call PortalSetFlash("Invitation created. Share the link with the user.", "success")
        End If
    ElseIf actionName = "status" Then
        Dim targetId, nextStatus
        targetId = SqlN(Request.Form("user_id"))
        nextStatus = LCase("" & Request.Form("status"))
        If Not PortalValidStatus(nextStatus) Then nextStatus = "active"
        If targetId > 0 And targetId <> uid Then
            Call PortalExec(db, "UPDATE users SET status=" & SqlQ(nextStatus) & " WHERE id=" & targetId & " AND tenant_id=" & tid)
            Call PortalSetFlash("User status updated.", "info")
        End If
    End If
End If

Set rsUsers = db.Execute("SELECT id,name,email,role,status,COALESCE(last_login_at,'-') AS last_login_at FROM users WHERE tenant_id=" & tid & " ORDER BY created_at DESC")
pageTitle = "Admin · Users"
%>
<!--#include file="../includes/layout_top.asp" -->

<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">User management</h1>
  <div class="btn-group">
    <a class="btn btn-outline-secondary btn-sm" href="<%=H(PortalUrl("admin/apps.asp"))%>">App Access</a>
    <a class="btn btn-outline-secondary btn-sm" href="<%=H(PortalUrl("admin/settings.asp"))%>">Organization</a>
  </div>
</div>

<div class="row g-3">
  <div class="col-lg-4">
    <div class="card p-3">
      <h2 class="h6 mb-3">Invite user</h2>
      <% If errMsg <> "" Then %><div class="alert alert-danger"><%=H(errMsg)%></div><% End If %>
      <form method="post" action="<%=H(PortalUrl("admin/users.asp"))%>">
        <%=PortalCsrfField()%>
        <input type="hidden" name="action" value="invite">
        <div class="mb-2">
          <label class="form-label">Email</label>
          <input class="form-control" type="email" name="email" required>
          <div class="invalid-feedback">Please provide a valid email.</div>
        </div>
        <div class="mb-3">
          <label class="form-label">Role</label>
          <select class="form-select" name="role">
            <option value="end_user">End User</option>
            <option value="tenant_admin">Tenant Admin</option>
          </select>
        </div>
        <button class="btn btn-primary w-100" type="submit">Create invite</button>
      </form>
      <% If inviteUrl <> "" Then %>
        <div class="mt-3 small">
          <div class="text-muted">Invitation link</div>
          <a href="<%=H(inviteUrl)%>"><%=H(inviteUrl)%></a>
        </div>
      <% End If %>
    </div>
  </div>

  <div class="col-lg-8">
    <div class="card p-3">
      <h2 class="h6 mb-3">Team members</h2>
      <div class="table-responsive">
        <table class="table table-sm align-middle">
          <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Last login</th><th></th></tr></thead>
          <tbody>
          <% Do Until rsUsers.EOF %>
            <tr>
              <td><%=H(rsUsers("name"))%></td>
              <td><%=H(rsUsers("email"))%></td>
              <td><%=H(rsUsers("role"))%></td>
              <td><span class="badge text-bg-light"><%=H(rsUsers("status"))%></span></td>
              <td class="small text-muted"><%=H(rsUsers("last_login_at"))%></td>
              <td>
                <% If CLng(0 & rsUsers("id")) <> uid Then %>
                  <form method="post" action="<%=H(PortalUrl("admin/users.asp"))%>" class="d-inline">
                    <%=PortalCsrfField()%>
                    <input type="hidden" name="action" value="status">
                    <input type="hidden" name="user_id" value="<%=CLng(0 & rsUsers("id"))%>">
                    <% If LCase("" & rsUsers("status")) = "active" Then %>
                      <input type="hidden" name="status" value="suspended">
                      <button class="btn btn-sm btn-outline-warning" type="submit">Suspend</button>
                    <% Else %>
                      <input type="hidden" name="status" value="active">
                      <button class="btn btn-sm btn-outline-success" type="submit">Activate</button>
                    <% End If %>
                  </form>
                <% End If %>
              </td>
            </tr>
            <% rsUsers.MoveNext %>
          <% Loop %>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>

<%
rsUsers.Close
Set rsUsers = Nothing
%>
<!--#include file="../includes/layout_bottom.asp" -->
<%
db.Close
Set db = Nothing
%>
