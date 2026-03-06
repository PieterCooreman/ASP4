<!--#include file="../../includes/core.asp" -->
<%
Dim tid, uid, actionName, winDate, q
Set db = PortalOpen()
Call PortalInit(db)
Call PortalHydrateSession(db)
Call PortalRequireApp("wins")
Call PortalTouchUsage(db, "wins")

tid = PortalCurrentTenantId()
uid = PortalCurrentUserId()

If UCase("" & Request.ServerVariables("REQUEST_METHOD")) = "POST" Then
    Call PortalRequirePostCsrf()
    actionName = LCase(Trim("" & Request.Form("action")))
    If actionName = "new" Then
        winDate = Trim("" & Request.Form("win_date"))
        If winDate = "" Then winDate = "" & PortalScalar(db, "SELECT date('now')", "")
        Call PortalExec(db, "INSERT OR IGNORE INTO wins_journal(tenant_id,user_id,win_date,title,details) VALUES(" & tid & "," & uid & "," & SqlQ(winDate) & "," & SqlQ(Left(Trim("" & Request.Form("title")),180)) & "," & SqlQ(Left(Trim("" & Request.Form("details")),2000)) & ")")
        Call PortalSetFlash("Win captured.", "success")
        Response.Redirect PortalUrl("app/wins/index.asp")
        Response.End
    ElseIf actionName = "delete" Then
        Call PortalExec(db, "DELETE FROM wins_journal WHERE id=" & SqlN(Request.Form("win_id")) & " AND tenant_id=" & tid & " AND user_id=" & uid)
        Call PortalSetFlash("Win removed.", "info")
        Response.Redirect PortalUrl("app/wins/index.asp")
        Response.End
    End If
End If

q = Trim("" & Request.QueryString("q"))
sql = "SELECT id,win_date,title,details FROM wins_journal WHERE tenant_id=" & tid & " AND user_id=" & uid
If q <> "" Then sql = sql & " AND (title LIKE " & SqlQ("%" & q & "%") & " OR details LIKE " & SqlQ("%" & q & "%") & ")"
sql = sql & " ORDER BY win_date DESC, created_at DESC LIMIT 120"
Set rsWins = db.Execute(sql)

weekCount = CLng(0 & PortalScalar(db, "SELECT COUNT(*) FROM wins_journal WHERE tenant_id=" & tid & " AND user_id=" & uid & " AND win_date >= date('now','-6 day')", 0))
pageTitle = "Wins Journal"
%>
<!--#include file="../../includes/layout_top.asp" -->

<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">Wins Journal</h1>
  <form method="get" action="<%=H(PortalUrl("app/wins/index.asp"))%>" class="d-flex"><input class="form-control form-control-sm" name="q" value="<%=H(q)%>" placeholder="Search wins"></form>
</div>

<div class="card p-3 mb-3 border-0" style="background:linear-gradient(135deg,#f8fff0,#ffffff);">
  <div class="d-flex justify-content-between align-items-center">
    <div>
      <strong>This week:</strong> <%=weekCount%> win(s)
      <div class="small text-muted">Small wins count. Capture one every day for momentum.</div>
    </div>
  </div>
</div>

<div class="row g-3">
  <div class="col-lg-4">
    <div class="card p-3">
      <h2 class="h6">Capture today’s win</h2>
      <form method="post" action="<%=H(PortalUrl("app/wins/index.asp"))%>">
        <%=PortalCsrfField()%>
        <input type="hidden" name="action" value="new">
        <div class="mb-2"><input class="form-control" type="date" name="win_date" value="<%=H(PortalScalar(db,"SELECT date('now')",""))%>"></div>
        <div class="mb-2"><input class="form-control" name="title" placeholder="What went well?" required></div>
        <div class="mb-2"><textarea class="form-control" rows="4" name="details" placeholder="Optional context"></textarea></div>
        <button class="btn btn-primary w-100" type="submit">Save win</button>
      </form>
    </div>
  </div>

  <div class="col-lg-8">
    <div class="card p-3">
      <h2 class="h6 mb-3">Recent wins</h2>
      <% If rsWins.EOF Then %><p class="text-muted mb-0">No wins logged yet.</p><% End If %>
      <% Do Until rsWins.EOF %>
      <div class="border rounded p-3 mb-3">
        <div class="d-flex justify-content-between align-items-start">
          <div>
            <div class="small text-muted"><%=H(rsWins("win_date"))%></div>
            <h3 class="h6 mb-1"><%=H(rsWins("title"))%></h3>
            <% If Trim("" & rsWins("details")) <> "" Then %><div class="small"><%=H(rsWins("details"))%></div><% End If %>
          </div>
          <form method="post" action="<%=H(PortalUrl("app/wins/index.asp"))%>">
            <%=PortalCsrfField()%>
            <input type="hidden" name="action" value="delete"><input type="hidden" name="win_id" value="<%=CLng(0 & rsWins("id"))%>">
            <button class="btn btn-sm btn-outline-danger" type="submit">Delete</button>
          </form>
        </div>
      </div>
      <% rsWins.MoveNext : Loop %>
    </div>
  </div>
</div>

<%
rsWins.Close : Set rsWins = Nothing
%>
<!--#include file="../../includes/layout_bottom.asp" -->
<% db.Close : Set db = Nothing %>
