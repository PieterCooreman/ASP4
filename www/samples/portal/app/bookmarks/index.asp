<!--#include file="../../includes/core.asp" -->
<%
Dim tid, uid, actionName, folderName, q
Set db = PortalOpen()
Call PortalInit(db)
Call PortalHydrateSession(db)
Call PortalRequireApp("bookmarks")
Call PortalTouchUsage(db, "bookmarks")

tid = PortalCurrentTenantId()
uid = PortalCurrentUserId()

If UCase("" & Request.ServerVariables("REQUEST_METHOD")) = "POST" Then
    Call PortalRequirePostCsrf()
    actionName = LCase("" & Request.Form("action"))
    If actionName = "new" Then
        If Trim("" & Request.Form("url")) <> "" Then
            Dim checkUrl, dupCount
            checkUrl = LCase(Trim("" & Request.Form("url")))
            dupCount = CLng(0 & PortalScalar(db, "SELECT COUNT(*) FROM bookmarks_items WHERE tenant_id=" & tid & " AND user_id=" & uid & " AND lower(url)=" & SqlQ(checkUrl), 0))
            If dupCount > 0 Then
                Call PortalSetFlash("That URL already exists in your bookmarks.", "warning")
            Else
                Call PortalExec(db, "INSERT INTO bookmarks_items(tenant_id,user_id,title,url,tags,folder_name,is_read) VALUES(" & tid & "," & uid & "," & SqlQ(Left(Trim("" & Request.Form("title")),180)) & "," & SqlQ(Left(Trim("" & Request.Form("url")),1200)) & "," & SqlQ(Left(Trim("" & Request.Form("tags")),500)) & "," & SqlQ(Left(Trim("" & Request.Form("folder_name")),120)) & ",0)")
                Call PortalSetFlash("Bookmark saved.", "success")
            End If
        End If
    ElseIf actionName = "toggle_read" Then
        Call PortalExec(db, "UPDATE bookmarks_items SET is_read = CASE WHEN is_read=1 THEN 0 ELSE 1 END WHERE id=" & SqlN(Request.Form("bookmark_id")) & " AND tenant_id=" & tid & " AND user_id=" & uid)
    ElseIf actionName = "delete" Then
        Call PortalExec(db, "DELETE FROM bookmarks_items WHERE id=" & SqlN(Request.Form("bookmark_id")) & " AND tenant_id=" & tid & " AND user_id=" & uid)
    End If
End If

q = Trim("" & Request.QueryString("q"))
folderName = Trim("" & Request.QueryString("folder"))
sql = "SELECT id,title,url,tags,folder_name,is_read,created_at FROM bookmarks_items WHERE tenant_id=" & tid & " AND user_id=" & uid
If q <> "" Then sql = sql & " AND (title LIKE " & SqlQ("%" & q & "%") & " OR url LIKE " & SqlQ("%" & q & "%") & " OR tags LIKE " & SqlQ("%" & q & "%") & ")"
If folderName <> "" Then sql = sql & " AND folder_name=" & SqlQ(folderName)
sql = sql & " ORDER BY created_at DESC"
Set rsBm = db.Execute(sql)
Set rsFolders = db.Execute("SELECT folder_name,COUNT(*) AS c FROM bookmarks_items WHERE tenant_id=" & tid & " AND user_id=" & uid & " GROUP BY folder_name ORDER BY folder_name")
pageTitle = "Bookmarks"
%>
<!--#include file="../../includes/layout_top.asp" -->

<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">Bookmarks / Reading List</h1>
  <form method="get" action="<%=H(PortalUrl("app/bookmarks/index.asp"))%>" class="d-flex gap-2">
    <input class="form-control form-control-sm" name="q" value="<%=H(q)%>" placeholder="Search links">
    <button class="btn btn-sm btn-outline-secondary" type="submit">Search</button>
  </form>
</div>

<div class="row g-3">
  <div class="col-lg-4">
    <div class="card p-3 mb-3">
      <h2 class="h6">Save bookmark</h2>
      <form method="post" action="<%=H(PortalUrl("app/bookmarks/index.asp"))%>">
        <%=PortalCsrfField()%>
        <input type="hidden" name="action" value="new">
        <div class="mb-2"><input class="form-control" name="title" placeholder="Title" required></div>
        <div class="mb-2"><input class="form-control" type="url" name="url" placeholder="https://..." required></div>
        <div class="mb-2"><input class="form-control" name="folder_name" placeholder="Folder"></div>
        <div class="mb-2"><input class="form-control" name="tags" placeholder="tags,comma,separated"></div>
        <button class="btn btn-primary w-100" type="submit">Save</button>
      </form>
    </div>
    <div class="card p-3">
      <h2 class="h6">Folders</h2>
      <a class="d-block small mb-1" href="<%=H(PortalUrl("app/bookmarks/index.asp"))%>">All</a>
      <% Do Until rsFolders.EOF %>
        <% If Trim("" & rsFolders("folder_name")) <> "" Then %>
          <a class="d-block small mb-1" href="<%=H(PortalUrl("app/bookmarks/index.asp"))%>?folder=<%=Server.URLEncode("" & rsFolders("folder_name"))%>"><%=H(rsFolders("folder_name"))%> (<%=CLng(0 & rsFolders("c"))%>)</a>
        <% End If %>
        <% rsFolders.MoveNext %>
      <% Loop %>
    </div>
  </div>

  <div class="col-lg-8">
    <div class="card p-3">
      <h2 class="h6 mb-3">Saved links</h2>
      <% If rsBm.EOF Then %><p class="text-muted mb-0">No bookmarks yet.</p><% End If %>
      <% Do Until rsBm.EOF %>
      <div class="border rounded p-3 mb-3">
        <div class="d-flex justify-content-between">
          <div>
            <h3 class="h6 mb-1"><a href="<%=H(rsBm("url"))%>" target="_blank" rel="noopener"><%=H(rsBm("title"))%></a></h3>
            <div class="small text-muted"><%=H(rsBm("url"))%></div>
            <div class="small">Folder: <%=H(rsBm("folder_name"))%> · Tags: <%=H(rsBm("tags"))%></div>
          </div>
          <div class="d-flex gap-2">
            <form method="post" action="<%=H(PortalUrl("app/bookmarks/index.asp"))%>">
              <%=PortalCsrfField()%>
              <input type="hidden" name="action" value="toggle_read"><input type="hidden" name="bookmark_id" value="<%=CLng(0 & rsBm("id"))%>">
              <button class="btn btn-sm <% If CLng(0 & rsBm("is_read"))=1 Then Response.Write "btn-success" Else Response.Write "btn-outline-secondary" End If %>" type="submit"><% If CLng(0 & rsBm("is_read"))=1 Then Response.Write "Read" Else Response.Write "Unread" End If %></button>
            </form>
            <form method="post" action="<%=H(PortalUrl("app/bookmarks/index.asp"))%>">
              <%=PortalCsrfField()%>
              <input type="hidden" name="action" value="delete"><input type="hidden" name="bookmark_id" value="<%=CLng(0 & rsBm("id"))%>">
              <button class="btn btn-sm btn-outline-danger" type="submit">Delete</button>
            </form>
          </div>
        </div>
      </div>
      <% rsBm.MoveNext : Loop %>
    </div>
  </div>
</div>

<%
rsFolders.Close : Set rsFolders = Nothing
rsBm.Close : Set rsBm = Nothing
%>
<!--#include file="../../includes/layout_bottom.asp" -->
<% db.Close : Set db = Nothing %>
