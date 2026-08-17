<section class="hero-panel mb-4">
    <span class="eyebrow">Start Here</span>
    <h1 class="display-5 mt-3 mb-3">Small MVC starter for new ASPPY apps.</h1>
    <p class="lead text-secondary mb-0">Copy this folder into `www`, then build from the existing structure instead of starting from a blank site.</p>
</section>

<section class="surface-card p-4 p-lg-5">
    <div class="row g-4">
        <div class="col-lg-7">
            <h2 class="h4 mb-3">What is already wired</h2>
            <div class="row g-3">
                <%
                Dim i
                For i = 0 To UBound(highlights)
                %>
                <div class="col-md-6">
                    <div class="info-card h-100">
                        <h3 class="h6 mb-2"><%=Html(highlights(i)(0))%></h3>
                        <p class="mb-0 text-secondary"><%=Html(highlights(i)(1))%></p>
                    </div>
                </div>
                <% Next %>
            </div>
        </div>
        <div class="col-lg-5">
            <div class="starter-note h-100">
                <h2 class="h5 mb-3">Starter checklist</h2>
                <ul class="starter-list mb-0">
                    <li>`index.asp` includes `default.asp`</li>
                    <li>`default.asp` owns routing and 404s</li>
                    <li>`asp/controllers`, `asp/models`, and `asp/views` exist</li>
                    <li>`data/app.db` is already present</li>
                    <li>`readme.md` travels with the starter</li>
                </ul>
                <p class="text-secondary small mt-3 mb-0">Tiny dynamic route example: <a href="/hello/taylor">`/hello/taylor`</a></p>
            </div>
        </div>
    </div>
</section>
