<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<!-- #include file="includes/includes.asp" -->
<%
Dim db, auth, usersSvc, pagesSvc, menuSvc, mediaSvc, settingsSvc
Dim m, action, flashMsg
Dim set_site_title, set_site_slogan
Dim set_color_primary, set_color_secondary, set_color_success, set_color_danger
Dim set_color_warning, set_color_info, set_color_light, set_color_dark
Dim set_font_body, set_font_heading, set_font_button

Set db = New cls_db
db.Open

Set auth = New cls_auth
Set usersSvc = New cls_user
Set pagesSvc = New cls_page
Set menuSvc = New cls_menu
Set mediaSvc = New cls_media
Set settingsSvc = New cls_settings

m = LCase(Trim("" & Request.QueryString("m")))
If m = "" Then m = "dashboard"
action = LCase(Trim("" & Request.Form("action")))
If action = "" Then action = LCase(Trim("" & Request.QueryString("action")))

If m = "logout" Then
    auth.Logout
    db.Close
    Set db = Nothing
    Response.Redirect "admin.asp?m=login"
    Response.End
End If

If m <> "login" Then
    auth.RequireLogin
End If

If IsPost() Then
    On Error Resume Next

    If m = "login" Then
        If auth.Login(db, Request.Form("email"), Request.Form("password")) Then
            db.Close
            Set db = Nothing
            On Error GoTo 0
            Response.Redirect "admin.asp?m=dashboard"
            Response.End
        Else
            SetFlash "Invalid login credentials."
            db.Close
            Set db = Nothing
            On Error GoTo 0
            Response.Redirect "admin.asp?m=login"
            Response.End
        End If
    End If

    If m = "users" Then
        auth.RequireAdmin
        If action = "create" Then
            If Trim(Request.Form("password")) = "" Then
                SetFlash "Password is required for new users."
            Else
                usersSvc.CreateUser db, Request.Form("name"), Request.Form("email"), Request.Form("password"), ToInt(Request.Form("is_admin"), 0)
                If Err.Number <> 0 Then
                    SetFlash "Could not create user. Email may already exist."
                    Err.Clear
                Else
                    SetFlash "User created."
                End If
            End If
        ElseIf action = "update" Then
            Dim updId, updNewIsAdmin, updOldIsAdmin, adminCountNow, resultAdminCount
            updId = ToInt(Request.Form("id"), 0)
            updNewIsAdmin = ToInt(Request.Form("is_admin"), 0)
            updOldIsAdmin = BoolInt(db.Scalar("SELECT is_admin FROM users WHERE id=" & updId, 0))
            adminCountNow = usersSvc.AdminCount(db)
            resultAdminCount = adminCountNow - updOldIsAdmin
            If updNewIsAdmin = 1 Then
                resultAdminCount = resultAdminCount + 1
            End If
            If resultAdminCount < 1 Then
                SetFlash "Cannot demote the last administrator."
            Else
                usersSvc.UpdateUser db, updId, Request.Form("name"), Request.Form("email"), updNewIsAdmin
                If Err.Number <> 0 Then
                    SetFlash "Could not update user."
                    Err.Clear
                Else
                    SetFlash "User updated."
                End If
            End If
        ElseIf action = "password" Then
            If Trim(Request.Form("password")) = "" Then
                SetFlash "Password cannot be empty."
            Else
                usersSvc.SetPassword db, ToInt(Request.Form("id"), 0), Request.Form("password")
                SetFlash "Password updated."
            End If
        ElseIf action = "delete" Then
            Dim delId, delIsAdmin
            delId = ToInt(Request.Form("id"), 0)
            delIsAdmin = BoolInt(db.Scalar("SELECT is_admin FROM users WHERE id=" & delId, 0))
            If delIsAdmin = 1 And usersSvc.AdminCount(db) <= 1 Then
                SetFlash "Cannot delete the last admin user."
            Else
                usersSvc.DeleteUser db, delId
                SetFlash "User deleted."
            End If
        End If
        db.Close
        Set db = Nothing
        On Error GoTo 0
        Response.Redirect "admin.asp?m=users"
        Response.End
    End If

    If m = "pages" Then
        If action = "save" Then
            pagesSvc.SavePage db, ToInt(Request.Form("id"), 0), Request.Form("title"), Request.Form("slug"), Request.Form("status"), Request.Form("body_html"), Request.Form("menu_title"), BoolInt(Request.Form("is_home"))
            If Err.Number <> 0 Then
                SetFlash "Could not save page. Slug may already exist."
                Err.Clear
            Else
                SetFlash "Page saved."
            End If
        ElseIf action = "delete" Then
            pagesSvc.DeletePage db, ToInt(Request.Form("id"), 0)
            SetFlash "Page deleted."
        ElseIf action = "set_home" Then
            pagesSvc.SetHome db, ToInt(Request.Form("id"), 0)
            SetFlash "Homepage updated."
        End If
        db.Close
        Set db = Nothing
        On Error GoTo 0
        Response.Redirect "admin.asp?m=pages"
        Response.End
    End If

    If m = "media" Then
        If action = "upload" Then
            Dim uploadObj
            Set uploadObj = Request.Files.Item("media_file")
            mediaSvc.SaveUpload db, uploadObj, ToInt(Session("uid"), 0)
            If Err.Number <> 0 Then
                SetFlash "Upload failed: " & Err.Description
                Err.Clear
            Else
                SetFlash "File uploaded."
            End If
            Set uploadObj = Nothing
        ElseIf action = "delete" Then
            mediaSvc.DeleteById db, ToInt(Request.Form("id"), 0)
            SetFlash "File deleted."
        End If
        db.Close
        Set db = Nothing
        On Error GoTo 0
        Response.Redirect "admin.asp?m=media"
        Response.End
    End If

    If m = "menu" Then
        If action = "move_up" Then
            menuSvc.MoveUp db, ToInt(Request.Form("id"), 0)
        ElseIf action = "move_down" Then
            menuSvc.MoveDown db, ToInt(Request.Form("id"), 0)
        ElseIf action = "save_csv" Then
            pagesSvc.SaveMenuOrder db, Request.Form("ids_csv")
        End If
        SetFlash "Menu updated."
        db.Close
        Set db = Nothing
        On Error GoTo 0
        Response.Redirect "admin.asp?m=menu"
        Response.End
    End If

    If m = "settings" Then
        auth.RequireAdmin
        If action = "branding" Then
            settingsSvc.SaveBranding db, Request.Form("site_title"), Request.Form("site_slogan")
            SetFlash "Branding saved."
        ElseIf action = "fonts" Then
            settingsSvc.SaveFonts db, Request.Form("font_body"), Request.Form("font_heading"), Request.Form("font_button")
            SetFlash "Fonts updated."
        ElseIf action = "palette_preset" Then
            settingsSvc.ApplyPreset db, Request.Form("palette_name")
            SetFlash "Palette preset applied."
        ElseIf action = "palette_custom" Then
            settingsSvc.SavePalette db, Request.Form("color_primary"), Request.Form("color_secondary"), Request.Form("color_success"), Request.Form("color_danger"), Request.Form("color_warning"), Request.Form("color_info"), Request.Form("color_light"), Request.Form("color_dark"), "custom"
            SetFlash "Custom palette saved."
        End If
        db.Close
        Set db = Nothing
        On Error GoTo 0
        Response.Redirect "admin.asp?m=settings"
        Response.End
    End If

    On Error GoTo 0
End If

Dim rsSettings
Set rsSettings = settingsSvc.GetOne(db)
If rsSettings.EOF Then
    set_site_title = "ASP4 CMS"
    set_site_slogan = ""
    set_color_primary = "#0d6efd"
    set_color_secondary = "#6c757d"
    set_color_success = "#198754"
    set_color_danger = "#dc3545"
    set_color_warning = "#ffc107"
    set_color_info = "#0dcaf0"
    set_color_light = "#f8f9fa"
    set_color_dark = "#212529"
    set_font_body = "Inter"
    set_font_heading = "Inter"
    set_font_button = "Inter"
Else
    set_site_title = "" & Nz(rsSettings("site_title"), "ASP4 CMS")
    set_site_slogan = "" & Nz(rsSettings("site_slogan"), "")
    set_color_primary = "" & Nz(rsSettings("color_primary"), "#0d6efd")
    set_color_secondary = "" & Nz(rsSettings("color_secondary"), "#6c757d")
    set_color_success = "" & Nz(rsSettings("color_success"), "#198754")
    set_color_danger = "" & Nz(rsSettings("color_danger"), "#dc3545")
    set_color_warning = "" & Nz(rsSettings("color_warning"), "#ffc107")
    set_color_info = "" & Nz(rsSettings("color_info"), "#0dcaf0")
    set_color_light = "" & Nz(rsSettings("color_light"), "#f8f9fa")
    set_color_dark = "" & Nz(rsSettings("color_dark"), "#212529")
    set_font_body = "" & Nz(rsSettings("font_body"), "Inter")
    set_font_heading = "" & Nz(rsSettings("font_heading"), "Inter")
    set_font_button = "" & Nz(rsSettings("font_button"), "Inter")
End If
rsSettings.Close
Set rsSettings = Nothing

flashMsg = GetFlash()
%>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><%=H(set_site_title)%> - Admin</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Roboto:wght@400;700&family=Open+Sans:wght@400;700&family=Lato:wght@400;700&family=Poppins:wght@400;600;700&family=Montserrat:wght@400;600;700&family=Raleway:wght@400;600;700&family=Nunito:wght@400;700&family=Merriweather:wght@400;700&family=Playfair+Display:wght@400;700&display=swap" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet" crossorigin="anonymous">
    <link href="https://cdn.jsdelivr.net/npm/quill@2.0.2/dist/quill.snow.css" rel="stylesheet">
    <style>
    :root{
      --bs-primary:<%=H(set_color_primary)%>;
      --bs-secondary:<%=H(set_color_secondary)%>;
      --bs-success:<%=H(set_color_success)%>;
      --bs-danger:<%=H(set_color_danger)%>;
      --bs-warning:<%=H(set_color_warning)%>;
      --bs-info:<%=H(set_color_info)%>;
      --bs-light:<%=H(set_color_light)%>;
      --bs-dark:<%=H(set_color_dark)%>;
    }
    body{font-family:'<%=H(set_font_body)%>',sans-serif;background:#f4f7fb;}
    h1,h2,h3,h4,h5,h6{font-family:'<%=H(set_font_heading)%>',serif;}
    .btn{font-family:'<%=H(set_font_button)%>',sans-serif;}
    .sidebar-link{display:block;padding:.5rem .75rem;border-radius:.5rem;color:#334155;text-decoration:none}
    .sidebar-link.active,.sidebar-link:hover{background:rgba(13,110,253,.1);color:var(--bs-primary)}
    #editor-container{height:300px}
    .users-table{min-width:1100px;}
    </style>
</head>
<body>
<% If m = "login" Then %>
<main class="container py-5" style="max-width:520px;">
  <div class="card shadow-sm border-0">
    <div class="card-body p-4">
      <h1 class="h4 mb-3">Admin Login</h1>
      <% If flashMsg <> "" Then %><div class="alert alert-danger"><%=H(flashMsg)%></div><% End If %>
      <form method="post" action="admin.asp?m=login">
        <input type="hidden" name="action" value="login">
        <div class="mb-3"><label class="form-label">Email</label><input class="form-control" type="email" name="email" required></div>
        <div class="mb-3"><label class="form-label">Password</label><input class="form-control" type="password" name="password" required></div>
        <button class="btn btn-primary w-100" type="submit">Sign In</button>
      </form>
      <p class="text-muted small mt-3 mb-0">Use your current admin credentials.</p>
    </div>
  </div>
</main>
<% Else %>
<nav class="navbar navbar-expand-lg bg-body border-bottom">
  <div class="container-fluid">
    <span class="navbar-brand"><%=H(set_site_title)%> Admin</span>
    <div class="d-flex gap-2 align-items-center">
      <a class="btn btn-sm btn-outline-primary" href="default.asp" target="_blank">View Site</a>
      <a class="btn btn-sm btn-outline-danger" href="admin.asp?m=logout">Logout</a>
    </div>
  </div>
</nav>

<main class="container-fluid py-3">
  <div class="row g-3">
    <div class="col-12 col-lg-2">
      <div class="card border-0 shadow-sm"><div class="card-body">
        <a class="sidebar-link <%If m="dashboard" Then Response.Write("active")%>" href="admin.asp?m=dashboard">Dashboard</a>
        <a class="sidebar-link <%If m="pages" Then Response.Write("active")%>" href="admin.asp?m=pages">Pages</a>
        <a class="sidebar-link <%If m="menu" Then Response.Write("active")%>" href="admin.asp?m=menu">Menu Editor</a>
        <a class="sidebar-link <%If m="media" Then Response.Write("active")%>" href="admin.asp?m=media">Media</a>
        <a class="sidebar-link <%If m="users" Then Response.Write("active")%>" href="admin.asp?m=users">Users</a>
        <a class="sidebar-link <%If m="settings" Then Response.Write("active")%>" href="admin.asp?m=settings">Admin Area</a>
      </div></div>
    </div>
    <div class="col-12 col-lg-10">
      <% If flashMsg <> "" Then %><div class="alert alert-info"><%=H(flashMsg)%></div><% End If %>

      <% If m = "dashboard" Then %>
      <div class="card border-0 shadow-sm"><div class="card-body">
        <h1 class="h4">Welcome, <%=H(Session("name"))%></h1>
        <p class="text-muted mb-0">Use the left menu to manage pages, media, users, menu order, and site styling.</p>
      </div></div>

      <% ElseIf m = "users" Then %>
      <% auth.RequireAdmin %>
      <div class="card border-0 shadow-sm mb-3"><div class="card-body">
        <h2 class="h5">Add User</h2>
        <form class="row g-2" method="post" action="admin.asp?m=users">
          <input type="hidden" name="action" value="create">
          <div class="col-md-3"><input class="form-control" name="name" placeholder="Name" required></div>
          <div class="col-md-3"><input class="form-control" name="email" type="email" placeholder="Email" required></div>
          <div class="col-md-3"><input class="form-control" name="password" type="password" placeholder="Password" required></div>
          <div class="col-md-2"><select class="form-select" name="is_admin"><option value="0">Editor</option><option value="1">Admin</option></select></div>
          <div class="col-md-1 d-grid"><button class="btn btn-primary" type="submit">Add</button></div>
        </form>
      </div></div>

      <div class="card border-0 shadow-sm"><div class="table-responsive">
        <table class="table align-middle mb-0 users-table">
          <thead><tr><th>ID</th><th>Name</th><th>Email</th><th>Role</th><th style="width:420px">Actions</th></tr></thead>
          <tbody>
            <%
            Dim rsUsers, adminCountUI, rowIsAdmin
            adminCountUI = usersSvc.AdminCount(db)
            Set rsUsers = usersSvc.ListAll(db)
            Do Until rsUsers.EOF
              rowIsAdmin = IsTruthy(Nz(rsUsers("is_admin"), 0))
            %>
            <tr>
              <td><%=rsUsers("id")%></td>
              <td><%=H(rsUsers("name"))%></td>
              <td><%=H(rsUsers("email"))%></td>
              <td><%If rowIsAdmin Then Response.Write("Admin") Else Response.Write("Editor") End If%></td>
              <td>
                <form class="d-flex gap-2 mb-2" method="post" action="admin.asp?m=users">
                  <input type="hidden" name="action" value="update"><input type="hidden" name="id" value="<%=rsUsers("id")%>">
                  <input class="form-control form-control-sm" name="name" value="<%=H(rsUsers("name"))%>">
                  <input class="form-control form-control-sm" name="email" value="<%=H(rsUsers("email"))%>">
                  <select class="form-select form-select-sm" name="is_admin"><option value="0" <%If Not rowIsAdmin Then Response.Write("selected")%> <%If rowIsAdmin And adminCountUI<=1 Then Response.Write("disabled")%>>Editor</option><option value="1" <%If rowIsAdmin Then Response.Write("selected")%>>Admin</option></select>
                  <button class="btn btn-sm btn-outline-primary" type="submit">Save</button>
                </form>
                <form class="d-flex gap-2 mb-2" method="post" action="admin.asp?m=users">
                  <input type="hidden" name="action" value="password">
                  <input type="hidden" name="id" value="<%=rsUsers("id")%>">
                  <input class="form-control form-control-sm" name="password" type="password" placeholder="New password">
                  <button class="btn btn-sm btn-outline-secondary" type="submit">Password</button>
                </form>
                <form class="d-flex gap-2" method="post" action="admin.asp?m=users">
                  <input type="hidden" name="id" value="<%=rsUsers("id")%>">
                  <% If rowIsAdmin And adminCountUI<=1 Then %>
                    <button class="btn btn-sm btn-outline-danger" type="button" disabled title="Last admin cannot be deleted">Delete</button>
                  <% Else %>
                    <button class="btn btn-sm btn-outline-danger" name="action" value="delete" type="submit" onclick="return confirm('Delete this user?')">Delete</button>
                  <% End If %>
                </form>
              </td>
            </tr>
            <% rsUsers.MoveNext: Loop
            rsUsers.Close: Set rsUsers = Nothing %>
          </tbody>
        </table>
      </div></div>

      <% ElseIf m = "pages" Then %>
      <%
      Dim editId, pageTitle, pageSlug, pageStatus, pageBody, pageMenuTitle, pageIsHome, rsEdit
      editId = ToInt(Request.QueryString("id"), 0)
      pageTitle = "": pageSlug = "": pageStatus = "draft": pageBody = "": pageMenuTitle = "": pageIsHome = 0
      If editId > 0 Then
          Set rsEdit = pagesSvc.GetById(db, editId)
          If Not rsEdit.EOF Then
              pageTitle = "" & Nz(rsEdit("title"), "")
              pageSlug = "" & Nz(rsEdit("slug"), "")
              pageStatus = "" & Nz(rsEdit("status"), "draft")
              pageBody = "" & Nz(rsEdit("body_html"), "")
              pageMenuTitle = "" & Nz(rsEdit("menu_title"), "")
              pageIsHome = BoolInt(Nz(rsEdit("is_home"), 0))
          End If
          rsEdit.Close
          Set rsEdit = Nothing
      End If
      %>
      <div class="card border-0 shadow-sm mb-3"><div class="card-body">
        <h2 class="h5"><%If editId>0 Then Response.Write("Edit Page") Else Response.Write("Create Page") End If%></h2>
        <form method="post" action="admin.asp?m=pages" onsubmit="document.getElementById('body_html').value = quill.root.innerHTML; return true;">
          <input type="hidden" name="action" value="save">
          <input type="hidden" name="id" value="<%=editId%>">
          <input type="hidden" id="body_html" name="body_html">
          <div class="row g-3">
            <div class="col-md-4"><label class="form-label">Title</label><input class="form-control" name="title" value="<%=H(pageTitle)%>" required></div>
            <div class="col-md-3"><label class="form-label">Slug</label><input class="form-control" name="slug" value="<%=H(pageSlug)%>" placeholder="auto if empty"></div>
            <div class="col-md-2"><label class="form-label">Status</label><select class="form-select" name="status"><option value="draft" <%If pageStatus="draft" Then Response.Write("selected")%>>Draft</option><option value="published" <%If pageStatus="published" Then Response.Write("selected")%>>Published</option></select></div>
            <div class="col-md-3"><label class="form-label">Menu Entry</label><input class="form-control" name="menu_title" value="<%=H(pageMenuTitle)%>" placeholder="defaults to title"></div>
            <div class="col-12"><div class="form-check"><input class="form-check-input" type="checkbox" id="is_home" name="is_home" value="1" <%If pageIsHome=1 Then Response.Write("checked")%>><label class="form-check-label" for="is_home">Set as homepage</label></div></div>
            <div class="col-12"><label class="form-label">Body</label><div id="editor-container"><%=pageBody%></div></div>
            <div class="col-12 d-flex gap-2"><button class="btn btn-primary" type="submit">Save Page</button><a class="btn btn-outline-secondary" href="admin.asp?m=pages">Reset</a></div>
          </div>
        </form>
      </div></div>

      <div class="card border-0 shadow-sm"><div class="table-responsive">
        <table class="table mb-0 align-middle"><thead><tr><th>Title</th><th>Slug</th><th>Status</th><th>Home</th><th>Menu Order</th><th>Actions</th></tr></thead><tbody>
        <%
        Dim rsPages
        Set rsPages = pagesSvc.ListAll(db)
        Do Until rsPages.EOF
        %>
        <tr>
          <td><%=H(rsPages("title"))%></td>
          <td><code><%=H(rsPages("slug"))%></code></td>
          <td><%=H(rsPages("status"))%></td>
          <td><%If IsTruthy(Nz(rsPages("is_home"), 0)) Then Response.Write("Yes") Else Response.Write("No") End If%></td>
          <td><%=H(Nz(rsPages("menu_order"), ""))%></td>
          <td class="d-flex gap-2">
            <a class="btn btn-sm btn-outline-primary" href="admin.asp?m=pages&id=<%=rsPages("id")%>">Edit</a>
            <form method="post" action="admin.asp?m=pages"><input type="hidden" name="action" value="set_home"><input type="hidden" name="id" value="<%=rsPages("id")%>"><button class="btn btn-sm btn-outline-secondary" type="submit">Set Home</button></form>
            <form method="post" action="admin.asp?m=pages"><input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="<%=rsPages("id")%>"><button class="btn btn-sm btn-outline-danger" type="submit" onclick="return confirm('Delete this page?')">Delete</button></form>
          </td>
        </tr>
        <% rsPages.MoveNext: Loop
        rsPages.Close: Set rsPages = Nothing %>
        </tbody></table>
      </div></div>

      <% ElseIf m = "menu" Then %>
      <% menuSvc.NormalizeOrders db %>
      <div class="card border-0 shadow-sm"><div class="card-body">
        <h2 class="h5">Menu Editor</h2>
        <p class="text-muted small">Use Up/Down to rearrange published pages.</p>
        <div class="table-responsive">
          <table class="table align-middle"><thead><tr><th>Order</th><th>Title</th><th>Slug</th><th>Status</th><th>Move</th></tr></thead><tbody>
          <%
          Dim rsMenu
          Set rsMenu = menuSvc.ListForEditor(db)
          Do Until rsMenu.EOF
          %>
          <tr>
            <td><%=H(Nz(rsMenu("menu_order"), ""))%></td>
            <td><%=H(rsMenu("title"))%></td>
            <td><code><%=H(rsMenu("slug"))%></code></td>
            <td><%=H(rsMenu("status"))%></td>
            <td class="d-flex gap-2">
              <form method="post" action="admin.asp?m=menu"><input type="hidden" name="action" value="move_up"><input type="hidden" name="id" value="<%=rsMenu("id")%>"><button class="btn btn-sm btn-outline-secondary" type="submit">Up</button></form>
              <form method="post" action="admin.asp?m=menu"><input type="hidden" name="action" value="move_down"><input type="hidden" name="id" value="<%=rsMenu("id")%>"><button class="btn btn-sm btn-outline-secondary" type="submit">Down</button></form>
            </td>
          </tr>
          <% rsMenu.MoveNext: Loop
          rsMenu.Close: Set rsMenu = Nothing %>
          </tbody></table>
        </div>
      </div></div>

      <% ElseIf m = "media" Then %>
      <div class="card border-0 shadow-sm mb-3"><div class="card-body">
        <h2 class="h5">Upload File</h2>
        <form method="post" action="admin.asp?m=media" enctype="multipart/form-data">
          <input type="hidden" name="action" value="upload">
          <div class="row g-2 align-items-end">
            <div class="col-md-8"><label class="form-label">File (max 5MB)</label><input class="form-control" type="file" name="media_file" required></div>
            <div class="col-md-4 d-grid"><button class="btn btn-primary" type="submit">Upload</button></div>
          </div>
        </form>
      </div></div>
      <div class="card border-0 shadow-sm"><div class="table-responsive"><table class="table align-middle mb-0"><thead><tr><th>Thumb</th><th>Name</th><th>Copy URL</th><th>Type</th><th>Size</th><th>Dimensions</th><th>Date</th><th>Action</th></tr></thead><tbody>
      <%
      Dim rsMedia, relPath, relUrl, shortUrl, ext, isImage, inputId
      Set rsMedia = mediaSvc.ListAll(db)
      Do Until rsMedia.EOF
        relPath = NormalizeRelPath("" & Nz(rsMedia("rel_path"), ""))
        relUrl = AppUrl(relPath)
        shortUrl = relPath
        ext = LCase("" & Nz(rsMedia("ext"), ""))
        isImage = (ext = "jpg" Or ext = "jpeg" Or ext = "png" Or ext = "gif" Or ext = "webp")
        inputId = "media_url_" & H(Nz(rsMedia("id"), "0"))
      %>
      <tr>
        <td>
          <% If isImage Then %>
            <a href="<%=H(relUrl)%>" target="_blank"><img src="<%=H(relUrl)%>" alt="" style="width:72px;height:72px;object-fit:cover;border-radius:.5rem;border:1px solid #e2e8f0;"></a>
          <% Else %>
            <span class="text-muted">-</span>
          <% End If %>
        </td>
        <td><a href="<%=H(relUrl)%>" target="_blank"><%=H(rsMedia("original_name"))%></a></td>
        <td>
          <div class="input-group input-group-sm" style="min-width:280px;">
            <input id="<%=inputId%>" class="form-control" readonly value="<%=H(shortUrl)%>">
            <button class="btn btn-outline-secondary" type="button" onclick="copyMediaUrl('<%=inputId%>')">Copy</button>
          </div>
        </td>
        <td><%=H(rsMedia("mime_type"))%></td>
        <td><%=H(Nz(rsMedia("size_bytes"), "0"))%> bytes</td>
        <td><% If IsNull(rsMedia("width")) Then Response.Write("-") Else Response.Write(H(Nz(rsMedia("width"), "")) & " x " & H(Nz(rsMedia("height"), ""))) End If %></td>
        <td><%=H(rsMedia("created_at"))%></td>
        <td><form method="post" action="admin.asp?m=media"><input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="<%=rsMedia("id")%>"><button class="btn btn-sm btn-outline-danger" type="submit" onclick="return confirm('Delete this file?')">Delete</button></form></td>
      </tr>
      <% rsMedia.MoveNext: Loop
      rsMedia.Close: Set rsMedia = Nothing %>
      </tbody></table></div></div>

      <% ElseIf m = "settings" Then %>
      <% auth.RequireAdmin %>
      <div class="card border-0 shadow-sm mb-3"><div class="card-body">
        <h2 class="h5">Site Branding</h2>
        <form method="post" action="admin.asp?m=settings" class="row g-2">
          <input type="hidden" name="action" value="branding">
          <div class="col-md-6"><label class="form-label">Site Title</label><input class="form-control" name="site_title" value="<%=H(set_site_title)%>"></div>
          <div class="col-md-6"><label class="form-label">Site Slogan</label><input class="form-control" name="site_slogan" value="<%=H(set_site_slogan)%>"></div>
          <div class="col-12"><button class="btn btn-primary" type="submit">Save Branding</button></div>
        </form>
      </div></div>

      <div class="card border-0 shadow-sm mb-3"><div class="card-body">
        <h2 class="h5">Fonts</h2>
        <form method="post" action="admin.asp?m=settings" class="row g-2">
          <input type="hidden" name="action" value="fonts">
          <%
          Dim fonts, fi, f
          fonts = Array("Inter","Roboto","Open Sans","Lato","Poppins","Montserrat","Raleway","Nunito","Merriweather","Playfair Display")
          %>
          <div class="col-md-4"><label class="form-label">Body</label><select class="form-select" name="font_body"><% For fi = 0 To UBound(fonts) : f = fonts(fi) %><option value="<%=H(f)%>" <%If f=set_font_body Then Response.Write("selected") End If%>><%=H(f)%></option><% Next %></select></div>
          <div class="col-md-4"><label class="form-label">Headings</label><select class="form-select" name="font_heading"><% For fi = 0 To UBound(fonts) : f = fonts(fi) %><option value="<%=H(f)%>" <%If f=set_font_heading Then Response.Write("selected") End If%>><%=H(f)%></option><% Next %></select></div>
          <div class="col-md-4"><label class="form-label">Buttons</label><select class="form-select" name="font_button"><% For fi = 0 To UBound(fonts) : f = fonts(fi) %><option value="<%=H(f)%>" <%If f=set_font_button Then Response.Write("selected") End If%>><%=H(f)%></option><% Next %></select></div>
          <div class="col-12"><button class="btn btn-primary" type="submit">Save Fonts</button></div>
        </form>
      </div></div>

      <div class="card border-0 shadow-sm"><div class="card-body">
        <h2 class="h5">Palette</h2>
        <form method="post" action="admin.asp?m=settings" class="row g-2 mb-3">
          <input type="hidden" name="action" value="palette_preset">
          <div class="col-md-4"><select class="form-select" name="palette_name"><option value="ocean">Ocean</option><option value="forest">Forest</option><option value="sunset">Sunset</option><option value="slate">Slate</option></select></div>
          <div class="col-md-2 d-grid"><button class="btn btn-outline-primary" type="submit">Apply Preset</button></div>
        </form>
        <form method="post" action="admin.asp?m=settings" class="row g-2">
          <input type="hidden" name="action" value="palette_custom">
          <div class="col-md-3"><label class="form-label">Primary</label><input type="color" class="form-control form-control-color" name="color_primary" value="<%=H(set_color_primary)%>"></div>
          <div class="col-md-3"><label class="form-label">Secondary</label><input type="color" class="form-control form-control-color" name="color_secondary" value="<%=H(set_color_secondary)%>"></div>
          <div class="col-md-3"><label class="form-label">Success</label><input type="color" class="form-control form-control-color" name="color_success" value="<%=H(set_color_success)%>"></div>
          <div class="col-md-3"><label class="form-label">Danger</label><input type="color" class="form-control form-control-color" name="color_danger" value="<%=H(set_color_danger)%>"></div>
          <div class="col-md-3"><label class="form-label">Warning</label><input type="color" class="form-control form-control-color" name="color_warning" value="<%=H(set_color_warning)%>"></div>
          <div class="col-md-3"><label class="form-label">Info</label><input type="color" class="form-control form-control-color" name="color_info" value="<%=H(set_color_info)%>"></div>
          <div class="col-md-3"><label class="form-label">Light</label><input type="color" class="form-control form-control-color" name="color_light" value="<%=H(set_color_light)%>"></div>
          <div class="col-md-3"><label class="form-label">Dark</label><input type="color" class="form-control form-control-color" name="color_dark" value="<%=H(set_color_dark)%>"></div>
          <div class="col-12"><button class="btn btn-primary" type="submit">Save Custom Palette</button></div>
        </form>
      </div></div>

      <% Else %>
      <div class="alert alert-warning">Unknown module.</div>
      <% End If %>
    </div>
  </div>
</main>
<% End If %>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js" crossorigin="anonymous"></script>
<script src="https://cdn.jsdelivr.net/npm/quill@2.0.2/dist/quill.js"></script>
<script>
if (document.getElementById('editor-container')) {
  const fullToolbarOptions = [
    [{ 'font': [] }],
    [{ 'header': [1, 2, 3, 4, 5, 6, false] }],
    [{ 'size': ['small', false, 'large', 'huge'] }],
    ['bold', 'italic', 'underline', 'strike'],
    ['blockquote', 'code-block'],
    [{ 'color': [] }, { 'background': [] }],
    [{ 'list': 'ordered'}, { 'list': 'bullet' }, { 'list': 'check' }],
    [{ 'script': 'sub'}, { 'script': 'super' }],
    [{ 'indent': '-1'}, { 'indent': '+1' }],
    [{ 'align': [] }],
    ['link', 'image', 'video'],
    ['clean']
  ];
  window.quill = new Quill('#editor-container', {
    modules: {
      toolbar: {
        container: fullToolbarOptions,
        handlers: {
          image: function () {
            var url = window.prompt('Paste image URL (example: uploads/my-image.jpg)', 'uploads/');
            if (!url) return;
            var range = this.quill.getSelection(true);
            this.quill.insertEmbed(range.index, 'image', url, 'user');
            this.quill.setSelection(range.index + 1, 0);
          },
          video: function () {
            var url = window.prompt('Paste video URL', '');
            if (!url) return;
            var range = this.quill.getSelection(true);
            this.quill.insertEmbed(range.index, 'video', url, 'user');
            this.quill.setSelection(range.index + 1, 0);
          }
        }
      }
    },
    theme: 'snow'
  });
}

function copyMediaUrl(inputId) {
  var el = document.getElementById(inputId);
  if (!el) return;
  el.select();
  el.setSelectionRange(0, 99999);
  try {
    navigator.clipboard.writeText(el.value);
  } catch (e) {
    document.execCommand('copy');
  }
}
</script>
</body>
</html>
<%
db.Close
Set db = Nothing
%>
