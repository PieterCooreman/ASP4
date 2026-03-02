<%
Class cls_media
    Private Sub EnsureUploadsFolder()
        Dim fso, uploadsPath, uploadsRel
        uploadsPath = AppMap("uploads")
        uploadsRel = AppRelPath("uploads")
        Set fso = Server.CreateObject("Scripting.FileSystemObject")
        If Not fso.FolderExists(uploadsPath) Then
            On Error Resume Next
            fso.CreateFolder uploadsPath
            If Err.Number <> 0 Then
                Err.Clear
                fso.CreateFolder uploadsRel
            End If
            On Error GoTo 0
        End If
        Set fso = Nothing
    End Sub

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
        allowed = "|jpg|jpeg|jpe|jfif|png|gif|webp|bmp|tif|tiff|avif|heic|heif|svg|pdf|doc|docx|xls|xlsx|zip|txt|"
        IsAllowedExt = (InStr(allowed, "|" & LCase(ext) & "|") > 0)
    End Function

    Private Function BaseNameOnly(fileName)
        Dim s, p
        s = "" & fileName
        p = InStrRev(s, ".")
        If p > 1 Then
            BaseNameOnly = Left(s, p - 1)
        Else
            BaseNameOnly = s
        End If
    End Function

    Public Sub SaveUpload(db, upload, userId)
        Dim ext, maxBytes, finalName, relPath, absPath, r, w, h, img, mime
        Dim curW, curH, newW, newH, finalSize, fso, fileObj
        Dim baseName
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
        baseName = SafeFileName(BaseNameOnly(upload.FileName))
        If Len(baseName) > 80 Then baseName = Left(baseName, 80)
        finalName = Replace(CStr(Timer()), ".", "") & "_" & r & "_" & baseName & "." & ext
        relPath = "uploads/" & finalName
        EnsureUploadsFolder
        absPath = AppMap(relPath)

        On Error Resume Next
        upload.SaveAs absPath
        If Err.Number <> 0 Then
            Dim saveErr
            saveErr = Err.Description
            Err.Clear
            On Error GoTo 0
            Err.Raise vbObjectError + 1303, "media", "Could not save upload: " & saveErr
        End If
        On Error GoTo 0

        w = "NULL"
        h = "NULL"
        On Error Resume Next
        If ext = "jpg" Or ext = "jpeg" Or ext = "jpe" Or ext = "jfif" Or ext = "png" Or ext = "gif" Or ext = "webp" Or ext = "bmp" Or ext = "tif" Or ext = "tiff" Then
            Set img = ASP4.image.Image.open(absPath)
            If Err.Number = 0 Then
                curW = ToInt(img.width, 0)
                curH = ToInt(img.height, 0)
                If curW > 1920 And curH > 0 Then
                    newW = 1920
                    newH = ToInt((curH * 1920) / curW, curH)
                    If newH < 1 Then newH = 1
                    Set img = img.resize(Array(newW, newH))
                    img.save absPath
                    If Err.Number = 0 Then
                        curW = ToInt(img.width, newW)
                        curH = ToInt(img.height, newH)
                    Else
                        Err.Clear
                    End If
                End If
                w = curW
                h = curH
            Else
                Err.Clear
            End If
        End If
        Err.Clear
        On Error GoTo 0

        finalSize = CLng(upload.Size)
        Set fso = Server.CreateObject("Scripting.FileSystemObject")
        If fso.FileExists(absPath) Then
            Set fileObj = fso.GetFile(absPath)
            finalSize = CLng(fileObj.Size)
            Set fileObj = Nothing
        End If
        Set fso = Nothing

        mime = "" & upload.ContentType
        db.Execute "INSERT INTO media(file_name,original_name,rel_path,mime_type,ext,size_bytes,width,height,uploaded_by,created_at) VALUES ('" & Q(finalName) & "','" & Q(upload.FileName) & "','" & Q(relPath) & "','" & Q(mime) & "','" & Q(ext) & "'," & finalSize & "," & w & "," & h & "," & CLng(userId) & ",datetime('now'))"
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
