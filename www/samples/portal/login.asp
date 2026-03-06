<!--#include file="includes/core.asp" -->
<%
Dim email, password, nextUrl, errorMsg, userId
Set db = PortalOpen()
Call PortalInit(db)
Call PortalHydrateSession(db)

If PortalIsLoggedIn() Then
    Response.Redirect PortalUrl("dashboard.asp")
    Response.End
End If

nextUrl = "" & Request.QueryString("next")
errorMsg = ""

If UCase("" & Request.ServerVariables("REQUEST_METHOD")) = "POST" Then
    Call PortalRequirePostCsrf()
    email = Trim("" & Request.Form("email"))
    password = "" & Request.Form("password")
    nextUrl = "" & Request.Form("next")

    userId = PortalAuthenticate(db, email, password)
    If CLng(0 & userId) > 0 Then
        Call PortalLoadUserSession(db, userId)
        Call PortalSetFlash("Welcome back, " & Session("portal_user_name") & ".", "success")
        If nextUrl <> "" Then
            Response.Redirect nextUrl
        Else
            Response.Redirect PortalHomeUrl()
        End If
        Response.End
    Else
        errorMsg = "Invalid credentials or inactive account."
    End If
End If

pageTitle = "Login"
%>
<!--#include file="includes/layout_top.asp" -->

<div class="row justify-content-center">
  <div class="col-md-7 col-lg-5">
    <div class="card p-4">
      <h2 class="h4 mb-3">Log in</h2>
      <% If errorMsg <> "" Then %><div class="alert alert-danger"><%=H(errorMsg)%></div><% End If %>
      <form method="post" action="<%=H(PortalUrl("login.asp"))%>">
        <%=PortalCsrfField()%>
        <input type="hidden" name="next" value="<%=H(nextUrl)%>">
        <div class="mb-3">
          <label class="form-label">Email</label>
          <input class="form-control" type="email" name="email" required>
          <div class="invalid-feedback">Please enter your email.</div>
        </div>
        <div class="mb-3">
          <label class="form-label">Password</label>
          <input class="form-control" type="password" name="password" required>
          <div class="invalid-feedback">Please enter your password.</div>
        </div>
        <button class="btn btn-primary w-100" type="submit">Continue</button>
      </form>
      <p class="small text-muted mt-3 mb-0">No account yet? <a href="<%=H(PortalUrl("signup.asp"))%>">Create one</a></p>
    </div>
  </div>
</div>

<!--#include file="includes/layout_bottom.asp" -->
<%
db.Close
Set db = Nothing
%>
