<!--#include file="../includes/core.asp" -->
<%
Dim tid, actionName, targetUser, appId, enabledVal, tenantType
Set db = PortalOpen()
Call PortalInit(db)
Call PortalHydrateSession(db)
Call PortalRequireTenantAdmin()

tid = PortalCurrentTenantId()
tenantType = LCase("" & Session("portal_tenant_type"))

If UCase("" & Request.ServerVariables("REQUEST_METHOD")) = "POST" Then
    Call PortalRequirePostCsrf()
    actionName = LCase("" & Request.Form("action"))
    If actionName = "toggle" Then
        targetUser = SqlN(Request.Form("user_id"))
        appId = LCase(Trim("" & Request.Form("app_id")))
        enabledVal = SqlN(Request.Form("enabled"))
        If targetUser > 0 And CLng(0 & PortalScalar(db, "SELECT COUNT(*) FROM app_catalog WHERE app_id=" & SqlQ(appId) & " AND is_enabled=1", 0)) > 0 Then
            Call PortalExec(db, "INSERT OR IGNORE INTO user_apps(user_id,app_id,enabled) VALUES(" & targetUser & "," & SqlQ(appId) & "," & enabledVal & ")")
            Call PortalExec(db, "UPDATE user_apps SET enabled=" & enabledVal & " WHERE user_id=" & targetUser & " AND app_id=" & SqlQ(appId))
            Call PortalSetFlash("Permissions updated.", "success")
        End If
    End If
End If

Set rsMatrix = db.Execute("SELECT u.id,u.name,u.email FROM users u WHERE u.tenant_id=" & tid & " ORDER BY u.name")
pageTitle = "Admin · App Access"
%>
<!--#include file="../includes/layout_top.asp" -->

<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">App access management</h1>
  <div class="btn-group">
    <a class="btn btn-outline-secondary btn-sm" href="<%=H(PortalUrl("admin/users.asp"))%>">Users</a>
    <a class="btn btn-outline-secondary btn-sm" href="<%=H(PortalUrl("admin/settings.asp"))%>">Organization</a>
  </div>
</div>

<div class="card p-3">
  <div class="table-responsive">
    <table class="table align-middle">
      <thead><tr><th>User</th><th>App switches</th></tr></thead>
      <tbody>
      <% Do Until rsMatrix.EOF %>
        <% Set rsApps = db.Execute("SELECT a.app_id,a.label,COALESCE(ua.enabled,1) AS enabled FROM app_catalog a JOIN tenant_apps ta ON ta.app_id=a.app_id AND ta.tenant_id=" & tid & " AND ta.enabled=1 LEFT JOIN user_apps ua ON ua.user_id=" & CLng(0 & rsMatrix("id")) & " AND ua.app_id=a.app_id WHERE a.is_enabled=1 AND (a.tenant_scope='all' OR (a.tenant_scope='personal' AND " & SqlQ(tenantType) & "='individual')) ORDER BY a.sort_order,a.app_id") %>
        <tr>
          <td>
            <div class="fw-semibold"><%=H(rsMatrix("name"))%></div>
            <div class="small text-muted"><%=H(rsMatrix("email"))%></div>
          </td>
          <td class="d-flex flex-wrap gap-2">
            <% Do Until rsApps.EOF %>
              <form method="post" action="<%=H(PortalUrl("admin/apps.asp"))%>" class="d-inline">
                <%=PortalCsrfField()%>
                <input type="hidden" name="action" value="toggle">
                <input type="hidden" name="user_id" value="<%=CLng(0 & rsMatrix("id"))%>">
                <input type="hidden" name="app_id" value="<%=H(rsApps("app_id"))%>">
                <input type="hidden" name="enabled" value="<% If CLng(0 & rsApps("enabled")) = 1 Then Response.Write "0" Else Response.Write "1" End If %>">
                <button class="btn btn-sm <% If CLng(0 & rsApps("enabled")) = 1 Then Response.Write "btn-success" Else Response.Write "btn-outline-secondary" End If %>" type="submit"><%=H(rsApps("label"))%></button>
              </form>
              <% rsApps.MoveNext %>
            <% Loop %>
          </td>
        </tr>
        <% rsApps.Close : Set rsApps = Nothing %>
        <% rsMatrix.MoveNext %>
      <% Loop %>
      </tbody>
    </table>
  </div>
</div>

<%
rsMatrix.Close
Set rsMatrix = Nothing
%>
<!--#include file="../includes/layout_bottom.asp" -->
<%
db.Close
Set db = Nothing
%>
