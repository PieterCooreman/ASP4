<!--#include file="includes/core.asp" -->
<%
Dim fullName, email, password, confirmPassword, errorMsg, userId
Set db = PortalOpen()
Call PortalInit(db)
Call PortalHydrateSession(db)

If PortalIsLoggedIn() Then
    Response.Redirect PortalUrl("dashboard.asp")
    Response.End
End If

errorMsg = ""
If UCase("" & Request.ServerVariables("REQUEST_METHOD")) = "POST" Then
    Call PortalRequirePostCsrf()
    fullName = Trim("" & Request.Form("full_name"))
    email = LCase(Trim("" & Request.Form("email")))
    password = "" & Request.Form("password")
    confirmPassword = "" & Request.Form("confirm_password")

    If fullName = "" Then
        errorMsg = "Please enter your name."
    ElseIf Not PortalLooksLikeEmail(email) Then
        errorMsg = "Please provide a valid email address."
    ElseIf Not PortalIsStrongPassword(password) Then
        errorMsg = "Password must be 10+ chars and include upper, lower, and number."
    ElseIf password <> confirmPassword Then
        errorMsg = "Passwords do not match."
    Else
        userId = PortalCreateIndividual(db, fullName, email, password)
        If CLng(0 & userId) <= 0 Then
            errorMsg = "That email is already in use."
        Else
            Call PortalLoadUserSession(db, userId)
            Call PortalSetFlash("Your workspace is ready.", "success")
            Response.Redirect PortalHomeUrl()
            Response.End
        End If
    End If
End If

pageTitle = "Sign up"
%>
<!--#include file="includes/layout_top.asp" -->

<div class="row justify-content-center">
  <div class="col-md-8 col-lg-6">
    <div class="card p-4">
      <h2 class="h4 mb-3">Create your portal</h2>
      <% If errorMsg <> "" Then %><div class="alert alert-danger"><%=H(errorMsg)%></div><% End If %>
      <form method="post" action="<%=H(PortalUrl("signup.asp"))%>">
        <%=PortalCsrfField()%>
        <div class="mb-3">
          <label class="form-label">Full name</label>
          <input class="form-control" type="text" name="full_name" required>
          <div class="invalid-feedback">Please enter your name.</div>
        </div>
        <div class="mb-3">
          <label class="form-label">Email</label>
          <input class="form-control" type="email" name="email" required>
          <div class="invalid-feedback">Please enter a valid email.</div>
        </div>
        <div class="row g-3">
          <div class="col-md-6">
            <label class="form-label">Password</label>
            <input id="signupPassword" class="form-control" type="password" name="password" data-rule="password-strong" required>
            <div class="form-text">10+ chars, uppercase, lowercase, number.</div>
            <div class="invalid-feedback">Password does not meet policy.</div>
          </div>
          <div class="col-md-6">
            <label class="form-label">Confirm password</label>
            <input class="form-control" type="password" name="confirm_password" data-match="signupPassword" required>
            <div class="invalid-feedback">Passwords must match.</div>
          </div>
        </div>
        <button class="btn btn-primary w-100 mt-4" type="submit">Create workspace</button>
      </form>
      <p class="small text-muted mt-3 mb-0">Already registered? <a href="<%=H(PortalUrl("login.asp"))%>">Log in</a></p>
    </div>
  </div>
</div>

<!--#include file="includes/layout_bottom.asp" -->
<%
db.Close
Set db = Nothing
%>
