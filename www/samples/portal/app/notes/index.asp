<!--#include file="../../includes/core.asp" -->
<%
Dim tid, uid, actionName, parentId
Set db = PortalOpen()
Call PortalInit(db)
Call PortalHydrateSession(db)
Call PortalRequireApp("notes")
Call PortalTouchUsage(db, "notes")

tid = PortalCurrentTenantId()
uid = PortalCurrentUserId()

If UCase("" & Request.ServerVariables("REQUEST_METHOD")) = "POST" Then
    Call PortalRequirePostCsrf()
    actionName = LCase("" & Request.Form("action"))
    If actionName = "new" Then
        Dim parentSql
        parentId = SqlN(Request.Form("parent_id"))
        If parentId > 0 Then
            parentSql = CStr(parentId)
        Else
            parentSql = "NULL"
        End If
        Call PortalExec(db, "INSERT INTO notes_pages(tenant_id,user_id,parent_id,title,body,is_shared) VALUES(" & tid & "," & uid & "," & parentSql & "," & SqlQ(Left(Trim("" & Request.Form("title")),180)) & "," & SqlQ(Left(Trim("" & Request.Form("body")),12000)) & ",0)")
        Call PortalSetFlash("Note saved.", "success")
    ElseIf actionName = "delete" Then
        Call PortalExec(db, "DELETE FROM notes_pages WHERE id=" & SqlN(Request.Form("note_id")) & " AND tenant_id=" & tid & " AND user_id=" & uid)
        Call PortalSetFlash("Note deleted.", "info")
    End If
End If

Set rsNotes = db.Execute("SELECT id,parent_id,title,substr(body,1,220) AS preview,updated_at FROM notes_pages WHERE tenant_id=" & tid & " AND user_id=" & uid & " ORDER BY updated_at DESC")
Set rsParents = db.Execute("SELECT id,title FROM notes_pages WHERE tenant_id=" & tid & " AND user_id=" & uid & " ORDER BY title")
pageTitle = "Notes"
%>
<!--#include file="../../includes/layout_top.asp" -->

<div class="d-flex justify-content-between align-items-center mb-3"><h1 class="h4 mb-0">Notes / Knowledge Base</h1></div>
<div class="row g-3">
  <div class="col-lg-4">
    <div class="card p-3">
      <h2 class="h6">New note</h2>
      <form method="post" action="<%=H(PortalUrl("app/notes/index.asp"))%>">
        <%=PortalCsrfField()%>
        <input type="hidden" name="action" value="new">
        <div class="mb-2"><input class="form-control" name="title" placeholder="Title" required></div>
        <div class="mb-2">
          <select class="form-select" name="parent_id">
            <option value="0">Top-level page</option>
            <% Do Until rsParents.EOF %>
              <option value="<%=CLng(0 & rsParents("id"))%>"><%=H(rsParents("title"))%></option>
              <% rsParents.MoveNext %>
            <% Loop %>
          </select>
        </div>
        <div class="mb-2"><textarea class="form-control" name="body" rows="7" placeholder="Structured note content"></textarea></div>
        <button class="btn btn-primary w-100" type="submit">Save note</button>
      </form>
    </div>
  </div>
  <div class="col-lg-8">
    <div class="card p-3">
      <h2 class="h6 mb-3">Pages</h2>
      <% If rsNotes.EOF Then %><p class="text-muted mb-0">No notes yet. Capture your first permanent note.</p><% End If %>
      <% Do Until rsNotes.EOF %>
        <div class="border rounded p-3 mb-3">
          <div class="d-flex justify-content-between">
            <div>
              <h3 class="h6 mb-1"><%=H(rsNotes("title"))%></h3>
              <div class="small text-muted"><% If CLng(0 & rsNotes("parent_id")) > 0 Then %>Subpage · <% End If %>Updated <%=H(rsNotes("updated_at"))%></div>
            </div>
            <form method="post" action="<%=H(PortalUrl("app/notes/index.asp"))%>">
              <%=PortalCsrfField()%>
              <input type="hidden" name="action" value="delete"><input type="hidden" name="note_id" value="<%=CLng(0 & rsNotes("id"))%>">
              <button class="btn btn-sm btn-outline-danger" type="submit">Delete</button>
            </form>
          </div>
          <% If Trim("" & rsNotes("preview")) <> "" Then %><div class="mt-2"><%=H(rsNotes("preview"))%></div><% End If %>
        </div>
        <% rsNotes.MoveNext %>
      <% Loop %>
    </div>
  </div>
</div>

<%
rsParents.Close : Set rsParents = Nothing
rsNotes.Close : Set rsNotes = Nothing
%>
<!--#include file="../../includes/layout_bottom.asp" -->
<% db.Close : Set db = Nothing %>
