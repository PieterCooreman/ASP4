<!--#include file="../../includes/core.asp" -->
<%
Dim tid, uid, actionName, todayStr
Set db = PortalOpen()
Call PortalInit(db)
Call PortalHydrateSession(db)
Call PortalRequireApp("habits")
Call PortalTouchUsage(db, "habits")

tid = PortalCurrentTenantId()
uid = PortalCurrentUserId()
todayStr = "" & PortalScalar(db, "SELECT date('now')", "")

If UCase("" & Request.ServerVariables("REQUEST_METHOD")) = "POST" Then
    Call PortalRequirePostCsrf()
    actionName = LCase("" & Request.Form("action"))
    If actionName = "new" Then
        Call PortalExec(db, "INSERT INTO habits_habits(tenant_id,user_id,title,cadence,goal_per_period) VALUES(" & tid & "," & uid & "," & SqlQ(Left(Trim("" & Request.Form("title")),180)) & "," & SqlQ(Trim("" & Request.Form("cadence"))) & "," & SqlN(Request.Form("goal")) & ")")
    ElseIf actionName = "log_today" Then
        Dim hid
        hid = SqlN(Request.Form("habit_id"))
        Call PortalExec(db, "INSERT OR IGNORE INTO habits_logs(habit_id,user_id,log_date,value) VALUES(" & hid & "," & uid & "," & SqlQ(todayStr) & ",1)")
        Call PortalSetFlash("Progress logged for today.", "success")
    ElseIf actionName = "delete" Then
        Dim hid2
        hid2 = SqlN(Request.Form("habit_id"))
        Call PortalExec(db, "DELETE FROM habits_logs WHERE habit_id=" & hid2 & " AND user_id=" & uid)
        Call PortalExec(db, "DELETE FROM habits_habits WHERE id=" & hid2 & " AND tenant_id=" & tid & " AND user_id=" & uid)
    End If
End If

Set rsHabits = db.Execute("SELECT h.id,h.title,h.cadence,h.goal_per_period, (SELECT COUNT(*) FROM habits_logs l WHERE l.habit_id=h.id AND l.user_id=" & uid & " AND l.log_date >= date('now','-6 day')) AS done_week, (SELECT COUNT(*) FROM habits_logs l WHERE l.habit_id=h.id AND l.user_id=" & uid & " AND l.log_date=" & SqlQ(todayStr) & ") AS done_today FROM habits_habits h WHERE h.tenant_id=" & tid & " AND h.user_id=" & uid & " ORDER BY h.created_at DESC")
pageTitle = "Habits"
%>
<!--#include file="../../includes/layout_top.asp" -->

<div class="d-flex justify-content-between align-items-center mb-3"><h1 class="h4 mb-0">Habit Tracker</h1></div>
<div class="row g-3">
  <div class="col-lg-4">
    <div class="card p-3">
      <h2 class="h6">New habit</h2>
      <form method="post" action="<%=H(PortalUrl("app/habits/index.asp"))%>">
        <%=PortalCsrfField()%>
        <input type="hidden" name="action" value="new">
        <div class="mb-2"><input class="form-control" name="title" placeholder="Habit title" required></div>
        <div class="row g-2">
          <div class="col-6">
            <select class="form-select" name="cadence"><option value="daily">Daily</option><option value="weekly">Weekly</option></select>
          </div>
          <div class="col-6"><input class="form-control" type="number" min="1" max="50" name="goal" value="1"></div>
        </div>
        <button class="btn btn-primary w-100 mt-3" type="submit">Add habit</button>
      </form>
    </div>
  </div>
  <div class="col-lg-8">
    <div class="card p-3">
      <h2 class="h6 mb-3">Your habits</h2>
      <% If rsHabits.EOF Then %><p class="text-muted mb-0">No habits yet.</p><% End If %>
      <% Do Until rsHabits.EOF %>
        <div class="border rounded p-3 mb-3 d-flex justify-content-between align-items-center">
          <div>
            <div class="fw-semibold"><%=H(rsHabits("title"))%></div>
            <div class="small text-muted"><%=H(rsHabits("cadence"))%> · Goal: <%=CLng(0 & rsHabits("goal_per_period"))%> · Last 7 days: <%=CLng(0 & rsHabits("done_week"))%></div>
          </div>
          <div class="d-flex gap-2">
            <form method="post" action="<%=H(PortalUrl("app/habits/index.asp"))%>" class="d-inline">
              <%=PortalCsrfField()%>
              <input type="hidden" name="action" value="log_today"><input type="hidden" name="habit_id" value="<%=CLng(0 & rsHabits("id"))%>">
              <button class="btn btn-sm <% If CLng(0 & rsHabits("done_today")) > 0 Then Response.Write "btn-success" Else Response.Write "btn-outline-success" End If %>" type="submit"><% If CLng(0 & rsHabits("done_today")) > 0 Then Response.Write "Done today" Else Response.Write "Log today" End If %></button>
            </form>
            <form method="post" action="<%=H(PortalUrl("app/habits/index.asp"))%>" class="d-inline">
              <%=PortalCsrfField()%>
              <input type="hidden" name="action" value="delete"><input type="hidden" name="habit_id" value="<%=CLng(0 & rsHabits("id"))%>">
              <button class="btn btn-sm btn-outline-danger" type="submit">Delete</button>
            </form>
          </div>
        </div>
        <% rsHabits.MoveNext %>
      <% Loop %>
    </div>
  </div>
</div>

<%
rsHabits.Close : Set rsHabits = Nothing
%>
<!--#include file="../../includes/layout_bottom.asp" -->
<% db.Close : Set db = Nothing %>
