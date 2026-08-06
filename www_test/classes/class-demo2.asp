<%@ Language="VBScript" CodePage="65001" %>
<%
Option Explicit
Response.CharSet = "UTF-8"
Response.ContentType = "text/html"
%>
<%
' ============================================================
'  VBSCRIPT CLASSES DEMO 2 — Procedural vs. Class-based
'
'  THE "WHY" EXAMPLE. It solves the SAME problem twice — manage
'  a collection of songs — first with the procedural style an
'  LLM defaults to (parallel arrays + Subs that take every array
'  as a parameter), then with classes. The output is identical;
'  only the maintainability differs.
'
'  Use this comparison to decide WHEN a class is worth it:
'
'    PROCEDURAL smell signs (left column below):
'      • Several arrays that must stay index-aligned
'        (procTitles(2) and procRatings(2) must be the SAME song).
'      • Subs that take 4+ parameters just to reach the data.
'      • No validation — procRatings(i) = 9 is silently accepted.
'      • Adding one field (genre) forces edits to every signature.
'
'    CLASS cure (right column below):
'      • A Song bundles its own fields; a Playlist owns the list.
'      • Validation lives in Property Let — invalid state is
'        impossible from outside.
'      • Search returns a NEW Playlist, reusing every method.
'
'  KEY VBSCRIPT FACTS shown here:
'    • An EMPTY growable array is  ReDim a(-1)  (UBound = -1).
'    • Store objects in an array with  Set a(i) = obj.
'    • Server.HTMLEncode() every piece of user/text data on output.
'    • A method may RETURN a new object of the same class
'      (SearchByArtist returns a Playlist) — compose freely.
' ============================================================


' ============================================================
' PART 1 — PROCEDURAL APPROACH (no classes)
' Parallel arrays + Subs. Note how every Sub must receive ALL
' the arrays, and how nothing prevents index drift or bad data.
' ============================================================

' Four parallel arrays. The ONLY thing linking a title to its
' rating is a shared index — fragile by construction.
Dim procTitles(4), procArtists(4), procDurations(4), procRatings(4)
procTitles(0) = "Blinding Lights"  : procArtists(0) = "The Weeknd"    : procDurations(0) = 200 : procRatings(0) = 4
procTitles(1) = "Levitating"       : procArtists(1) = "Dua Lipa"      : procDurations(1) = 203 : procRatings(1) = 3
procTitles(2) = "Save Your Tears"  : procArtists(2) = "The Weeknd"    : procDurations(2) = 215 : procRatings(2) = 5
procTitles(3) = "Watermelon Sugar" : procArtists(3) = "Harry Styles"  : procDurations(3) = 174 : procRatings(3) = 4
procTitles(4) = "Peaches"          : procArtists(4) = "Justin Bieber" : procDurations(4) = 198 : procRatings(4) = 2

' Every procedural Sub needs ALL FOUR arrays passed in.
Sub ProcFormatSong(index, titles, artists, durations, ratings)
    If index < 0 Or index > UBound(titles) Then
        Response.Write "<span class='error'>[ERROR: index out of range]</span>"
        Exit Sub
    End If
    Dim stars : stars = String(ratings(index), "&#9733;") & String(5 - ratings(index), "&#9734;")
    Dim mins  : mins  = durations(index) \ 60
    Dim secs  : secs  = durations(index) Mod 60
    Response.Write "<strong>" & Server.HTMLEncode(titles(index)) & "</strong>"
    Response.Write " by " & Server.HTMLEncode(artists(index))
    Response.Write " <span class='muted'>(" & mins & ":" & Right("0" & secs, 2) & ")</span>"
    Response.Write " <span class='warn'>" & stars & "</span>"
End Sub

Function ProcAverageRating(titles, ratings)
    Dim total, count, i
    total = 0 : count = 0
    For i = 0 To UBound(titles)
        If titles(i) <> "" Then
            total = total + ratings(i)
            count = count + 1
        End If
    Next
    If count > 0 Then ProcAverageRating = total / count Else ProcAverageRating = 0
End Function

' Returns a comma-separated string of indexes — the caller must
' then re-parse and re-index into the global arrays. Clumsy.
Function ProcSearchByArtist(artist, titles, artists)
    Dim results, i
    results = ""
    For i = 0 To UBound(artists)
        If LCase(artists(i)) = LCase(artist) Then
            If results <> "" Then results = results & ","
            results = results & i
        End If
    Next
    ProcSearchByArtist = results
End Function

Sub ProcDisplaySearchResults(indexList, titles, artists, durations, ratings)
    Dim parts, i, idx
    If indexList = "" Then
        Response.Write "<em class='muted'>No matches found.</em>"
        Exit Sub
    End If
    parts = Split(indexList, ",")
    For i = 0 To UBound(parts)
        idx = CInt(parts(i))
        Call ProcFormatSong(idx, titles, artists, durations, ratings)
        Response.Write "<br>"
    Next
End Sub


' ============================================================
' PART 2 — CLASS-BASED APPROACH
' ============================================================

' --- Song: one cohesive record. Each field has validation in
'     its Property Let, so a Song can never hold a bad rating. ---
Class Song
    Private p_Title, p_Artist, p_Duration, p_Rating

    Private Sub Class_Initialize()
        p_Title = "Untitled" : p_Artist = "Unknown"
        p_Duration = 0 : p_Rating = 0
    End Sub

    Public Property Get Title()  : Title = p_Title  : End Property
    ' NOTE: a one-line  If ... Then ...  swallows the rest of the line,
    ' so a setter containing an If must use the multi-line block form —
    ' otherwise the  End Property  is consumed and you get "Expected End".
    Public Property Let Title(v)
        If v <> "" Then p_Title = v
    End Property

    Public Property Get Artist()  : Artist = p_Artist : End Property
    Public Property Let Artist(v)
        If v <> "" Then p_Artist = v
    End Property

    Public Property Get Duration()  : Duration = p_Duration : End Property
    Public Property Let Duration(v)
        If IsNumeric(v) And CInt(v) > 0 Then p_Duration = CInt(v)
    End Property

    ' Validation in the setter: a rating outside 1..5 is REJECTED.
    Public Property Get Rating()  : Rating = p_Rating : End Property
    Public Property Let Rating(v)
        If IsNumeric(v) And CInt(v) >= 1 And CInt(v) <= 5 Then p_Rating = CInt(v)
    End Property

    ' Computed (read-only) properties — formatting lives WITH the data.
    Public Property Get DurationFormatted()
        Dim mins, secs
        mins = p_Duration \ 60
        secs = p_Duration Mod 60
        DurationFormatted = mins & ":" & Right("0" & secs, 2)
    End Property

    Public Property Get StarString()
        StarString = String(p_Rating, "&#9733;") & String(5 - p_Rating, "&#9734;")
    End Property

    Public Sub Display()
        Response.Write "<strong>" & Server.HTMLEncode(p_Title) & "</strong>"
        Response.Write " by " & Server.HTMLEncode(p_Artist)
        Response.Write " <span class='muted'>(" & DurationFormatted & ")</span>"
        Response.Write " <span class='warn'>" & StarString & "</span>"
    End Sub

    Public Function MatchesArtist(artist)
        MatchesArtist = (LCase(p_Artist) = LCase(artist))
    End Function
End Class


' --- Playlist: owns a collection of Song objects and all the
'     operations on it. Callers never touch arrays or indexes. ---
Class Playlist
    Private p_Name
    Private p_Songs()      ' array of Song objects

    Private Sub Class_Initialize()
        p_Name = "Untitled Playlist"
        ReDim p_Songs(-1)  ' empty growable array: UBound = -1
    End Sub

    Public Property Get Name()  : Name = p_Name : End Property
    Public Property Let Name(v)
        If v <> "" Then p_Name = v
    End Property

    Public Property Get Count() : Count = UBound(p_Songs) + 1 : End Property

    ' song is an OBJECT, so store it with  Set.
    Public Sub Add(song)
        Dim newSize
        newSize = UBound(p_Songs) + 1
        ReDim Preserve p_Songs(newSize)
        Set p_Songs(newSize) = song
    End Sub

    Public Function GetAt(index)
        If index >= 0 And index <= UBound(p_Songs) Then
            Set GetAt = p_Songs(index)
        Else
            Set GetAt = Nothing
        End If
    End Function

    Public Sub DisplayAll()
        Dim i
        If UBound(p_Songs) < 0 Then
            Response.Write "<em class='muted'>Playlist is empty.</em>"
            Exit Sub
        End If
        For i = 0 To UBound(p_Songs)
            Response.Write "<div style='margin-bottom:.35rem'>"
            p_Songs(i).Display()
            Response.Write "</div>"
        Next
    End Sub

    Public Function AverageRating()
        Dim total, i : total = 0
        For i = 0 To UBound(p_Songs)
            total = total + p_Songs(i).Rating
        Next
        If UBound(p_Songs) >= 0 Then
            AverageRating = total / (UBound(p_Songs) + 1)
        Else
            AverageRating = 0
        End If
    End Function

    ' Returns a NEW Playlist — reusing every method on the result.
    Public Function SearchByArtist(artist)
        Dim results, i
        Set results = New Playlist
        results.Name = "Search: " & artist
        For i = 0 To UBound(p_Songs)
            If p_Songs(i).MatchesArtist(artist) Then results.Add p_Songs(i)
        Next
        Set SearchByArtist = results
    End Function

    Public Function TotalDuration()
        Dim total, i : total = 0
        For i = 0 To UBound(p_Songs)
            total = total + p_Songs(i).Duration
        Next
        TotalDuration = total
    End Function

    Public Sub Clear()
        Dim i
        For i = 0 To UBound(p_Songs)
            Set p_Songs(i) = Nothing
        Next
        ReDim p_Songs(-1)
    End Sub
End Class


' ============================================================
' PART 3 — BUILD THE CLASS-BASED PLAYLIST
' Note the temporary-variable pattern: fill a Song, Add it (the
' Playlist takes its own reference), then reuse the variable.
' ============================================================
Dim lib, s
Set lib = New Playlist
lib.Name = "Summer Hits 2025"

Set s = New Song
s.Title = "Blinding Lights" : s.Artist = "The Weeknd" : s.Duration = 200 : s.Rating = 4
lib.Add s : Set s = Nothing

Set s = New Song
s.Title = "Levitating" : s.Artist = "Dua Lipa" : s.Duration = 203 : s.Rating = 3
lib.Add s : Set s = Nothing

Set s = New Song
s.Title = "Save Your Tears" : s.Artist = "The Weeknd" : s.Duration = 215 : s.Rating = 5
lib.Add s : Set s = Nothing

Set s = New Song
s.Title = "Watermelon Sugar" : s.Artist = "Harry Styles" : s.Duration = 174 : s.Rating = 4
lib.Add s : Set s = Nothing

Set s = New Song
s.Title = "Peaches" : s.Artist = "Justin Bieber" : s.Duration = 198 : s.Rating = 2
lib.Add s : Set s = Nothing
%>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>VBScript Classes Demo 2 — Procedural vs. Classes</title>
  <style>
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Courier New',monospace;background:#0f1117;color:#e2e8f0;padding:2rem;line-height:1.6}
    h1{font-size:1.5rem;color:#7dd3fc;margin-bottom:.25rem}
    h2{font-size:1rem;color:#94a3b8;font-weight:normal;margin-bottom:1.75rem}
    h3{font-size:1rem;color:#7dd3fc;margin:1.25rem 0 .6rem;border-left:3px solid #7dd3fc;padding-left:.6rem}
    .grid{display:grid;grid-template-columns:1fr 1fr;gap:1.25rem}
    @media(max-width:860px){.grid{grid-template-columns:1fr}}
    .section{background:#1e2330;border:1px solid #2d3748;border-radius:6px;padding:1.1rem 1.4rem;margin-bottom:1.25rem}
    .col{background:#1e2330;border:1px solid #2d3748;border-radius:6px;padding:1.1rem 1.4rem}
    .col.proc{border-top:3px solid #b91c1c}
    .col.cls{border-top:3px solid #22c55e}
    .muted{color:#64748b}.warn{color:#fcd34d}.error{color:#f87171}.k{color:#7dd3fc}.value{color:#86efac}
    .pill{display:inline-block;border-radius:9999px;padding:.15rem .65rem;font-size:.72rem;font-weight:bold;letter-spacing:.06em;text-transform:uppercase}
    .pill-proc{background:#450a0a;color:#fca5a5}.pill-cls{background:#14532d;color:#86efac}
    table{width:100%;border-collapse:collapse;font-size:.85rem}
    th{text-align:left;color:#94a3b8;font-weight:normal;padding:.4rem .6rem;border-bottom:1px solid #2d3748}
    td{padding:.4rem .6rem;border-bottom:1px solid #1a2035;vertical-align:top}
    pre{background:#0d1117;border:1px solid #2d3748;border-radius:4px;padding:.7rem .9rem;font-size:.78rem;overflow-x:auto;color:#a5b4c8;white-space:pre-wrap}
    code{color:#7dd3fc}
    .note{font-size:.82rem;color:#64748b;margin-top:.6rem}
    .sub{margin:.9rem 0 .35rem;color:#94a3b8;font-size:.85rem;text-transform:uppercase;letter-spacing:.06em}
    .flaw{background:#2a0f12;border:1px solid #7f1d1d;border-radius:6px;padding:.7rem .9rem;font-size:.82rem;color:#fca5a5;margin-top:.8rem}
    .virtue{background:#0f2a17;border:1px solid #166534;border-radius:6px;padding:.7rem .9rem;font-size:.82rem;color:#86efac;margin-top:.8rem}
  </style>
</head>
<body>
  <h1>Demo 2 — Procedural vs. Classes</h1>
  <h2>The same playlist, two ways. Identical output — very different maintainability.</h2>

  <div class="grid">

    <!-- ============ PROCEDURAL ============ -->
    <div class="col proc">
      <span class="pill pill-proc">Procedural</span>
      <h3 style="border:none;padding:0;margin:.7rem 0 .4rem">Parallel arrays &amp; Subs</h3>

      <div class="sub">Data storage</div>
      <pre>Dim procTitles(4), procArtists(4)
Dim procDurations(4), procRatings(4)
procTitles(0)="Blinding Lights" : procArtists(0)="The Weeknd"
' index 0 in every array must mean the SAME song — by hand</pre>

      <div class="sub">Output</div>
      <%
        Dim i
        For i = 0 To 4
            Call ProcFormatSong(i, procTitles, procArtists, procDurations, procRatings)
            Response.Write "<br>"
        Next
      %>

      <div class="sub">Average rating</div>
      <span class="value" style="font-size:1.2rem;font-weight:bold"><%= ProcAverageRating(procTitles, procRatings) %></span> / 5

      <div class="sub">Search by artist ("The Weeknd")</div>
      <%
        Dim resultStr
        resultStr = ProcSearchByArtist("The Weeknd", procTitles, procArtists)
        Call ProcDisplaySearchResults(resultStr, procTitles, procArtists, procDurations, procRatings)
      %>

      <div class="flaw">
        <strong>&#10005; Fragile by design.</strong> Every Sub needs all four arrays passed.
        Adding a field (genre, year, BPM) means editing every signature and every loop.
        One off-by-one index silently shows the wrong data, and nothing stops
        <code>procRatings(i) = 9</code> — there is no validation anywhere.
      </div>
    </div>

    <!-- ============ CLASSES ============ -->
    <div class="col cls">
      <span class="pill pill-cls">Classes</span>
      <h3 style="border:none;padding:0;margin:.7rem 0 .4rem">Song &amp; Playlist objects</h3>

      <div class="sub">Data storage</div>
      <pre>Set s = New Song
s.Title = "Blinding Lights"
s.Artist = "The Weeknd"
s.Duration = 200 : s.Rating = 4   ' Rating &gt; 5 is rejected
lib.Add s                          ' the Song holds itself together</pre>

      <div class="sub">Output</div>
      <% lib.DisplayAll() %>

      <div class="sub">Average rating</div>
      <span class="value" style="font-size:1.2rem;font-weight:bold"><%= lib.AverageRating() %></span> / 5

      <div class="sub">Search by artist ("The Weeknd")</div>
      <%
        Dim result
        Set result = lib.SearchByArtist("The Weeknd")
        result.DisplayAll()
        Set result = Nothing
      %>

      <div class="virtue">
        <strong>&#10003; Encapsulated by design.</strong> A <code>Song</code> bundles its own fields;
        a <code>Playlist</code> owns the list. Validation lives in <code>Property Let</code>, so a bad
        rating can't exist. Adding a <code>Genre</code> touches only the <code>Song</code> class.
        Search returns a NEW <code>Playlist</code> — every method works on it unchanged.
      </div>
    </div>

  </div>

  <h3>What classes give you</h3>
  <div class="section">
    <table>
      <tr><th style="width:22%">Concern</th><th>Procedural (arrays + Subs)</th><th>Classes</th></tr>
      <tr><td class="k">Data cohesion</td>
          <td>Fields live in separate arrays; nothing guarantees <code>titles(2)</code> and <code>ratings(2)</code> are the same song. An insert/delete shifts every array.</td>
          <td>A <code>Song</code> holds all its fields together; ordering/removal is the <code>Playlist</code>'s job, not the caller's.</td></tr>
      <tr><td class="k">Validation</td>
          <td>None. <code>procRatings(i) = 9</code> is accepted silently; <code>procTitles(-1)</code> crashes at runtime.</td>
          <td>Built into <code>Property Let</code>: <code>Rating = 9</code> is rejected (max 5). Invalid state is impossible from outside.</td></tr>
      <tr><td class="k">Extensibility</td>
          <td>Add a genre = new array + update every Sub signature + every loop, with index-drift risk.</td>
          <td>Add <code>p_Genre</code> + a Get/Let pair in <code>Song</code>. One change, no ripple.</td></tr>
      <tr><td class="k">Reusability</td>
          <td>Subs are tied to the global arrays; to reuse one you must pass all four arrays again.</td>
          <td><code>Song.Display()</code> works on any Song; a <code>Playlist</code> works on any set of Songs — even search results.</td></tr>
      <tr><td class="k">Search results</td>
          <td>Returns a comma-string of indexes; the caller re-parses and re-indexes the global arrays.</td>
          <td>Returns a new <code>Playlist</code>; the same methods (<code>DisplayAll</code>, <code>AverageRating</code>) just work.</td></tr>
      <tr><td class="k">Cleanup</td>
          <td>Global arrays live for the whole page; no early scoping or release.</td>
          <td>Objects are reference-counted; <code>Set x = Nothing</code> / <code>Clear()</code> release them when done.</td></tr>
    </table>
  </div>

  <h3>Rules for coding agents — when is a class worth it?</h3>
  <div class="section">
    <table>
      <tr><th>Reach for a class when…</th><th>Stay procedural when…</th></tr>
      <tr><td class="value">You find yourself keeping 2+ arrays index-aligned</td><td class="muted">A single throwaway array suffices</td></tr>
      <tr><td class="value">Subs need 3+ parameters just to reach the data</td><td class="muted">A one-line helper with 1 argument does the job</td></tr>
      <tr><td class="value">Values need validation/invariants</td><td class="muted">There are no rules to enforce</td></tr>
      <tr><td class="value">An operation should return a reusable collection</td><td class="muted">You only need a scalar result</td></tr>
    </table>
    <p class="note">Heuristic: <strong>parallel arrays are a code smell.</strong> The moment you have two
    arrays that must stay in sync, you almost certainly want a class with one array of objects.</p>
  </div>

<%
' --- cleanup: Clear() releases each Song, then drop the Playlist ---
lib.Clear()
Set lib = Nothing
%>
</body>
</html>
