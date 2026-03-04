<!--#include file="../../includes/core.asp" -->
<%
Dim tid, uid, actionName, listId, statusFilter, sortBy
Set db = PortalOpen()
Call PortalInit(db)
Call PortalHydrateSession(db)
Call PortalRequireApp("todo")
Call PortalTouchUsage(db, "todo")

tid = PortalCurrentTenantId()
uid = PortalCurrentUserId()

If CLng(0 & PortalScalar(db, "SELECT COUNT(*) FROM todo_lists WHERE tenant_id=" & tid & " AND user_id=" & uid, 0)) = 0 Then
    Call PortalExec(db, "INSERT INTO todo_lists(tenant_id,user_id,name,is_shared) VALUES(" & tid & "," & uid & ",'My Tasks',0)")
End If

If UCase("" & Request.ServerVariables("REQUEST_METHOD")) = "POST" Then
    Call PortalRequirePostCsrf()
    actionName = LCase("" & Request.Form("action"))
    If actionName = "new_list" Then
        Call PortalExec(db, "INSERT INTO todo_lists(tenant_id,user_id,name,is_shared) VALUES(" & tid & "," & uid & "," & SqlQ(Trim("" & Request.Form("list_name"))) & ",0)")
        Call PortalSetFlash("List created.", "success")
    ElseIf actionName = "new_task" Then
        listId = SqlN(Request.Form("list_id"))
        If listId > 0 And Trim("" & Request.Form("title")) <> "" Then
            Dim _p
            _p = Trim("" & Request.Form("priority"))
            If _p <> "None" And _p <> "Low" And _p <> "Medium" And _p <> "High" Then _p = "None"
            Call PortalExec(db, "INSERT INTO todo_tasks(tenant_id,user_id,list_id,title,description,due_date,priority,status,position) VALUES(" & tid & "," & uid & "," & listId & "," & SqlQ(Left(Trim("" & Request.Form("title")), 180)) & "," & SqlQ(Left(Trim("" & Request.Form("description")), 4000)) & "," & SqlQ(Trim("" & Request.Form("due_date"))) & "," & SqlQ(_p) & ",'Open'," & CLng(0 & PortalScalar(db, "SELECT COALESCE(MAX(position),0)+1 FROM todo_tasks WHERE list_id=" & listId, 1)) & ")")
            Call PortalSetFlash("Task added.", "success")
        End If
    ElseIf actionName = "set_status" Then
        Dim _st
        _st = Trim("" & Request.Form("status"))
        If _st <> "Open" And _st <> "In Progress" And _st <> "Done" Then _st = "Open"
        Call PortalExec(db, "UPDATE todo_tasks SET status=" & SqlQ(_st) & ",updated_at=CURRENT_TIMESTAMP WHERE id=" & SqlN(Request.Form("task_id")) & " AND tenant_id=" & tid & " AND user_id=" & uid)
    ElseIf actionName = "delete" Then
        Call PortalExec(db, "DELETE FROM todo_tasks WHERE id=" & SqlN(Request.Form("task_id")) & " AND tenant_id=" & tid & " AND user_id=" & uid)
        Call PortalSetFlash("Task deleted.", "info")
    End If
End If

listId = SqlN(Request.QueryString("list_id"))
If listId <= 0 Then
    listId = CLng(0 & PortalScalar(db, "SELECT id FROM todo_lists WHERE tenant_id=" & tid & " AND user_id=" & uid & " ORDER BY id LIMIT 1", 0))
End If

statusFilter = Trim("" & Request.QueryString("status"))
sortBy = LCase(Trim("" & Request.QueryString("sort")))
If sortBy = "" Then sortBy = "due"

Set rsLists = db.Execute("SELECT id,name FROM todo_lists WHERE tenant_id=" & tid & " AND user_id=" & uid & " ORDER BY name")

taskSql = "SELECT id,title,description,due_date,priority,status,updated_at FROM todo_tasks WHERE tenant_id=" & tid & " AND user_id=" & uid & " AND list_id=" & listId
If statusFilter <> "" Then taskSql = taskSql & " AND status=" & SqlQ(statusFilter)
If sortBy = "priority" Then
    taskSql = taskSql & " ORDER BY CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 WHEN 'Low' THEN 3 ELSE 4 END, due_date"
Else
    taskSql = taskSql & " ORDER BY CASE WHEN due_date IS NULL OR due_date='' THEN 1 ELSE 0 END, due_date"
End If
Set rsTasks = db.Execute(taskSql)

pageTitle = "Todo List"
%>
<!--#include file="../../includes/layout_top.asp" -->

<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">Todo List</h1>
  <span class="metric-chip">Shortcut: press N in form field focus flow</span>
</div>

<div class="row g-3">
  <div class="col-lg-4">
    <div class="card p-3 mb-3">
      <h2 class="h6">Lists</h2>
      <div class="list-group mb-3">
        <% Do Until rsLists.EOF %>
          <a class="list-group-item list-group-item-action <% If CLng(0 & rsLists("id")) = listId Then Response.Write "active" End If %>" href="<%=H(PortalUrl("app/todo/index.asp"))%>?list_id=<%=CLng(0 & rsLists("id"))%>"><%=H(rsLists("name"))%></a>
          <% rsLists.MoveNext %>
        <% Loop %>
      </div>
      <form method="post" action="<%=H(PortalUrl("app/todo/index.asp"))%>">
        <%=PortalCsrfField()%>
        <input type="hidden" name="action" value="new_list">
        <div class="input-group">
          <input class="form-control" name="list_name" placeholder="New list name" required>
          <button class="btn btn-outline-primary" type="submit">Add</button>
        </div>
      </form>
    </div>

    <div class="card p-3">
      <h2 class="h6">Add task</h2>
      <form method="post" action="<%=H(PortalUrl("app/todo/index.asp"))%>?list_id=<%=listId%>">
        <%=PortalCsrfField()%>
        <input type="hidden" name="action" value="new_task">
        <input type="hidden" name="list_id" value="<%=listId%>">
        <div class="mb-2"><input id="taskTitle" class="form-control" name="title" placeholder="Task title" required></div>
        <div class="mb-2"><textarea class="form-control" name="description" rows="3" placeholder="Description"></textarea></div>
        <div class="row g-2">
          <div class="col-6"><input class="form-control" type="date" name="due_date"></div>
          <div class="col-6">
            <select class="form-select" name="priority">
              <option>None</option><option>Low</option><option selected>Medium</option><option>High</option>
            </select>
          </div>
        </div>
        <button class="btn btn-primary w-100 mt-3" type="submit">Create task</button>
      </form>
    </div>
  </div>

  <div class="col-lg-8">
    <div class="card p-3">
      <div class="d-flex justify-content-between align-items-center mb-2">
        <h2 class="h6 mb-0">Tasks</h2>
        <div class="d-flex gap-2">
          <a class="btn btn-sm btn-outline-secondary" href="<%=H(PortalUrl("app/todo/index.asp"))%>?list_id=<%=listId%>&sort=due">Sort by due date</a>
          <a class="btn btn-sm btn-outline-secondary" href="<%=H(PortalUrl("app/todo/index.asp"))%>?list_id=<%=listId%>&sort=priority">Sort by priority</a>
        </div>
      </div>
      <div class="table-responsive">
        <table class="table align-middle">
          <thead><tr><th>Task</th><th>Due</th><th>Priority</th><th>Status</th><th></th></tr></thead>
          <tbody>
          <% If rsTasks.EOF Then %>
            <tr><td colspan="5" class="text-muted">No tasks yet. Create your first task.</td></tr>
          <% End If %>
          <% Do Until rsTasks.EOF %>
            <tr>
              <td>
                <div class="fw-semibold"><%=H(rsTasks("title"))%></div>
                <% If Trim("" & rsTasks("description")) <> "" Then %><div class="small text-muted"><%=H(rsTasks("description"))%></div><% End If %>
              </td>
              <td><%=H(rsTasks("due_date"))%></td>
              <td><span class="badge text-bg-light"><%=H(rsTasks("priority"))%></span></td>
              <td>
                <form method="post" action="<%=H(PortalUrl("app/todo/index.asp"))%>?list_id=<%=listId%>" class="d-flex gap-2">
                  <%=PortalCsrfField()%>
                  <input type="hidden" name="action" value="set_status">
                  <input type="hidden" name="task_id" value="<%=CLng(0 & rsTasks("id"))%>">
                  <select class="form-select form-select-sm" name="status" onchange="this.form.submit()">
                    <option <% If "" & rsTasks("status") = "Open" Then Response.Write "selected" End If %>>Open</option>
                    <option <% If "" & rsTasks("status") = "In Progress" Then Response.Write "selected" End If %>>In Progress</option>
                    <option <% If "" & rsTasks("status") = "Done" Then Response.Write "selected" End If %>>Done</option>
                  </select>
                </form>
              </td>
              <td>
                <form method="post" action="<%=H(PortalUrl("app/todo/index.asp"))%>?list_id=<%=listId%>">
                  <%=PortalCsrfField()%>
                  <input type="hidden" name="action" value="delete">
                  <input type="hidden" name="task_id" value="<%=CLng(0 & rsTasks("id"))%>">
                  <button class="btn btn-sm btn-outline-danger" type="submit">Delete</button>
                </form>
              </td>
            </tr>
            <% rsTasks.MoveNext %>
          <% Loop %>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>

<script>
document.addEventListener('keydown', function(e){
  if ((e.key === 'n' || e.key === 'N') && !e.ctrlKey && !e.metaKey) {
    var t = document.getElementById('taskTitle');
    if (t) { t.focus(); e.preventDefault(); }
  }
});
</script>

<%
rsLists.Close
Set rsLists = Nothing
rsTasks.Close
Set rsTasks = Nothing
%>
<!--#include file="../../includes/layout_bottom.asp" -->
<%
db.Close
Set db = Nothing
%>
