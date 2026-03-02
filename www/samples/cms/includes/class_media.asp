<%
Class cls_media
    Public Function ListAll(db)
        Set ListAll = db.Query("SELECT id,file_name,original_name,rel_path,mime_type,ext,size_bytes,width,height,created_at FROM media ORDER BY id DESC")
    End Function

    Private Function FileExt(fileName)
        Dim p
        p = InStrRev(fileName, ".")
        If p > 0 Then
            FileExt = LCase(Mid(fileName, p + 1))
        Else
            FileExt = ""
        End If
    End Function

    Private Function IsAllowedExt(ext)
        Dim allowed
        allowed = "|jpg|jpeg|png|gif|webp|svg|pdf|doc|docx|xls|xlsx|zip|txt|"
        IsAllowedExt = (InStr(allowed, "|" & LCase(ext) & "|") > 0)
    End Function

    Public Sub SaveUpload(db, upload, userId)
        Dim ext, maxBytes, finalName, relPath, absPath, r, w, h, img, mime
        maxBytes = 5 * 1024 * 1024

        If upload Is Nothing Then
            Err.Raise vbObjectError + 1300, "media", "No file uploaded"
        End If

        ext = FileExt(upload.FileName)
        If Not IsAllowedExt(ext) Then
            Err.Raise vbObjectError + 1301, "media", "File type not allowed"
        End If
        If CLng(upload.Size) > CLng(maxBytes) Then
            Err.Raise vbObjectError + 1302, "media", "File exceeds 5MB"
        End If

        Randomize
        r = CStr(Int((Rnd() * 900000) + 100000))
        finalName = Replace(CStr(Timer()), ".", "") & "_" & r & "_" & SafeFileName(upload.FileName)
        relPath = "uploads/" & finalName
        absPath = AppMap(relPath)

        upload.SaveAs absPath

        w = "NULL"
        h = "NULL"
        On Error Resume Next
        If ext = "jpg" Or ext = "jpeg" Or ext = "png" Or ext = "gif" Or ext = "webp" Then
            Set img = ASP4.Image.open(absPath)
            If Err.Number = 0 Then
                If CLng(img.width) > 1920 Then
                    Set img = img.resize(Array(1920, CLng((CLng(img.height) * 1920) / CLng(img.width))))
                    img.save absPath
                End If
                w = CLng(img.width)
                h = CLng(img.height)
            End If
        End If
        On Error GoTo 0

        mime = "" & upload.ContentType
        db.Execute "INSERT INTO media(file_name,original_name,rel_path,mime_type,ext,size_bytes,width,height,uploaded_by,created_at) VALUES ('" & Q(finalName) & "','" & Q(upload.FileName) & "','" & Q(relPath) & "','" & Q(mime) & "','" & Q(ext) & "'," & CLng(upload.Size) & "," & w & "," & h & "," & CLng(userId) & ",datetime('now'))"
    End Sub

    Public Sub DeleteById(db, id)
        Dim rs, relPath, fso
        Set rs = db.Query("SELECT rel_path FROM media WHERE id=" & CLng(id) & " LIMIT 1")
        If Not rs.EOF Then
            relPath = NormalizeRelPath("" & rs("rel_path"))
            On Error Resume Next
            Set fso = Server.CreateObject("Scripting.FileSystemObject")
            If relPath <> "" Then
                fso.DeleteFile AppMap(relPath), True
            End If
            Set fso = Nothing
            On Error GoTo 0
        End If
        rs.Close
        Set rs = Nothing
        db.Execute "DELETE FROM media WHERE id=" & CLng(id)
    End Sub
End Class
%>
