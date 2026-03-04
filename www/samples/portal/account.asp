<!--#include file="includes/core.asp" -->
<%
Dim uid, nameVal, tzVal, pass1, pass2, errMsg
Set db = PortalOpen()
Call PortalInit(db)
Call PortalHydrateSession(db)
Call PortalRequireLogin()

uid = PortalCurrentUserId()
errMsg = ""

If UCase("" & Request.ServerVariables("REQUEST_METHOD")) = "POST" Then
    Call PortalRequirePostCsrf()
    nameVal = Trim("" & Request.Form("name"))
    tzVal = Trim("" & Request.Form("timezone"))
    pass1 = "" & Request.Form("password")
    pass2 = "" & Request.Form("password2")

    If nameVal = "" Then
        errMsg = "Name cannot be empty."
    Else
        Call PortalExec(db, "UPDATE users SET name=" & SqlQ(nameVal) & ", timezone=" & SqlQ(tzVal) & " WHERE id=" & uid)
        If pass1 <> "" Then
            If Not PortalIsStrongPassword(pass1) Then
                errMsg = "Password must be 10+ chars and include upper, lower, and number."
            ElseIf pass1 <> pass2 Then
                errMsg = "Passwords do not match."
            Else
                Call PortalExec(db, "UPDATE users SET password_hash=" & SqlQ(ASP4.Crypto.Hash(pass1, 10)) & " WHERE id=" & uid)
            End If
        End If
        If errMsg = "" Then
            Call PortalLoadUserSession(db, uid)
            Call PortalSetFlash("Account updated.", "success")
            Response.Redirect PortalUrl("account.asp")
            Response.End
        End If
    End If
End If

Set rsUser = db.Execute("SELECT name,email,timezone FROM users WHERE id=" & uid & " LIMIT 1")
pageTitle = "Account"
%>
<!--#include file="includes/layout_top.asp" -->

<div class="row justify-content-center">
  <div class="col-lg-8">
    <div class="card p-4">
      <h1 class="h4 mb-3">Account settings</h1>
      <% If errMsg <> "" Then %><div class="alert alert-danger"><%=H(errMsg)%></div><% End If %>
      <form method="post" action="<%=H(PortalUrl("account.asp"))%>">
        <%=PortalCsrfField()%>
        <div class="row g-3">
          <div class="col-md-6">
            <label class="form-label">Name</label>
            <input class="form-control" type="text" name="name" value="<%=H(rsUser("name"))%>" required>
            <div class="invalid-feedback">Name is required.</div>
          </div>
          <div class="col-md-6">
            <label class="form-label">Email</label>
            <input class="form-control" type="email" value="<%=H(rsUser("email"))%>" disabled>
          </div>
          <div class="col-md-6">
            <label class="form-label">Timezone</label>
            <input class="form-control" type="text" name="timezone" value="<%=H(rsUser("timezone"))%>" placeholder="UTC">
          </div>
          <div class="col-md-6">
            <label class="form-label">New password</label>
            <input id="accountPassword" class="form-control" type="password" name="password" data-rule="password-strong" placeholder="Leave empty to keep current">
            <div class="form-text">Optional. If set: 10+ chars, uppercase, lowercase, number.</div>
          </div>
          <div class="col-md-6">
            <label class="form-label">Confirm password</label>
            <input class="form-control" type="password" name="password2" data-match="accountPassword">
            <div class="invalid-feedback">Passwords must match.</div>
          </div>
        </div>
        <button class="btn btn-primary mt-4" type="submit">Save changes</button>
      </form>
    </div>
  </div>
</div>

<%
rsUser.Close
Set rsUser = Nothing
%>
<!--#include file="includes/layout_bottom.asp" -->
<%
db.Close
Set db = Nothing
%>
