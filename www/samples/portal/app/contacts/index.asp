<!--#include file="../../includes/core.asp" -->
<%
Dim tid, uid, actionName, q
Set db = PortalOpen()
Call PortalInit(db)
Call PortalHydrateSession(db)
Call PortalRequireApp("contacts")
Call PortalTouchUsage(db, "contacts")

tid = PortalCurrentTenantId()
uid = PortalCurrentUserId()

If UCase("" & Request.ServerVariables("REQUEST_METHOD")) = "POST" Then
    Call PortalRequirePostCsrf()
    actionName = LCase("" & Request.Form("action"))
    If actionName = "new" Then
        Call PortalExec(db, "INSERT INTO contacts_people(tenant_id,user_id,full_name,email,phone,company,tags,notes,last_interaction,updated_at) VALUES(" & tid & "," & uid & "," & SqlQ(Left(Trim("" & Request.Form("full_name")),180)) & "," & SqlQ(Left(Trim("" & Request.Form("email")),180)) & "," & SqlQ(Left(Trim("" & Request.Form("phone")),80)) & "," & SqlQ(Left(Trim("" & Request.Form("company")),180)) & "," & SqlQ(Left(Trim("" & Request.Form("tags")),500)) & "," & SqlQ(Left(Trim("" & Request.Form("notes")),4000)) & "," & SqlQ(Trim("" & Request.Form("last_interaction"))) & ",CURRENT_TIMESTAMP)")
        Call PortalSetFlash("Contact added.", "success")
    ElseIf actionName = "delete" Then
        Call PortalExec(db, "DELETE FROM contacts_people WHERE id=" & SqlN(Request.Form("contact_id")) & " AND tenant_id=" & tid & " AND user_id=" & uid)
        Call PortalSetFlash("Contact removed.", "info")
    End If
End If

q = Trim("" & Request.QueryString("q"))
sql = "SELECT id,full_name,email,phone,company,tags,last_interaction FROM contacts_people WHERE tenant_id=" & tid & " AND user_id=" & uid
If q <> "" Then
    sql = sql & " AND (full_name LIKE " & SqlQ("%" & q & "%") & " OR email LIKE " & SqlQ("%" & q & "%") & " OR company LIKE " & SqlQ("%" & q & "%") & " OR tags LIKE " & SqlQ("%" & q & "%") & ")"
End If
sql = sql & " ORDER BY full_name"
Set rsContacts = db.Execute(sql)
pageTitle = "Contacts"
%>
<!--#include file="../../includes/layout_top.asp" -->

<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h4 mb-0">Contacts / People Manager</h1>
  <form method="get" action="<%=H(PortalUrl("app/contacts/index.asp"))%>" class="d-flex"><input class="form-control form-control-sm" name="q" value="<%=H(q)%>" placeholder="Search contacts"></form>
</div>

<div class="row g-3">
  <div class="col-lg-4">
    <div class="card p-3">
      <h2 class="h6">New contact</h2>
      <form method="post" action="<%=H(PortalUrl("app/contacts/index.asp"))%>">
        <%=PortalCsrfField()%>
        <input type="hidden" name="action" value="new">
        <div class="mb-2"><input class="form-control" name="full_name" placeholder="Full name" required></div>
        <div class="mb-2"><input class="form-control" type="email" name="email" placeholder="Email"></div>
        <div class="mb-2"><input class="form-control" name="phone" placeholder="Phone"></div>
        <div class="mb-2"><input class="form-control" name="company" placeholder="Company"></div>
        <div class="mb-2"><input class="form-control" name="tags" placeholder="tags,comma,separated"></div>
        <div class="mb-2"><input class="form-control" type="date" name="last_interaction"></div>
        <div class="mb-2"><textarea class="form-control" rows="4" name="notes" placeholder="Notes"></textarea></div>
        <button class="btn btn-primary w-100" type="submit">Save contact</button>
      </form>
    </div>
  </div>
  <div class="col-lg-8">
    <div class="card p-3">
      <h2 class="h6 mb-3">People</h2>
      <% If rsContacts.EOF Then %><p class="text-muted mb-0">No contacts yet.</p><% End If %>
      <% Do Until rsContacts.EOF %>
      <div class="border rounded p-3 mb-3">
        <div class="d-flex justify-content-between align-items-start">
          <div>
            <h3 class="h6 mb-1"><%=H(rsContacts("full_name"))%></h3>
            <div class="small text-muted"><%=H(rsContacts("company"))%> · <%=H(rsContacts("email"))%> · <%=H(rsContacts("phone"))%></div>
            <% If Trim("" & rsContacts("tags")) <> "" Then %><div class="small mt-1">Tags: <%=H(rsContacts("tags"))%></div><% End If %>
          </div>
          <form method="post" action="<%=H(PortalUrl("app/contacts/index.asp"))%>">
            <%=PortalCsrfField()%>
            <input type="hidden" name="action" value="delete"><input type="hidden" name="contact_id" value="<%=CLng(0 & rsContacts("id"))%>">
            <button class="btn btn-sm btn-outline-danger" type="submit">Delete</button>
          </form>
        </div>
      </div>
      <% rsContacts.MoveNext : Loop %>
    </div>
  </div>
</div>

<%
rsContacts.Close : Set rsContacts = Nothing
%>
<!--#include file="../../includes/layout_bottom.asp" -->
<% db.Close : Set db = Nothing %>
