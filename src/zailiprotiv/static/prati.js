// Following an MP by mail: the form sent to the counter from the page (the reader stays here) and its answer shown.
// Without the script the form goes there itself and the counter answers with a page of its own.
(function () {
  var form = document.querySelector(".prati-box");
  if (!form || !window.fetch || !window.URLSearchParams) return;
  var button = form.querySelector("button"), box = form.parentNode;
  box.addEventListener("toggle", function () { if (box.open) form.querySelector("input[type=email]").focus({ preventScroll: true }); });
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var body = new URLSearchParams(new FormData(form));
    body.set("js", "1");
    button.disabled = true;
    // site.js: only on the project's own hosts; a page opened elsewhere sends nothing
    (window.zipOwn ? fetch(form.action, { method: "POST", body: body }).then(function (r) { return r.ok; }, function () { return false; }) : Promise.resolve(false))
      .then(function (ok) {
        form.querySelector(".prati-done").hidden = !ok;
        form.querySelector(".prati-err").hidden = ok;
        if (ok) { form.querySelector(".prati-row").hidden = true; form.querySelector(".prati-what").hidden = true; }
        button.disabled = false;
      });
  });
})();
