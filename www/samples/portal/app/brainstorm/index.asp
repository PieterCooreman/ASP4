<!--#include file="../../includes/core.asp" -->
<%
Dim tid, uid, actionName, collectionId, searchQ, similarSql, similarRs, justTitle
Set db = PortalOpen()
Call PortalInit(db)
Call PortalHydrateSession(db)
Call PortalRequireApp("brainstorm")
Call PortalTouchUsage(db, "brainstorm")

tid = PortalCurrentTenantId()
uid = PortalCurrentUserId()

If CLng(0 & PortalScalar(db, "SELECT COUNT(*) FROM idea_collections WHERE tenant_id=" & tid & " AND user_id=" & uid, 0)) = 0 Then
    Call PortalExec(db, "INSERT INTO idea_collections(tenant_id,user_id,name) VALUES(" & tid & "," & uid & ",'Inbox')")
End If

justTitle = ""
If UCase("" & Request.ServerVariables("REQUEST_METHOD")) = "POST" Then
    Call PortalRequirePostCsrf()
    actionName = LCase("" & Request.Form("action"))
    If actionName = "new_collection" Then
        Call PortalExec(db, "INSERT INTO idea_collections(tenant_id,user_id,name) VALUES(" & tid & "," & uid & "," & SqlQ(Trim("" & Request.Form("name"))) & ")")
    ElseIf actionName = "new_idea" Then
        collectionId = SqlN(Request.Form("collection_id"))
        justTitle = Trim("" & Request.Form("title"))
        If collectionId > 0 And justTitle <> "" Then
            Dim _ideaStatus
            _ideaStatus = Trim("" & Request.Form("status"))
            If _ideaStatus <> "Raw" And _ideaStatus <> "Developing" And _ideaStatus <> "Validated" And _ideaStatus <> "Archived" Then _ideaStatus = "Raw"
            Dim _revisit
            _revisit = Trim("" & Request.Form("revisit_on"))
            Call PortalExec(db, "INSERT INTO ideas(tenant_id,user_id,collection_id,title,body,tags,status,is_pinned,revisit_on) VALUES(" & tid & "," & uid & "," & collectionId & "," & SqlQ(Left(justTitle, 180)) & "," & SqlQ(Left(Trim("" & Request.Form("body")), 8000)) & "," & SqlQ(Left(Trim("" & Request.Form("tags")), 500)) & "," & SqlQ(_ideaStatus) & "," & SqlN(Request.Form("is_pinned")) & "," & SqlQ(_revisit) & ")")
            Call PortalSetFlash("Idea saved.", "success")
        End If
    ElseIf actionName = "revisit_tomorrow" Then
        Call PortalExec(db, "UPDATE ideas SET revisit_on=date('now','+1 day'),updated_at=CURRENT_TIMESTAMP WHERE id=" & SqlN(Request.Form("idea_id")) & " AND tenant_id=" & tid & " AND user_id=" & uid)
    ElseIf actionName = "archive" Then
        Call PortalExec(db, "UPDATE ideas SET status='Archived',updated_at=CURRENT_TIMESTAMP WHERE id=" & SqlN(Request.Form("idea_id")) & " AND tenant_id=" & tid & " AND user_id=" & uid)
    ElseIf actionName = "promote" Then
        Dim promoteId, pRs, pTitle, pBody
        promoteId = SqlN(Request.Form("idea_id"))
        Set pRs = db.Execute("SELECT title,body FROM ideas WHERE id=" & promoteId & " AND tenant_id=" & tid & " AND user_id=" & uid & " LIMIT 1")
        If Not pRs.EOF Then
            pTitle = "" & pRs("title")
            pBody = "" & pRs("body")
            Call PortalExec(db, "INSERT INTO notes_pages(tenant_id,user_id,parent_id,title,body,is_shared) VALUES(" & tid & "," & uid & ",NULL," & SqlQ(Left(pTitle,180)) & "," & SqlQ(Left(pBody,12000)) & ",0)")
            Call PortalExec(db, "UPDATE ideas SET status='Validated',updated_at=CURRENT_TIMESTAMP WHERE id=" & promoteId)
            Call PortalSetFlash("Idea promoted to Notes.", "success")
        End If
        pRs.Close
        Set pRs = Nothing
    ElseIf actionName = "delete" Then
        Call PortalExec(db, "DELETE FROM ideas WHERE id=" & SqlN(Request.Form("idea_id")) & " AND tenant_id=" & tid & " AND user_id=" & uid)
    End If
End If

collectionId = SqlN(Request.QueryString("collection_id"))
If collectionId <= 0 Then collectionId = CLng(0 & PortalScalar(db, "SELECT id FROM idea_collections WHERE tenant_id=" & tid & " AND user_id=" & uid & " ORDER BY id LIMIT 1", 0))
searchQ = Trim("" & Request.QueryString("q"))

Set rsCollections = db.Execute("SELECT id,name FROM idea_collections WHERE tenant_id=" & tid & " AND user_id=" & uid & " ORDER BY name")

ideaSql = "SELECT id,title,body,tags,status,is_pinned,revisit_on,created_at FROM ideas WHERE tenant_id=" & tid & " AND user_id=" & uid & " AND collection_id=" & collectionId
If searchQ <> "" Then
    ideaSql = ideaSql & " AND (title LIKE " & SqlQ("%" & searchQ & "%") & " OR body LIKE " & SqlQ("%" & searchQ & "%") & " OR tags LIKE " & SqlQ("%" & searchQ & "%") & ")"
End If
ideaSql = ideaSql & " ORDER BY is_pinned DESC, created_at DESC"
Set rsIdeas = db.Execute(ideaSql)

Set similarRs = Nothing
If justTitle <> "" Then
    similarSql = "SELECT id,title,created_at FROM ideas WHERE tenant_id=" & tid & " AND user_id=" & uid & " AND title LIKE " & SqlQ("%" & justTitle & "%") & " ORDER BY created_at DESC LIMIT 3"
    Set similarRs = db.Execute(similarSql)
End If

pageTitle = "Ideas"
%>
<!--#include file="../../includes/layout_top.asp" -->

<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">Brainstorm / Ideas</h1>
  <form class="d-flex" method="get" action="<%=H(PortalUrl("app/brainstorm/index.asp"))%>">
    <input type="hidden" name="collection_id" value="<%=collectionId%>">
    <input class="form-control form-control-sm" type="search" name="q" value="<%=H(searchQ)%>" placeholder="Search ideas">
  </form>
</div>

<div class="row g-3">
  <div class="col-lg-4">
    <div class="card p-3 mb-3">
      <h2 class="h6">Collections</h2>
      <div class="list-group mb-3">
        <% Do Until rsCollections.EOF %>
          <a class="list-group-item list-group-item-action <% If CLng(0 & rsCollections("id")) = collectionId Then Response.Write "active" End If %>" href="<%=H(PortalUrl("app/brainstorm/index.asp"))%>?collection_id=<%=CLng(0 & rsCollections("id"))%>"><%=H(rsCollections("name"))%></a>
          <% rsCollections.MoveNext %>
        <% Loop %>
      </div>
      <form method="post" action="<%=H(PortalUrl("app/brainstorm/index.asp"))%>">
        <%=PortalCsrfField()%>
        <input type="hidden" name="action" value="new_collection">
        <div class="input-group">
          <input class="form-control" name="name" placeholder="New collection" required>
          <button class="btn btn-outline-primary" type="submit">Add</button>
        </div>
      </form>
    </div>

    <div class="card p-3">
      <h2 class="h6">New idea</h2>
      <form method="post" action="<%=H(PortalUrl("app/brainstorm/index.asp"))%>?collection_id=<%=collectionId%>">
        <%=PortalCsrfField()%>
        <input type="hidden" name="action" value="new_idea">
        <input type="hidden" name="collection_id" value="<%=collectionId%>">
        <div class="mb-2"><input class="form-control" name="title" placeholder="Idea title" required></div>
        <div class="mb-2"><textarea class="form-control" name="body" rows="4" placeholder="Idea details"></textarea></div>
        <div class="mb-2"><input class="form-control" name="tags" placeholder="tags,comma,separated"></div>
        <div class="row g-2">
          <div class="col-8">
            <select class="form-select" name="status">
              <option>Raw</option>
              <option>Developing</option>
              <option>Validated</option>
            </select>
          </div>
          <div class="col-4 d-flex align-items-center">
            <div class="form-check"><input class="form-check-input" type="checkbox" name="is_pinned" value="1"><label class="form-check-label">Pin</label></div>
          </div>
        </div>
        <div class="mt-2"><input class="form-control" type="date" name="revisit_on" placeholder="Revisit on"></div>
        <button class="btn btn-primary w-100 mt-3" type="submit">Save idea</button>
      </form>
    </div>
  </div>

  <div class="col-lg-8">
    <% If Not (similarRs Is Nothing) Then %>
      <% If Not similarRs.EOF Then %>
      <div class="card border-warning p-3 mb-3">
        <h2 class="h6 mb-2"><i class="bi bi-exclamation-triangle me-1"></i>This looks similar to previous ideas</h2>
        <ul class="mb-0 small">
          <% Do Until similarRs.EOF %>
            <li><strong><%=H(similarRs("title"))%></strong> · <span class="text-muted"><%=H(similarRs("created_at"))%></span></li>
            <% similarRs.MoveNext %>
          <% Loop %>
        </ul>
      </div>
      <% End If %>
    <% End If %>

    <div class="card p-3">
      <h2 class="h6 mb-3">Ideas</h2>
      <% If rsIdeas.EOF Then %>
        <p class="text-muted mb-0">No ideas yet. Capture your first one.</p>
      <% End If %>
      <% Do Until rsIdeas.EOF %>
        <div class="border rounded p-3 mb-3">
          <div class="d-flex justify-content-between">
            <div>
              <h3 class="h6 mb-1"><%=H(rsIdeas("title"))%> <% If CLng(0 & rsIdeas("is_pinned")) = 1 Then %><i class="bi bi-pin-angle-fill text-primary"></i><% End If %></h3>
              <div class="small text-muted">Status: <%=H(rsIdeas("status"))%> · Tags: <%=H(rsIdeas("tags"))%><% If Trim("" & rsIdeas("revisit_on")) <> "" Then %> · Revisit: <%=H(rsIdeas("revisit_on"))%><% End If %></div>
            </div>
            <div class="d-flex gap-2">
              <form method="post" action="<%=H(PortalUrl("app/brainstorm/index.asp"))%>?collection_id=<%=collectionId%>">
                <%=PortalCsrfField()%>
                <input type="hidden" name="action" value="revisit_tomorrow"><input type="hidden" name="idea_id" value="<%=CLng(0 & rsIdeas("id"))%>">
                <button class="btn btn-sm btn-outline-secondary" type="submit">Revisit tomorrow</button>
              </form>
              <% If PortalHasApp("notes") Then %>
              <form method="post" action="<%=H(PortalUrl("app/brainstorm/index.asp"))%>?collection_id=<%=collectionId%>">
                <%=PortalCsrfField()%>
                <input type="hidden" name="action" value="promote"><input type="hidden" name="idea_id" value="<%=CLng(0 & rsIdeas("id"))%>">
                <button class="btn btn-sm btn-outline-primary" type="submit">Promote to Note</button>
              </form>
              <% End If %>
              <form method="post" action="<%=H(PortalUrl("app/brainstorm/index.asp"))%>?collection_id=<%=collectionId%>">
                <%=PortalCsrfField()%>
                <input type="hidden" name="action" value="archive"><input type="hidden" name="idea_id" value="<%=CLng(0 & rsIdeas("id"))%>">
                <button class="btn btn-sm btn-outline-secondary" type="submit">Archive</button>
              </form>
              <form method="post" action="<%=H(PortalUrl("app/brainstorm/index.asp"))%>?collection_id=<%=collectionId%>">
                <%=PortalCsrfField()%>
                <input type="hidden" name="action" value="delete"><input type="hidden" name="idea_id" value="<%=CLng(0 & rsIdeas("id"))%>">
                <button class="btn btn-sm btn-outline-danger" type="submit">Delete</button>
              </form>
            </div>
          </div>
          <% If Trim("" & rsIdeas("body")) <> "" Then %><div class="mt-2"><%=H(rsIdeas("body"))%></div><% End If %>
        </div>
        <% rsIdeas.MoveNext %>
      <% Loop %>
    </div>
  </div>
</div>

<%
rsCollections.Close
Set rsCollections = Nothing
rsIdeas.Close
Set rsIdeas = Nothing
If Not similarRs Is Nothing Then
    similarRs.Close
    Set similarRs = Nothing
End If
%>
<!--#include file="../../includes/layout_bottom.asp" -->
<%
db.Close
Set db = Nothing
%>
