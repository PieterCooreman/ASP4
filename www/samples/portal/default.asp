<!--#include file="includes/core.asp" -->
<%
Set db = PortalOpen()
Call PortalInit(db)
Call PortalHydrateSession(db)

If PortalIsLoggedIn() Then
    Response.Redirect PortalHomeUrl()
    Response.End
End If

pageTitle = "Welcome"
%>
<!--#include file="includes/layout_top.asp" -->

<div class="row g-4 align-items-center">
  <div class="col-lg-7">
    <div class="card p-4 p-lg-5">
      <h1 class="display-6 mb-3">Build momentum with a focused portal.</h1>
      <p class="lead text-muted">A multi-tenant workspace for teams and individuals. Start with Todo and Ideas, add apps over time, and manage access from one dashboard.</p>
      <div class="d-flex gap-2 mt-3">
        <a href="<%=H(PortalUrl("signup.asp"))%>" class="btn btn-primary btn-lg">Create account</a>
        <a href="<%=H(PortalUrl("login.asp"))%>" class="btn btn-outline-secondary btn-lg">Log in</a>
      </div>
    </div>
  </div>
  <div class="col-lg-5">
    <div class="card p-4">
      <h5 class="section-title mb-3">What is included now</h5>
      <ul class="mb-0 text-muted">
        <li>Tenant-aware user accounts and roles</li>
        <li>Permission-based app dashboard</li>
        <li>Todo lists with statuses and priorities</li>
        <li>Ideas manager with collections and tags</li>
      </ul>
    </div>
  </div>
</div>

<!--#include file="includes/layout_bottom.asp" -->
<%
db.Close
Set db = Nothing
%>
