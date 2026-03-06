<%
Class cls_mailclient
    Public Function OpenClient(proto, host, port, username, password, useSSL, folder)
        Dim p, c
        p = LCase(Trim("" & proto))

        If p = "pop3" Then
            Set c = Server.CreateObject("ASPpy.POP3")
            c.Connect host, ToInt(port, 995), useSSL, 30
            c.Login username, password
        Else
            Set c = Server.CreateObject("ASPpy.IMAP")
            c.Connect host, ToInt(port, 993), useSSL, 30
            c.Login username, password
            c.Select folder, False
        End If

        Set OpenClient = c
    End Function

    Public Sub DeleteMessage(proto, client, msgNum)
        Dim p
        p = LCase(Trim("" & proto))
        If p = "pop3" Then
            client.Delete ToInt(msgNum, 0)
        Else
            client.Delete "" & msgNum
            client.Expunge
        End If
    End Sub

    Public Sub CloseClient(client)
        If client Is Nothing Then Exit Sub
        On Error Resume Next
        client.Close
        On Error GoTo 0
    End Sub
End Class
%>
