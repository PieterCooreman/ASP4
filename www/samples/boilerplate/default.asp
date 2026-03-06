<%@LANGUAGE="VBSCRIPT" CODEPAGE="65001"%>
<!-- #include file="asp/begin.asp"-->
<!-- #include file="asp/includes.asp"-->
<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="utf-8">
	<meta name="viewport" content="width=device-width, initial-scale=1">
	<title>ASP Classic Boilerplate</title>
	<meta name="description" content="">
	<meta name="keywords" content="">
	<!-- #include file="asp/head.asp"-->

	<!-- Bootstrap 5.3.8 -->
	<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-sRIl4kxILFvY47J16cr9ZwB07vP4J8+LH7qKQnuqkuIAvNWLzeN8tE5YBujZqJLB" crossorigin="anonymous">
	<!-- Bootstrap Icons -->
	<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.13.0/font/bootstrap-icons.min.css" rel="stylesheet">
</head>
<body>

	<!-- Navigation -->
	<nav class="navbar navbar-expand-lg navbar-dark bg-dark">
		<div class="container">
			<a class="navbar-brand" href="default.asp">
				<i class="bi bi-code-slash me-2"></i>ASP Boilerplate
			</a>
			<button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#mainNav" aria-controls="mainNav" aria-expanded="false" aria-label="Toggle navigation">
				<span class="navbar-toggler-icon"></span>
			</button>
			<div class="collapse navbar-collapse" id="mainNav">
				<ul class="navbar-nav ms-auto">
					<li class="nav-item">
						<a class="nav-link active" href="default.asp"><i class="bi bi-house me-1"></i>Home</a>
					</li>
					<li class="nav-item">
						<a class="nav-link" href="#"><i class="bi bi-info-circle me-1"></i>About</a>
					</li>
					<li class="nav-item">
						<a class="nav-link" href="#"><i class="bi bi-envelope me-1"></i>Contact</a>
					</li>
				</ul>
			</div>
		</div>
	</nav>

	<!-- Hero -->
	<div class="bg-dark text-white py-5">
		<div class="container text-center">
			<i class="bi bi-server display-4 mb-3 d-block"></i>
			<h1 class="display-5 fw-bold">ASP Classic Boilerplate</h1>
			<p class="lead">A modern starting point for classic ASP/VBScript web applications.</p>
			<a href="default.asp" class="btn btn-outline-light mt-2">
				<i class="bi bi-arrow-clockwise me-1"></i>Reload
			</a>
		</div>
	</div>

	<!-- Main -->
	<main class="py-5">
		<div class="container">

			<header class="mb-4">
				<h2 class="fw-bold">
					<i class="bi bi-terminal me-2 text-secondary"></i>
					<%
					dim helloWorld
					set helloWorld=new cls_sample
					response.write helloWorld.hello
					set helloWorld=nothing
					%>
				</h2>
				<hr>
			</header>

			<div class="row g-4">
				<div class="col-md-8">
					<p>This little sample site could be the starting point for a new web application written in ASP/VBScript, even in 2026.
					ASP classic runs on basically all Windows PC's and Servers and there is no reason to believe ASP Classic will ever stop working.</p>

					<p>ASP Classic fully supports UTF-8. Therefore, you can use any language and/or any set of symbols.</p>

					<p>Smart use of the <code>#include</code>-directive can keep your code clean and easy to maintain.</p>

					<p>When using HTML5 and CSS3, your classic ASP application will look and behave exactly like any other modern website.</p>

					<p>I have built various large ASP Classic applications ever since 1999 and most of them are still around and working without issues, even in 2026.</p>

					<p class="fw-semibold"><i class="bi bi-emoji-smile me-1 text-warning"></i>Enjoy ASP Classic!</p>
				</div>

				<div class="col-md-4">
					<div class="card border-0 shadow-sm">
						<div class="card-body">
							<h5 class="card-title"><i class="bi bi-lightning-charge-fill text-warning me-2"></i>Quick Facts</h5>
							<ul class="list-unstyled mb-0">
								<li class="mb-2"><i class="bi bi-check-circle-fill text-success me-2"></i>Runs on all Windows Servers</li>
								<li class="mb-2"><i class="bi bi-check-circle-fill text-success me-2"></i>Full UTF-8 support</li>
								<li class="mb-2"><i class="bi bi-check-circle-fill text-success me-2"></i>Clean with #include files</li>
								<li class="mb-2"><i class="bi bi-check-circle-fill text-success me-2"></i>Modern HTML5 &amp; CSS3 ready</li>
								<li><i class="bi bi-check-circle-fill text-success me-2"></i>Battle-tested since 1999</li>
							</ul>
						</div>
					</div>
				</div>
			</div>

		</div>
	</main>

	<!-- Footer -->
	<footer class="bg-dark text-white-50 py-4 mt-auto">
		<div class="container text-center">
			<p class="mb-1">
				<i class="bi bi-code-slash me-1"></i>
				ASP Classic Boilerplate &mdash; Built with Bootstrap 5.3.8
			</p>
			<small><i class="bi bi-c-circle me-1"></i>Your Company &mdash; All rights reserved.</small>
		</div>
	</footer>

	<!-- Popper + Bootstrap JS bundle (includes Popper) -->
	<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js" integrity="sha384-FKyoEForCGlyvwx9Hj09JcYn3nv7wiPVlz7YYwJrWVcXK/BmnVDxM+D2scQbITxI" crossorigin="anonymous"></script>

</body>
</html>