<!--#include file="../../includes/core.asp" -->
<%
Dim tid, uid, actionName, q
Set db = PortalOpen()
Call PortalInit(db)
Call PortalHydrateSession(db)
Call PortalRequireApp("vault")
Call PortalTouchUsage(db, "vault")

tid = PortalCurrentTenantId()
uid = PortalCurrentUserId()

If UCase("" & Request.ServerVariables("REQUEST_METHOD")) = "POST" Then
    Call PortalRequirePostCsrf()
    actionName = LCase("" & Request.Form("action"))
    If actionName = "new" Then
        Call PortalExec(db, "INSERT INTO vault_snippets(tenant_id,user_id,title,body,kind,tags,is_shared,updated_at) VALUES(" & tid & "," & uid & "," & SqlQ(Left(Trim("" & Request.Form("title")),180)) & "," & SqlQ(Left("" & Request.Form("body"),12000)) & "," & SqlQ(Trim("" & Request.Form("kind"))) & "," & SqlQ(Left(Trim("" & Request.Form("tags")),500)) & "," & SqlN(Request.Form("is_shared")) & ",CURRENT_TIMESTAMP)")
        Call PortalSetFlash("Snippet saved.", "success")
    ElseIf actionName = "delete" Then
        Call PortalExec(db, "DELETE FROM vault_snippets WHERE id=" & SqlN(Request.Form("snippet_id")) & " AND tenant_id=" & tid & " AND user_id=" & uid)
    End If
End If

q = Trim("" & Request.QueryString("q"))
sql = "SELECT id,title,kind,tags,substr(body,1,220) AS preview,updated_at FROM vault_snippets WHERE tenant_id=" & tid & " AND user_id=" & uid
If q <> "" Then sql = sql & " AND (title LIKE " & SqlQ("%" & q & "%") & " OR body LIKE " & SqlQ("%" & q & "%") & " OR tags LIKE " & SqlQ("%" & q & "%") & ")"
sql = sql & " ORDER BY updated_at DESC"
Set rsSnips = db.Execute(sql)
pageTitle = "Vault"
%>
<!--#include file="../../includes/layout_top.asp" -->

<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">File / Snippet Vault</h1>
  <form method="get" action="<%=H(PortalUrl("app/vault/index.asp"))%>" class="d-flex"><input class="form-control form-control-sm" name="q" value="<%=H(q)%>" placeholder="Search snippets"></form>
</div>

<div class="row g-3">
  <div class="col-lg-4">
    <div class="card p-3">
      <h2 class="h6">New snippet</h2>
      <form method="post" action="<%=H(PortalUrl("app/vault/index.asp"))%>">
        <%=PortalCsrfField()%>
        <input type="hidden" name="action" value="new">
        <div class="mb-2"><input class="form-control" name="title" placeholder="Snippet title" required></div>
        <div class="mb-2">
          <select class="form-select" name="kind">
            <option value="text">Text</option>
            <option value="code">Code</option>
            <option value="template">Template</option>
          </select>
        </div>
        <div class="mb-2"><input class="form-control" name="tags" placeholder="tags,comma,separated"></div>
        <div class="mb-2"><textarea class="form-control" rows="7" name="body" placeholder="Snippet body" required></textarea></div>
        <button class="btn btn-primary w-100" type="submit">Save snippet</button>
      </form>
    </div>
  </div>

  <div class="col-lg-8">
    <div class="card p-3">
      <h2 class="h6 mb-3">Your snippets</h2>
      <% If rsSnips.EOF Then %><p class="text-muted mb-0">No snippets yet.</p><% End If %>
      <% Do Until rsSnips.EOF %>
        <div class="border rounded p-3 mb-3">
          <div class="d-flex justify-content-between align-items-start">
            <div>
              <h3 class="h6 mb-1"><%=H(rsSnips("title"))%></h3>
              <div class="small text-muted"><%=H(rsSnips("kind"))%> · <%=H(rsSnips("updated_at"))%></div>
              <div class="small">Tags: <%=H(rsSnips("tags"))%></div>
            </div>
            <form method="post" action="<%=H(PortalUrl("app/vault/index.asp"))%>">
              <%=PortalCsrfField()%>
              <input type="hidden" name="action" value="delete"><input type="hidden" name="snippet_id" value="<%=CLng(0 & rsSnips("id"))%>">
              <button class="btn btn-sm btn-outline-danger" type="submit">Delete</button>
            </form>
          </div>
          <pre class="mt-2 mb-0 small"><%=H(rsSnips("preview"))%></pre>
        </div>
        <% rsSnips.MoveNext %>
      <% Loop %>
    </div>
  </div>
</div>

<%
rsSnips.Close : Set rsSnips = Nothing
%>
<!--#include file="../../includes/layout_bottom.asp" -->
<% db.Close : Set db = Nothing %>
