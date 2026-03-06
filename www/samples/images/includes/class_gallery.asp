<%
Class cls_gallery
    Private Sub EnsureFolders()
        Dim fso, p1
        Set fso = Server.CreateObject("Scripting.FileSystemObject")
        p1 = Server.MapPath("uploads")
        If Not fso.FolderExists(p1) Then fso.CreateFolder p1
        Set fso = Nothing
    End Sub

    Private Function ExtOf(fileName)
        Dim p
        p = InStrRev("" & fileName, ".")
        If p > 0 Then
            ExtOf = LCase(Mid(fileName, p + 1))
        Else
            ExtOf = ""
        End If
    End Function

    Private Function IsImageExt(ext)
        Dim ok
        ok = "|jpg|jpeg|jpe|jfif|png|gif|webp|bmp|tif|tiff|"
        IsImageExt = (InStr(ok, "|" & LCase(ext) & "|") > 0)
    End Function

    Public Function ListImages(db)
        Set ListImages = db.Query("SELECT id,original_name,file_name,rel_path,width,height,size_bytes,created_at FROM images ORDER BY id DESC")
    End Function

    Public Function GetById(db, id)
        Set GetById = db.Query("SELECT * FROM images WHERE id=" & ToInt(id, 0) & " LIMIT 1")
    End Function

    Public Sub SaveUpload(db, upload)
        Dim ext, baseName, finalName, relPath, absPath
        Dim img, w, h, maxDim, factor, newW, newH
        Dim fso, finalSize, fileObj, r

        If upload Is Nothing Then Err.Raise vbObjectError + 2201, "gallery", "No file uploaded"
        ext = ExtOf(upload.FileName)
        If Not IsImageExt(ext) Then Err.Raise vbObjectError + 2202, "gallery", "Only image files are allowed"

        EnsureFolders

        Randomize
        r = CStr(Int((Rnd() * 900000) + 100000))
        baseName = SafeBaseName(upload.FileName)
        finalName = Replace(CStr(Timer()), ".", "") & "_" & r & "_" & baseName & "." & ext
        relPath = "uploads/" & finalName
        absPath = Server.MapPath(relPath)

        upload.SaveAs absPath

        Set img = ASPpy.image.Image.open(absPath)
        w = ToInt(img.width, 0)
        h = ToInt(img.height, 0)
        maxDim = w
        If h > maxDim Then maxDim = h
        If maxDim > 1920 And maxDim > 0 Then
            factor = 1920 / maxDim
            newW = ToInt(w * factor, w)
            newH = ToInt(h * factor, h)
            If newW < 1 Then newW = 1
            If newH < 1 Then newH = 1
            Set img = img.resize(Array(newW, newH))
            img.save absPath
            w = ToInt(img.width, newW)
            h = ToInt(img.height, newH)
        End If

        Set fso = Server.CreateObject("Scripting.FileSystemObject")
        finalSize = CLng(upload.Size)
        If fso.FileExists(absPath) Then
            Set fileObj = fso.GetFile(absPath)
            finalSize = CLng(fileObj.Size)
            Set fileObj = Nothing
        End If
        Set fso = Nothing

        db.Execute "INSERT INTO images(original_name,file_name,rel_path,thumb_path,width,height,size_bytes,created_at) VALUES('" & Q(upload.FileName) & "','" & Q(finalName) & "','" & Q(relPath) & "',''," & w & "," & h & "," & finalSize & ",datetime('now'))"
    End Sub

    Public Sub DeleteImage(db, id)
        Dim rs, fso, p1
        Set rs = db.Query("SELECT rel_path FROM images WHERE id=" & ToInt(id, 0) & " LIMIT 1")
        If Not rs.EOF Then
            Set fso = Server.CreateObject("Scripting.FileSystemObject")
            p1 = Server.MapPath("" & rs("rel_path"))
            On Error Resume Next
            If fso.FileExists(p1) Then fso.DeleteFile p1, True
            On Error GoTo 0
            Set fso = Nothing
        End If
        rs.Close
        Set rs = Nothing
        db.Execute "DELETE FROM images WHERE id=" & ToInt(id, 0)
    End Sub

    Public Function BuildThumbBytes(db, id)
        Dim rs, srcPath, img, w, h, maxDim, factor, newW, newH
        EnsureFolders
        Set rs = GetById(db, id)
        If rs.EOF Then
            rs.Close
            Set rs = Nothing
            Err.Raise vbObjectError + 2203, "gallery", "Image not found"
        End If
        srcPath = Server.MapPath("" & rs("rel_path"))
        rs.Close
        Set rs = Nothing

        Set img = ASPpy.image.Image.open(srcPath)
        w = ToInt(img.width, 0)
        h = ToInt(img.height, 0)
        maxDim = w
        If h > maxDim Then maxDim = h
        If maxDim > 300 And maxDim > 0 Then
            factor = 300 / maxDim
            newW = ToInt(w * factor, w)
            newH = ToInt(h * factor, h)
            If newW < 1 Then newW = 1
            If newH < 1 Then newH = 1
            Set img = img.resize(Array(newW, newH))
        End If
        BuildThumbBytes = img.savebytes("JPEG", 85)
    End Function

    Public Function BuildFilterBytes(db, id, filterName)
        Dim rs, srcPath, img
        EnsureFolders
        Set rs = GetById(db, id)
        If rs.EOF Then
            rs.Close
            Set rs = Nothing
            Err.Raise vbObjectError + 2203, "gallery", "Image not found"
        End If
        srcPath = Server.MapPath("" & rs("rel_path"))
        rs.Close
        Set rs = Nothing

        Set img = ASPpy.image.Image.open(srcPath)
        Select Case UCase(Trim("" & filterName))
            Case "BLUR": Set img = img.filter(ASPpy.image.ImageFilter.BLUR)
            Case "CONTOUR": Set img = img.filter(ASPpy.image.ImageFilter.CONTOUR)
            Case "DETAIL": Set img = img.filter(ASPpy.image.ImageFilter.DETAIL)
            Case "EDGE_ENHANCE": Set img = img.filter(ASPpy.image.ImageFilter.EDGE_ENHANCE)
            Case "EDGE_ENHANCE_MORE": Set img = img.filter(ASPpy.image.ImageFilter.EDGE_ENHANCE_MORE)
            Case "EMBOSS": Set img = img.filter(ASPpy.image.ImageFilter.EMBOSS)
            Case "FIND_EDGES": Set img = img.filter(ASPpy.image.ImageFilter.FIND_EDGES)
            Case "SHARPEN": Set img = img.filter(ASPpy.image.ImageFilter.SHARPEN)
            Case "SMOOTH": Set img = img.filter(ASPpy.image.ImageFilter.SMOOTH)
            Case "SMOOTH_MORE": Set img = img.filter(ASPpy.image.ImageFilter.SMOOTH_MORE)
            Case Else
                Err.Raise vbObjectError + 2204, "gallery", "Unknown filter"
        End Select
        BuildFilterBytes = img.savebytes("JPEG", 90)
    End Function
End Class
%>
