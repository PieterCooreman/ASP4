<%
Dim __pageTitle, __flash, __flashLevel, __primary
Dim __timeoutMinutes, __warnSeconds
__pageTitle = "Portal"
If "" & pageTitle <> "" Then __pageTitle = "" & pageTitle
__flash = PortalPopFlash()
__flashLevel = PortalFlashLevel()
__primary = "" & Session("portal_primary_color")
If __primary = "" Then __primary = "#2f6fed"
__timeoutMinutes = 20
__warnSeconds = 60
If PortalIsLoggedIn() Then
  __timeoutMinutes = PortalSessionTimeoutMinutes()
  __warnSeconds = 90
End If
%>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title><%=H(__pageTitle)%> - ASPpy Portal</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet" crossorigin="anonymous">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.13.1/font/bootstrap-icons.min.css" rel="stylesheet">
  <link href="<%=H(PortalUrl("assets/portal.css"))%>" rel="stylesheet">
  <style>:root{--color-primary:<%=H(__primary)%>;}</style>
</head>
<body data-session-timeout-min="<%=__timeoutMinutes%>" data-session-warning-sec="<%=__warnSeconds%>">
<nav class="navbar navbar-expand-lg border-bottom bg-white sticky-top">
  <div class="container">
    <a class="navbar-brand fw-semibold" href="<%=H(PortalUrl("dashboard.asp"))%>"><i class="bi bi-grid-1x2-fill me-2 text-primary"></i>Portal</a>
    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navMain"><span class="navbar-toggler-icon"></span></button>
    <div class="collapse navbar-collapse" id="navMain">
      <ul class="navbar-nav me-auto mb-2 mb-lg-0">
        <% If PortalIsLoggedIn() Then %>
          <li class="nav-item"><a class="nav-link" href="<%=H(PortalUrl("dashboard.asp"))%>">Dashboard</a></li>
          <% If PortalHasApp("briefing") Then %><li class="nav-item"><a class="nav-link" href="<%=H(PortalUrl("app/briefing/index.asp"))%>">Today</a></li><% End If %>
          <% If PortalHasApp("todo") Then %><li class="nav-item"><a class="nav-link" href="<%=H(PortalUrl("app/todo/index.asp"))%>">Todo</a></li><% End If %>
          <% If PortalHasApp("brainstorm") Then %><li class="nav-item"><a class="nav-link" href="<%=H(PortalUrl("app/brainstorm/index.asp"))%>">Ideas</a></li><% End If %>
          <% If PortalHasApp("notes") Then %><li class="nav-item"><a class="nav-link" href="<%=H(PortalUrl("app/notes/index.asp"))%>">Notes</a></li><% End If %>
          <% If PortalHasApp("contacts") Then %><li class="nav-item"><a class="nav-link" href="<%=H(PortalUrl("app/contacts/index.asp"))%>">Contacts</a></li><% End If %>
          <% If PortalHasApp("bookmarks") Then %><li class="nav-item"><a class="nav-link" href="<%=H(PortalUrl("app/bookmarks/index.asp"))%>">Bookmarks</a></li><% End If %>
          <% If PortalHasApp("habits") Then %><li class="nav-item"><a class="nav-link" href="<%=H(PortalUrl("app/habits/index.asp"))%>">Habits</a></li><% End If %>
          <% If PortalHasApp("vault") Then %><li class="nav-item"><a class="nav-link" href="<%=H(PortalUrl("app/vault/index.asp"))%>">Vault</a></li><% End If %>
          <% If PortalHasApp("wins") Then %><li class="nav-item"><a class="nav-link" href="<%=H(PortalUrl("app/wins/index.asp"))%>">Wins</a></li><% End If %>
          <% If PortalIsTenantAdmin() Then %><li class="nav-item"><a class="nav-link" href="<%=H(PortalUrl("admin/users.asp"))%>">Admin</a></li><% End If %>
        <% End If %>
      </ul>
      <div class="d-flex align-items-center gap-2">
        <% If PortalIsLoggedIn() Then %>
          <span class="small text-muted d-none d-md-inline"><%=H(Session("portal_user_name"))%> · <%=H(Session("portal_tenant_name"))%></span>
          <a class="btn btn-sm btn-outline-secondary" href="<%=H(PortalUrl("account.asp"))%>">Account</a>
          <a class="btn btn-sm btn-outline-danger" href="<%=H(PortalUrl("logout.asp"))%>">Logout</a>
        <% Else %>
          <a class="btn btn-sm btn-outline-primary" href="<%=H(PortalUrl("login.asp"))%>">Login</a>
          <a class="btn btn-sm btn-primary" href="<%=H(PortalUrl("signup.asp"))%>">Sign up</a>
        <% End If %>
      </div>
    </div>
  </div>
</nav>

<main class="container py-4">
  <% If PortalIsLoggedIn() Then %>
    <div id="sessionWarn" class="alert alert-warning d-none d-flex justify-content-between align-items-center" role="alert" aria-live="polite">
      <span><i class="bi bi-hourglass-split me-1"></i>Your session is about to expire due to inactivity. <strong id="sessionWarnCountdown">60</strong>s</span>
      <button type="button" id="staySignedIn" class="btn btn-sm btn-warning">Stay signed in</button>
    </div>
  <% End If %>
  <% If __flash <> "" Then %>
    <div class="alert alert-<%=H(__flashLevel)%> alert-dismissible fade show" role="alert">
      <%=H(__flash)%>
      <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    </div>
  <% End If %>
