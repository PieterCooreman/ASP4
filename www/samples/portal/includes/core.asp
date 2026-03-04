<%
Function PortalBasePath()
    Dim s, l, p
    s = "" & Request.ServerVariables("SCRIPT_NAME")
    l = LCase(s)

    p = InStr(l, "/app/")
    If p > 0 Then
        PortalBasePath = Left(s, p - 1)
        Exit Function
    End If

    p = InStr(l, "/admin/")
    If p > 0 Then
        PortalBasePath = Left(s, p - 1)
        Exit Function
    End If

    p = InStrRev(s, "/")
    If p > 1 Then
        PortalBasePath = Left(s, p - 1)
    Else
        PortalBasePath = ""
    End If
End Function

Function PortalUrl(relPath)
    Dim p
    p = Trim("" & relPath)
    If Left(p, 1) = "/" Then p = Mid(p, 2)
    PortalUrl = PortalBasePath() & "/" & p
End Function

Function PortalHomeUrl()
    If PortalHasApp("briefing") Then
        PortalHomeUrl = PortalUrl("app/briefing/index.asp")
    Else
        PortalHomeUrl = PortalUrl("dashboard.asp")
    End If
End Function

Function H(v)
    H = Server.HTMLEncode("" & v)
End Function

Function PortalNormalizeEmail(v)
    PortalNormalizeEmail = LCase(Trim("" & v))
End Function

Function PortalLooksLikeEmail(v)
    Dim s, atPos, dotPos
    s = PortalNormalizeEmail(v)
    atPos = InStr(1, s, "@", 1)
    dotPos = InStrRev(s, ".")
    PortalLooksLikeEmail = (atPos > 1 And dotPos > atPos + 1 And dotPos < Len(s))
End Function

Function PortalIsStrongPassword(pw)
    Dim s, i, ch, hasUpper, hasLower, hasDigit
    s = "" & pw
    hasUpper = False
    hasLower = False
    hasDigit = False
    If Len(s) < 10 Then
        PortalIsStrongPassword = False
        Exit Function
    End If
    For i = 1 To Len(s)
        ch = Mid(s, i, 1)
        If ch >= "A" And ch <= "Z" Then hasUpper = True
        If ch >= "a" And ch <= "z" Then hasLower = True
        If ch >= "0" And ch <= "9" Then hasDigit = True
    Next
    PortalIsStrongPassword = (hasUpper And hasLower And hasDigit)
End Function

Function PortalCleanName(v, fallback)
    Dim s
    s = Trim("" & v)
    If s = "" Then s = fallback
    If Len(s) > 80 Then s = Left(s, 80)
    PortalCleanName = s
End Function

Function PortalValidRole(roleName)
    Dim r
    r = LCase(Trim("" & roleName))
    PortalValidRole = (r = "end_user" Or r = "tenant_admin" Or r = "platform_admin")
End Function

Function PortalValidStatus(statusName)
    Dim s
    s = LCase(Trim("" & statusName))
    PortalValidStatus = (s = "active" Or s = "suspended" Or s = "invited")
End Function

Function PortalValidColorHex(v)
    Dim s, i, ch
    s = Trim("" & v)
    If Len(s) <> 7 Then
        PortalValidColorHex = False
        Exit Function
    End If
    If Left(s, 1) <> "#" Then
        PortalValidColorHex = False
        Exit Function
    End If
    For i = 2 To 7
        ch = UCase(Mid(s, i, 1))
        If InStr(1, "0123456789ABCDEF", ch, 1) = 0 Then
            PortalValidColorHex = False
            Exit Function
        End If
    Next
    PortalValidColorHex = True
End Function

Function SqlQ(v)
    If IsNull(v) Then
        SqlQ = "NULL"
    Else
        SqlQ = "'" & Replace(CStr(v), "'", "''") & "'"
    End If
End Function

Function SqlN(v)
    If IsNumeric(v) Then
        SqlN = CLng(v)
    Else
        SqlN = 0
    End If
End Function

Function PortalDbPath()
    PortalDbPath = Server.MapPath(PortalUrl("data/portal.db"))
End Function

Sub PortalEnsureStorage()
    Dim fso, folderPath, dbPath, stream
    Set fso = Server.CreateObject("Scripting.FileSystemObject")
    folderPath = Server.MapPath(PortalUrl("data"))
    dbPath = PortalDbPath()

    If Not fso.FolderExists(folderPath) Then
        fso.CreateFolder folderPath
    End If
    If Not fso.FileExists(dbPath) Then
        Set stream = fso.CreateTextFile(dbPath, True)
        stream.Write ""
        stream.Close
        Set stream = Nothing
    End If
    Set fso = Nothing
End Sub

Function PortalOpen()
    Dim conn
    Call PortalEnsureStorage()
    Set conn = Server.CreateObject("ADODB.Connection")
    conn.Open "Provider=SQLite;Data Source=" & PortalDbPath()
    Set PortalOpen = conn
End Function

Sub PortalExec(conn, sql)
    conn.Execute sql
End Sub

Function PortalScalar(conn, sql, defaultValue)
    Dim rs
    On Error Resume Next
    Set rs = conn.Execute(sql)
    If Err.Number <> 0 Then
        PortalScalar = defaultValue
        Err.Clear
        Exit Function
    End If
    On Error GoTo 0
    If rs.EOF Then
        PortalScalar = defaultValue
    Else
        PortalScalar = rs(0)
    End If
    rs.Close
    Set rs = Nothing
End Function

Sub PortalInit(conn)
    Call PortalExec(conn, "CREATE TABLE IF NOT EXISTS tenants (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, tenant_type TEXT NOT NULL DEFAULT 'company', primary_color TEXT NOT NULL DEFAULT '#2f6fed', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    Call PortalExec(conn, "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, name TEXT NOT NULL, email TEXT NOT NULL, password_hash TEXT, role TEXT NOT NULL DEFAULT 'end_user', status TEXT NOT NULL DEFAULT 'active', timezone TEXT NOT NULL DEFAULT 'UTC', follow_up_days INTEGER NOT NULL DEFAULT 21, last_login_at TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(tenant_id,email))")
    Call PortalExec(conn, "CREATE TABLE IF NOT EXISTS app_catalog (app_id TEXT PRIMARY KEY, label TEXT NOT NULL, description TEXT NOT NULL, icon TEXT NOT NULL, route TEXT NOT NULL, tenant_scope TEXT NOT NULL DEFAULT 'all', is_enabled INTEGER NOT NULL DEFAULT 1, sort_order INTEGER NOT NULL DEFAULT 0)")
    Call PortalExec(conn, "CREATE TABLE IF NOT EXISTS tenant_apps (id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, app_id TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, UNIQUE(tenant_id,app_id))")
    Call PortalExec(conn, "CREATE TABLE IF NOT EXISTS user_apps (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, app_id TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, UNIQUE(user_id,app_id))")
    Call PortalExec(conn, "CREATE TABLE IF NOT EXISTS user_app_usage (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, app_id TEXT NOT NULL, last_used_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id,app_id))")

    Call PortalExec(conn, "CREATE TABLE IF NOT EXISTS invitations (id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, email TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'end_user', token TEXT NOT NULL UNIQUE, expires_at TEXT NOT NULL, accepted_at TEXT, created_by INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")

    Call PortalExec(conn, "CREATE TABLE IF NOT EXISTS todo_lists (id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, user_id INTEGER NOT NULL, name TEXT NOT NULL, is_shared INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    Call PortalExec(conn, "CREATE TABLE IF NOT EXISTS todo_tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, user_id INTEGER NOT NULL, list_id INTEGER NOT NULL, title TEXT NOT NULL, description TEXT, due_date TEXT, priority TEXT NOT NULL DEFAULT 'None', status TEXT NOT NULL DEFAULT 'Open', position INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")

    Call PortalExec(conn, "CREATE TABLE IF NOT EXISTS idea_collections (id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, user_id INTEGER NOT NULL, name TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    Call PortalExec(conn, "CREATE TABLE IF NOT EXISTS ideas (id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, user_id INTEGER NOT NULL, collection_id INTEGER NOT NULL, title TEXT NOT NULL, body TEXT, tags TEXT, status TEXT NOT NULL DEFAULT 'Raw', is_pinned INTEGER NOT NULL DEFAULT 0, revisit_on TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")

    Call PortalExec(conn, "CREATE TABLE IF NOT EXISTS notes_pages (id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, user_id INTEGER NOT NULL, parent_id INTEGER, title TEXT NOT NULL, body TEXT, is_shared INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    Call PortalExec(conn, "CREATE TABLE IF NOT EXISTS contacts_people (id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, user_id INTEGER NOT NULL, full_name TEXT NOT NULL, email TEXT, phone TEXT, company TEXT, tags TEXT, notes TEXT, last_interaction TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    Call PortalExec(conn, "CREATE TABLE IF NOT EXISTS bookmarks_items (id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, user_id INTEGER NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL, tags TEXT, folder_name TEXT, is_read INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    Call PortalExec(conn, "CREATE TABLE IF NOT EXISTS habits_habits (id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, user_id INTEGER NOT NULL, title TEXT NOT NULL, cadence TEXT NOT NULL DEFAULT 'daily', goal_per_period INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    Call PortalExec(conn, "CREATE TABLE IF NOT EXISTS habits_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, habit_id INTEGER NOT NULL, user_id INTEGER NOT NULL, log_date TEXT NOT NULL, value INTEGER NOT NULL DEFAULT 1, UNIQUE(habit_id,user_id,log_date))")
    Call PortalExec(conn, "CREATE TABLE IF NOT EXISTS vault_snippets (id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, user_id INTEGER NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'text', tags TEXT, is_shared INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    Call PortalExec(conn, "CREATE TABLE IF NOT EXISTS wins_journal (id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, user_id INTEGER NOT NULL, win_date TEXT NOT NULL, title TEXT NOT NULL, details TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id,win_date,title))")
    Call PortalExec(conn, "CREATE TABLE IF NOT EXISTS tenant_notices (id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, message TEXT NOT NULL, active_from TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, active_until TEXT, created_by INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    Call PortalExec(conn, "CREATE TABLE IF NOT EXISTS briefing_snooze (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, item_type TEXT NOT NULL, item_id INTEGER NOT NULL, snooze_until TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id,item_type,item_id))")
    Call PortalExec(conn, "CREATE TABLE IF NOT EXISTS briefing_focus (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, focus_date TEXT NOT NULL, task_id INTEGER NOT NULL, title_snapshot TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id,focus_date))")

    On Error Resume Next
    Call PortalExec(conn, "ALTER TABLE users ADD COLUMN timezone TEXT NOT NULL DEFAULT 'UTC'")
    Call PortalExec(conn, "ALTER TABLE users ADD COLUMN follow_up_days INTEGER NOT NULL DEFAULT 21")
    Call PortalExec(conn, "ALTER TABLE app_catalog ADD COLUMN tenant_scope TEXT NOT NULL DEFAULT 'all'")
    Call PortalExec(conn, "ALTER TABLE ideas ADD COLUMN revisit_on TEXT")
    Err.Clear
    On Error GoTo 0

    Call PortalExec(conn, "INSERT OR IGNORE INTO app_catalog(app_id,label,description,icon,route,tenant_scope,sort_order) VALUES('briefing','Today Briefing','Daily priorities across all your apps','bi-sunrise','app/briefing/index.asp','all',0)")
    Call PortalExec(conn, "INSERT OR IGNORE INTO app_catalog(app_id,label,description,icon,route,tenant_scope,sort_order) VALUES('todo','Todo List','Organize tasks by list and status','bi-check2-square','app/todo/index.asp','all',1)")
    Call PortalExec(conn, "INSERT OR IGNORE INTO app_catalog(app_id,label,description,icon,route,tenant_scope,sort_order) VALUES('brainstorm','Ideas','Capture and refine ideas','bi-lightbulb','app/brainstorm/index.asp','all',2)")
    Call PortalExec(conn, "INSERT OR IGNORE INTO app_catalog(app_id,label,description,icon,route,tenant_scope,sort_order) VALUES('notes','Notes','Structured personal or team knowledge base','bi-journal-richtext','app/notes/index.asp','all',3)")
    Call PortalExec(conn, "INSERT OR IGNORE INTO app_catalog(app_id,label,description,icon,route,tenant_scope,sort_order) VALUES('contacts','Contacts','People and lightweight CRM records','bi-people','app/contacts/index.asp','all',4)")
    Call PortalExec(conn, "INSERT OR IGNORE INTO app_catalog(app_id,label,description,icon,route,tenant_scope,sort_order) VALUES('bookmarks','Bookmarks','Save links with tags and reading queues','bi-bookmark-star','app/bookmarks/index.asp','all',5)")
    Call PortalExec(conn, "INSERT OR IGNORE INTO app_catalog(app_id,label,description,icon,route,tenant_scope,sort_order) VALUES('habits','Habits','Recurring routines with streak tracking','bi-calendar-check','app/habits/index.asp','personal',6)")
    Call PortalExec(conn, "INSERT OR IGNORE INTO app_catalog(app_id,label,description,icon,route,tenant_scope,sort_order) VALUES('vault','Vault','Reusable snippets and quick references','bi-safe2','app/vault/index.asp','all',7)")
    Call PortalExec(conn, "INSERT OR IGNORE INTO app_catalog(app_id,label,description,icon,route,tenant_scope,sort_order) VALUES('wins','Wins Journal','Capture one daily win and keep momentum','bi-trophy','app/wins/index.asp','all',8)")

    Call PortalExec(conn, "UPDATE app_catalog SET route = REPLACE(route, " & SqlQ(PortalBasePath() & "/") & ", '') WHERE instr(route, " & SqlQ(PortalBasePath() & "/") & ") > 0")
    Call PortalExec(conn, "UPDATE app_catalog SET route = substr(route, 2) WHERE substr(route,1,1)='/'")

    Call PortalExec(conn, "INSERT OR IGNORE INTO tenant_apps(tenant_id,app_id,enabled) SELECT t.id,a.app_id,CASE WHEN a.tenant_scope='personal' AND t.tenant_type<>'individual' THEN 0 ELSE 1 END FROM tenants t CROSS JOIN app_catalog a WHERE a.is_enabled=1")
End Sub

Function PortalIsLoggedIn()
    PortalIsLoggedIn = (CLng(0 & Session("portal_user_id")) > 0)
End Function

Function PortalCurrentUserId()
    PortalCurrentUserId = CLng(0 & Session("portal_user_id"))
End Function

Function PortalCurrentTenantId()
    PortalCurrentTenantId = CLng(0 & Session("portal_tenant_id"))
End Function

Function PortalCurrentRole()
    PortalCurrentRole = LCase(Trim("" & Session("portal_role")))
End Function

Function PortalSessionTimeoutMinutes()
    On Error Resume Next
    PortalSessionTimeoutMinutes = CLng(0 & Session.Timeout)
    If Err.Number <> 0 Or PortalSessionTimeoutMinutes <= 0 Then
        PortalSessionTimeoutMinutes = 20
    End If
    Err.Clear
    On Error GoTo 0
End Function

Function PortalIsTenantAdmin()
    Dim r
    r = PortalCurrentRole()
    PortalIsTenantAdmin = (r = "tenant_admin" Or r = "platform_admin")
End Function

Function PortalCsvHas(csv, item)
    Dim needle
    needle = "," & LCase(Trim(csv)) & ","
    PortalCsvHas = (InStr(1, needle, "," & LCase(Trim(item)) & ",", 1) > 0)
End Function

Function PortalHasApp(appId)
    PortalHasApp = PortalCsvHas("" & Session("portal_apps_csv"), appId)
End Function

Sub PortalSetFlash(msg, level)
    Session("portal_flash_msg") = "" & msg
    Session("portal_flash_level") = "" & level
End Sub

Function PortalCsrfToken()
    Dim t, connTmp
    t = "" & Session("portal_csrf_token")
    If t = "" Then
        Set connTmp = PortalOpen()
        t = "" & Replace(PortalNewToken(connTmp), "-", "")
        connTmp.Close
        Set connTmp = Nothing
        Session("portal_csrf_token") = t
    End If
    PortalCsrfToken = t
End Function

Function PortalCsrfField()
    PortalCsrfField = "<input type=""hidden"" name=""csrf_token"" value=""" & H(PortalCsrfToken()) & """>"
End Function

Sub PortalRequirePostCsrf()
    Dim expected, actual
    expected = "" & Session("portal_csrf_token")
    actual = "" & Request.Form("csrf_token")
    If expected = "" Or actual = "" Or expected <> actual Then
        Call PortalSetFlash("Security token mismatch. Please try again.", "danger")
        Response.Redirect PortalUrl("login.asp")
        Response.End
    End If
End Sub

Function PortalPopFlash()
    Dim s
    s = "" & Session("portal_flash_msg")
    Session("portal_flash_msg") = ""
    PortalPopFlash = s
End Function

Function PortalFlashLevel()
    Dim lv
    lv = "" & Session("portal_flash_level")
    If lv = "" Then lv = "info"
    Session("portal_flash_level") = ""
    PortalFlashLevel = lv
End Function

Sub PortalSignOut()
    Session("portal_user_id") = ""
    Session("portal_tenant_id") = ""
    Session("portal_user_name") = ""
    Session("portal_tenant_name") = ""
    Session("portal_role") = ""
    Session("portal_apps_csv") = ""
    Session("portal_primary_color") = ""
End Sub

Sub PortalLoadUserSession(conn, userId)
    Dim rs, tenantId, appRs, csv, tenantType
    Set rs = conn.Execute("SELECT u.id,u.name,u.email,u.role,u.status,u.follow_up_days,u.tenant_id,t.name AS tenant_name,t.primary_color,t.tenant_type FROM users u JOIN tenants t ON t.id=u.tenant_id WHERE u.id=" & SqlN(userId) & " LIMIT 1")
    If rs.EOF Then
        rs.Close
        Set rs = Nothing
        Call PortalSignOut()
        Exit Sub
    End If

    Session("portal_user_id") = CLng(0 & rs("id"))
    Session("portal_user_name") = "" & rs("name")
    Session("portal_user_email") = "" & rs("email")
    Session("portal_role") = LCase("" & rs("role"))
    Session("portal_tenant_id") = CLng(0 & rs("tenant_id"))
    Session("portal_tenant_name") = "" & rs("tenant_name")
    Session("portal_primary_color") = "" & rs("primary_color")
    Session("portal_tenant_type") = "" & rs("tenant_type")
    Session("portal_follow_up_days") = CLng(0 & rs("follow_up_days"))
    tenantId = CLng(0 & rs("tenant_id"))
    tenantType = LCase("" & rs("tenant_type"))
    rs.Close
    Set rs = Nothing

    csv = ""
    Set appRs = conn.Execute("SELECT a.app_id FROM app_catalog a JOIN tenant_apps ta ON ta.app_id=a.app_id AND ta.tenant_id=" & tenantId & " AND ta.enabled=1 LEFT JOIN user_apps ua ON ua.app_id=a.app_id AND ua.user_id=" & SqlN(userId) & " WHERE a.is_enabled=1 AND COALESCE(ua.enabled,1)=1 AND (a.tenant_scope='all' OR (a.tenant_scope='personal' AND " & SqlQ(tenantType) & "='individual')) ORDER BY a.sort_order,a.app_id")
    Do Until appRs.EOF
        If csv <> "" Then csv = csv & ","
        csv = csv & LCase("" & appRs("app_id"))
        appRs.MoveNext
    Loop
    appRs.Close
    Set appRs = Nothing
    Session("portal_apps_csv") = csv
End Sub

Sub PortalHydrateSession(conn)
    If PortalIsLoggedIn() Then
        Call PortalLoadUserSession(conn, PortalCurrentUserId())
    End If
End Sub

Sub PortalRequireLogin()
    If Not PortalIsLoggedIn() Then
        Response.Redirect PortalUrl("login.asp") & "?next=" & Server.URLEncode("" & Request.ServerVariables("URL"))
        Response.End
    End If
End Sub

Sub PortalRequireTenantAdmin()
    Call PortalRequireLogin()
    If Not PortalIsTenantAdmin() Then
        Call PortalSetFlash("Admin access is required.", "warning")
        Response.Redirect PortalUrl("dashboard.asp")
        Response.End
    End If
End Sub

Sub PortalRequireApp(appId)
    Call PortalRequireLogin()
    If Not PortalHasApp(appId) Then
        Call PortalSetFlash("You do not have access to that app.", "warning")
        Response.Redirect PortalUrl("dashboard.asp")
        Response.End
    End If
End Sub

Sub PortalTouchUsage(conn, appId)
    Dim uid
    uid = PortalCurrentUserId()
    If uid <= 0 Then Exit Sub
    Call PortalExec(conn, "INSERT OR IGNORE INTO user_app_usage(user_id,app_id,last_used_at) VALUES(" & uid & "," & SqlQ(appId) & ",CURRENT_TIMESTAMP)")
    Call PortalExec(conn, "UPDATE user_app_usage SET last_used_at=CURRENT_TIMESTAMP WHERE user_id=" & uid & " AND app_id=" & SqlQ(appId))
End Sub

Function PortalNewToken(conn)
    Dim rs
    Set rs = conn.Execute("SELECT lower(hex(randomblob(16))) AS t")
    PortalNewToken = "" & rs("t")
    rs.Close
    Set rs = Nothing
End Function

Function PortalCreateIndividual(conn, fullName, email, password)
    Dim hash, tenantName, tenantId, userId
    email = PortalNormalizeEmail(email)
    If Not PortalLooksLikeEmail(email) Then
        PortalCreateIndividual = 0
        Exit Function
    End If
    If Not PortalIsStrongPassword(password) Then
        PortalCreateIndividual = 0
        Exit Function
    End If
    If fullName = "" Then fullName = Split(email, "@")(0)
    fullName = PortalCleanName(fullName, "User")

    If CLng(0 & PortalScalar(conn, "SELECT COUNT(*) FROM users WHERE lower(email)=" & SqlQ(email), 0)) > 0 Then
        PortalCreateIndividual = 0
        Exit Function
    End If

    hash = ASP4.Crypto.Hash(password, 10)
    tenantName = fullName & " Workspace"

    Call PortalExec(conn, "INSERT INTO tenants(name,tenant_type,primary_color) VALUES(" & SqlQ(tenantName) & ",'individual','#2f6fed')")
    tenantId = CLng(0 & PortalScalar(conn, "SELECT id FROM tenants ORDER BY id DESC LIMIT 1", 0))

    Call PortalExec(conn, "INSERT INTO users(tenant_id,name,email,password_hash,role,status,timezone) VALUES(" & tenantId & "," & SqlQ(fullName) & "," & SqlQ(email) & "," & SqlQ(hash) & ",'tenant_admin','active','UTC')")
    userId = CLng(0 & PortalScalar(conn, "SELECT id FROM users ORDER BY id DESC LIMIT 1", 0))

    Call PortalExec(conn, "INSERT OR IGNORE INTO tenant_apps(tenant_id,app_id,enabled) SELECT " & tenantId & ",app_id,1 FROM app_catalog WHERE is_enabled=1")
    Call PortalExec(conn, "INSERT OR IGNORE INTO user_apps(user_id,app_id,enabled) SELECT " & userId & ",app_id,1 FROM app_catalog WHERE is_enabled=1")
    Call PortalExec(conn, "INSERT INTO todo_lists(tenant_id,user_id,name,is_shared) VALUES(" & tenantId & "," & userId & ",'My Tasks',0)")
    Call PortalExec(conn, "INSERT INTO idea_collections(tenant_id,user_id,name) VALUES(" & tenantId & "," & userId & ",'Inbox')")

    PortalCreateIndividual = userId
End Function

Function PortalAuthenticate(conn, email, password)
    Dim rs, ok, uid
    email = PortalNormalizeEmail(email)
    uid = 0
    Set rs = conn.Execute("SELECT id,password_hash,status FROM users WHERE lower(email)=" & SqlQ(email) & " LIMIT 1")
    If Not rs.EOF Then
        If LCase("" & rs("status")) = "active" Then
            ok = ASP4.Crypto.Verify(password, "" & rs("password_hash"))
            If ok Then uid = CLng(0 & rs("id"))
        End If
    End If
    rs.Close
    Set rs = Nothing

    If uid > 0 Then
        Call PortalExec(conn, "UPDATE users SET last_login_at=CURRENT_TIMESTAMP WHERE id=" & uid)
    End If
    PortalAuthenticate = uid
End Function
%>
