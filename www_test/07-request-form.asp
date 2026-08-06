<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<%
Option Explicit
%>
<!--#include file="includes/helpers.asp"-->
<%
' ============================================================================
' 07-request-form.asp - Request, Response and form handling
' Demonstrates: reading Request.QueryString and Request.Form, a self-posting
' form (POST back to itself), server-side validation, and reading
' Request.ServerVariables. Shows the full request round-trip.
' ============================================================================
Dim PageTitle : PageTitle = "Request & Forms"
%>
<!--#include file="includes/header.asp"-->
<%
' --- Gather and validate the posted form ----------------------------------
Dim wasPosted, fName, fEmail, fColor, fAgree, errors
wasPosted = (UCase(Request.ServerVariables("REQUEST_METHOD")) = "POST")
errors = ""

fName  = Trim(Request.Form("name")  & "")
fEmail = Trim(Request.Form("email") & "")
fColor = Trim(Request.Form("color") & "")
fAgree = (Request.Form("agree") = "yes")

If wasPosted Then
    If IsBlank(fName)  Then errors = errors & "<li>Name is required.</li>"
    If IsBlank(fEmail) Or InStr(fEmail, "@") = 0 Then errors = errors & "<li>A valid email is required.</li>"
    If Not fAgree Then errors = errors & "<li>You must tick the agreement box.</li>"
End If
%>
<h1>Request &amp; Forms</h1>
<p class="lead">Reading the QueryString, handling a POSTed form, and inspecting the request.</p>

<h2>QueryString</h2>
<%
DemoStart "Try appending ?q=hello&n=5 to the URL"
WriteLine "<table class=""kv"">"
RenderTableRow "Request.QueryString(""q"")", Coalesce(Request.QueryString("q"), "(not supplied)")
RenderTableRow "Request.QueryString(""n"")", Coalesce(Request.QueryString("n"), "(not supplied)")
RenderTableRow "Raw QueryString",            Coalesce(Request.ServerVariables("QUERY_STRING"), "(empty)")
WriteLine "</table>"
WriteLine "<p><a href=""?q=hello&n=5"">Click here to add a sample query string &raquo;</a></p>"
DemoEnd
%>

<h2>Self-posting form</h2>
<%
If wasPosted And Len(errors) = 0 Then
    ' Success branch.
    DemoStart "Submission accepted"
    WriteLine "<p class=""ok"">Thank you, your details were received:</p>"
    WriteLine "<table class=""kv"">"
    RenderTableRow "Name",  fName
    RenderTableRow "Email", fEmail
    RenderTableRow "Favourite colour", Coalesce(fColor, "(none)")
    RenderTableRow "Agreed", fAgree
    WriteLine "</table>"
    WriteLine "<p><a href=""07-request-form.asp"">Reset form &raquo;</a></p>"
    DemoEnd
Else
    ' Show the form (and any validation errors).
    If wasPosted And Len(errors) > 0 Then
        WriteLine "<div class=""demo""><p class=""err""><strong>Please fix:</strong></p><ul class=""err"">" & errors & "</ul></div>"
    End If
    DemoStart "Fill in and submit (posts back to this page)"
%>
    <form method="post" action="07-request-form.asp" class="demo-form">
      <div>
        <label for="name">Name *</label>
        <input type="text" id="name" name="name" value="<%= HtmlEncode(fName) %>">
      </div>
      <div>
        <label for="email">Email *</label>
        <input type="text" id="email" name="email" value="<%= HtmlEncode(fEmail) %>">
      </div>
      <div>
        <label for="color">Favourite colour</label>
        <select id="color" name="color">
<%
        Dim opts, o
        opts = Array("", "red", "green", "blue", "amber")
        For Each o In opts
            Dim sel : sel = ""
            If o = fColor Then sel = " selected"
            If o = "" Then
                WriteLine "          <option value=""""" & sel & ">-- pick one --</option>"
            Else
                WriteLine "          <option value=""" & HtmlEncode(o) & """" & sel & ">" & HtmlEncode(o) & "</option>"
            End If
        Next
%>
        </select>
      </div>
      <div>
        <label><input type="checkbox" name="agree" value="yes"<% If fAgree Then Response.Write " checked" %>> I agree to the terms *</label>
      </div>
      <button type="submit">Submit</button>
    </form>
<%
    DemoEnd
End If
%>

<h2>Request inspection (ServerVariables)</h2>
<%
DemoStart "A few useful server variables"
WriteLine "<table class=""kv"">"
RenderTableRow "REQUEST_METHOD",  Request.ServerVariables("REQUEST_METHOD")
RenderTableRow "URL",             Request.ServerVariables("URL")
RenderTableRow "REMOTE_ADDR",     Request.ServerVariables("REMOTE_ADDR")
RenderTableRow "HTTP_USER_AGENT", Left(Request.ServerVariables("HTTP_USER_AGENT") & "", 80)
RenderTableRow "SERVER_PORT",     Request.ServerVariables("SERVER_PORT")
RenderTableRow "LOCAL_ADDR",      Request.ServerVariables("LOCAL_ADDR")
WriteLine "</table>"
DemoEnd
%>
<!--#include file="includes/footer.asp"-->
