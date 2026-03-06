<%
Class cls_zip_export
    Private Sub PurgeLegacyTemp()
        Dim fso, p
        Set fso = Server.CreateObject("Scripting.FileSystemObject")
        p = Server.MapPath("tmp")
        On Error Resume Next
        If fso.FolderExists(p) Then
            fso.DeleteFolder p, True
        End If
        On Error GoTo 0
        Set fso = Nothing
    End Sub

    Public Function BuildSamplesZip()
        Dim srcPath, outPath, stamp
        PurgeLegacyTemp
        srcPath = Server.MapPath("..")
        stamp = Replace(CStr(Timer()), ".", "")
        outPath = Server.MapPath("../../samples_" & stamp & ".zip")
        BuildSamplesZip = ASPpy.zip.Zip(srcPath, outPath)
    End Function
End Class
%>
