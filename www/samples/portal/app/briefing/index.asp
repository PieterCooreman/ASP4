<!--#include file="../../includes/core.asp" -->
<%
Dim tid, uid, dueTodayCount, overdueCount, highPriorityCount, followUpCount, revisitCount
Dim priorityMsg, urgency, followUpDays, actionName, snoozeDays
Dim calendarFrom, calendarTo

Set db = PortalOpen()
Call PortalInit(db)
Call PortalHydrateSession(db)
Call PortalRequireApp("briefing")
Call PortalTouchUsage(db, "briefing")

tid = PortalCurrentTenantId()
uid = PortalCurrentUserId()

followUpDays = CLng(0 & Session("portal_follow_up_days"))
If followUpDays <> 14 And followUpDays <> 21 And followUpDays <> 30 Then followUpDays = 21

If UCase("" & Request.ServerVariables("REQUEST_METHOD")) = "POST" Then
    Call PortalRequirePostCsrf()
    actionName = LCase(Trim("" & Request.Form("action")))

    If actionName = "set_followup_days" Then
        followUpDays = SqlN(Request.Form("follow_up_days"))
        If followUpDays <> 14 And followUpDays <> 21 And followUpDays <> 30 Then followUpDays = 21
        Call PortalExec(db, "UPDATE users SET follow_up_days=" & followUpDays & " WHERE id=" & uid)
        Session("portal_follow_up_days") = followUpDays
        Call PortalSetFlash("Follow-up window updated.", "success")
        Response.Redirect PortalUrl("app/briefing/index.asp")
        Response.End

    ElseIf actionName = "snooze" Then
        snoozeDays = SqlN(Request.Form("days"))
        If snoozeDays <= 0 Then snoozeDays = 1
        If snoozeDays > 30 Then snoozeDays = 30
        Call PortalExec(db, "INSERT OR IGNORE INTO briefing_snooze(user_id,item_type,item_id,snooze_until) VALUES(" & uid & "," & SqlQ(Trim("" & Request.Form("item_type"))) & "," & SqlN(Request.Form("item_id")) & ",date('now','+" & snoozeDays & " day'))")
        Call PortalExec(db, "UPDATE briefing_snooze SET snooze_until=date('now','+" & snoozeDays & " day') WHERE user_id=" & uid & " AND item_type=" & SqlQ(Trim("" & Request.Form("item_type"))) & " AND item_id=" & SqlN(Request.Form("item_id")))
        Call PortalSetFlash("Item snoozed for " & snoozeDays & " day(s).", "info")
        Response.Redirect PortalUrl("app/briefing/index.asp")
        Response.End

    ElseIf actionName = "set_focus" Then
        Dim fTaskId, fTitle
        fTaskId = SqlN(Request.Form("task_id"))
        fTitle = Left(Trim("" & Request.Form("title")), 180)
        If fTaskId > 0 And fTitle <> "" Then
            Call PortalExec(db, "INSERT OR IGNORE INTO briefing_focus(user_id,focus_date,task_id,title_snapshot) VALUES(" & uid & ",date('now')," & fTaskId & "," & SqlQ(fTitle) & ")")
            Call PortalExec(db, "UPDATE briefing_focus SET task_id=" & fTaskId & ", title_snapshot=" & SqlQ(fTitle) & " WHERE user_id=" & uid & " AND focus_date=date('now')")
            Call PortalSetFlash("First focus block set.", "success")
        End If
        Response.Redirect PortalUrl("app/briefing/index.asp")
        Response.End

    ElseIf actionName = "unsnooze" Then
        Call PortalExec(db, "DELETE FROM briefing_snooze WHERE user_id=" & uid & " AND item_type=" & SqlQ(Trim("" & Request.Form("item_type"))) & " AND item_id=" & SqlN(Request.Form("item_id")))
        Call PortalSetFlash("Snooze removed.", "success")
        Response.Redirect PortalUrl("app/briefing/index.asp")
        Response.End
    End If
End If

dueTodayCount = CLng(0 & PortalScalar(db, "SELECT COUNT(*) FROM todo_tasks t LEFT JOIN briefing_snooze s ON s.user_id=" & uid & " AND s.item_type='todo_due' AND s.item_id=t.id AND date(s.snooze_until) >= date('now') WHERE t.tenant_id=" & tid & " AND t.user_id=" & uid & " AND t.status <> 'Done' AND t.due_date = date('now') AND s.id IS NULL", 0))
overdueCount = CLng(0 & PortalScalar(db, "SELECT COUNT(*) FROM todo_tasks t LEFT JOIN briefing_snooze s ON s.user_id=" & uid & " AND s.item_type='todo_overdue' AND s.item_id=t.id AND date(s.snooze_until) >= date('now') WHERE t.tenant_id=" & tid & " AND t.user_id=" & uid & " AND t.status <> 'Done' AND t.due_date <> '' AND t.due_date < date('now') AND s.id IS NULL", 0))
highPriorityCount = CLng(0 & PortalScalar(db, "SELECT COUNT(*) FROM todo_tasks WHERE tenant_id=" & tid & " AND user_id=" & uid & " AND status <> 'Done' AND priority='High'", 0))
revisitCount = CLng(0 & PortalScalar(db, "SELECT COUNT(*) FROM ideas i LEFT JOIN briefing_snooze s ON s.user_id=" & uid & " AND s.item_type='idea_revisit' AND s.item_id=i.id AND date(s.snooze_until) >= date('now') WHERE i.tenant_id=" & tid & " AND i.user_id=" & uid & " AND i.revisit_on IS NOT NULL AND i.revisit_on <> '' AND i.revisit_on <= date('now') AND i.status <> 'Archived' AND s.id IS NULL", 0))
followUpCount = CLng(0 & PortalScalar(db, "SELECT COUNT(*) FROM contacts_people c LEFT JOIN briefing_snooze s ON s.user_id=" & uid & " AND s.item_type='contact_followup' AND s.item_id=c.id AND date(s.snooze_until) >= date('now') WHERE c.tenant_id=" & tid & " AND c.user_id=" & uid & " AND (c.last_interaction IS NULL OR c.last_interaction='' OR c.last_interaction <= date('now','-" & followUpDays & " day')) AND s.id IS NULL", 0))

urgency = overdueCount * 3 + highPriorityCount * 2 + dueTodayCount
If urgency >= 12 Then
    priorityMsg = "High-focus day: clear overdue tasks first, then high-priority items."
ElseIf urgency >= 6 Then
    priorityMsg = "Balanced day: start with top 1-2 high-priority tasks, then complete due-today items."
Else
    priorityMsg = "Steady day: use this time for proactive work and idea follow-through."
End If

Set rsFocus = db.Execute("SELECT task_id,title_snapshot FROM briefing_focus WHERE user_id=" & uid & " AND focus_date=date('now') LIMIT 1")
Set rsCarry = db.Execute("SELECT t.id,t.title,t.due_date,t.priority FROM todo_tasks t WHERE t.tenant_id=" & tid & " AND t.user_id=" & uid & " AND t.status <> 'Done' AND t.priority='High' AND t.due_date <> '' AND t.due_date < date('now') ORDER BY t.due_date, t.updated_at LIMIT 1")
Set rsDue = db.Execute("SELECT t.id,t.title,t.due_date,t.priority,t.status FROM todo_tasks t LEFT JOIN briefing_snooze s ON s.user_id=" & uid & " AND s.item_type='todo_due' AND s.item_id=t.id AND date(s.snooze_until) >= date('now') WHERE t.tenant_id=" & tid & " AND t.user_id=" & uid & " AND t.status <> 'Done' AND t.due_date = date('now') AND s.id IS NULL ORDER BY CASE t.priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 WHEN 'Low' THEN 3 ELSE 4 END, t.title LIMIT 8")
Set rsOver = db.Execute("SELECT t.id,t.title,t.due_date,t.priority FROM todo_tasks t LEFT JOIN briefing_snooze s ON s.user_id=" & uid & " AND s.item_type='todo_overdue' AND s.item_id=t.id AND date(s.snooze_until) >= date('now') WHERE t.tenant_id=" & tid & " AND t.user_id=" & uid & " AND t.status <> 'Done' AND t.due_date <> '' AND t.due_date < date('now') AND s.id IS NULL ORDER BY t.due_date, t.title LIMIT 8")
Set rsIdeas = db.Execute("SELECT i.id,i.title,i.revisit_on,i.status FROM ideas i LEFT JOIN briefing_snooze s ON s.user_id=" & uid & " AND s.item_type='idea_revisit' AND s.item_id=i.id AND date(s.snooze_until) >= date('now') WHERE i.tenant_id=" & tid & " AND i.user_id=" & uid & " AND i.revisit_on IS NOT NULL AND i.revisit_on <> '' AND i.revisit_on <= date('now') AND i.status <> 'Archived' AND s.id IS NULL ORDER BY i.revisit_on, i.created_at DESC LIMIT 6")
Set rsContacts = db.Execute("SELECT c.id,c.full_name,c.company,c.last_interaction FROM contacts_people c LEFT JOIN briefing_snooze s ON s.user_id=" & uid & " AND s.item_type='contact_followup' AND s.item_id=c.id AND date(s.snooze_until) >= date('now') WHERE c.tenant_id=" & tid & " AND c.user_id=" & uid & " AND (c.last_interaction IS NULL OR c.last_interaction='' OR c.last_interaction <= date('now','-" & followUpDays & " day')) AND s.id IS NULL ORDER BY COALESCE(c.last_interaction,'1900-01-01') LIMIT 6")
Set rsNotices = db.Execute("SELECT message,active_until,created_at FROM tenant_notices WHERE tenant_id=" & tid & " AND datetime('now') >= datetime(active_from) AND (active_until IS NULL OR active_until='' OR datetime('now') <= datetime(active_until)) ORDER BY created_at DESC LIMIT 2")
Set rsWinsWeek = db.Execute("SELECT win_date,title FROM wins_journal WHERE tenant_id=" & tid & " AND user_id=" & uid & " AND win_date >= date('now','-6 day') ORDER BY win_date DESC, created_at DESC LIMIT 3")
winsWeekCount = CLng(0 & PortalScalar(db, "SELECT COUNT(*) FROM wins_journal WHERE tenant_id=" & tid & " AND user_id=" & uid & " AND win_date >= date('now','-6 day')", 0))
Set rsSnoozed = db.Execute("SELECT s.item_type,s.item_id,s.snooze_until, " & _
    "CASE " & _
    "WHEN s.item_type IN ('todo_due','todo_overdue') THEN COALESCE((SELECT t.title FROM todo_tasks t WHERE t.id=s.item_id AND t.user_id=" & uid & "), '(task removed)') " & _
    "WHEN s.item_type='idea_revisit' THEN COALESCE((SELECT i.title FROM ideas i WHERE i.id=s.item_id AND i.user_id=" & uid & "), '(idea removed)') " & _
    "WHEN s.item_type='contact_followup' THEN COALESCE((SELECT c.full_name FROM contacts_people c WHERE c.id=s.item_id AND c.user_id=" & uid & "), '(contact removed)') " & _
    "ELSE '(item)' END AS title " & _
    "FROM briefing_snooze s WHERE s.user_id=" & uid & " AND date(s.snooze_until) >= date('now') ORDER BY s.snooze_until, s.item_type LIMIT 20")

calendarFrom = "date('now','-3 day')"
calendarTo = "date('now','+21 day')"
Set rsCal = db.Execute("SELECT * FROM (" & _
    "SELECT t.due_date AS event_date,'Task' AS kind,t.title AS title,'Todo' AS source FROM todo_tasks t WHERE t.tenant_id=" & tid & " AND t.user_id=" & uid & " AND t.status <> 'Done' AND t.due_date <> '' " & _
    "UNION ALL " & _
    "SELECT i.revisit_on AS event_date,'Idea revisit' AS kind,i.title AS title,'Ideas' AS source FROM ideas i WHERE i.tenant_id=" & tid & " AND i.user_id=" & uid & " AND i.status <> 'Archived' AND i.revisit_on IS NOT NULL AND i.revisit_on <> '' " & _
    "UNION ALL " & _
    "SELECT date(c.last_interaction,'+" & followUpDays & " day') AS event_date,'Contact follow-up' AS kind,c.full_name AS title,'Contacts' AS source FROM contacts_people c WHERE c.tenant_id=" & tid & " AND c.user_id=" & uid & " AND c.last_interaction IS NOT NULL AND c.last_interaction <> '' " & _
    "UNION ALL " & _
    "SELECT w.win_date AS event_date,'Win logged' AS kind,w.title AS title,'Wins' AS source FROM wins_journal w WHERE w.tenant_id=" & tid & " AND w.user_id=" & uid & " AND w.win_date IS NOT NULL AND w.win_date <> ''" & _
    ") x WHERE event_date IS NOT NULL AND event_date <> '' AND event_date BETWEEN " & calendarFrom & " AND " & calendarTo & " ORDER BY event_date, kind, title LIMIT 60")

pageTitle = "Today Briefing"
%>
<!--#include file="../../includes/layout_top.asp" -->

<div class="d-flex justify-content-between align-items-center mb-3">
  <div>
    <h1 class="h3 mb-1">Today Briefing</h1>
    <p class="text-muted mb-0">A single daily view across tasks, ideas, follow-ups, and scheduled dates.</p>
  </div>
  <a class="btn btn-outline-secondary btn-sm" href="<%=H(PortalUrl("dashboard.asp"))%>">Open app grid</a>
</div>

<div class="card p-3 mb-3 border-0" style="background:linear-gradient(135deg,#edf3ff,#ffffff);">
  <div class="d-flex flex-wrap gap-2 mb-2">
    <span class="metric-chip">Due today: <strong><%=dueTodayCount%></strong></span>
    <span class="metric-chip">Overdue: <strong><%=overdueCount%></strong></span>
    <span class="metric-chip">High priority: <strong><%=highPriorityCount%></strong></span>
    <span class="metric-chip">Ideas to revisit: <strong><%=revisitCount%></strong></span>
    <span class="metric-chip">Contact follow-ups: <strong><%=followUpCount%></strong></span>
  </div>
  <div><strong>Suggested focus:</strong> <%=H(priorityMsg)%></div>
  <form method="post" action="<%=H(PortalUrl("app/briefing/index.asp"))%>" class="row g-2 align-items-end mt-2">
    <%=PortalCsrfField()%>
    <input type="hidden" name="action" value="set_followup_days">
    <div class="col-auto">
      <label class="form-label small">Contact follow-up window</label>
      <select class="form-select form-select-sm" name="follow_up_days">
        <option value="14" <% If followUpDays=14 Then Response.Write "selected" End If %>>14 days</option>
        <option value="21" <% If followUpDays=21 Then Response.Write "selected" End If %>>21 days</option>
        <option value="30" <% If followUpDays=30 Then Response.Write "selected" End If %>>30 days</option>
      </select>
    </div>
    <div class="col-auto"><button class="btn btn-sm btn-outline-primary" type="submit">Apply</button></div>
  </form>
</div>

<% If Not rsFocus.EOF Then %>
<div class="card p-3 mb-3 border-success-subtle">
  <h2 class="h6 mb-1"><i class="bi bi-bullseye me-1"></i>First focus block</h2>
  <div class="small"><strong><%=H(rsFocus("title_snapshot"))%></strong></div>
</div>
<% End If %>

<div class="card p-3 mb-3 border-success-subtle">
  <h2 class="h6 mb-2"><i class="bi bi-trophy me-1"></i>Weekly momentum</h2>
  <div class="small mb-2">You captured <strong><%=winsWeekCount%></strong> win(s) in the last 7 days.</div>
  <% If rsWinsWeek.EOF Then %>
    <div class="small text-muted mb-2">No wins logged this week yet — capture one small win today.</div>
  <% Else %>
    <ul class="small mb-2">
      <% Do Until rsWinsWeek.EOF %>
        <li><%=H(rsWinsWeek("win_date"))%> — <%=H(rsWinsWeek("title"))%></li>
        <% rsWinsWeek.MoveNext %>
      <% Loop %>
    </ul>
  <% End If %>
  <a class="small" href="<%=H(PortalUrl("app/wins/index.asp"))%>">Open Wins Journal</a>
</div>

<% If Not rsSnoozed.EOF Then %>
<div class="card p-3 mb-3">
  <h2 class="h6 mb-2"><i class="bi bi-clock-history me-1"></i>Snoozed items</h2>
  <% Do Until rsSnoozed.EOF %>
    <div class="border rounded p-2 mb-2 small d-flex justify-content-between align-items-center">
      <span><strong><%=H(rsSnoozed("title"))%></strong> · <%=H(rsSnoozed("item_type"))%> · until <%=H(rsSnoozed("snooze_until"))%></span>
      <form method="post" action="<%=H(PortalUrl("app/briefing/index.asp"))%>" class="m-0">
        <%=PortalCsrfField()%>
        <input type="hidden" name="action" value="unsnooze">
        <input type="hidden" name="item_type" value="<%=H(rsSnoozed("item_type"))%>">
        <input type="hidden" name="item_id" value="<%=CLng(0 & rsSnoozed("item_id"))%>">
        <button class="btn btn-sm btn-outline-primary" type="submit">Unsnooze</button>
      </form>
    </div>
    <% rsSnoozed.MoveNext %>
  <% Loop %>
</div>
<% End If %>

<% If Not rsCarry.EOF Then %>
<div class="card p-3 mb-3 border-danger-subtle">
  <h2 class="h6 mb-2"><i class="bi bi-arrow-repeat me-1"></i>Carry-over suggestion</h2>
  <div class="small mb-2">Convert this overdue high-priority task into today’s first focus block: <strong><%=H(rsCarry("title"))%></strong></div>
  <form method="post" action="<%=H(PortalUrl("app/briefing/index.asp"))%>">
    <%=PortalCsrfField()%>
    <input type="hidden" name="action" value="set_focus">
    <input type="hidden" name="task_id" value="<%=CLng(0 & rsCarry("id"))%>">
    <input type="hidden" name="title" value="<%=H(rsCarry("title"))%>">
    <button class="btn btn-sm btn-danger" type="submit">Set as first focus block</button>
  </form>
</div>
<% End If %>

<% If Not rsNotices.EOF Then %>
<div class="card p-3 mb-3 border-warning-subtle">
  <h2 class="h6 mb-2"><i class="bi bi-megaphone me-1"></i>Organization notices</h2>
  <% Do Until rsNotices.EOF %>
    <div class="small mb-2"><%=H(rsNotices("message"))%> <span class="text-muted">(posted <%=H(rsNotices("created_at"))%>)</span></div>
    <% rsNotices.MoveNext %>
  <% Loop %>
</div>
<% End If %>

<div class="row g-3">
  <div class="col-lg-6">
    <div class="card p-3 h-100">
      <h2 class="h6">Tasks due today</h2>
      <% If rsDue.EOF Then %><p class="text-muted mb-0">No tasks due today.</p><% End If %>
      <% Do Until rsDue.EOF %>
        <div class="border rounded p-2 mb-2 small d-flex justify-content-between align-items-center">
          <span><strong><%=H(rsDue("title"))%></strong> · <%=H(rsDue("priority"))%></span>
          <form method="post" action="<%=H(PortalUrl("app/briefing/index.asp"))%>" class="m-0">
            <%=PortalCsrfField()%>
            <input type="hidden" name="action" value="snooze"><input type="hidden" name="item_type" value="todo_due"><input type="hidden" name="item_id" value="<%=CLng(0 & rsDue("id"))%>"><input type="hidden" name="days" value="1">
            <button class="btn btn-sm btn-outline-secondary" type="submit">Snooze 1d</button>
          </form>
        </div>
        <% rsDue.MoveNext %>
      <% Loop %>
      <a class="small" href="<%=H(PortalUrl("app/todo/index.asp"))%>">Open Todo</a>
    </div>
  </div>

  <div class="col-lg-6">
    <div class="card p-3 h-100">
      <h2 class="h6">Overdue tasks</h2>
      <% If rsOver.EOF Then %><p class="text-muted mb-0">No overdue tasks. Nice work.</p><% End If %>
      <% Do Until rsOver.EOF %>
        <div class="border rounded p-2 mb-2 small d-flex justify-content-between align-items-center">
          <span><strong><%=H(rsOver("title"))%></strong> · due <%=H(rsOver("due_date"))%></span>
          <form method="post" action="<%=H(PortalUrl("app/briefing/index.asp"))%>" class="m-0">
            <%=PortalCsrfField()%>
            <input type="hidden" name="action" value="snooze"><input type="hidden" name="item_type" value="todo_overdue"><input type="hidden" name="item_id" value="<%=CLng(0 & rsOver("id"))%>"><input type="hidden" name="days" value="2">
            <button class="btn btn-sm btn-outline-secondary" type="submit">Snooze 2d</button>
          </form>
        </div>
        <% rsOver.MoveNext %>
      <% Loop %>
      <a class="small" href="<%=H(PortalUrl("app/todo/index.asp?sort=priority"))%>">Prioritize in Todo</a>
    </div>
  </div>

  <div class="col-lg-6">
    <div class="card p-3 h-100">
      <h2 class="h6">Ideas flagged to revisit</h2>
      <% If rsIdeas.EOF Then %><p class="text-muted mb-0">No idea revisit items for today.</p><% End If %>
      <% Do Until rsIdeas.EOF %>
        <div class="border rounded p-2 mb-2 small d-flex justify-content-between align-items-center">
          <span><strong><%=H(rsIdeas("title"))%></strong> · revisit <%=H(rsIdeas("revisit_on"))%></span>
          <form method="post" action="<%=H(PortalUrl("app/briefing/index.asp"))%>" class="m-0">
            <%=PortalCsrfField()%>
            <input type="hidden" name="action" value="snooze"><input type="hidden" name="item_type" value="idea_revisit"><input type="hidden" name="item_id" value="<%=CLng(0 & rsIdeas("id"))%>"><input type="hidden" name="days" value="3">
            <button class="btn btn-sm btn-outline-secondary" type="submit">Snooze 3d</button>
          </form>
        </div>
        <% rsIdeas.MoveNext %>
      <% Loop %>
      <a class="small" href="<%=H(PortalUrl("app/brainstorm/index.asp"))%>">Open Ideas</a>
    </div>
  </div>

  <div class="col-lg-6">
    <div class="card p-3 h-100">
      <h2 class="h6">People to follow up</h2>
      <% If rsContacts.EOF Then %><p class="text-muted mb-0">No stale follow-ups right now.</p><% End If %>
      <% Do Until rsContacts.EOF %>
        <div class="border rounded p-2 mb-2 small d-flex justify-content-between align-items-center">
          <span><strong><%=H(rsContacts("full_name"))%></strong> <% If Trim("" & rsContacts("company")) <> "" Then %>· <%=H(rsContacts("company"))%><% End If %></span>
          <form method="post" action="<%=H(PortalUrl("app/briefing/index.asp"))%>" class="m-0">
            <%=PortalCsrfField()%>
            <input type="hidden" name="action" value="snooze"><input type="hidden" name="item_type" value="contact_followup"><input type="hidden" name="item_id" value="<%=CLng(0 & rsContacts("id"))%>"><input type="hidden" name="days" value="7">
            <button class="btn btn-sm btn-outline-secondary" type="submit">Snooze 7d</button>
          </form>
        </div>
        <% rsContacts.MoveNext %>
      <% Loop %>
      <a class="small" href="<%=H(PortalUrl("app/contacts/index.asp"))%>">Open Contacts</a>
    </div>
  </div>
</div>

<div class="card p-3 mt-3">
  <h2 class="h6 mb-2"><i class="bi bi-calendar3 me-1"></i>Calendar timeline (next 3 weeks)</h2>
  <div class="table-responsive">
    <table class="table table-sm align-middle mb-0">
      <thead><tr><th style="width:130px">Date</th><th style="width:140px">Type</th><th>Item</th><th style="width:120px">Source</th></tr></thead>
      <tbody>
      <% If rsCal.EOF Then %>
        <tr><td colspan="4" class="text-muted">No dated items in this window.</td></tr>
      <% End If %>
      <% Do Until rsCal.EOF %>
        <tr>
          <td><%=H(rsCal("event_date"))%></td>
          <td><%=H(rsCal("kind"))%></td>
          <td><%=H(rsCal("title"))%></td>
          <td><%=H(rsCal("source"))%></td>
        </tr>
        <% rsCal.MoveNext %>
      <% Loop %>
      </tbody>
    </table>
  </div>
</div>

<%
rsFocus.Close: Set rsFocus = Nothing
rsCarry.Close: Set rsCarry = Nothing
rsDue.Close: Set rsDue = Nothing
rsOver.Close: Set rsOver = Nothing
rsIdeas.Close: Set rsIdeas = Nothing
rsContacts.Close: Set rsContacts = Nothing
rsNotices.Close: Set rsNotices = Nothing
rsWinsWeek.Close: Set rsWinsWeek = Nothing
rsSnoozed.Close: Set rsSnoozed = Nothing
rsCal.Close: Set rsCal = Nothing
%>
<!--#include file="../../includes/layout_bottom.asp" -->
<% db.Close: Set db = Nothing %>
