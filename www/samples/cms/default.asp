<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<!-- #include file="includes/includes.asp" -->
<%
Dim db, pagesSvc, settingsSvc
Dim slug, rsPage, rsMenu, rsSettings
Dim siteTitle, siteSlogan
Dim cPrimary, cSecondary, cSuccess, cDanger, cWarning, cInfo, cLight, cDark
Dim fBody, fHeading, fButton
Dim pageTitle, pageBody, pageFound

Set db = New cls_db
db.Open
Set pagesSvc = New cls_page
Set settingsSvc = New cls_settings

Set rsSettings = settingsSvc.GetOne(db)
If rsSettings.EOF Then
    siteTitle = "ASP4 CMS"
    siteSlogan = ""
    cPrimary = "#0d6efd": cSecondary = "#6c757d": cSuccess = "#198754": cDanger = "#dc3545"
    cWarning = "#ffc107": cInfo = "#0dcaf0": cLight = "#f8f9fa": cDark = "#212529"
    fBody = "Inter": fHeading = "Inter": fButton = "Inter"
Else
    siteTitle = "" & Nz(rsSettings("site_title"), "ASP4 CMS")
    siteSlogan = "" & Nz(rsSettings("site_slogan"), "")
    cPrimary = "" & Nz(rsSettings("color_primary"), "#0d6efd")
    cSecondary = "" & Nz(rsSettings("color_secondary"), "#6c757d")
    cSuccess = "" & Nz(rsSettings("color_success"), "#198754")
    cDanger = "" & Nz(rsSettings("color_danger"), "#dc3545")
    cWarning = "" & Nz(rsSettings("color_warning"), "#ffc107")
    cInfo = "" & Nz(rsSettings("color_info"), "#0dcaf0")
    cLight = "" & Nz(rsSettings("color_light"), "#f8f9fa")
    cDark = "" & Nz(rsSettings("color_dark"), "#212529")
    fBody = "" & Nz(rsSettings("font_body"), "Inter")
    fHeading = "" & Nz(rsSettings("font_heading"), "Inter")
    fButton = "" & Nz(rsSettings("font_button"), "Inter")
End If
rsSettings.Close
Set rsSettings = Nothing

slug = Trim(Request.QueryString("page"))

Set rsPage = pagesSvc.GetPublicBySlugOrHome(db, slug)
pageFound = (Not rsPage.EOF)
If pageFound Then
    pageTitle = "" & Nz(rsPage("title"), "")
    pageBody = "" & Nz(rsPage("body_html"), "")
Else
    pageTitle = "Page not found"
    pageBody = "<p>The requested page does not exist or is not published.</p>"
End If

Set rsMenu = pagesSvc.FrontMenu(db)
%>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><%=H(pageTitle)%> - <%=H(siteTitle)%></title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Roboto:wght@400;700&family=Open+Sans:wght@400;700&family=Lato:wght@400;700&family=Poppins:wght@400;600;700&family=Montserrat:wght@400;600;700&family=Raleway:wght@400;600;700&family=Nunito:wght@400;700&family=Merriweather:wght@400;700&family=Playfair+Display:wght@400;700&display=swap" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet" crossorigin="anonymous">
    <style>
    :root{
      --bs-primary:<%=H(cPrimary)%>;
      --bs-secondary:<%=H(cSecondary)%>;
      --bs-success:<%=H(cSuccess)%>;
      --bs-danger:<%=H(cDanger)%>;
      --bs-warning:<%=H(cWarning)%>;
      --bs-info:<%=H(cInfo)%>;
      --bs-light:<%=H(cLight)%>;
      --bs-dark:<%=H(cDark)%>;
    }
    body{
      font-family:'<%=H(fBody)%>',sans-serif;
      background:radial-gradient(1000px 400px at 10% -5%, rgba(14,165,233,.12), transparent),#f8fafc;
    }
    h1,h2,h3,h4,h5,h6{font-family:'<%=H(fHeading)%>',serif;}
    .btn{font-family:'<%=H(fButton)%>',sans-serif;}
    .content-wrap{background:#fff;border-radius:1rem;box-shadow:0 10px 30px rgba(15,23,42,.08);}
    </style>
</head>
<body>
<nav class="navbar navbar-expand-lg bg-body border-bottom">
  <div class="container">
    <a class="navbar-brand fw-bold" href="default.asp"><%=H(siteTitle)%></a>
    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#mainNav"><span class="navbar-toggler-icon"></span></button>
    <div class="collapse navbar-collapse" id="mainNav">
      <ul class="navbar-nav ms-auto mb-2 mb-lg-0">
        <% Do Until rsMenu.EOF %>
        <li class="nav-item"><a class="nav-link" href="default.asp?page=<%=Server.URLEncode(rsMenu("slug"))%>"><%=H(rsMenu("menu_label"))%></a></li>
        <% rsMenu.MoveNext : Loop %>
        <li class="nav-item"><a class="nav-link" href="admin.asp?m=login">Admin</a></li>
      </ul>
    </div>
  </div>
</nav>

<header class="py-5 border-bottom bg-white">
  <div class="container text-center">
    <h1 class="display-6 mb-2"><%=H(pageTitle)%></h1>
    <p class="text-muted mb-0"><%=H(siteSlogan)%></p>
  </div>
</header>

<main class="container py-4 py-lg-5">
  <div class="content-wrap p-4 p-lg-5">
    <% If pageFound Then %>
      <%=pageBody%>
    <% Else %>
      <div class="alert alert-warning mb-0"><%=pageBody%></div>
    <% End If %>
  </div>
</main>

<footer class="py-4 text-center text-muted">
  <small><%=H(siteTitle)%> - <%=H(siteSlogan)%></small>
</footer>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js" crossorigin="anonymous"></script>
</body>
</html>
<%
rsPage.Close
Set rsPage = Nothing
rsMenu.Close
Set rsMenu = Nothing
db.Close
Set db = Nothing
%>
