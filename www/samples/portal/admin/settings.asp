<!--#include file="../includes/core.asp" -->
<%
Dim tid, orgName, primaryColor, actionName, noticeMsg, noticeDays
Set db = PortalOpen()
Call PortalInit(db)
Call PortalHydrateSession(db)
Call PortalRequireTenantAdmin()

tid = PortalCurrentTenantId()

If UCase("" & Request.ServerVariables("REQUEST_METHOD")) = "POST" Then
    Call PortalRequirePostCsrf()
    actionName = LCase(Trim("" & Request.Form("action")))
    If actionName = "save_org" Then
        orgName = Trim("" & Request.Form("org_name"))
        primaryColor = Trim("" & Request.Form("primary_color"))
        If orgName <> "" Then
            orgName = PortalCleanName(orgName, "Workspace")
            If primaryColor = "" Then primaryColor = "#2f6fed"
            If Not PortalValidColorHex(primaryColor) Then primaryColor = "#2f6fed"
            Call PortalExec(db, "UPDATE tenants SET name=" & SqlQ(orgName) & ", primary_color=" & SqlQ(primaryColor) & " WHERE id=" & tid)
            Call PortalLoadUserSession(db, PortalCurrentUserId())
            Call PortalSetFlash("Organization settings saved.", "success")
            Response.Redirect PortalUrl("admin/settings.asp")
            Response.End
        End If
    ElseIf actionName = "save_notice" Then
        noticeMsg = Left(Trim("" & Request.Form("notice_message")), 500)
        noticeDays = SqlN(Request.Form("notice_days"))
        If noticeDays <= 0 Then noticeDays = 3
        If noticeDays > 30 Then noticeDays = 30
        If noticeMsg <> "" Then
            Call PortalExec(db, "INSERT INTO tenant_notices(tenant_id,message,active_from,active_until,created_by) VALUES(" & tid & "," & SqlQ(noticeMsg) & ",CURRENT_TIMESTAMP,datetime('now','+" & noticeDays & " day')," & PortalCurrentUserId() & ")")
            Call PortalSetFlash("Notice published to daily briefings.", "success")
            Response.Redirect PortalUrl("admin/settings.asp")
            Response.End
        End If
    ElseIf actionName = "clear_notice" Then
        Call PortalExec(db, "UPDATE tenant_notices SET active_until=datetime('now','-1 minute') WHERE id=" & SqlN(Request.Form("notice_id")) & " AND tenant_id=" & tid)
        Call PortalSetFlash("Notice archived.", "info")
        Response.Redirect PortalUrl("admin/settings.asp")
        Response.End
    End If
End If

Set rsOrg = db.Execute("SELECT name,primary_color,tenant_type FROM tenants WHERE id=" & tid & " LIMIT 1")
Set rsNotice = db.Execute("SELECT id,message,active_until,created_at FROM tenant_notices WHERE tenant_id=" & tid & " AND (active_until IS NULL OR active_until='' OR datetime(active_until) >= datetime('now')) ORDER BY created_at DESC LIMIT 3")
pageTitle = "Admin · Organization"
%>
<!--#include file="../includes/layout_top.asp" -->

<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">Organization settings</h1>
  <div class="btn-group">
    <a class="btn btn-outline-secondary btn-sm" href="<%=H(PortalUrl("admin/users.asp"))%>">Users</a>
    <a class="btn btn-outline-secondary btn-sm" href="<%=H(PortalUrl("admin/apps.asp"))%>">App Access</a>
  </div>
</div>

<div class="card p-4">
  <form method="post" action="<%=H(PortalUrl("admin/settings.asp"))%>">
    <%=PortalCsrfField()%>
    <input type="hidden" name="action" value="save_org">
    <div class="row g-3">
      <div class="col-md-8">
        <label class="form-label">Organization name</label>
        <input class="form-control" type="text" name="org_name" value="<%=H(rsOrg("name"))%>" required>
      </div>
      <div class="col-md-4">
        <label class="form-label">Primary color</label>
        <input class="form-control form-control-color" type="color" name="primary_color" value="<%=H(rsOrg("primary_color"))%>">
      </div>
      <div class="col-12">
        <div class="small text-muted">Tenant type: <%=H(rsOrg("tenant_type"))%></div>
      </div>
    </div>
    <button class="btn btn-primary mt-4" type="submit">Save settings</button>
  </form>
</div>

<div class="card p-4 mt-3">
  <h2 class="h6">Daily briefing notice</h2>
  <p class="small text-muted">Publish a company-wide note that appears in each user’s Today Briefing.</p>
  <form method="post" action="<%=H(PortalUrl("admin/settings.asp"))%>">
    <%=PortalCsrfField()%>
    <input type="hidden" name="action" value="save_notice">
    <div class="mb-2"><textarea class="form-control" name="notice_message" rows="3" placeholder="Short announcement for all users" required></textarea></div>
    <div class="row g-2 align-items-end">
      <div class="col-md-3">
        <label class="form-label">Visible days</label>
        <input class="form-control" type="number" min="1" max="30" name="notice_days" value="3">
      </div>
      <div class="col-md-3">
        <button class="btn btn-primary" type="submit">Publish notice</button>
      </div>
    </div>
  </form>

  <div class="mt-3">
    <% If rsNotice.EOF Then %>
      <div class="small text-muted">No active notices.</div>
    <% End If %>
    <% Do Until rsNotice.EOF %>
      <div class="border rounded p-2 mb-2 d-flex justify-content-between align-items-start">
        <div class="small"><%=H(rsNotice("message"))%><div class="text-muted">until <%=H(rsNotice("active_until"))%></div></div>
        <form method="post" action="<%=H(PortalUrl("admin/settings.asp"))%>">
          <%=PortalCsrfField()%>
          <input type="hidden" name="action" value="clear_notice">
          <input type="hidden" name="notice_id" value="<%=CLng(0 & rsNotice("id"))%>">
          <button class="btn btn-sm btn-outline-danger" type="submit">Archive</button>
        </form>
      </div>
      <% rsNotice.MoveNext %>
    <% Loop %>
  </div>
</div>

<%
rsOrg.Close
Set rsOrg = Nothing
rsNotice.Close
Set rsNotice = Nothing
%>
<!--#include file="../includes/layout_bottom.asp" -->
<%
db.Close
Set db = Nothing
%>
