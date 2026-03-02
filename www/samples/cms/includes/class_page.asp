<%
Class cls_page
    Private Sub NormalizeMenuOrder(db)
        Dim rs, idx, pageId
        idx = 1
        Set rs = db.Query("SELECT id FROM pages ORDER BY menu_order ASC, id ASC")
        Do Until rs.EOF
            pageId = ToInt(rs("id"), 0)
            If pageId > 0 Then
                db.Execute "UPDATE pages SET menu_order=" & idx & " WHERE id=" & pageId
                idx = idx + 1
            End If
            rs.MoveNext
        Loop
        rs.Close
        Set rs = Nothing
    End Sub

    Public Function ListAll(db)
        Set ListAll = db.Query("SELECT id,title,slug,status,body_html,menu_title,is_home,menu_order,created_at,updated_at FROM pages ORDER BY menu_order ASC, id DESC")
    End Function

    Public Function GetById(db, id)
        Set GetById = db.Query("SELECT * FROM pages WHERE id=" & CLng(id) & " LIMIT 1")
    End Function

    Public Function GetPublicBySlugOrHome(db, slug)
        Dim sql
        If Trim("" & slug) = "" Then
            sql = "SELECT * FROM pages WHERE status='published' AND is_home=1 LIMIT 1"
        Else
            sql = "SELECT * FROM pages WHERE status='published' AND slug='" & Q(slug) & "' LIMIT 1"
        End If
        Set GetPublicBySlugOrHome = db.Query(sql)
    End Function

    Public Function FrontMenu(db)
        Set FrontMenu = db.Query("SELECT id,slug,COALESCE(NULLIF(menu_title,''),title) AS menu_label FROM pages WHERE status='published' ORDER BY menu_order ASC, id ASC")
    End Function

    Public Sub SavePage(db, id, title, slug, status, bodyHtml, menuTitle, isHome)
        Dim finalSlug, sql, pageId, nextOrder
        finalSlug = Slugify(slug)
        If finalSlug = "" Then finalSlug = Slugify(title)
        If Trim(menuTitle) = "" Then menuTitle = title

        If CLng(0 & id) = 0 Then
            nextOrder = ToInt(db.Scalar("SELECT COALESCE(MAX(menu_order),0) + 1 FROM pages", 1), 1)
            sql = "INSERT INTO pages(title,slug,status,body_html,menu_title,is_home,menu_order,created_at) VALUES ('" & Q(title) & "','" & Q(finalSlug) & "','" & Q(status) & "','" & Q(bodyHtml) & "','" & Q(menuTitle) & "'," & BoolInt(isHome) & "," & nextOrder & ",datetime('now'))"
            db.Execute sql
            pageId = CLng(db.Scalar("SELECT id FROM pages WHERE slug='" & Q(finalSlug) & "' ORDER BY id DESC LIMIT 1", 0))
        Else
            pageId = CLng(id)
            sql = "UPDATE pages SET title='" & Q(title) & "',slug='" & Q(finalSlug) & "',status='" & Q(status) & "',body_html='" & Q(bodyHtml) & "',menu_title='" & Q(menuTitle) & "',updated_at=datetime('now') WHERE id=" & pageId
            db.Execute sql
        End If

        If BoolInt(isHome) = 1 Then
            db.Execute "UPDATE pages SET is_home=0 WHERE id<>" & pageId
            db.Execute "UPDATE pages SET is_home=1 WHERE id=" & pageId
        End If
    End Sub

    Public Sub DeletePage(db, id)
        db.Execute "DELETE FROM pages WHERE id=" & CLng(id)
        NormalizeMenuOrder db
    End Sub

    Public Sub SetHome(db, id)
        db.Execute "UPDATE pages SET is_home=0"
        db.Execute "UPDATE pages SET is_home=1 WHERE id=" & CLng(id)
    End Sub

    Public Sub SaveMenuOrder(db, idsCsv)
        Dim arr, i, id
        arr = Split(idsCsv, ",")
        For i = 0 To UBound(arr)
            id = CLng(0 & Trim(arr(i)))
            If id > 0 Then
                db.Execute "UPDATE pages SET menu_order=" & (i + 1) & " WHERE id=" & id
            End If
        Next
        NormalizeMenuOrder db
    End Sub
End Class
%>
