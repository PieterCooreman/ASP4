<%
' header.asp - Common page header. Set the page title BEFORE including:
'   Dim PageTitle : PageTitle = "My Page"
'   <!--#include file="includes/header.asp"-->
If IsEmpty(PageTitle) Then PageTitle = "Classic ASP/VBScript Samples"
Response.CodePage = 65001      ' emit UTF-8 to match the page CODEPAGE directive
Response.CharSet = "UTF-8"
%><!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title><%= HtmlEncode(PageTitle) %></title>
<meta name="description" content="Working Classic ASP / VBScript sample code running on IIS: subs, functions, classes, control flow, FSO, sessions and more.">
<style>
  :root { --bg:#0f1117; --panel:#1a1d27; --ink:#e7e9ee; --muted:#9aa3b2;
          --accent:#5cc8ff; --accent2:#ffd479; --line:#2a2f3d; }
  * { box-sizing:border-box; }
  body { margin:0; font:16px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
         background:var(--bg); color:var(--ink); }
  a { color:var(--accent); }
  header.site { background:linear-gradient(135deg,#10131c,#1c2233); border-bottom:1px solid var(--line);
                padding:18px 24px; }
  header.site .brand { font-weight:700; font-size:18px; letter-spacing:.3px; }
  header.site .brand span { color:var(--accent2); }
  nav.crumbs { padding:8px 24px; font-size:13px; color:var(--muted); border-bottom:1px solid var(--line); }
  nav.crumbs a { text-decoration:none; }
  main { max-width:960px; margin:0 auto; padding:24px; }
  h1 { font-size:28px; margin:.2em 0 .4em; }
  h2 { font-size:21px; margin-top:1.6em; border-bottom:1px solid var(--line); padding-bottom:.3em; }
  h3 { font-size:16px; margin:.2em 0 .6em; color:var(--accent); }
  p.lead { color:var(--muted); margin-top:0; }
  section.demo { background:var(--panel); border:1px solid var(--line); border-radius:10px;
                 padding:14px 16px; margin:14px 0; }
  .demo-output { font-size:15px; }
  pre.code { background:#0b0d13; border:1px solid var(--line); border-radius:8px; padding:12px 14px;
             overflow:auto; font:13px/1.5 Consolas,Menlo,monospace; color:#cfe8ff; }
  table.kv { width:100%; border-collapse:collapse; margin:6px 0; }
  table.kv th, table.kv td { text-align:left; padding:6px 10px; border-bottom:1px solid var(--line);
                             vertical-align:top; }
  table.kv th[scope="row"] { color:var(--muted); font-weight:600; width:34%; white-space:nowrap; }
  ul.cards { list-style:none; padding:0; display:grid; gap:12px;
             grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); }
  ul.cards li { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:14px 16px; }
  ul.cards li a { font-weight:700; font-size:16px; text-decoration:none; }
  ul.cards li p { margin:.4em 0 0; color:var(--muted); font-size:14px; }
  .tag { display:inline-block; font-size:11px; color:#0b0d13; background:var(--accent2);
         border-radius:999px; padding:2px 8px; margin-left:6px; vertical-align:middle; }
  footer.site { border-top:1px solid var(--line); color:var(--muted); font-size:13px;
                padding:18px 24px; text-align:center; }
  .ok { color:#7ee787; } .warn { color:#ffd479; } .err { color:#ff7b72; }
  form.demo-form { display:grid; gap:10px; max-width:420px; }
  form.demo-form label { font-size:14px; color:var(--muted); }
  form.demo-form input, form.demo-form select, form.demo-form textarea {
     width:100%; padding:8px 10px; background:#0b0d13; color:var(--ink);
     border:1px solid var(--line); border-radius:6px; font:inherit; }
  form.demo-form button { justify-self:start; background:var(--accent); color:#06121c; border:0;
     border-radius:6px; padding:9px 16px; font-weight:700; cursor:pointer; }
</style>
</head>
<body>
<header class="site">
  <div class="brand">Classic <span>ASP</span> / VBScript &mdash; Live Samples on IIS</div>
</header>
<nav class="crumbs">
  <a href="index.asp">Home</a> &raquo; <%= HtmlEncode(PageTitle) %>
</nav>
<main>
