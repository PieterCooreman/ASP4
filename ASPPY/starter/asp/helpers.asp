<%
Function TextValue(value)
    If IsNull(value) Then
        TextValue = ""
    Else
        TextValue = CStr(value)
    End If
End Function

Function NormalizeRoute(rawPath)
    Dim value
    value = LCase(Trim(TextValue(rawPath)))

    If value = "" Then
        value = "/"
    ElseIf value <> "/" And Right(value, 1) = "/" Then
        value = Left(value, Len(value) - 1)
    End If

    NormalizeRoute = value
End Function

Function CurrentRoute()
    CurrentRoute = NormalizeRoute(Request.Path)
End Function

Function RouteIs(matchPath)
    RouteIs = (CurrentRoute() = NormalizeRoute(matchPath))
End Function

Function RouteStarts(prefix)
    Dim routeValue, prefixValue
    routeValue = CurrentRoute()
    prefixValue = NormalizeRoute(prefix)
    RouteStarts = (Left(routeValue, Len(prefixValue)) = prefixValue)
End Function

Function TrimSlashes(rawValue)
    Dim value
    value = TextValue(rawValue)

    Do While Len(value) > 0 And Left(value, 1) = "/"
        value = Mid(value, 2)
    Loop

    Do While Len(value) > 0 And Right(value, 1) = "/"
        value = Left(value, Len(value) - 1)
    Loop

    TrimSlashes = value
End Function

Function RouteParts()
    Dim trimmedRoute
    trimmedRoute = TrimSlashes(CurrentRoute())

    If trimmedRoute = "" Then
        RouteParts = Split("", Chr(0))
    Else
        RouteParts = Split(trimmedRoute, "/")
    End If
End Function

Function Html(value)
    Html = Server.HTMLEncode(TextValue(value))
End Function
%>
