<!--#include file="includes/core.asp" -->
<%
Dim appsRs, appId, overdueCount, ideaCount, winsWeekCount, badgeText, uid, tid
Set db = PortalOpen()
Call PortalInit(db)
Call PortalHydrateSession(db)
Call PortalRequireLogin()

uid = PortalCurrentUserId()
tid = PortalCurrentTenantId()

overdueCount = CLng(0 & PortalScalar(db, "SELECT COUNT(*) FROM todo_tasks WHERE tenant_id=" & tid & " AND user_id=" & uid & " AND status <> 'Done' AND due_date IS NOT NULL AND due_date <> '' AND due_date < date('now')", 0))
ideaCount = CLng(0 & PortalScalar(db, "SELECT COUNT(*) FROM ideas WHERE tenant_id=" & tid & " AND user_id=" & uid & " AND status IN ('Raw','Developing')", 0))
winsWeekCount = CLng(0 & PortalScalar(db, "SELECT COUNT(*) FROM wins_journal WHERE tenant_id=" & tid & " AND user_id=" & uid & " AND win_date >= date('now','-6 day')", 0))

Set appsRs = db.Execute("SELECT a.app_id,a.label,a.description,a.icon,a.route,COALESCE(u.last_used_at,'1970-01-01') AS last_used_at FROM app_catalog a JOIN tenant_apps ta ON ta.app_id=a.app_id AND ta.tenant_id=" & tid & " AND ta.enabled=1 LEFT JOIN user_apps ua ON ua.app_id=a.app_id AND ua.user_id=" & uid & " LEFT JOIN user_app_usage u ON u.app_id=a.app_id AND u.user_id=" & uid & " WHERE a.is_enabled=1 AND COALESCE(ua.enabled,1)=1 ORDER BY u.last_used_at DESC,a.sort_order,a.app_id")

pageTitle = "Dashboard"
%>
<!--#include file="includes/layout_top.asp" -->

<div class="d-flex justify-content-between align-items-center mb-3">
  <div>
    <h1 class="h3 mb-1">Welcome, <%=H(Session("portal_user_name"))%></h1>
    <p class="text-muted mb-0">Your available apps in <strong><%=H(Session("portal_tenant_name"))%></strong>.</p>
  </div>
</div>

<div class="row g-3">
  <% Do Until appsRs.EOF %>
    <% appId = LCase("" & appsRs("app_id")) : badgeText = "" %>
    <% If appId = "briefing" Then badgeText = "start here" %>
    <% If appId = "todo" And overdueCount > 0 Then badgeText = overdueCount & " overdue" %>
    <% If appId = "brainstorm" And ideaCount > 0 Then badgeText = ideaCount & " active ideas" %>
    <% If appId = "wins" And winsWeekCount > 0 Then badgeText = winsWeekCount & " this week" %>
    <div class="col-12 col-md-6 col-xl-4">
      <a class="text-decoration-none" href="<%=H(PortalUrl("" & appsRs("route")))%>">
        <div class="card app-card h-100 p-3">
          <div class="d-flex justify-content-between align-items-start">
            <div>
              <div class="text-muted small"><i class="bi <%=H(appsRs("icon"))%> me-1"></i><%=H(appId)%></div>
              <h2 class="h5 mt-1 mb-2 text-dark"><%=H(appsRs("label"))%></h2>
            </div>
            <% If badgeText <> "" Then %><span class="metric-chip"><%=H(badgeText)%></span><% End If %>
          </div>
          <p class="text-muted mb-0"><%=H(appsRs("description"))%></p>
        </div>
      </a>
    </div>
    <% appsRs.MoveNext %>
  <% Loop %>
</div>

<%
appsRs.Close
Set appsRs = Nothing
%>

<!--#include file="includes/layout_bottom.asp" -->
<%
db.Close
Set db = Nothing
%>
