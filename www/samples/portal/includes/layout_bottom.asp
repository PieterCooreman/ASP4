  </main>
  <footer class="border-top py-3 mt-4 bg-white">
    <div class="container small text-muted d-flex justify-content-between">
      <span>ASP4 Portal Reference App</span>
      <span>Multi-tenant · Session-based auth</span>
    </div>
  </footer>
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js" crossorigin="anonymous"></script>
  <script>
  (function(){
    var forms = document.querySelectorAll('form');
    for (var i = 0; i < forms.length; i++) {
      forms[i].setAttribute('novalidate', 'novalidate');
      forms[i].addEventListener('submit', function (event) {
        if (!this.checkValidity()) {
          event.preventDefault();
          event.stopPropagation();
        }
        this.classList.add('was-validated');
      });
    }

    function setCustomValidity(input) {
      if (!input) return;
      input.setCustomValidity('');
      var rule = input.getAttribute('data-rule');
      if (rule === 'password-strong') {
        var v = input.value || '';
        if (v === '' && !input.hasAttribute('required')) return;
        var ok = v.length >= 10 && /[A-Z]/.test(v) && /[a-z]/.test(v) && /[0-9]/.test(v);
        if (!ok) input.setCustomValidity('Password must be 10+ chars with upper, lower, and number.');
      }
      var match = input.getAttribute('data-match');
      if (match) {
        var other = document.getElementById(match);
        if (other && input.value !== other.value) {
          input.setCustomValidity('Values do not match.');
        }
      }
    }

    var ruleInputs = document.querySelectorAll('[data-rule], [data-match]');
    for (var j = 0; j < ruleInputs.length; j++) {
      ruleInputs[j].addEventListener('input', function(){ setCustomValidity(this); });
      ruleInputs[j].addEventListener('change', function(){ setCustomValidity(this); });
      setCustomValidity(ruleInputs[j]);
    }

    var warn = document.getElementById('sessionWarn');
    var countdown = document.getElementById('sessionWarnCountdown');
    var stayBtn = document.getElementById('staySignedIn');
    var timeoutMin = parseInt(document.body.getAttribute('data-session-timeout-min') || '0', 10);
    var warnSec = parseInt(document.body.getAttribute('data-session-warning-sec') || '60', 10);
    if (!warn || !countdown || !stayBtn || !timeoutMin || timeoutMin < 2) return;

    var idleSeconds = 0;
    var totalSeconds = timeoutMin * 60;
    var warned = false;

    function hideWarn() {
      warn.classList.add('d-none');
      warned = false;
    }

    function pingSession() {
      fetch('<%=H(PortalUrl("session_ping.asp"))%>', { credentials: 'same-origin' })
        .then(function(){ idleSeconds = 0; hideWarn(); })
        .catch(function(){});
    }

    function resetIdle() {
      idleSeconds = 0;
      if (warned) hideWarn();
    }

    ['mousemove','keydown','click','scroll','touchstart'].forEach(function(ev){
      window.addEventListener(ev, resetIdle, { passive: true });
    });

    stayBtn.addEventListener('click', function(){
      pingSession();
    });

    setInterval(function(){
      idleSeconds += 1;
      var left = totalSeconds - idleSeconds;
      if (left <= warnSec && left > 0) {
        warned = true;
        warn.classList.remove('d-none');
        countdown.textContent = String(left);
      }
      if (left <= 0) {
        window.location.href = '<%=H(PortalUrl("logout.asp"))%>';
      }
    }, 1000);
  })();
  </script>
</body>
</html>
